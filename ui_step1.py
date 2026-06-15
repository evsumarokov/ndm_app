# Файл: ui_step1.py
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import plotly.graph_objects as go
from shapely.geometry import Polygon
from analysis.preprocessor import Preprocessor, CalcConfig
from core.ndm_solver import NDMSolver
from analysis.pm_surface import CapacityAnalyzer

def render_step1():
    if 'tbl_concrete_df' not in st.session_state:
        st.session_state.tbl_concrete_df = pd.DataFrame([{"x": 0, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 400}, {"x": 0, "y": 400}])
    if 'tbl_rebar_df' not in st.session_state:
        st.session_state.tbl_rebar_df = pd.DataFrame([
            {"x": 55, "y": 55, "d_nom": 36, "class": "A500"},
            {"x": 345, "y": 55, "d_nom": 36, "class": "A500"},
            {"x": 55, "y": 345, "d_nom": 36, "class": "A500"},
            {"x": 345, "y": 345, "d_nom": 36, "class": "A500"},
        ])

    col_left, col_center, col_right = st.columns([1.3, 1.7, 1.5], gap="large")
    
    # =========================================================================
    # ⬅️ ЛЕВАЯ ПАНЕЛЬ
    # =========================================================================
    with col_left:
        st.markdown('<p class="panel-title">⚙️ Параметры проекта</p>', unsafe_allow_html=True)
        
        with st.expander("1. Материалы и Нагрузки", expanded=False):
            c_class = st.selectbox("Класс бетона", ['B15', 'B20', 'B25', 'B30', 'B35', 'B40', 'B50', 'B60'], index=3)
            c1, c2 = st.columns(2)
            gamma_b = c1.number_input("γ_b (Бетон)", value=1.3, step=0.05)
            k_Rb = c2.number_input("k_Rb", value=1.0, step=0.05)
            
            s_class = st.selectbox("Класс арматуры", ['A240', 'A400', 'A500'], index=2)
            c3, c4 = st.columns(2)
            gamma_s = c3.number_input("γ_s (Сталь)", value=1.15, step=0.05)
            k_Rs = c4.number_input("k_Rs", value=1.0, step=0.05)
            
            H_col = st.number_input("Высота H, м", min_value=1.0, value=4.2, step=0.1)
            mu_col = st.number_input("Коэфф. μ", min_value=0.1, value=0.8, step=0.1)
            apply_eta = st.checkbox("Учет эффектов 2-го порядка", value=True)
            
            N_design = st.number_input("Сила N, кН", value=-1749.0, step=100.0)
            Mx_static = st.number_input("Момент Mₓ, кН·м", value=25.5, step=5.0)
            My_static = st.number_input("Момент Mᵧ, кН·м", value=28.1, step=5.0)

        st.markdown('<p class="panel-title">📝 Управляющие таблицы геометрии</p>', unsafe_allow_html=True)
        
        edited_c_df = st.data_editor(st.session_state.tbl_concrete_df, num_rows="dynamic", use_container_width=True, key="edit_c_df")
        
        r_df_disp = st.session_state.tbl_rebar_df.copy()
        if not r_df_disp.empty:
            r_df_disp['class'] = s_class
            
        edited_r_df = st.data_editor(r_df_disp, num_rows="dynamic", use_container_width=True, key="edit_r_df")
        
        st.session_state.tbl_concrete_df = edited_c_df
        st.session_state.tbl_rebar_df = edited_r_df

    # =========================================================================
    # ⏺️ ЦЕНТРАЛЬНАЯ ПАНЕЛЬ
    # =========================================================================
    with col_center:
        st.markdown('<p class="panel-title">👁️ Live-превью сечения</p>', unsafe_allow_html=True)
        
        is_valid_geom = False
        base_coords = edited_c_df[['x', 'y']].values.tolist() if not edited_c_df.empty else []
        
        if len(base_coords) >= 3:
            fig_prev, ax_prev = plt.subplots(figsize=(4, 4))
            poly_patch = MplPolygon(base_coords, closed=True, fill=True, color='#1E88E5', alpha=0.2, edgecolor='#1E88E5', linewidth=2)
            ax_prev.add_patch(poly_patch)
            
            if not edited_r_df.empty:
                ax_prev.scatter(edited_r_df['x'], edited_r_df['y'], color='#E53935', s=60, zorder=5, label='Арматура')
                for idx, row in edited_r_df.iterrows():
                    ax_prev.text(row['x']+8, row['y']+8, str(idx), fontsize=9, color='black', weight='bold')

            ax_prev.set_aspect('equal')
            ax_prev.grid(True, linestyle='--', alpha=0.6)
            ax_prev.autoscale_view()
            st.pyplot(fig_prev)
            
            test_poly = Polygon(base_coords)
            if not test_poly.is_valid:
                st.error("❌ Геометрическая ошибка: Контур бетона имеет самопересечения! Проверьте порядок точек в таблице.")
            else:
                is_valid_geom = True
        else:
            st.error("❌ Задайте контур бетона (минимум 3 точки) в таблице слева.")
                
        calc_btn = st.button("🚀 ВЫПОЛНИТЬ ПРИНУДИТЕЛЬНЫЙ РАСЧЕТ", type="primary", disabled=not is_valid_geom, use_container_width=True)

    # =========================================================================
    # ➡️ ПРАВАЯ ПАНЕЛЬ
    # =========================================================================
    if is_valid_geom and (calc_btn or st.session_state.auto_calc):
        config_step1 = CalcConfig(calc_mode='design', gamma_b=gamma_b, gamma_s=gamma_s, k_Rb_global=k_Rb, k_Eb_global=1.0, k_Rs_global=k_Rs, apply_eta_ea=apply_eta)
        col_data_step1 = {'concrete_class': c_class, 'H_col': H_col, 'mu_col': mu_col, 'N_design': N_design, 'Mx_static': Mx_static, 'My_static': My_static, 'delta_x_tilt': 0, 'delta_y_tilt': 0, 'delta_x_misalign': 0, 'delta_y_misalign': 0, 'delta_geo': 0}
        
        geom_step1 = [{'type': 'base', 'coords': base_coords}]
        rebars_step1 = edited_r_df.to_dict('records')
        for r in rebars_step1: 
            if 'k_area' not in r: r['k_area'] = 0.0
            if 'k_bond' not in r: r['k_bond'] = 1.0
        
        solver = NDMSolver(target_cells=1200)
        analyzer = CapacityAnalyzer(solver)
        
        try:
            ndm_1 = Preprocessor.process(config_step1, col_data_step1, geom_step1, rebars_step1)
            res_1 = solver.solve(ndm_1)
            lambda_1, _ = analyzer.find_lambda(ndm_1)
            
            st.session_state.raw_config = config_step1
            st.session_state.raw_col_data = col_data_step1
            st.session_state.raw_geom = geom_step1
            st.session_state.raw_rebars = rebars_step1
            st.session_state.step1_input = ndm_1
            st.session_state.step1_result = res_1
            st.session_state.lambda_1 = lambda_1
            st.session_state.analyzer = analyzer
        except Exception as e:
            with col_right: st.error(f"Ошибка расчета НДМ: {e}")

    with col_right:
        st.markdown('<p class="panel-title">📊 Аналитика (Эталон)</p>', unsafe_allow_html=True)
        
        if st.session_state.step1_result is not None:
            ndm_in = st.session_state.step1_input
            res = st.session_state.step1_result
            lam = st.session_state.lambda_1
            analyzer = st.session_state.analyzer
            
            if lam >= 1.0: 
                st.markdown(f'<div class="success-box">✅ <b>ЗАПАС ПРОЧНОСТИ: λ = {lam:.3f}</b></div>', unsafe_allow_html=True)
            else: 
                st.markdown(f'<div class="error-box">❌ <b>РАЗРУШЕНИЕ СЕЧЕНИЯ: λ = {lam:.3f}</b></div>', unsafe_allow_html=True)

            t_2d, t_3d, t_ndm, t_log = st.tabs(["📈 N-M", "🎲 3D", "🧊 Эпюра", "📋 Лог"])
            
            # ==========================================
            # 1. 2D ГРАФИКИ (Mx и My со звездочками)
            # ==========================================
            with t_2d:
                c_mx, c_my = st.columns(2)
                
                with c_mx:
                    Nx, Mx = analyzer.generate_nmx_curve(ndm_in)
                    fig_x, ax_x = plt.subplots(figsize=(3, 3))
                    ax_x.plot(Mx, Nx, 'b-', linewidth=1.8)
                    ax_x.fill(Mx, Nx, 'blue', alpha=0.08)
                    # Фактическая точка
                    ax_x.plot(ndm_in.Mx_ext/1e6, ndm_in.N_ext/1000, 'ro')
                    # Луч нагружения
                    ax_x.plot([0, ndm_in.Mx_ext/1e6 * lam], [0, ndm_in.N_ext/1000 * lam], 'r--', alpha=0.6)
                    # Звездочка разрушения
                    ax_x.plot(ndm_in.Mx_ext/1e6 * lam, ndm_in.N_ext/1000 * lam, 'r*', markersize=10)
                    
                    ax_x.grid(True, linestyle=':', alpha=0.6); ax_x.set_xlabel('Mx, кН·м', fontsize=8); ax_x.set_ylabel('N, кН', fontsize=8)
                    st.pyplot(fig_x)
                    
                with c_my:
                    # Пробуем построить плоскость My (если метод реализован в ядре)
                    try:
                        Ny, My = analyzer.generate_nmy_curve(ndm_in) # Предполагаем наличие этого метода
                        fig_y, ax_y = plt.subplots(figsize=(3, 3))
                        ax_y.plot(My, Ny, 'g-', linewidth=1.8)
                        ax_y.fill(My, Ny, 'green', alpha=0.08)
                        ax_y.plot(ndm_in.My_ext/1e6, ndm_in.N_ext/1000, 'ro')
                        ax_y.plot([0, ndm_in.My_ext/1e6 * lam], [0, ndm_in.N_ext/1000 * lam], 'r--', alpha=0.6)
                        ax_y.plot(ndm_in.My_ext/1e6 * lam, ndm_in.N_ext/1000 * lam, 'r*', markersize=10)
                        ax_y.grid(True, linestyle=':', alpha=0.6); ax_y.set_xlabel('My, кН·м', fontsize=8); ax_y.set_ylabel('N, кН', fontsize=8)
                        st.pyplot(fig_y)
                    except AttributeError:
                        st.caption("💡 Добавьте метод generate_nmy_curve в pm_surface.py для вывода плоскости My")

            # ==========================================
            # 2. 3D ПОВЕРХНОСТЬ (С лучом и точкой разрушения)
            # ==========================================
            with t_3d:
                N_3d, Mx_3d, My_3d = analyzer.generate_3d_surface(ndm_in)
                fig_3d = go.Figure(data=[go.Mesh3d(x=Mx_3d, y=My_3d, z=N_3d, alphahull=0, opacity=0.25, color='blue')])
                
                # Фактическая точка (Красная точка)
                fig_3d.add_trace(go.Scatter3d(
                    x=[ndm_in.Mx_ext/1e6], y=[ndm_in.My_ext/1e6], z=[ndm_in.N_ext/1000], 
                    mode='markers', marker=dict(color='red', size=6), name='Факт'
                ))
                
                # Линия луча (Красный пунктир)
                fig_3d.add_trace(go.Scatter3d(
                    x=[0, ndm_in.Mx_ext/1e6 * lam], y=[0, ndm_in.My_ext/1e6 * lam], z=[0, ndm_in.N_ext/1000 * lam], 
                    mode='lines', line=dict(color='red', dash='dash', width=4), name='Траектория'
                ))
                
                # Точка предельного состояния (Темно-красный ромб/звездочка на поверхности)
                fig_3d.add_trace(go.Scatter3d(
                    x=[ndm_in.Mx_ext/1e6 * lam], y=[ndm_in.My_ext/1e6 * lam], z=[ndm_in.N_ext/1000 * lam], 
                    mode='markers', marker=dict(color='darkred', symbol='diamond', size=8), name='Разрушение'
                ))
                
                fig_3d.update_layout(margin=dict(l=0, r=0, b=0, t=0), scene=dict(xaxis_title='Mx', yaxis_title='My', zaxis_title='N'))
                st.plotly_chart(fig_3d, use_container_width=True)

            # ==========================================
            # 3. ЭПЮРА НДМ (Две независимые цветовые шкалы)
            # ==========================================
            with t_ndm:
                if res.status != "NO_CONVERGENCE":
                    fig_ndm = go.Figure()
                    cells = res.concrete_cells
                    sig_b = cells['sigma']
                    
                    # Масштаб бетона
                    min_sig_b = np.min(sig_b) if len(sig_b) > 0 else -1
                    max_sig_b = np.max(sig_b) if len(sig_b) > 0 else 0
                    
                    fig_ndm.add_trace(go.Scatter3d(
                        x=cells['x'], y=cells['y'], z=sig_b, 
                        mode='markers', 
                        marker=dict(
                            size=3, 
                            color=sig_b, 
                            colorscale='Blues', # Отдельная шкала для бетона
                            cmin=min_sig_b, 
                            cmax=max_sig_b,
                            colorbar=dict(title="Бетон (σ_b)", x=0.85, thickness=15, len=0.4, y=0.75)
                        ), 
                        name='Бетон'
                    ))
                    
                    cx, cy = ndm_in.section.effective_polygon.centroid.coords[0]
                    
                    # Собираем напряжения в стали
                    sig_s_list = []
                    for rb in ndm_in.rebars:
                        eps_s = (res.eps0 + res.kx*(rb.y-cy) + res.ky*(rb.x-cx)) * rb.psi_bond
                        sig_s = NDMSolver(1)._get_steel_stress(np.array([eps_s]), ndm_in.steel_props)[0]
                        sig_s_list.append(sig_s)
                        
                    min_sig_s = min(sig_s_list) if sig_s_list else -1
                    max_sig_s = max(sig_s_list) if sig_s_list else 1
                    
                    # Отрисовка арматуры
                    for i, rb in enumerate(ndm_in.rebars):
                        sig_s = sig_s_list[i]
                        
                        fig_ndm.add_trace(go.Scatter3d(
                            x=[rb.x, rb.x], y=[rb.y, rb.y], z=[0, sig_s], 
                            mode='lines+markers',
                            line=dict(color=sig_s, colorscale='Reds', cmin=min_sig_s, cmax=max_sig_s, width=6),
                            marker=dict(
                                color=sig_s, colorscale='Reds', cmin=min_sig_s, cmax=max_sig_s,
                                size=6,
                                colorbar=dict(title="Сталь (σ_s)", x=1.05, thickness=15, len=0.4, y=0.25) # Вторая шкала
                            ),
                            showlegend=(i==0), name='Арматура'
                        ))
                        
                    fig_ndm.update_layout(
                        margin=dict(l=0, r=0, b=0, t=0),
                        scene=dict(xaxis_title='X, мм', yaxis_title='Y, мм', zaxis_title='σ, МПа')
                    )
                    st.plotly_chart(fig_ndm, use_container_width=True)
                else:
                    st.error("Разрушение сечения при итерациях")
                    
            # ПОЛНОСТЬЮ ОБНОВЛЕННЫЙ ЖУРНАЛ РАСЧЕТА
            with t_log:
                st.markdown("**1. Физико-геометрические параметры**")
                A_b = ndm_in.section.effective_polygon.area
                A_s = sum(rb.area_eff for rb in ndm_in.rebars)
                cx, cy = ndm_in.section.effective_polygon.centroid.coords[0]
                st.write(f"- Площадь бетона ($A_b$): **{A_b:,.0f}** мм²")
                st.write(f"- Площадь арматуры ($A_s$): **{A_s:,.0f}** мм²")
                st.write(f"- Геометрический центр: $x_c$ = **{cx:.1f}** мм, $y_c$ = **{cy:.1f}** мм")
                
                st.markdown("**2. Напряжения и деформации (НДМ)**")
                if res.status != "NO_CONVERGENCE":
                    st.write(f"- Итераций Ньютона: **{res.iterations}**")
                    st.write(f"- $\epsilon_0$ = **{res.eps0:.6e}**")
                    st.write(f"- $1/r_x$ = **{res.kx:.6e}** | $1/r_y$ = **{res.ky:.6e}**")
                    
                    min_sig_b = np.min(res.concrete_cells['sigma']) if len(res.concrete_cells['sigma']) > 0 else 0
                    st.write(f"- Максимальное сжатие бетона ($\sigma_{{b,min}}$): **{min_sig_b:.2f}** МПа")
                    
                    if ndm_in.rebars:
                        sig_s_arr = []
                        for rb in ndm_in.rebars:
                            eps_s = (res.eps0 + res.kx*(rb.y-cy) + res.ky*(rb.x-cx)) * rb.psi_bond
                            sig_s = NDMSolver(1)._get_steel_stress(np.array([eps_s]), ndm_in.steel_props)[0]
                            sig_s_arr.append(sig_s)
                        st.write(f"- Напряжения в арматуре: от **{np.min(sig_s_arr):.1f}** до **{np.max(sig_s_arr):.1f}** МПа")
                else:
                    st.write("- Статус: **Разрушение (баланс не найден)**")

                st.markdown("**3. Сводка СП 63.13330 (Жесткость и Эксцентриситеты)**")
                for title, lines in ndm_in.calc_log.items():
                    st.markdown(f"*{title}*")
                    for l in lines:
                        st.caption(f"› {l}")