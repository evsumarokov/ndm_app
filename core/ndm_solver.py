# Файл: core/ndm_solver.py
import numpy as np
from scipy.optimize import root
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from shapely.geometry import Point
from analysis.preprocessor import NDMInput, ConcreteSection

@dataclass
class NDMResult:
    status: str
    eps0: float
    kx: float
    ky: float
    max_eps_b: float
    max_eps_s: float
    concrete_cells: Dict[str, np.ndarray]
    iterations: int
    history: list

class NDMSolver:
    def __init__(self, target_cells: int = 1000):
        self.target_cells = target_cells

    def _rasterize_section(self, section: ConcreteSection) -> Tuple[np.ndarray, ...]:
        poly = section.effective_polygon
        
        if poly.area < 1.0:
            return np.array([]), np.array([]), 0.0, np.array([]), np.array([]), np.array([])
            
        minx, miny, maxx, maxy = poly.bounds
        area = poly.area
        cell_size = max(np.sqrt(area / self.target_cells), 1.0)
        
        x_coords = np.arange(minx + cell_size/2, maxx, cell_size)
        y_coords = np.arange(miny + cell_size/2, maxy, cell_size)
        
        x_c, y_c = [], []
        k_Rb, k_Eb, k_eps_bu = [], [], []

        for x in x_coords:
            for y in y_coords:
                p = Point(x, y)
                if poly.contains(p):
                    x_c.append(x)
                    y_c.append(y)
                    
                    kr, ke, ku = 1.0, 1.0, 1.0
                    for dz in section.degraded_zones:
                        if dz.polygon.contains(p):
                            kr *= dz.k_Rb
                            ke *= dz.k_Eb
                            ku *= dz.k_eps_bu
                            
                    k_Rb.append(kr)
                    k_Eb.append(ke)
                    k_eps_bu.append(ku)
                    
        return (
            np.array(x_c), np.array(y_c), cell_size**2, 
            np.array(k_Rb), np.array(k_Eb), np.array(k_eps_bu)
        )

    def _get_concrete_stress(self, eps_b: np.ndarray, props: Dict[str, float], 
                             k_Rb: np.ndarray, k_Eb: np.ndarray, k_eps_bu: np.ndarray) -> np.ndarray:
        Rb = props['Rb'] * k_Rb
        Eb = props['Eb'] * k_Eb
        eps_b0 = props['eps_b0']
        eps_bu = props['eps_bu'] * k_eps_bu
        eps_b1 = props['eps_b1_red']
        k_desc = props['k_desc']

        sigma = np.zeros_like(eps_b)
        abs_eps = np.abs(eps_b)
        comp = eps_b < 0
        
        m1 = comp & (abs_eps <= eps_b1)
        sigma[m1] = -Eb[m1] * abs_eps[m1]
        
        m2 = comp & (abs_eps > eps_b1) & (abs_eps <= eps_b0)
        sigma_b1 = Eb * eps_b1
        sigma[m2] = -(sigma_b1[m2] + (Rb[m2] - sigma_b1[m2]) * ((abs_eps[m2] - eps_b1) / (eps_b0 - eps_b1)))
        
        m3 = comp & (abs_eps > eps_b0) & (abs_eps <= eps_bu)
        sigma[m3] = -(Rb[m3] - Rb[m3] * k_desc * ((abs_eps[m3] - eps_b0) / (eps_bu[m3] - eps_b0)))

        m4 = comp & (abs_eps > eps_bu)
        sigma_limit = Rb[m4] * (1.0 - k_desc)
        sigma[m4] = -(sigma_limit + 0.05 * Eb[m4] * (abs_eps[m4] - eps_bu[m4]))

        Rbt = props['Rbt'] * k_Rb
        eps_bt0 = Rbt / Eb
        tens = (eps_b > 0) & (eps_b <= eps_bt0)
        sigma[tens] = Eb[tens] * eps_b[tens]
        
        tens_crack = (eps_b > eps_bt0)
        sigma[tens_crack] = 0.001 * Eb[tens_crack] * (eps_b[tens_crack] - eps_bt0[tens_crack])

        return sigma

    def _get_steel_stress(self, eps_s: np.ndarray, props: Dict[str, float]) -> np.ndarray:
        Es = props['Es']
        Rs = props['Rs']
        Rsc = props['Rsc']

        sigma = Es * eps_s
        sigma = np.clip(sigma, -Rsc, Rs)
        
        m_fail = np.abs(eps_s) > props['eps_su']
        if np.any(m_fail):
            sigma[m_fail] += np.sign(eps_s[m_fail]) * 0.01 * Es * (np.abs(eps_s[m_fail]) - props['eps_su'])
        
        return sigma

    def solve(self, data: NDMInput) -> NDMResult:
        x_c, y_c, dA, k_Rb, k_Eb, k_eps_bu = self._rasterize_section(data.section)
        
        if len(x_c) == 0:
            return NDMResult("FAIL", 0, 0, 0, 0, 0, {}, 0, [])
            
        cx, cy = data.section.effective_polygon.centroid.coords[0]

        if data.rebars:
            x_s = np.array([rb.x for rb in data.rebars])
            y_s = np.array([rb.y for rb in data.rebars])
            As = np.array([rb.area_eff for rb in data.rebars])
            psi_bond = np.array([rb.psi_bond for rb in data.rebars])
        else:
            x_s = y_s = As = psi_bond = np.array([])

        history_log = []
        eval_counter = [0]

        def equilibrium_equations_scaled(X_scaled):
            eval_counter[0] += 1
            
            eps0 = X_scaled[0] * 1e-3
            kx = X_scaled[1] * 1e-6
            ky = X_scaled[2] * 1e-6
            
            eps_b = eps0 + kx * (y_c - cy) + ky * (x_c - cx)
            
            if len(As) > 0:
                eps_s = (eps0 + kx * (y_s - cy) + ky * (x_s - cx)) * psi_bond
            else:
                eps_s = np.array([])
            
            sigma_b = self._get_concrete_stress(eps_b, data.concrete_props, k_Rb, k_Eb, k_eps_bu)
            sigma_s = self._get_steel_stress(eps_s, data.steel_props) if len(As) > 0 else np.array([])
            
            N_int = np.sum(sigma_b * dA) + np.sum(sigma_s * As)
            Mx_int = np.sum(sigma_b * dA * (y_c - cy)) + np.sum(sigma_s * As * (y_s - cy))
            My_int = np.sum(sigma_b * dA * (x_c - cx)) + np.sum(sigma_s * As * (x_s - cx))
            
            res_N = (N_int - data.N_ext) / 1000.0
            res_Mx = (Mx_int - data.Mx_ext) / 1000000.0
            res_My = (My_int - data.My_ext) / 1000000.0
            
            if eval_counter[0] % 5 == 0 or eval_counter[0] == 1:
                history_log.append({
                    'Шаг': eval_counter[0],
                    'eps0': eps0, 'kx': kx, 'ky': ky,
                    'Невязка N (кН)': res_N, 'Невязка Mx (кН·м)': res_Mx, 'Невязка My (кН·м)': res_My
                })
            
            return [res_N, res_Mx, res_My]

        Eb_val = data.concrete_props['Eb']
        Es_val = data.steel_props['Es']
        alpha = Es_val / Eb_val

        # ИСПРАВЛЕНО: Правильный подсчет площади сечения
        A_eq = dA * len(x_c) + (np.sum(As * alpha) if len(As) > 0 else 0)
        Ix_eq = np.sum(dA * (y_c - cy)**2) + (np.sum(As * alpha * (y_s - cy)**2) if len(As) > 0 else 0)
        Iy_eq = np.sum(dA * (x_c - cx)**2) + (np.sum(As * alpha * (x_s - cx)**2) if len(As) > 0 else 0)

        eps0_init = data.N_ext / (Eb_val * max(A_eq, 1.0))
        kx_init = data.Mx_ext / (Eb_val * max(Ix_eq, 1.0))
        ky_init = data.My_ext / (Eb_val * max(Iy_eq, 1.0))

        initial_guess_scaled = [eps0_init * 1e3, kx_init * 1e6, ky_init * 1e6]

        solution = root(equilibrium_equations_scaled, initial_guess_scaled, method='lm')
        
        if not solution.success:
            history_log.append({'Шаг': 'СМЕНА МЕТОДА', 'eps0': 0, 'kx': 0, 'ky': 0, 'Невязка N (кН)': 0, 'Невязка Mx (кН·м)': 0, 'Невязка My (кН·м)': 0})
            solution = root(equilibrium_equations_scaled, initial_guess_scaled, method='hybr')

        res_N, res_Mx, res_My = equilibrium_equations_scaled(solution.x)
        
        if abs(res_N) > 1.0 or abs(res_Mx) > 2.0 or abs(res_My) > 2.0:
            return NDMResult("NO_CONVERGENCE", 0, 0, 0, 0, 0, {}, solution.nfev, history_log)

        eps0 = solution.x[0] * 1e-3
        kx = solution.x[1] * 1e-6
        ky = solution.x[2] * 1e-6
        
        eps_b_final = eps0 + kx * (y_c - cy) + ky * (x_c - cx)
        sigma_b_final = self._get_concrete_stress(eps_b_final, data.concrete_props, k_Rb, k_Eb, k_eps_bu)
        eps_s_final = (eps0 + kx * (y_s - cy) + ky * (x_s - cx)) * psi_bond if len(As) > 0 else np.array([0])

        max_comp_b = np.min(eps_b_final)
        max_tens_s = np.max(np.abs(eps_s_final))

        eps_bu_array = data.concrete_props['eps_bu'] * k_eps_bu
        status = "PASS"
        if np.any(eps_b_final < -eps_bu_array) or max_tens_s > data.steel_props['eps_su']:
            status = "FAIL"

        return NDMResult(
            status=status, eps0=eps0, kx=kx, ky=ky,
            max_eps_b=max_comp_b, max_eps_s=max_tens_s,
            concrete_cells={'x': x_c, 'y': y_c, 'sigma': sigma_b_final, 'eps': eps_b_final},
            iterations=solution.nfev,
            history=history_log
        )