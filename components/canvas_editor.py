# Файл: components/canvas_editor.py
import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas

def _generate_fabric_json(df_concrete, df_rebars, canvas_size):
    """Конвертирует таблицы координат в JSON-объекты для отрисовки на холсте"""
    objects = []
    
    if not df_concrete.empty and len(df_concrete) >= 3:
        path = []
        for i, row in df_concrete.iterrows():
            cmd = "M" if i == 0 else "L"
            path.append([cmd, float(row['x']), float(canvas_size - row['y'])])
        path.append(["z"]) # Замыкаем полигон
        
        objects.append({
            "type": "path", "version": "4.4.0",
            "originX": "left", "originY": "top",
            "left": 0, "top": 0, "path": path,
            "fill": "rgba(30, 136, 229, 0.2)",
            "stroke": "#1E88E5", "strokeWidth": 2,
            "selectable": True # Разрешаем выделение для удаления
        })
        
    if not df_rebars.empty:
        for _, row in df_rebars.iterrows():
            objects.append({
                "type": "circle", "version": "4.4.0",
                "originX": "center", "originY": "center",
                "left": float(row['x']), "top": float(canvas_size - row['y']),
                "radius": 5, "fill": "rgba(229, 57, 53, 1)",
                "selectable": True # Разрешаем выделение для удаления
            })
            
    return {"version": "4.4.0", "objects": objects}

def render_cad_canvas(init_df_c, init_df_r, canvas_key=0, key_prefix="cad", grid_size=20, canvas_size=400):
    st.markdown('<p class="panel-title">📐 Векторный холст-оцифровщик</p>', unsafe_allow_html=True)
    
    # CSS-сетка для Iframe
    st.markdown(f"""
        <style>
        iframe[title="streamlit_drawable_canvas.st_canvas"] {{
            background-color: #FAFAFA !important;
            background-size: {grid_size}px {grid_size}px !important;
            background-image: linear-gradient(to right, #EBEBEB 1px, transparent 1px), linear-gradient(to bottom, #EBEBEB 1px, transparent 1px) !important;
            border: 1px solid #E0E0E0; border-radius: 4px;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    c_tool1, c_tool2 = st.columns([3, 1])
    with c_tool1:
        drawing_mode = st.radio(
            "Режим работы:",
            ("polygon", "point", "transform"),
            format_func=lambda x: {"polygon": "🟩 Контур", "point": "🔴 Арматура", "transform": "🖱️ Выделить/Удалить"}[x],
            horizontal=True, key=f"{key_prefix}_tool_{canvas_key}"
        )
    with c_tool2:
        if st.button("🗑️ Сбросить холст", key=f"{key_prefix}_clear", use_container_width=True):
            st.session_state.canvas_concrete_df = pd.DataFrame(columns=["x", "y"])
            st.session_state.canvas_rebar_df = pd.DataFrame(columns=["x", "y", "d_nom", "class"])
            st.session_state.canvas_key += 1
            st.rerun()

    # Генерируем геометрию из таблиц
    initial_drawing = _generate_fabric_json(init_df_c, init_df_r, canvas_size)

    # Вызов холста с динамическим ключом для принудительной перерисовки
    canvas_result = st_canvas(
        fill_color="rgba(30, 136, 229, 0.2)" if drawing_mode == "polygon" else "rgba(229, 57, 53, 1)",
        stroke_width=2 if drawing_mode == "polygon" else 0,
        stroke_color="#1E88E5" if drawing_mode == "polygon" else "#E53935",
        background_color="rgba(0,0,0,0)", 
        initial_drawing=initial_drawing, 
        update_streamlit=True,
        height=canvas_size, width=canvas_size,
        drawing_mode="polygon" if drawing_mode == "polygon" else ("point" if drawing_mode == "point" else "transform"),
        point_display_radius=5 if drawing_mode == 'point' else 0,
        display_toolbar=True,
        key=f"{key_prefix}_canvas_{canvas_key}",
    )
    
    # Парсинг текущего состояния холста обратно в координаты
    concrete_coords, rebars = [], []
    if canvas_result.json_data is not None:
        for obj in canvas_result.json_data.get("objects", []):
            if obj["type"] == "path": 
                coords = []
                for step in obj["path"]:
                    if step[0] in ['M', 'L']:
                        # Учитываем возможное смещение объекта (left/top) при перетаскивании
                        x = step[1] + (obj.get("left", 0) if obj.get("left") else 0)
                        y = step[2] + (obj.get("top", 0) if obj.get("top") else 0)
                        coords.append({"x": int(round(x / grid_size) * grid_size), "y": int(canvas_size - round(y / grid_size) * grid_size)})
                if coords and len(coords) > 1 and coords[0] == coords[-1]: coords.pop()
                concrete_coords = coords
            elif obj["type"] == "circle":
                rebars.append({
                    "x": int(round(obj["left"] / grid_size) * grid_size), 
                    "y": int(canvas_size - round(obj["top"] / grid_size) * grid_size)
                })
                
    df_concrete = pd.DataFrame(concrete_coords) if concrete_coords else pd.DataFrame(columns=["x", "y"])
    df_rebars = pd.DataFrame(rebars) if rebars else pd.DataFrame(columns=["x", "y"])
    return df_concrete, df_rebars