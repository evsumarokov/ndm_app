# Файл: analysis/preprocessor.py
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any
from shapely.geometry import Polygon
from shapely.ops import unary_union

CONCRETE_DICTIONARY = {
    'B15': {'Rb': 8.5,  'Rbt': 0.75, 'Eb': 24000, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B20': {'Rb': 11.5, 'Rbt': 0.90, 'Eb': 27500, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B25': {'Rb': 14.5, 'Rbt': 1.05, 'Eb': 30000, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B30': {'Rb': 17.0, 'Rbt': 1.15, 'Eb': 32500, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B35': {'Rb': 19.5, 'Rbt': 1.30, 'Eb': 34500, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B40': {'Rb': 22.0, 'Rbt': 1.40, 'Eb': 36000, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B50': {'Rb': 27.5, 'Rbt': 1.60, 'Eb': 39000, 'eps_b0': 0.002, 'eps_bu': 0.0035, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
    'B60': {'Rb': 33.0, 'Rbt': 1.80, 'Eb': 39500, 'eps_b0': 0.002, 'eps_bu': 0.0033, 'eps_b1_red': 0.0015, 'k_desc': 0.15},
}

REBAR_DICTIONARY = {
    'A240': {'Rs': 215, 'Rsc': 215, 'Es': 200000, 'eps_su': 0.025},
    'A400': {'Rs': 355, 'Rsc': 355, 'Es': 200000, 'eps_su': 0.025},
    'A500': {'Rs': 435, 'Rsc': 400, 'Es': 200000, 'eps_su': 0.025},
}

@dataclass
class CalcConfig:
    gamma_b: float = 1.3
    gamma_s: float = 1.15
    calc_mode: str = 'design'
    apply_eta_ea: bool = True  # Тумблер для включения/выключения нормативных эффектов

@dataclass
class DegradedZone:
    polygon: Polygon
    k_Rb: float
    k_Eb: float
    k_eps_bu: float

@dataclass
class Rebar:
    x: float
    y: float
    d_nom: float
    rebar_class: str
    k_area: float
    k_bond: float
    area_eff: float = field(init=False)
    psi_bond: float = field(init=False)

    def __post_init__(self):
        area_nom = (math.pi * self.d_nom**2) / 4.0
        self.area_eff = area_nom * (1.0 - self.k_area)
        self.psi_bond = self.k_bond

@dataclass
class ConcreteSection:
    base_polygon: Polygon
    spalls: List[Polygon] = field(default_factory=list)
    degraded_zones: List[DegradedZone] = field(default_factory=list)
    effective_polygon: Polygon = field(init=False)

    def __post_init__(self):
        if not self.spalls:
            self.effective_polygon = self.base_polygon
        else:
            union_spalls = unary_union(self.spalls)
            self.effective_polygon = self.base_polygon.difference(union_spalls)

@dataclass
class NDMInput:
    section: ConcreteSection
    rebars: List[Rebar]
    concrete_props: Dict[str, float]
    steel_props: Dict[str, float]
    N_ext: float  
    Mx_ext: float 
    My_ext: float 
    config: CalcConfig
    # Метрология для вывода в интерфейс
    ea_x: float = 0.0
    ea_y: float = 0.0
    eta: float = 1.0

class Preprocessor:
    @staticmethod
    def process(config: CalcConfig, column_data: Dict[str, Any], geometry_data: List[Dict[str, Any]], rebar_data: List[Dict[str, Any]]) -> NDMInput:
        base_poly = None
        spalls, degraded = [], []

        for item in geometry_data:
            # Преобразуем координаты, обеспечивая замыкание полигона
            coords = item['coords']
            if len(coords) > 2:
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0) # Лечим самопересечения
                
                if item['type'] == 'base':
                    base_poly = poly
                elif item['type'] == 'spall':
                    spalls.append(poly)
                elif item['type'] == 'degraded':
                    degraded.append(DegradedZone(
                        polygon=poly, k_Rb=item.get('k_Rb', 1.0), k_Eb=item.get('k_Eb', 1.0), k_eps_bu=item.get('k_eps_bu', 1.0)
                    ))

        section = ConcreteSection(base_polygon=base_poly, spalls=spalls, degraded_zones=degraded)

        rebars = []
        for rb in rebar_data:
            rebars.append(Rebar(
                x=rb['x'], y=rb['y'], d_nom=rb['d_nom'], rebar_class=rb['class'],
                k_area=rb.get('k_area', 0.0), k_bond=rb.get('k_bond', 1.0)
            ))

        conc_class = column_data.get('concrete_class', 'B25')
        steel_class = rebars[0].rebar_class if rebars else 'A500' 

        base_c_props = CONCRETE_DICTIONARY[conc_class].copy()
        s_props = REBAR_DICTIONARY[steel_class].copy()

        base_c_props['Rb'] /= config.gamma_b
        base_c_props['Rbt'] /= config.gamma_b
        s_props['Rs'] /= config.gamma_s
        s_props['Rsc'] /= config.gamma_s

        N_ext = column_data['N_design'] * 1000.0  
        Mx_stat = column_data['Mx_static'] * 1000000.0 
        My_stat = column_data['My_static'] * 1000000.0 

        # Вычисление эксцентриситетов и продольного изгиба
        e_add_x = e_add_y = 0.0
        eta = 1.0
        
        if config.apply_eta_ea:
            minx, miny, maxx, maxy = section.effective_polygon.bounds
            hx, hy = maxx - minx, maxy - miny
            l0_mm = column_data['length_l0'] * 1000.0

            # Случайный эксцентриситет
            ea_x_norm = max(l0_mm / 600, hx / 30, 10.0) 
            ea_y_norm = max(l0_mm / 600, hy / 30, 10.0) 

            # Фактический (геодезический) эксцентриситет
            efact_x = abs(column_data.get('delta_x_tilt', 0.0) + column_data.get('delta_x_misalign', 0.0)) + column_data.get('delta_geo', 0.0)
            efact_y = abs(column_data.get('delta_y_tilt', 0.0) + column_data.get('delta_y_misalign', 0.0)) + column_data.get('delta_geo', 0.0)

            e_add_x = max(ea_x_norm, efact_x)
            e_add_y = max(ea_y_norm, efact_y)

            # Оценка коэффициента продольного изгиба eta (Упрощенно по Эйлеру для отображения гибкости)
            # D = 0.15 * Eb * I + Es * Is
            I_x = (hx * hy**3) / 12.0
            I_s = sum(rb.area_eff * (rb.y - (miny+hy/2))**2 for rb in rebars)
            D = 0.15 * base_c_props['Eb'] * I_x + s_props['Es'] * I_s
            N_cr = (math.pi**2 * D) / (l0_mm**2)
            
            if N_ext < 0 and abs(N_ext) < N_cr: # Сжатие
                eta = 1.0 / (1.0 - abs(N_ext)/N_cr)
                eta = max(1.0, eta)

        Mx_ext = Mx_stat * eta + abs(N_ext) * e_add_y
        My_ext = My_stat * eta + abs(N_ext) * e_add_x

        return NDMInput(
            section=section, rebars=rebars, 
            concrete_props=base_c_props, steel_props=s_props, 
            N_ext=N_ext, Mx_ext=Mx_ext, My_ext=My_ext, config=config,
            ea_x=e_add_x, ea_y=e_add_y, eta=eta
        )