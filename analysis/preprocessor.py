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
    calc_mode: str = 'design'
    gamma_b: float = 1.3
    gamma_s: float = 1.15
    k_Rb_global: float = 1.0  
    k_Eb_global: float = 1.0
    k_Rs_global: float = 1.0
    apply_eta_ea: bool = True

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
    ea_x: float = 0.0
    ea_y: float = 0.0
    eta_x: float = 1.0
    eta_y: float = 1.0
    calc_log: Dict[str, List[str]] = field(default_factory=dict)

class Preprocessor:
    @staticmethod
    def process(config: CalcConfig, column_data: Dict[str, Any], geometry_data: List[Dict[str, Any]], rebar_data: List[Dict[str, Any]]) -> NDMInput:
        calc_log = {}
        
        base_poly = None
        spalls, degraded = [], []

        for item in geometry_data:
            coords = item['coords']
            if len(coords) > 2:
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if item['type'] == 'base':
                    base_poly = poly
                elif item['type'] == 'spall':
                    spalls.append(poly)
                elif item['type'] == 'degraded':
                    degraded.append(DegradedZone(
                        polygon=poly, k_Rb=item.get('k_Rb', 1.0), 
                        k_Eb=item.get('k_Eb', 1.0), k_eps_bu=item.get('k_eps_bu', 1.0)
                    ))

        section = ConcreteSection(base_polygon=base_poly, spalls=spalls, degraded_zones=degraded)

        rebars = []
        for rb in rebar_data:
            rebars.append(Rebar(x=rb['x'], y=rb['y'], d_nom=rb['d_nom'], rebar_class=rb['class'], k_area=rb.get('k_area', 0.0), k_bond=rb.get('k_bond', 1.0)))

        conc_class = column_data.get('concrete_class', 'B25')
        steel_class = rebars[0].rebar_class if rebars else 'A500' 

        base_c_props = CONCRETE_DICTIONARY[conc_class].copy()
        s_props = REBAR_DICTIONARY[steel_class].copy()

        base_c_props['Rb'] = (base_c_props['Rb'] / config.gamma_b) * config.k_Rb_global
        base_c_props['Rbt'] = (base_c_props['Rbt'] / config.gamma_b) * config.k_Rb_global
        base_c_props['Eb'] = base_c_props['Eb'] * config.k_Eb_global
        
        s_props['Rs'] = (s_props['Rs'] / config.gamma_s) * config.k_Rs_global
        s_props['Rsc'] = (s_props['Rsc'] / config.gamma_s) * config.k_Rs_global

        calc_log["1. Фактические характеристики материалов (База)"] = [
            f"Бетон {conc_class}: R_b = {base_c_props['Rb']:.2f} МПа (γ_b={config.gamma_b}, k_Rb,global={config.k_Rb_global})",
            f"Сталь {steel_class}: R_s = {s_props['Rs']:.0f} МПа (γ_s={config.gamma_s}, k_Rs,global={config.k_Rs_global})"
        ]

        N_ext = column_data['N_design'] * 1000.0  
        Mx_stat = column_data['Mx_static'] * 1000000.0 
        My_stat = column_data['My_static'] * 1000000.0 

        e_add_x = e_add_y = 0.0
        eta_x = eta_y = 1.0
        
        if config.apply_eta_ea:
            # Габариты описывающего прямоугольника нужны только для эксцентриситета e_a = h/30
            minx, miny, maxx, maxy = section.effective_polygon.bounds
            hx, hy = maxx - minx, maxy - miny
            
            H_mm = column_data.get('H_col', 3.0) * 1000.0
            mu = column_data.get('mu_col', 1.0)
            l0_mm = H_mm * mu

            calc_log["2. Расчетная длина"] = [
                f"Высота H = {H_mm/1000:.2f} м, μ = {mu:.2f} ➔ l₀ = {l0_mm:.1f} мм",
                f"Описывающий габарит (для e_a): hx = {hx:.1f} мм, hy = {hy:.1f} мм"
            ]

            e0_x = abs(My_stat / N_ext) if abs(N_ext) > 1.0 else 0
            e0_y = abs(Mx_stat / N_ext) if abs(N_ext) > 1.0 else 0

            ea_x_norm = max(l0_mm / 600, hx / 30, 10.0) 
            ea_y_norm = max(l0_mm / 600, hy / 30, 10.0) 

            efact_x = abs(column_data.get('delta_x_tilt', 0.0) + column_data.get('delta_x_misalign', 0.0)) + column_data.get('delta_geo', 0.0)
            efact_y = abs(column_data.get('delta_y_tilt', 0.0) + column_data.get('delta_y_misalign', 0.0)) + column_data.get('delta_geo', 0.0)

            e_add_x = max(ea_x_norm, efact_x)
            e_add_y = max(ea_y_norm, efact_y)

            calc_log["3. Эксцентриситеты (СП 63, п. 8.1.7)"] = [
                f"Нормативные: eₐₓ = {ea_x_norm:.1f} мм, eₐᵧ = {ea_y_norm:.1f} мм",
                f"Геодезические: e_fact,x = {efact_x:.1f} мм, e_fact,y = {efact_y:.1f} мм",
                f"Итоговые (max): e_add,x = {e_add_x:.1f} мм, e_add,y = {e_add_y:.1f} мм"
            ]

            # =========================================================================
            # УНИВЕРСАЛЬНЫЙ РАСЧЕТ МОМЕНТОВ ИНЕРЦИИ (По формуле Грина для полигонов)
            # =========================================================================
            def calc_inertia(geom):
                if geom.is_empty: return 0.0, 0.0
                cx, cy = geom.centroid.x, geom.centroid.y
                
                def ring_inertia(ring):
                    x, y = ring.xy
                    Ix, Iy = 0.0, 0.0
                    for i in range(len(x)-1):
                        xi, yi = x[i] - cx, y[i] - cy
                        xip, yip = x[i+1] - cx, y[i+1] - cy
                        a = xi * yip - xip * yi
                        Ix += (yi**2 + yi*yip + yip**2) * a
                        Iy += (xi**2 + xi*xip + xip**2) * a
                    return abs(Ix / 12.0), abs(Iy / 12.0)
                
                Ix_tot, Iy_tot = 0.0, 0.0
                from shapely.geometry import MultiPolygon
                geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
                
                for p in geoms:
                    ix, iy = ring_inertia(p.exterior)
                    Ix_tot += ix; Iy_tot += iy
                    for hole in p.interiors:
                        hix, hiy = ring_inertia(hole)
                        Ix_tot -= hix; Iy_tot -= hiy
                return Ix_tot, Iy_tot

            I_x, I_y = calc_inertia(section.effective_polygon)
            cx, cy = section.effective_polygon.centroid.x, section.effective_polygon.centroid.y

            I_sx = sum(rb.area_eff * (rb.y - cy)**2 for rb in rebars)
            I_sy = sum(rb.area_eff * (rb.x - cx)**2 for rb in rebars)

            D_x = 0.15 * base_c_props['Eb'] * I_x + s_props['Es'] * I_sx
            D_y = 0.15 * base_c_props['Eb'] * I_y + s_props['Es'] * I_sy
            
            N_cr_x = (math.pi**2 * D_x) / (l0_mm**2) if l0_mm > 0 else float('inf')
            N_cr_y = (math.pi**2 * D_y) / (l0_mm**2) if l0_mm > 0 else float('inf')
            
            calc_log["4. Продольный изгиб (Точный анализ жесткости)"] = [
                f"Моменты инерции бетона: Iₓ = {I_x:,.0f} мм⁴, Iᵧ = {I_y:,.0f} мм⁴",
                f"Моменты инерции арматуры: Iₛₓ = {I_sx:,.0f} мм⁴, Iₛᵧ = {I_sy:,.0f} мм⁴",
                f"Жесткость сечения: Dₓ = {D_x:,.0f} Н·мм², Dᵧ = {D_y:,.0f} Н·мм²",
                f"Критические силы: N_cr,x = {N_cr_x/1000:,.1f} кН, N_cr,y = {N_cr_y/1000:,.1f} кН"
            ]

            if N_ext < 0:
                if abs(N_ext) < N_cr_x:
                    eta_x = max(1.0, 1.0 / (1.0 - abs(N_ext)/N_cr_x))
                if abs(N_ext) < N_cr_y:
                    eta_y = max(1.0, 1.0 / (1.0 - abs(N_ext)/N_cr_y))
                
                calc_log["4. Продольный изгиб (Точный анализ жесткости)"].extend([
                    f"Коэфф. продольного изгиба ηₓ = {eta_x:.3f} (относительно оси X)",
                    f"Коэфф. продольного изгиба ηᵧ = {eta_y:.3f} (относительно оси Y)"
                ])
            else:
                calc_log["4. Продольный изгиб (Точный анализ жесткости)"].append("Сжатие отсутствует ➔ ηₓ = 1.0, ηᵧ = 1.0")

        Mx_ext = Mx_stat * eta_x + abs(N_ext) * e_add_y
        My_ext = My_stat * eta_y + abs(N_ext) * e_add_x

        calc_log["5. Итоговые расчетные усилия"] = [
            f"N = {N_ext/1000:,.1f} кН",
            f"Mx = Mₓ·ηₓ + N·e_add,y = {Mx_ext/1000000:,.1f} кН·м",
            f"My = Mᵧ·ηᵧ + N·e_add,x = {My_ext/1000000:,.1f} кН·м"
        ]

        return NDMInput(
            section=section, rebars=rebars, 
            concrete_props=base_c_props, steel_props=s_props, 
            N_ext=N_ext, Mx_ext=Mx_ext, My_ext=My_ext, config=config,
            ea_x=e_add_x, ea_y=e_add_y, eta_x=eta_x, eta_y=eta_y, calc_log=calc_log
        )