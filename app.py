# Файл: app.py
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

# ============================================================================
# 📄 НАСТРОЙКИ СТРАНИЦЫ
# ============================================================================
st.set_page_config(
    layout="wide", 
    page_title="Scan-to-NDM: Анализ колонны",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# Кастомные стили для улучшения внешнего вида
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #424242;
        margin: 1.5rem 0 0.5rem 0;
    }
    .info-box {
        background-color: #E3F2FD;
        border-left: 4px solid #1E88E5;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .success-box {
        background-color: #E8F5E9;
        border-left: 4px solid #43A047;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .warning-box {
        background-color: #FFF3E0;
        border-left: 4px solid #FB8C00;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# 🎯 ЗАГОЛОВОК И ОПИСАНИЕ
# ============================================================================
st.markdown('<p class="main-header">🏗️ Scan-to-NDM</p>', unsafe_allow_html=True)
st.markdown("### Программный комплекс нелинейного деформационного расчета железобетонных сечений")

st.markdown("""
<div class="info-box">
<strong>📌 Назначение:</strong> Расчет несущей способности колонн по СП 63.13330.2018 
с учетом фактической геометрии, дефектов и нелинейной работы материалов.
</div>
""", unsafe_allow_html=True)

# ============================================================================
# 💾 ИНИЦИАЛИЗАЦИЯ SESSION STATE
# ============================================================================
if 'defects' not in st.session_state:
    st.session_state.defects = [
        {
            "type": "Скол (Вычитание)", "k_Rb": 1.0, "k_Eb": 1.0,
            "df": pd.DataFrame([{"x": 400, "y": 400}, {"x": 300, "y": 400}, {"x": 400, "y": 300}])
        },
        {
            "type": "Коррозия бетона (Деградация)", "k_Rb": 0.5, "k_Eb": 0.5,
            "df": pd.DataFrame([{"x": 0, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 50}, {"x": 0, "y": 50}])
        }
    ]

# ============================================================================
# 📊 БОКОВАЯ ПАНЕЛЬ — ПАРАМЕТРЫ РАСЧЕТА
# ============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Параметры расчета")
    
    # Режим расчета
    st.markdown('<p class="sub-header">1. Режим расчета</p>', unsafe_allow_html=True)
    calc_mode_ui = st.radio(
        "Тип оценки:", 
        ["Проектирование (СП 63)", "Обследование (Фактика)"],
        help="Проектирование: с коэффициентами надежности\nОбследование: фактические характеристики"
    )
    calc_mode = 'design' if "Проектирование" in calc_mode_ui else 'survey'
    
    apply_eta_ea = st.checkbox(
        "Учитывать эффекты 2-го порядка (η) и эксцентриситеты (ea)", 
        value=True,
        help="η — коэффициент продольного изгиба\nea — случайный эксцентриситет"
    )
    
    # Материалы
    st.markdown('<p class="sub-header">2. Материалы</p>', unsafe_allow_html=True)
    c_class = st.selectbox(
        "Класс бетона", 
        ['B15', 'B20', 'B25', 'B30', 'B35', 'B40', 'B50', 'B60'], 
        index=2,
        help="B25 — бетон класса B25 (Rb = 14.5 МПа)"
    )
    
    l0 = st.number_input(
        "Расчетная длина колонны l₀, м", 
        min_value=1.0, 
        value=3.0, 
        step=0.1,
        help="Расстояние между точками закрепления"
    )
    
    # Нагрузки
    st.markdown('<p class="sub-header">3. Нагрузки</p>', unsafe_allow_html=True)
    N_design = st.number_input(
        "Продольная сила N, кН", 
        value=-1500.0, 
        step=100.0,
        help="Отрицательное значение — сжатие"
    )
    Mx_static = st.number_input(
        "Момент Mₓ (статика), кН·м", 
        value=80.0, 
        step=10.0,
        help="Момент относительно оси X"
    )
    My_static = st.number_input(
        "Момент Mᵧ (статика), кН·м", 
        value=20.0, 
        step=10.0,
        help="Момент относительно оси Y"
    )

    # Геодезия
    st.markdown('<p class="sub-header">4. Геометрические несовершенства</p>', unsafe_allow_html=True)
    st.markdown("#### Наклон колонны (верх):")
    col_geo1, col_geo2 = st.columns(2)
    with col_geo1:
        delta_x_tilt = st.number_input("ΔX, мм", value=15.0, key="tilt_x")
    with col_geo2:
        delta_y_tilt = st.number_input("ΔY, мм", value=5.0, key="tilt_y")
    
    st.markdown("#### Межэтажное смещение:")
    col_geo3, col_geo4 = st.columns(2)
    with col_geo3:
        delta_x_misalign = st.number_input("ΔX, мм", value=10.0, key="mis_x")
    with col_geo4:
        delta_y_misalign = st.number_input("ΔY, мм", value=0.0, key="mis_y")
    
    delta_geo = st.number_input(
        "Погрешность геодезической съемки, мм", 
        value=5.0,
        help="Дополнительный запас на неточность измерений"
    )

# ============================================================================
# 📐 ОСНОВНАЯ ОБЛАСТЬ — ГЕОМЕТРИЯ
# ============================================================================
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown('<p class="sub-header">5. Контур сечения бетона</p>', unsafe_allow_html=True)
    st.markdown("Координаты вершин многоугольника (мм)")
    base_df_init = pd.DataFrame([
        {"x": 0, "y": 0}, 
        {"x": 400, "y": 0}, 
        {"x": 400, "y": 400}, 
        {"x": 0, "y": 400}
    ])
    base_df = st.data_editor(
        base_df_init, 
        num_rows="dynamic", 
        width="stretch",
        key="base_coords",
        column_config={
            "x": st.column_config.NumberColumn("X, мм", min_value=0),
            "y": st.column_config.NumberColumn("Y, мм", min_value=0),
        }
    )

with col_t2:
    st.markdown('<p class="sub-header">6. Арматурные стержни</p>', unsafe_allow_html=True)
    st.markdown("Положение и характеристики арматуры")
    rebar_df_init = pd.DataFrame([
        {"x": 40, "y": 40, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
        {"x": 200, "y": 40, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
        {"x": 360, "y": 40, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
        {"x": 40, "y": 360, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
        {"x": 200, "y": 360, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
        {"x": 360, "y": 360, "d_nom": 25, "class": "A500", "k_area": 0.0, "k_bond": 1.0},
    ])
    rebar_df = st.data_editor(
        rebar_df_init, 
        num_rows="dynamic", 
        width="stretch",
        key="rebar_coords",
        column_config={
            "x": st.column_config.NumberColumn("X, мм"),
            "y": st.column_config.NumberColumn("Y, мм"),
            "d_nom": st.column_config.NumberColumn("Ø, мм"),
            "class": st.column_config.TextColumn("Класс"),
            "k_area": st.column_config.NumberColumn("k_площади", min_value=0.0, max_value=1.0),
            "k_bond": st.column_config.NumberColumn("k_сцепления", min_value=0.0, max_value=1.0),
        }
    )

# ============================================================================
# 🚨 ДЕФЕКТЫ
# ============================================================================
st.markdown('<p class="sub-header">7. Локальные дефекты бетона</p>', unsafe_allow_html=True)

if st.button("➕ Добавить дефект", type="secondary"):
    st.session_state.defects.append({
        "type": "Скол (Вычитание)", "k_Rb": 1.0, "k_Eb": 1.0,
        "df": pd.DataFrame([{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 0, "y": 100}])
    })

defect_data = []
defs_to_remove = []

for i, d in enumerate(st.session_state.defects):
    with st.expander(f"🔸 Дефект #{i+1}: {d['type']}", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 2])
        
        with c1:
            d['type'] = st.selectbox(
                "Тип повреждения", 
                ["Скол (Вычитание)", "Коррозия бетона (Деградация)"], 
                key=f"t_{i}", 
                index=0 if "Скол" in d['type'] else 1
            )
            
            if st.button("🗑️ Удалить", key=f"del_{i}"):
                defs_to_remove.append(i)
                
        with c2:
            if "Деградация" in d['type']:
                d['k_Rb'] = st.number_input(
                    "k_Rb", 
                    value=d['k_Rb'], 
                    key=f"krb_{i}", 
                    step=0.1,
                    min_value=0.0,
                    max_value=1.0,
                    help="Коэффициент снижения прочности"
                )
                d['k_Eb'] = st.number_input(
                    "k_Eb", 
                    value=d['k_Eb'], 
                    key=f"keb_{i}", 
                    step=0.1,
                    min_value=0.0,
                    max_value=1.0,
                    help="Коэффициент снижения модуля упругости"
                )
        
        with c3:
            st.markdown("Координаты контура дефекта:")
            d['df'] = st.data_editor(
                d['df'], 
                num_rows="dynamic", 
                key=f"df_{i}", 
                width="stretch"
            )
        
        defect_data.append(d)

if defs_to_remove:
    for i in reversed(defs_to_remove):
        st.session_state.defects.pop(i)
    st.rerun()

st.markdown("---")

# ============================================================================
# 👁️ ВИЗУАЛИЗАЦИЯ СЕЧЕНИЯ
# ============================================================================
st.markdown('<p class="sub-header">👁️ Визуализация сечения</p>', unsafe_allow_html=True)

fig_preview, ax_preview = plt.subplots(figsize=(7, 7), dpi=100)
base_coords = base_df[['x', 'y']].values.tolist()

# Бетонное сечение
if len(base_coords) >= 3:
    ax_preview.add_patch(
        MplPolygon(base_coords, closed=True, fill=True, color='lightgray', alpha=0.5)
    )

# Дефекты
for i, d in enumerate(defect_data):
    pts = d['df'][['x', 'y']].values.tolist()
    if len(pts) >= 3:
        poly_geom = Polygon(pts)
        if not poly_geom.is_valid:
            poly_geom = poly_geom.buffer(0)
        cx, cy = poly_geom.centroid.x, poly_geom.centroid.y
        
        if "Скол" in d['type']:
            ax_preview.add_patch(
                MplPolygon(pts, closed=True, fill=True, color='white', hatch='//', 
                          edgecolor='red', linewidth=2)
            )
            ax_preview.text(cx+25, cy+25, f"Д{i+1}", color='red', fontsize=11, 
                          ha='center', va='center', fontweight='bold')
        else:
            ax_preview.add_patch(
                MplPolygon(pts, closed=True, fill=True, color='red', alpha=0.3)
            )
            ax_preview.text(cx, cy, f"Д{i+1}", color='darkred', fontsize=11, 
                          ha='center', va='center', fontweight='bold')

# Арматура
rb_x = rebar_df['x'].tolist()
rb_y = rebar_df['y'].tolist()
ax_preview.scatter(rb_x, rb_y, color='black', s=50, zorder=5, marker='o')

# Номера стержней
for idx, row in rebar_df.iterrows():
    ax_preview.text(row['x'] + 10, row['y'] + 10, str(idx), 
                   color='black', fontsize=9, fontweight='bold', zorder=6)

# Масштабирование
all_x = base_df['x'].tolist() + rebar_df['x'].tolist()
all_y = base_df['y'].tolist() + rebar_df['y'].tolist()

if all_x and all_y:
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    
    x_range = x_max - x_min
    y_range = y_max - y_min
    padding_x = x_range * 0.15 if x_range > 0 else 50
    padding_y = y_range * 0.15 if y_range > 0 else 50
    
    ax_preview.set_xlim(x_min - padding_x, x_max + padding_x)
    ax_preview.set_ylim(y_min - padding_y, y_max + padding_y)

ax_preview.set_aspect('equal')
ax_preview.grid(True, linestyle='--', alpha=0.3)
ax_preview.set_xlabel('X, мм', fontsize=10)
ax_preview.set_ylabel('Y, мм', fontsize=10)
ax_preview.legend(loc='upper right', bbox_to_anchor=(1.35, 1), fontsize=9)
plt.tight_layout()

col_viz1, col_viz2 = st.columns([2, 1])
with col_viz1:
    st.pyplot(fig_preview, bbox_inches='tight')

with col_viz2:
    st.markdown("#### Условные обозначения:")
    st.markdown("""
    - ⬜ **Серая область** — бетонное сечение
    - 🔴 **Красная область** — зона деградации
    - ⬛ **Черные точки** — арматурные стержни
    - 📐 **Штриховка** — скол бетона
    """)

# ============================================================================
# 📐 ГЕОМЕТРИЧЕСКАЯ СХЕМА
# ============================================================================
with st.expander("📐 Геометрическая схема (Профиль колонны)", expanded=False):
    st.markdown("### Фактическая ось и смещения")
    st.markdown("Визуализация отклонений от вертикали")
    
    fig_geo = go.Figure()

    # Нижняя колонна
    fig_geo.add_trace(go.Scatter3d(
        x=[0, delta_x_tilt], y=[0, delta_y_tilt], z=[0, l0],
        mode='lines+markers', 
        line=dict(color='blue', width=6), 
        name='Нижняя колонна',
        marker=dict(size=4)
    ))

    # Межэтажное смещение
    s_x = delta_x_tilt + delta_x_misalign
    s_y = delta_y_tilt + delta_y_misalign
    fig_geo.add_trace(go.Scatter3d(
        x=[delta_x_tilt, s_x], y=[delta_y_tilt, s_y], z=[l0, l0],
        mode='lines', 
        line=dict(color='black', width=4, dash='dot'), 
        name='Межэтажный сдвиг'
    ))

    # Верхняя колонна (вертикальная)
    fig_geo.add_trace(go.Scatter3d(
        x=[s_x, s_x], y=[s_y, s_y], z=[l0, l0*2],
        mode='lines+markers', 
        line=dict(color='red', width=6), 
        name='Верхняя колонна',
        marker=dict(size=4)
    ))

    fig_geo.update_layout(
        scene=dict(
            xaxis_title='Смещение X (мм)', 
            yaxis_title='Смещение Y (мм)', 
            zaxis_title='Высота (м)',
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=2)
        ), 
        height=500,
        margin=dict(l=0, r=0, b=0, t=0)
    )
    st.plotly_chart(fig_geo, use_container_width=True)

# Добавьте эту строку после инициализации session_state.defects
if 'auto_calc' not in st.session_state:
    st.session_state.auto_calc = False

if 'last_params_hash' not in st.session_state:
    st.session_state.last_params_hash = None

# ============================================================================
# 🚀 КНОПКА РАСЧЕТА И РЕЗУЛЬТАТЫ
# ============================================================================
st.markdown("---")
st.markdown('<p class="sub-header">🚀 Расчет</p>', unsafe_allow_html=True)

# Добавляем галочку автоматического расчета
col_calc1, col_calc2 = st.columns([1, 3])
with col_calc1:
    auto_calc = st.checkbox(
        "⚡ Автоматический расчет", 
        value=st.session_state.auto_calc,
        key="auto_calc_checkbox",
        help="Пересчитывать автоматически при изменении параметров"
    )
    st.session_state.auto_calc = auto_calc

with col_calc2:
    calc_button = st.button(
        "🚀 РАССЧИТАТЬ СЕЧЕНИЕ", 
        type="primary", 
        use_container_width=True,
        disabled=auto_calc  # Отключаем кнопку, если авторасчет включен
    )

# Проверяем, нужно ли запускать расчет
should_calculate = calc_button or auto_calc

if should_calculate:
    # Подготовка данных
    gamma_b = 1.3 if calc_mode == 'design' else 1.0
    gamma_s = 1.15 if calc_mode == 'design' else 1.0
    config = CalcConfig(calc_mode=calc_mode, gamma_b=gamma_b, gamma_s=gamma_s, apply_eta_ea=apply_eta_ea)

    column_data = {
        'concrete_class': c_class, 'length_l0': l0, 'N_design': N_design,
        'Mx_static': Mx_static, 'My_static': My_static,
        'delta_x_tilt': delta_x_tilt, 'delta_y_tilt': delta_y_tilt,
        'delta_x_misalign': delta_x_misalign, 'delta_y_misalign': delta_y_misalign,
        'delta_geo': delta_geo
    }

    geometry_data = [{'type': 'base', 'coords': base_coords}]
    for d in defect_data:
        dtype = 'spall' if 'Скол' in d['type'] else 'degraded'
        def_coords = d['df'][['x', 'y']].values.tolist()
        geometry_data.append({
            'type': dtype, 'coords': def_coords,
            'k_Rb': d.get('k_Rb', 1.0), 'k_Eb': d.get('k_Eb', 1.0)
        })

    rebar_data_list = rebar_df.to_dict('records')

    try:
        # Расчет
        ndm_input = Preprocessor.process(config, column_data, geometry_data, rebar_data_list)
        solver = NDMSolver(target_cells=1200)
        analyzer = CapacityAnalyzer(solver)
        
        with st.spinner('⏳ Выполняется нелинейный расчет...'):
            current_state_result = solver.solve(ndm_input)
            lambda_factor, log = analyzer.find_lambda(ndm_input)

        # Результаты
        st.markdown('<p class="sub-header">📊 Результаты расчета</p>', unsafe_allow_html=True)
        
        col_l1, col_l2 = st.columns([1, 2.5])
        
        with col_l1:
            if lambda_factor >= 1.0:
                st.markdown(f"""
                <div class="success-box">
                <h3>✅ ЗАПАС ПРОЧНОСТИ</h3>
                <h1>λ = {lambda_factor:.3f}</h1>
                <p>Сечение выдерживает нагрузку с запасом {(lambda_factor-1)*100:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="warning-box">
                <h3>❌ ПЕРЕГРУЗКА</h3>
                <h1>λ = {lambda_factor:.3f}</h1>
                <p>Нагрузка превышает несущую способность на {(1-lambda_factor)*100:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
            
            N_ext_kN = ndm_input.N_ext / 1000.0
            Mx_ext_kNm = ndm_input.Mx_ext / 1000000.0
            My_ext_kNm = ndm_input.My_ext / 1000000.0
            
            st.markdown("#### Внешние усилия:")
            st.write(f"""
            - Продольная сила: **N = {N_ext_kN:,.1f} кН**
            - Момент Mₓ: **{Mx_ext_kNm:,.1f} кН·м**
            - Момент Mᵧ: **{My_ext_kNm:,.1f} кН·м**
            """)
            
            if apply_eta_ea:
                st.info(f"""
                **📐 Учет СП 63:**
                - η = {ndm_input.eta:.2f} (продольный изгиб)
                - eₓ = {ndm_input.ea_x:.1f} мм (случайный эксцентриситет)
                - eᵧ = {ndm_input.ea_y:.1f} мм
                """)

        with col_l2:
            tab_2d_x, tab_2d_y, tab_3d, tab_diag = st.tabs([
                "📈 2D (N - Mₓ)", "📈 2D (N - Mᵧ)", "🎲 3D Поверхность прочности", "🔬 Диагностика"
            ])
              
            with tab_diag:
                st.markdown("### 🔬 Диагностика напряженно-деформированного состояния")

                if current_state_result.status != "NO_CONVERGENCE":
                    st.markdown("#### 3D Эпюра напряжений (Бетон + Арматура)")
                    
                    fig_ndm = go.Figure()
                    cells = current_state_result.concrete_cells
                    
                    eps0, kx, ky = current_state_result.eps0, current_state_result.kx, current_state_result.ky
                    cx, cy = ndm_input.section.effective_polygon.centroid.coords[0]
                    
                    # Расчет напряжений в арматуре
                    rebar_sigmas = []
                    for rb in ndm_input.rebars:
                        eps_s = (eps0 + kx * (rb.y - cy) + ky * (rb.x - cx)) * rb.psi_bond
                        sigma_s = solver._get_steel_stress(np.array([eps_s]), ndm_input.steel_props)[0]
                        rebar_sigmas.append(sigma_s)
                    
                    # Диапазоны для цветовых шкал
                    concrete_min = min(cells['sigma'])
                    concrete_max = max(cells['sigma'])
                    c_concrete = max(abs(concrete_min), abs(concrete_max)) * 1.05
                    cmin_b, cmax_b = -c_concrete, c_concrete
                    
                    steel_min = min(rebar_sigmas)
                    steel_max = max(rebar_sigmas)
                    c_steel = max(abs(steel_min), abs(steel_max)) * 1.05
                    cmin_s, cmax_s = -c_steel, c_steel

                    # Бетон
                    fig_ndm.add_trace(go.Scatter3d(
                        x=cells['x'], y=cells['y'], z=cells['sigma'],
                        mode='markers', 
                        marker=dict(
                            size=3, 
                            color=cells['sigma'], 
                            colorscale='RdBu_r', 
                            showscale=True, 
                            cmin=cmin_b,
                            cmax=cmax_b,
                            colorbar=dict(
                                title="σ_b, МПа", 
                                x=0.82,
                                len=0.7,
                                thickness=15
                            )
                        ),
                        name="Бетон",
                        showlegend=True
                    ))
                    
                    # Арматура
                    for i, rb in enumerate(ndm_input.rebars):
                        sigma_s = rebar_sigmas[i]
                        
                        fig_ndm.add_trace(go.Scatter3d(
                            x=[rb.x, rb.x], 
                            y=[rb.y, rb.y], 
                            z=[0, sigma_s],
                            mode='lines+markers', 
                            line=dict(
                                color=[0, sigma_s],
                                colorscale='RdBu_r', 
                                cmin=cmin_s, 
                                cmax=cmax_s, 
                                width=8,
                                showscale=False
                            ), 
                            marker=dict(
                                size=6, 
                                color=[sigma_s],
                                colorscale='RdBu_r', 
                                cmin=cmin_s, 
                                cmax=cmax_s,
                                showscale=False
                            ),
                            showlegend=False
                        ))
                        
                    # Вторая шкала для арматуры
                    fig_ndm.add_trace(go.Scatter3d(
                        x=[None], y=[None], z=[None],
                        mode='markers',
                        marker=dict(
                            size=0,
                            color=[cmin_s, cmax_s],
                            colorscale='RdBu_r',
                            cmin=cmin_s,
                            cmax=cmax_s,
                            showscale=True,
                            colorbar=dict(
                                title="σ_s, МПа", 
                                x=0.98,
                                len=0.7,
                                thickness=15
                            )
                        ),
                        showlegend=False
                    ))
                        
                    fig_ndm.update_layout(
                        scene=dict(
                            xaxis_title='X, мм', 
                            yaxis_title='Y, мм', 
                            zaxis_title='σ, МПа'
                        ), 
                        height=600,
                        legend=dict(
                            x=0.01,
                            y=0.99,
                            bgcolor='rgba(255,255,255,0.7)'
                        ),
                        margin=dict(l=0, r=0, b=0, t=0)
                    )
                    st.plotly_chart(fig_ndm, use_container_width=True)
                else:
                    st.error("❌ Система уравнений не сошлась. Проверьте исходные данные.")
                
                # Диаграммы материалов
                st.markdown("#### Диаграммы деформирования материалов")
                st.info("💡 Показаны фактические зависимости σ-ε, используемые в расчете")
                
                c_props = ndm_input.concrete_props
                s_props = ndm_input.steel_props
                
                eps_c_arr = np.linspace(-c_props['eps_bu'] - 0.001, c_props['Rbt']/c_props['Eb'] + 0.0005, 500)
                eps_s_arr = np.linspace(-s_props['eps_su'] - 0.01, s_props['eps_su'] + 0.01, 500)
                
                sig_c_base = solver._get_concrete_stress(
                    eps_c_arr, c_props, np.ones_like(eps_c_arr), np.ones_like(eps_c_arr), np.ones_like(eps_c_arr)
                )
                sig_s = solver._get_steel_stress(eps_s_arr, s_props)
                
                fig_mat = go.Figure()
                fig_mat.add_trace(go.Scatter(
                    x=eps_c_arr*1000, y=sig_c_base, 
                    mode='lines', 
                    name=f'Бетон {c_class}',
                    line=dict(color='blue', width=2)
                ))
                
                deg_idx = 1
                for d in defect_data:
                    if "Деградация" in d['type']:
                        krb, keb = d['k_Rb'], d['k_Eb']
                        sig_c_deg = solver._get_concrete_stress(
                            eps_c_arr, c_props, np.full_like(eps_c_arr, krb), np.full_like(eps_c_arr, keb), np.ones_like(eps_c_arr)
                        )
                        fig_mat.add_trace(go.Scatter(
                            x=eps_c_arr*1000, y=sig_c_deg, 
                            mode='lines', 
                            line=dict(dash='dash', color='orange', width=2), 
                            name=f'Деградация Д{deg_idx}'
                        ))
                        deg_idx += 1
                        
                fig_mat.add_trace(go.Scatter(
                    x=eps_s_arr*1000, y=sig_s, 
                    mode='lines', 
                    name=f'Арматура',
                    line=dict(color='red', width=2),
                    yaxis='y2'
                ))

                fig_mat.update_layout(
                    title="Диаграммы деформирования",
                    xaxis=dict(title="Деформации ε, ‰"),
                    yaxis=dict(
                        title=dict(text="Напряжения в бетоне σ_b, МПа", font=dict(color="blue")), 
                        tickfont=dict(color="blue"),
                        side="left"
                    ),
                    yaxis2=dict(
                        title=dict(text="Напряжения в стали σ_s, МПа", font=dict(color="red")), 
                        tickfont=dict(color="red"), 
                        overlaying="y", 
                        side="right"
                    ),
                    height=450, 
                    margin=dict(l=60, r=60, b=40, t=60),
                    showlegend=True,
                    legend=dict(x=0.02, y=0.98)
                )
                st.plotly_chart(fig_mat, use_container_width=True)
                
                # Лог решения
                with st.expander("📋 Подробный лог решения уравнений", expanded=False):
                    st.write(f"**Входные усилия:** N={ndm_input.N_ext:,.1f} Н, Mx={ndm_input.Mx_ext:,.1f} Н·мм, My={ndm_input.My_ext:,.1f} Н·мм")
                    
                    if current_state_result.history:
                        df_log = pd.DataFrame(current_state_result.history)
                        st.dataframe(df_log, use_container_width=True)
                    
                    if current_state_result.status == "NO_CONVERGENCE":
                        st.error("❌ Решатель не смог свести невязку усилий к допустимому минимуму.")
                    else:
                        st.success("✅ Система уравнений успешно сошлась.")
                
            with tab_2d_x:
                st.markdown("#### Диаграмма N-Mₓ")
                N_curve_x, M_curve_x = analyzer.generate_nmx_curve(ndm_input)
                fig3, ax3 = plt.subplots(figsize=(8, 5))
                ax3.plot(M_curve_x, N_curve_x, 'b-', linewidth=2, label='Предельная кривая')
                ax3.fill(M_curve_x, N_curve_x, color='blue', alpha=0.1)
                ax3.plot(Mx_ext_kNm, N_ext_kN, 'ro', markersize=10, label='Рабочая точка')
                ax3.plot([0, Mx_ext_kNm * lambda_factor], [0, N_ext_kN * lambda_factor], 'r--', linewidth=1.5)
                ax3.plot(Mx_ext_kNm * lambda_factor, N_ext_kN * lambda_factor, 'r*', markersize=15, label='Предельная точка')
                ax3.grid(True, alpha=0.3)
                ax3.set_xlabel('Mₓ, кН·м')
                ax3.set_ylabel('N, кН')
                ax3.legend()
                ax3.set_title('Диаграмма взаимодействия N-Mₓ')
                st.pyplot(fig3)
                
            with tab_2d_y:
                st.markdown("#### Диаграмма N-Mᵧ")
                N_curve_y, M_curve_y = analyzer.generate_nmy_curve(ndm_input)
                fig4, ax4 = plt.subplots(figsize=(8, 5))
                ax4.plot(M_curve_y, N_curve_y, 'g-', linewidth=2, label='Предельная кривая')
                ax4.fill(M_curve_y, N_curve_y, color='green', alpha=0.1)
                ax4.plot(My_ext_kNm, N_ext_kN, 'ro', markersize=10, label='Рабочая точка')
                ax4.plot([0, My_ext_kNm * lambda_factor], [0, N_ext_kN * lambda_factor], 'r--', linewidth=1.5)
                ax4.plot(My_ext_kNm * lambda_factor, N_ext_kN * lambda_factor, 'r*', markersize=15, label='Предельная точка')
                ax4.grid(True, alpha=0.3)
                ax4.set_xlabel('Mᵧ, кН·м')
                ax4.set_ylabel('N, кН')
                ax4.legend()
                ax4.set_title('Диаграмма взаимодействия N-Mᵧ')
                st.pyplot(fig4)
                
            with tab_3d:
                st.markdown("#### Трехмерная поверхность прочности")
                N_3d, Mx_3d, My_3d = analyzer.generate_3d_surface(ndm_input)
                fig_3d = go.Figure()
                fig_3d.add_trace(go.Mesh3d(
                    x=Mx_3d, y=My_3d, z=N_3d, 
                    alphahull=0, opacity=0.3, color='blue', 
                    contour=dict(show=True, color='black', width=2),
                    name='Поверхность прочности'
                ))
                fig_3d.add_trace(go.Scatter3d(
                    x=[Mx_ext_kNm], y=[My_ext_kNm], z=[N_ext_kN], 
                    mode='markers', 
                    marker=dict(color='red', size=8),
                    name='Рабочая точка'
                ))
                fig_3d.add_trace(go.Scatter3d(
                    x=[0, Mx_ext_kNm * lambda_factor], 
                    y=[0, My_ext_kNm * lambda_factor], 
                    z=[0, N_ext_kN * lambda_factor], 
                    mode='lines+markers', 
                    line=dict(color='red', width=4, dash='dash'),
                    marker=dict(symbol='diamond', size=[0, 12], color='red'),
                    name='Вектор нагружения'
                ))
                fig_3d.update_layout(
                    scene=dict(
                        xaxis_title='Mₓ, кН·м', 
                        yaxis_title='Mᵧ, кН·м', 
                        zaxis_title='N, кН'
                    ), 
                    height=600,
                    margin=dict(l=0, r=0, b=0, t=0)
                )
                st.plotly_chart(fig_3d, use_container_width=True)
              
    except Exception as e:
        st.error(f"❌ Ошибка вычислений: {str(e)}")
        st.exception(e)