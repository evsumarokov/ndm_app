# Файл: ui_step2.py
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import plotly.graph_objects as go
from analysis.preprocessor import Preprocessor
from core.ndm_solver import NDMSolver

def render_step2():
    st.markdown('<p class="step-header">Этап 2: Учет геометрических несовершенств (Монтаж)</p>', unsafe_allow_html=True)
    
    if st.session_state.step1_result is None:
        st.warning("⚠️ Сначала выполните расчет на вкладке 'ШАГ 1: ПРОЕКТ'.")
        return
        
    st.info("Внесите данные геодезической съемки. Проектный вектор нагружения будет показан полупрозрачным синим цветом, а фактический с учетом геодезии — красным.")
    
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        delta_x_tilt = st.number_input("ΔX (Наклон), мм", value=15.0, step=1.0)
        delta_y_tilt = st.number_input("ΔY (Наклон), мм", value=5.0, step=1.0)
    with col_g2:
        delta_x_misalign = st.number_input("ΔX (Сдвиг), мм", value=10.0, step=1.0)
        delta_y_misalign = st.number_input("ΔY (Сдвиг), мм", value=0.0, step=1.0)
    with col_g3:
        delta_geo = st.number_input("Доп. погрешность прибора, мм", value=5.0, step=1.0)

    st.markdown("### 👁️ Интерактивный просмотр геометрии")
    c_live1, c_live2 = st.columns([2, 1])
    
    with c_live1:
        raw_h = st.session_state.raw_col_data['H_col']
        raw_mu = st.session_state.raw_col_data['mu_col']
        l0 = st.session_state.raw_config.apply_eta_ea * raw_h * raw_mu * 1000
        if l0 == 0: l0 = 3000
        
        fig_geo_live = go.Figure()
        fig_geo_live.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[0, l0*2], mode='lines', line=dict(color='gray', dash='dash')))
        fig_geo_live.add_trace(go.Scatter3d(x=[0, delta_x_tilt], y=[0, delta_y_tilt], z=[0, l0], mode='lines+markers', line=dict(color='blue', width=5)))
        s_x, s_y = delta_x_tilt + delta_x_misalign, delta_y_tilt + delta_y_misalign
        fig_geo_live.add_trace(go.Scatter3d(x=[delta_x_tilt, s_x], y=[delta_y_tilt, s_y], z=[l0, l0], mode='lines', line=dict(color='black', width=3, dash='dot')))
        fig_geo_live.add_trace(go.Scatter3d(x=[s_x, s_x], y=[s_y, s_y], z=[l0, l0*2], mode='lines+markers', line=dict(color='red', width=5)))
        fig_geo_live.update_layout(scene=dict(xaxis_title='dX (мм)', yaxis_title='dY (мм)', zaxis_title='Высота', aspectratio=dict(x=1,y=1,z=2)), height=300, margin=dict(l=0,r=0,b=0,t=0), showlegend=False)
        st.plotly_chart(fig_geo_live, use_container_width=True, key="live_geo_step2")

    with c_live2:
        fig_2d_prev, ax_2d_prev = plt.subplots(figsize=(2, 2))
        ax_2d_prev.add_patch(MplPolygon(st.session_state.raw_geom[0]['coords'], closed=True, fill=True, color='lightgray', alpha=0.7))
        for rb in st.session_state.raw_rebars: ax_2d_prev.scatter(rb['x'], rb['y'], color='black', s=20)
        ax_2d_prev.set_aspect('equal'); ax_2d_prev.axis('off')
        st.pyplot(fig_2d_prev)

    calc_btn = st.button("🚀 ПРИНУДИТЕЛЬНЫЙ РАСЧЕТ (ШАГ 2)", type="primary")

    if calc_btn or st.session_state.auto_calc:
        col_data_2 = st.session_state.raw_col_data.copy()
        col_data_2.update({'delta_x_tilt': delta_x_tilt, 'delta_y_tilt': delta_y_tilt, 'delta_x_misalign': delta_x_misalign, 'delta_y_misalign': delta_y_misalign, 'delta_geo': delta_geo})
        st.session_state.step2_col_data = col_data_2 
        
        try:
            ndm_2 = Preprocessor.process(st.session_state.raw_config, col_data_2, st.session_state.raw_geom, st.session_state.raw_rebars)
            solver_step2 = NDMSolver(target_cells=1200)
            res_2 = solver_step2.solve(ndm_2)
            lambda_2, _ = st.session_state.analyzer.find_lambda(ndm_2)
            
            st.session_state.step2_input = ndm_2
            st.session_state.step2_result = res_2
            st.session_state.lambda_2 = lambda_2
        except Exception as e:
            st.error(f"Ошибка вычислений: {e}")

    if st.session_state.step2_result is not None:
        ndm_1, lam_1 = st.session_state.step1_input, st.session_state.lambda_1
        ndm_2, res_2, lam_2 = st.session_state.step2_input, st.session_state.step2_result, st.session_state.lambda_2
        analyzer = st.session_state.analyzer
        
        st.markdown("---")
        c_res1, c_res2 = st.columns([1, 2.5])
        
        with c_res1:
            if lam_2 >= 1.0: st.markdown(f'<div class="success-box"><h3>✅ ЗАПАС (Монтаж)</h3><h1>λ = {lam_2:.3f}</h1></div>', unsafe_allow_html=True)
            else: st.markdown(f'<div class="warning-box"><h3>❌ ПЕРЕГРУЗ (Монтаж)</h3><h1>λ = {lam_2:.3f}</h1></div>', unsafe_allow_html=True)
            
            loss = (1 - (lam_2 / lam_1)) * 100 if lam_1 > 0 else 0
            st.error(f"📉 **Падение прочности от кривизны:** {loss:.1f}%")
            st.write(f"**Мx:** {ndm_1.Mx_ext/1e6:.1f} ➔ **{ndm_2.Mx_ext/1e6:.1f}** кН·м")
            st.write(f"**Мy:** {ndm_1.My_ext/1e6:.1f} ➔ **{ndm_2.My_ext/1e6:.1f}** кН·м")

        with c_res2:
            t2_2d, t2_3d_surf, t2_3d_ndm, t2_log = st.tabs(["📈 2D (N-M)", "🎲 3D Поверхность", "🧊 Эпюра НДМ", "📋 Лог расчета"])

            with t2_2d:
                c_2dx, c_2dy = st.columns(2)
                with c_2dx:
                    Nx, Mx = analyzer.generate_nmx_curve(ndm_1)
                    fig_x, ax_x = plt.subplots(figsize=(5, 4))
                    ax_x.plot(Mx, Nx, 'k--', label='Огибающая (Проект)')
                    
                    # Проектный вектор (полутоном)
                    ax_x.plot(ndm_1.Mx_ext/1e6, ndm_1.N_ext/1000, 'bo', markersize=6, alpha=0.4)
                    ax_x.plot([0, ndm_1.Mx_ext/1e6 * lam_1], [0, ndm_1.N_ext/1000 * lam_1], 'b--', linewidth=1.5, alpha=0.3, label='Вектор (Проект)')
                    ax_x.plot(ndm_1.Mx_ext/1e6 * lam_1, ndm_1.N_ext/1000 * lam_1, 'b*', markersize=12, alpha=0.3)
                    
                    # Фактический вектор
                    ax_x.plot(ndm_2.Mx_ext/1e6, ndm_2.N_ext/1000, 'ro', markersize=8, label='Рабочая точка (Геодезия)')
                    ax_x.plot([0, ndm_2.Mx_ext/1e6 * lam_2], [0, ndm_2.N_ext/1000 * lam_2], 'r-', linewidth=1.5)
                    ax_x.plot(ndm_2.Mx_ext/1e6 * lam_2, ndm_2.N_ext/1000 * lam_2, 'r*', markersize=12, label='Новый предел')
                    
                    ax_x.annotate('', xy=(ndm_2.Mx_ext/1e6, ndm_2.N_ext/1000), xytext=(ndm_1.Mx_ext/1e6, ndm_1.N_ext/1000), arrowprops=dict(arrowstyle="->", color='red'))
                    ax_x.grid(True); ax_x.set_title("Смещение по Mx"); ax_x.legend(fontsize=8)
                    st.pyplot(fig_x)
                    
                with c_2dy:
                    Ny, My = analyzer.generate_nmy_curve(ndm_1)
                    fig_y, ax_y = plt.subplots(figsize=(5, 4))
                    ax_y.plot(My, Ny, 'k--', label='Огибающая (Проект)')
                    
                    ax_y.plot(ndm_1.My_ext/1e6, ndm_1.N_ext/1000, 'bo', markersize=6, alpha=0.4)
                    ax_y.plot([0, ndm_1.My_ext/1e6 * lam_1], [0, ndm_1.N_ext/1000 * lam_1], 'b--', linewidth=1.5, alpha=0.3, label='Вектор (Проект)')
                    ax_y.plot(ndm_1.My_ext/1e6 * lam_1, ndm_1.N_ext/1000 * lam_1, 'b*', markersize=12, alpha=0.3)
                    
                    ax_y.plot(ndm_2.My_ext/1e6, ndm_2.N_ext/1000, 'ro', markersize=8, label='Рабочая точка (Геодезия)')
                    ax_y.plot([0, ndm_2.My_ext/1e6 * lam_2], [0, ndm_2.N_ext/1000 * lam_2], 'r-', linewidth=1.5)
                    ax_y.plot(ndm_2.My_ext/1e6 * lam_2, ndm_2.N_ext/1000 * lam_2, 'r*', markersize=12, label='Новый предел')
                    
                    ax_y.annotate('', xy=(ndm_2.My_ext/1e6, ndm_2.N_ext/1000), xytext=(ndm_1.My_ext/1e6, ndm_1.N_ext/1000), arrowprops=dict(arrowstyle="->", color='red'))
                    ax_y.grid(True); ax_y.set_title("Смещение по My"); ax_y.legend(fontsize=8)
                    st.pyplot(fig_y)

            with t2_3d_surf:
                N_3d, Mx_3d, My_3d = analyzer.generate_3d_surface(ndm_1)
                fig_3d = go.Figure(data=[go.Mesh3d(x=Mx_3d, y=My_3d, z=N_3d, alphahull=0, opacity=0.3, color='blue')])
                fig_3d.add_trace(go.Scatter3d(x=[ndm_2.Mx_ext/1e6], y=[ndm_2.My_ext/1e6], z=[ndm_2.N_ext/1000], mode='markers', marker=dict(color='red', size=8)))
                fig_3d.add_trace(go.Scatter3d(x=[0, ndm_2.Mx_ext/1e6 * lam_2], y=[0, ndm_2.My_ext/1e6 * lam_2], z=[0, ndm_2.N_ext/1000 * lam_2], mode='lines+markers', line=dict(color='red', width=4, dash='dash')))
                fig_3d.update_layout(scene=dict(xaxis_title='Mₓ', yaxis_title='Mᵧ', zaxis_title='N'), height=450, margin=dict(l=0, r=0, b=0, t=0))
                st.plotly_chart(fig_3d, use_container_width=True, key="fig_surf_2")

            with t2_3d_ndm:
                if res_2.status != "NO_CONVERGENCE":
                    fig_ndm = go.Figure()
                    cells = res_2.concrete_cells
                    c_c = max(abs(min(cells['sigma'])), abs(max(cells['sigma']))) * 1.05 if len(cells['sigma']) > 0 else 1
                    fig_ndm.add_trace(go.Scatter3d(x=cells['x'], y=cells['y'], z=cells['sigma'], mode='markers', marker=dict(size=3, color=cells['sigma'], colorscale='RdBu_r', cmin=-c_c, cmax=c_c)))
                    cx, cy = ndm_2.section.effective_polygon.centroid.coords[0]
                    for rb in ndm_2.rebars:
                        eps_s = (res_2.eps0 + res_2.kx*(rb.y-cy) + res_2.ky*(rb.x-cx)) * rb.psi_bond
                        sigma_s = NDMSolver(1)._get_steel_stress(np.array([eps_s]), ndm_2.steel_props)[0]
                        fig_ndm.add_trace(go.Scatter3d(x=[rb.x, rb.x], y=[rb.y, rb.y], z=[0, sigma_s], mode='lines+markers', line=dict(color='black', width=6)))
                    fig_ndm.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='σ, МПа'), height=450, margin=dict(l=0,r=0,b=0,t=0), showlegend=False)
                    st.plotly_chart(fig_ndm, use_container_width=True, key="fig_ndm_step2")

            with t2_log:
                with st.expander("Журнал вычислений эксцентриситетов (Шаг 2)", expanded=True):
                    for title, lines in ndm_2.calc_log.items():
                        st.write(f"**{title}**"); [st.write(f"- {l}") for l in lines]