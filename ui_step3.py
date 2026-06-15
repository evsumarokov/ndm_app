# Файл: ui_step3.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import plotly.graph_objects as go
from shapely.geometry import Polygon
from analysis.preprocessor import Preprocessor, CalcConfig
from core.ndm_solver import NDMSolver

def render_step3():
    st.markdown('<p class="step-header">Этап 3: Учет дефектов и фактического состояния (Обследование)</p>', unsafe_allow_html=True)
    
    if st.session_state.step1_result is None:
        st.warning("⚠️ Сначала выполните расчет эталонной модели на вкладке 'ШАГ 1: ПРОЕКТ'.")
        return

    col_in1, col_in2 = st.columns([1, 1.5])
    
    with col_in1:
        st.markdown("**1. Фактическая надежность (Обследование)**")
        c1, c2 = st.columns(2)
        gamma_b_step3 = c1.number_input("γ_b (Бетон, факт)", value=1.0, step=0.05, key="gb3")
        gamma_s_step3 = c2.number_input("γ_s (Сталь, факт)", value=1.0, step=0.05, key="gs3")
        
        st.markdown("**Унаследованная геодезия (из Шага 2)**")
        step2_data = st.session_state.get('step2_col_data', st.session_state.raw_col_data)
        cg1, cg2 = st.columns(2)
        cg1.text_input("ΔX (Наклон+Сдвиг)", value=f"{step2_data.get('delta_x_tilt', 0)} + {step2_data.get('delta_x_misalign', 0)} мм", disabled=True)
        cg2.text_input("ΔY (Наклон+Сдвиг)", value=f"{step2_data.get('delta_y_tilt', 0)} + {step2_data.get('delta_y_misalign', 0)} мм", disabled=True)

        st.markdown("**2. Коррозия арматуры**")
        df_r = pd.DataFrame(st.session_state.raw_rebars)
        if 'k_area' not in df_r.columns: df_r['k_area'] = 0.0
        if 'k_bond' not in df_r.columns: df_r['k_bond'] = 1.0
        
        rebar_df_step3 = st.data_editor(
            df_r, num_rows="fixed", width="stretch", key="rebar_step3", disabled=["x", "y", "d_nom", "class"],
            column_config={
                "k_area": st.column_config.NumberColumn("k_площади", min_value=0.0, max_value=1.0, step=0.05),
                "k_bond": st.column_config.NumberColumn("k_сцепления", min_value=0.0, max_value=1.0, step=0.05)
            }
        )

    with col_in2:
        st.markdown("**3. Локальные дефекты бетона**")
        if st.button("➕ Добавить дефект бетона", type="secondary", key="add_def3"):
            st.session_state.defects.append({"type": "Скол (Вычитание)", "k_Rb": 1.0, "k_Eb": 1.0, "df": pd.DataFrame([{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 0, "y": 100}])})

        defect_data, defs_to_remove = [], []
        for i, d in enumerate(st.session_state.defects):
            with st.expander(f"🔸 Дефект #{i+1}: {d['type']}", expanded=True):
                c_d1, c_d2, c_d3 = st.columns([1.2, 1, 1.5])
                with c_d1:
                    d['type'] = st.selectbox("Тип повреждения", ["Скол (Вычитание)", "Деградация бетона"], key=f"t3_{i}", index=0 if "Скол" in d['type'] else 1)
                    if st.button("🗑️ Удалить", key=f"del3_{i}"): defs_to_remove.append(i)
                with c_d2:
                    if "Деградация" in d['type']:
                        d['k_Rb'] = st.number_input("k_Rb (Локальный)", value=d.get('k_Rb', 0.5), key=f"krb3_{i}", step=0.1)
                        d['k_Eb'] = st.number_input("k_Eb (Локальный)", value=d.get('k_Eb', 0.5), key=f"keb3_{i}", step=0.1)
                with c_d3:
                    d['df'] = st.data_editor(d['df'], num_rows="dynamic", key=f"df3_{i}", width="stretch", height=120)
                defect_data.append(d)

        if defs_to_remove:
            for i in reversed(defs_to_remove): st.session_state.defects.pop(i)
            st.rerun()

    # LIVE-ПРЕВЬЮ СЕЧЕНИЯ
    st.markdown("### 👁️ Интерактивный просмотр фактического сечения")
    fig_2d_prev, ax_2d_prev = plt.subplots(figsize=(2, 2))
    ax_2d_prev.add_patch(MplPolygon(st.session_state.raw_geom[0]['coords'], closed=True, fill=True, color='lightgray', alpha=0.7))
    for d in defect_data:
        pts = d['df'][['x', 'y']].values.tolist()
        if len(pts) >= 3:
            if "Скол" in d['type']: ax_2d_prev.add_patch(MplPolygon(pts, closed=True, fill=True, color='white', hatch='//', edgecolor='red', linewidth=1))
            else: ax_2d_prev.add_patch(MplPolygon(pts, closed=True, fill=True, color='red', alpha=0.3))
    for rb in rebar_df_step3.to_dict('records'):
        color = 'red' if rb['k_area'] > 0 or rb['k_bond'] < 1.0 else 'black'
        ax_2d_prev.scatter(rb['x'], rb['y'], color=color, s=20)
    ax_2d_prev.set_aspect('equal'); ax_2d_prev.axis('off')
    st.pyplot(fig_2d_prev)

    calc_btn = st.button("🚀 ПРИНУДИТЕЛЬНЫЙ РАСЧЕТ (ШАГ 3)", type="primary", key="calc_btn_3")

    if calc_btn or st.session_state.auto_calc:
        config_step3 = CalcConfig(calc_mode='survey', gamma_b=gamma_b_step3, gamma_s=gamma_s_step3, k_Rb_global=st.session_state.raw_config.k_Rb_global, k_Eb_global=st.session_state.raw_config.k_Eb_global, k_Rs_global=st.session_state.raw_config.k_Rs_global, apply_eta_ea=st.session_state.raw_config.apply_eta_ea)
        col_data_step3 = st.session_state.get('step2_col_data', st.session_state.raw_col_data).copy()
        geom_step3 = [{'type': 'base', 'coords': st.session_state.raw_geom[0]['coords']}]
        for d in defect_data:
            dtype = 'spall' if 'Скол' in d['type'] else 'degraded'
            geom_step3.append({'type': dtype, 'coords': d['df'][['x', 'y']].values.tolist(), 'k_Rb': d.get('k_Rb', 1.0), 'k_Eb': d.get('k_Eb', 1.0)})
        rebars_step3 = rebar_df_step3.to_dict('records')
        
        try:
            ndm_3 = Preprocessor.process(config_step3, col_data_step3, geom_step3, rebars_step3)
            solver_step3 = NDMSolver(target_cells=1200)
            res_3 = solver_step3.solve(ndm_3)
            lambda_3, _ = st.session_state.analyzer.find_lambda(ndm_3)
            
            st.session_state.step3_input = ndm_3
            st.session_state.step3_result = res_3
            st.session_state.lambda_3 = lambda_3
        except Exception as e:
            st.error(f"Ошибка вычислений: {e}")

    if st.session_state.step3_result is not None:
        ndm_in, res, lam = st.session_state.step3_input, st.session_state.step3_result, st.session_state.lambda_3
        ndm_1, lam_1, analyzer = st.session_state.step1_input, st.session_state.lambda_1, st.session_state.analyzer
        
        st.markdown("---")
        c_res1, c_res2 = st.columns([1, 2.5])
        
        with c_res1:
            if lam >= 1.0: st.markdown(f'<div class="success-box"><h3>✅ ЗАПАС (Факт)</h3><h1>λ = {lam:.3f}</h1></div>', unsafe_allow_html=True)
            else: st.markdown(f'<div class="warning-box"><h3>❌ РАЗРУШЕНИЕ (Факт)</h3><h1>λ = {lam:.3f}</h1></div>', unsafe_allow_html=True)
            
            loss = (1 - (lam / lam_1)) * 100 if lam_1 > 0 else 0
            st.error(f"📉 **Снижение надежности от дефектов: {loss:.1f}%**")
            st.info(f"N_ult = {ndm_in.N_ext/1000 * lam:,.1f} кН\n\n*(По проекту было: {ndm_1.N_ext/1000 * lam_1:,.1f} кН)*")

        with c_res2:
            t_2d, t_3d_s, t_3d_n, t_diag = st.tabs(["📈 N-M: Проект vs Факт", "🎲 3D Поверхность", "🧊 Эпюра НДМ", "📋 Диагностика"])
            
            with t_2d:
                c_2dx, c_2dy = st.columns(2)
                with c_2dx:
                    Nx1, Mx1 = analyzer.generate_nmx_curve(ndm_1)
                    Nx3, Mx3 = analyzer.generate_nmx_curve(ndm_in)
                    fig_x, ax_x = plt.subplots(figsize=(5, 4))
                    
                    # Проектная огибающая и вектор
                    ax_x.plot(Mx1, Nx1, 'k--', linewidth=1.5, label='Проект (Эталон)')
                    ax_x.plot([0, ndm_1.Mx_ext/1e6 * lam_1], [0, ndm_1.N_ext/1000 * lam_1], 'k--', linewidth=1.5, alpha=0.3, label='Вектор (Проект)')
                    ax_x.plot(ndm_1.Mx_ext/1e6 * lam_1, ndm_1.N_ext/1000 * lam_1, 'k*', markersize=10, alpha=0.3)
                    
                    # Фактическая огибающая и вектор
                    ax_x.plot(Mx3, Nx3, 'r-', linewidth=2, label='Факт (С дефектами)')
                    ax_x.fill(Mx3, Nx3, 'red', alpha=0.1)
                    ax_x.plot(ndm_in.Mx_ext/1e6, ndm_in.N_ext/1000, 'ro', markersize=8, label='Рабочая точка')
                    ax_x.plot([0, ndm_in.Mx_ext/1e6 * lam], [0, ndm_in.N_ext/1000 * lam], 'r-', linewidth=1.5)
                    ax_x.plot(ndm_in.Mx_ext/1e6 * lam, ndm_in.N_ext/1000 * lam, 'r*', markersize=12)
                    
                    ax_x.grid(True); ax_x.set_title("N-Mₓ"); ax_x.legend(fontsize=8)
                    st.pyplot(fig_x)
                    
                with c_2dy:
                    Ny1, My1 = analyzer.generate_nmy_curve(ndm_1)
                    Ny3, My3 = analyzer.generate_nmy_curve(ndm_in)
                    fig_y, ax_y = plt.subplots(figsize=(5, 4))
                    
                    # Проектная огибающая и вектор
                    ax_y.plot(My1, Ny1, 'k--', linewidth=1.5, label='Проект (Эталон)')
                    ax_y.plot([0, ndm_1.My_ext/1e6 * lam_1], [0, ndm_1.N_ext/1000 * lam_1], 'k--', linewidth=1.5, alpha=0.3, label='Вектор (Проект)')
                    ax_y.plot(ndm_1.My_ext/1e6 * lam_1, ndm_1.N_ext/1000 * lam_1, 'k*', markersize=10, alpha=0.3)
                    
                    # Фактическая огибающая и вектор
                    ax_y.plot(My3, Ny3, 'r-', linewidth=2, label='Факт (С дефектами)')
                    ax_y.fill(My3, Ny3, 'red', alpha=0.1)
                    ax_y.plot(ndm_in.My_ext/1e6, ndm_in.N_ext/1000, 'ro', markersize=8, label='Рабочая точка')
                    ax_y.plot([0, ndm_in.My_ext/1e6 * lam], [0, ndm_in.N_ext/1000 * lam], 'r-', linewidth=1.5)
                    ax_y.plot(ndm_in.My_ext/1e6 * lam, ndm_in.N_ext/1000 * lam, 'r*', markersize=12)
                    
                    ax_y.grid(True); ax_y.set_title("N-Mᵧ"); ax_y.legend(fontsize=8)
                    st.pyplot(fig_y)
            
            with t_3d_s:
                N_3d, Mx_3d, My_3d = analyzer.generate_3d_surface(ndm_in)
                fig_3d = go.Figure(data=[go.Mesh3d(x=Mx_3d, y=My_3d, z=N_3d, alphahull=0, opacity=0.3, color='red')])
                fig_3d.add_trace(go.Scatter3d(x=[ndm_in.Mx_ext/1e6], y=[ndm_in.My_ext/1e6], z=[ndm_in.N_ext/1000], mode='markers', marker=dict(color='red', size=8)))
                fig_3d.add_trace(go.Scatter3d(x=[0, ndm_in.Mx_ext/1e6 * lam], y=[0, ndm_in.My_ext/1e6 * lam], z=[0, ndm_in.N_ext/1000 * lam], mode='lines+markers', line=dict(color='red', width=4, dash='dash')))
                fig_3d.update_layout(scene=dict(xaxis_title='Mₓ', yaxis_title='Mᵧ', zaxis_title='N'), height=450, margin=dict(l=0, r=0, b=0, t=0))
                st.plotly_chart(fig_3d, use_container_width=True, key="fig_surf_3")

            with t_3d_n:
                if res.status != "NO_CONVERGENCE":
                    fig_ndm = go.Figure()
                    cells = res.concrete_cells
                    c_c = max(abs(min(cells['sigma'])), abs(max(cells['sigma']))) * 1.05 if len(cells['sigma']) > 0 else 1
                    fig_ndm.add_trace(go.Scatter3d(x=cells['x'], y=cells['y'], z=cells['sigma'], mode='markers', marker=dict(size=3, color=cells['sigma'], colorscale='RdBu_r', cmin=-c_c, cmax=c_c)))
                    cx, cy = ndm_in.section.effective_polygon.centroid.coords[0]
                    for rb in ndm_in.rebars:
                        eps_s = (res.eps0 + res.kx*(rb.y-cy) + res.ky*(rb.x-cx)) * rb.psi_bond
                        sigma_s = NDMSolver(1)._get_steel_stress(np.array([eps_s]), ndm_in.steel_props)[0]
                        color = 'red' if rb.k_area > 0 or rb.k_bond < 1.0 else 'black'
                        fig_ndm.add_trace(go.Scatter3d(x=[rb.x, rb.x], y=[rb.y, rb.y], z=[0, sigma_s], mode='lines+markers', line=dict(color=color, width=6)))
                    fig_ndm.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='σ, МПа'), height=450, margin=dict(l=0,r=0,b=0,t=0), showlegend=False)
                    st.plotly_chart(fig_ndm, use_container_width=True, key="fig_ndm_step3")

            with t_diag:
                st.markdown("#### Диаграммы материалов (Фактические)")
                c_props, s_props = ndm_in.concrete_props, ndm_in.steel_props
                eps_c = np.linspace(-c_props['eps_bu'] - 0.001, c_props['Rbt']/c_props['Eb'] + 0.0005, 500)
                fig_mat = go.Figure()
                sig_c_base = NDMSolver(1)._get_concrete_stress(eps_c, c_props, np.ones_like(eps_c), np.ones_like(eps_c), np.ones_like(eps_c))
                fig_mat.add_trace(go.Scatter(x=eps_c, y=sig_c_base, name='Здоровый бетон', line=dict(color='blue')))
                for i, d in enumerate(defect_data):
                    if "Деградация" in d['type']:
                        sig_c_deg = NDMSolver(1)._get_concrete_stress(eps_c, c_props, np.full_like(eps_c, d['k_Rb']), np.full_like(eps_c, d['k_Eb']), np.ones_like(eps_c))
                        fig_mat.add_trace(go.Scatter(x=eps_c, y=sig_c_deg, name=f'Деградация {i+1}', line=dict(dash='dash', color='orange')))
                fig_mat.update_layout(yaxis=dict(title=dict(text="σ_b, МПа", font=dict(color="blue")), tickfont=dict(color="blue")), height=300, margin=dict(l=0, r=0, b=0, t=30))
                st.plotly_chart(fig_mat, use_container_width=True, key="fig_mat_step3")