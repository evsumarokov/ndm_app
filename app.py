# Файл: app.py
import streamlit as st
import pandas as pd

# ============================================================================
# 📄 НАСТРОЙКИ СТРАНИЦЫ И СТИЛИСПЕЦИФИКАЦИЯ (СТРОГАЯ ВЕРСТКА)
# ============================================================================
st.set_page_config(layout="wide", page_title="Scan-to-NDM: Аналитический комплекс")

# Жесткое ограничение размеров графиков и стилизация панелей
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #1E88E5; margin-bottom: 0.5rem;}
    .step-header {font-size: 1.4rem; font-weight: 700; color: #2E7D32; margin-bottom: 1rem; border-bottom: 2px solid #2E7D32; padding-bottom: 0.5rem;}
    .panel-title {font-size: 1.1rem; font-weight: 600; color: #424242; margin-bottom: 0.8rem; padding-bottom: 0.3rem; border-bottom: 1px dashed #ccc;}
    .success-box {background-color: #E8F5E9; border-left: 5px solid #43A047; padding: 1rem; margin: 0.5rem 0; border-radius: 4px;}
    .warning-box {background-color: #FFF3E0; border-left: 5px solid #FB8C00; padding: 1rem; margin: 0.5rem 0; border-radius: 4px;}
    .error-box {background-color: #FFEBEE; border-left: 5px solid #E53935; padding: 1rem; margin: 0.5rem 0; border-radius: 4px;}
    
    /* Ограничительный контейнер для графиков, чтобы они не скакали по высоте */
    .stPlotlyChart { max-height: 450px !important; }
    div[data-testid="stForm"] { border: 1px solid #E0E0E0; border-radius: 6px; padding: 1rem; }
    </style>
""", unsafe_allow_html=True)

# Верхняя командная строка с глобальным Live-тумблером
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown('<p class="main-header">🏗️ Scan-to-NDM: Инженерный CAD-комплекс</p>', unsafe_allow_html=True)
with col_head2:
    st.session_state.auto_calc = st.toggle(
        "⚡ Live-режим (Авторасчет)", 
        value=True, 
        help="Мгновенный перерасчет прочности по НДМ при изменении любых параметров или геометрии на холсте"
    )

# ============================================================================
# 💾 ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ (SESSION STATE STORAGE)
# ============================================================================
# 1. Базовые массивы геометрии (Хранят данные для синхронизации Холст <-> Таблица)
if 'canvas_concrete_df' not in st.session_state: 
    st.session_state.canvas_concrete_df = pd.DataFrame([{"x": 0, "y": 0}, {"x": 400, "y": 0}, {"x": 400, "y": 400}, {"x": 0, "y": 400}])
if 'canvas_rebar_df' not in st.session_state:
    st.session_state.canvas_rebar_df = pd.DataFrame([
        {"x": 55, "y": 55, "d_nom": 36, "class": "A500"},
        {"x": 345, "y": 55, "d_nom": 36, "class": "A500"},
        {"x": 55, "y": 345, "d_nom": 36, "class": "A500"},
        {"x": 345, "y": 345, "d_nom": 36, "class": "A500"},
    ])

# 2. Буферные проектные данные для передачи между шагами
if 'raw_config' not in st.session_state: st.session_state.raw_config = None
if 'raw_col_data' not in st.session_state: st.session_state.raw_col_data = None
if 'raw_geom' not in st.session_state: st.session_state.raw_geom = None
if 'raw_rebars' not in st.session_state: st.session_state.raw_rebars = None

# 3. Кэш результатов расчетов НДМ и анализа поверхностей
if 'step1_input' not in st.session_state: st.session_state.step1_input = None
if 'step1_result' not in st.session_state: st.session_state.step1_result = None
if 'lambda_1' not in st.session_state: st.session_state.lambda_1 = None
if 'analyzer' not in st.session_state: st.session_state.analyzer = None

if 'step2_col_data' not in st.session_state: st.session_state.step2_col_data = None
if 'step2_input' not in st.session_state: st.session_state.step2_input = None
if 'step2_result' not in st.session_state: st.session_state.step2_result = None
if 'lambda_2' not in st.session_state: st.session_state.lambda_2 = None

if 'step3_input' not in st.session_state: st.session_state.step3_input = None
if 'step3_result' not in st.session_state: st.session_state.step3_result = None
if 'lambda_3' not in st.session_state: st.session_state.lambda_3 = None
if 'defects' not in st.session_state: st.session_state.defects = []

# ============================================================================
# 🗂️ РАСПРЕДЕЛЕНИЕ ПО ШАГАМ (МАРШРУТИЗАЦИЯ)
# ============================================================================
try:
    from ui_step1 import render_step1
    from ui_step2 import render_step2
    from ui_step3 import render_step3
    
    tab1, tab2, tab3 = st.tabs([
        "🏗️ ШАГ 1: ПРОЕКТ (Эталон)", 
        "📐 ШАГ 2: МОНТАЖ (Геодезия)", 
        "🏚️ ШАГ 3: ЭКСПЛУАТАЦИЯ (Дефекты)"
    ])
    
    with tab1: render_step1()
    with tab2: render_step2()
    with tab3: render_step3()
    
except ModuleNotFoundError as e:
    st.error(f"Ошибка инициализации модулей UI: {e}. Убедитесь, что ui_step1.py, ui_step2.py и ui_step3.py находятся в корневой директории приложения.")