# Файл: analysis/pm_surface.py
import numpy as np
from scipy.spatial import ConvexHull
from core.ndm_solver import NDMSolver
from analysis.preprocessor import NDMInput

class CapacityAnalyzer:
    def __init__(self, solver: NDMSolver):
        self.solver = solver

    def find_lambda(self, data: NDMInput, tol: float = 0.01):
        log = []
        log.append(f"▶ СТАРТ: Поиск запаса λ для нагрузки N={data.N_ext/1000:.1f} кН, Mx={data.Mx_ext/1e6:.1f} кН·м, My={data.My_ext/1e6:.1f} кН·м")
        
        if abs(data.N_ext) < 1.0 and abs(data.Mx_ext) < 1.0 and abs(data.My_ext) < 1.0:
            log.append("ℹ️ Нагрузка нулевая. Запас бесконечен.")
            return 999.0, log

        lambda_min = 0.0
        lambda_max = 5.0

        def check_multiplier(l_factor):
            test_data = NDMInput(
                section=data.section, rebars=data.rebars,
                concrete_props=data.concrete_props, steel_props=data.steel_props,
                N_ext=data.N_ext * l_factor, Mx_ext=data.Mx_ext * l_factor, My_ext=data.My_ext * l_factor,
                config=data.config
            )
            res = self.solver.solve(test_data)
            return res.status == "PASS"

        while check_multiplier(lambda_max):
            log.append(f"Грубый поиск: λ={lambda_max:.1f} -> СЕЧЕНИЕ ДЕРЖИТ (Удваиваем границу)")
            lambda_max *= 2.0
            if lambda_max > 100.0: 
                log.append("⚠️ Достигнут предел алгоритма (λ > 100).")
                return 100.0, log
        log.append(f"Грубый поиск: λ={lambda_max:.1f} -> РАЗРУШЕНИЕ (Верхняя граница найдена)")

        log.append("▶ СТАРТ УТОЧНЕНИЯ: Метод половинного деления")
        for i in range(30):
            mid = (lambda_min + lambda_max) / 2.0
            if check_multiplier(mid):
                lambda_min = mid
                log.append(f"Итерация {i+1}: λ={mid:.3f} -> УСПЕХ (Поднимаем нижний порог)")
            else:
                lambda_max = mid
                log.append(f"Итерация {i+1}: λ={mid:.3f} -> РАЗРУШЕНИЕ (Опускаем верхний порог)")
                
            if (lambda_max - lambda_min) < tol:
                log.append(f"▶ ФИНИШ: Точность достигнута. Итоговый λ = {lambda_min:.3f}")
                break
                
        return lambda_min, log

    def generate_nmx_curve(self, data: NDMInput, points: int = 150):
        x_c, y_c, dA, k_Rb, k_Eb, k_eps_bu = self.solver._rasterize_section(data.section)
        cx, cy = data.section.effective_polygon.centroid.coords[0]
        
        if data.rebars:
            y_s = np.array([rb.y for rb in data.rebars])
            As = np.array([rb.area_eff for rb in data.rebars])
            psi_bond = np.array([rb.psi_bond for rb in data.rebars])
            min_ys, max_ys = np.min(y_s), np.max(y_s)
        else:
            min_ys, max_ys = np.min(y_c), np.max(y_c)
            y_s = As = psi_bond = np.array([])
            
        min_y, max_y = np.min(y_c), np.max(y_c)
        eps_bu, eps_su = data.concrete_props['eps_bu'], data.steel_props['eps_su']
        N_points, M_points = [], []
        
        def add_state(y1, y2, eps1, eps2):
            if abs(y1 - y2) < 1e-6: return
            kx = (eps1 - eps2) / (y1 - y2)
            eps0 = eps1 - kx * (y1 - cy)
            
            eps_b = eps0 + kx * (y_c - cy)
            if len(As) > 0:
                eps_s = (eps0 + kx * (y_s - cy)) * psi_bond
            else:
                eps_s = np.array([])
            
            sigma_b = self.solver._get_concrete_stress(eps_b, data.concrete_props, k_Rb, k_Eb, k_eps_bu)
            sigma_s = self.solver._get_steel_stress(eps_s, data.steel_props) if len(As) > 0 else np.array([])
            
            N_points.append((np.sum(sigma_b * dA) + np.sum(sigma_s * As)) / 1000.0)
            M_points.append((np.sum(sigma_b * dA * (y_c - cy)) + np.sum(sigma_s * As * (y_s - cy))) / 1000000.0)

        for es in np.linspace(-eps_bu, eps_su, points): add_state(max_y, min_ys, -eps_bu, es)
        for eb in np.linspace(-eps_bu, eps_su, points): add_state(max_y, min_ys, eb, eps_su)
        for es in np.linspace(-eps_bu, eps_su, points): add_state(min_y, max_ys, -eps_bu, es)
        for eb in np.linspace(-eps_bu, eps_su, points): add_state(min_y, max_ys, eb, eps_su)

        points_2d = np.column_stack((M_points, N_points))
        hull = ConvexHull(points_2d)
        hull_points = points_2d[hull.vertices]
        hull_points = np.vstack((hull_points, hull_points[0]))
        return hull_points[:, 1], hull_points[:, 0]

    def generate_nmy_curve(self, data: NDMInput, points: int = 150):
        x_c, y_c, dA, k_Rb, k_Eb, k_eps_bu = self.solver._rasterize_section(data.section)
        cx, cy = data.section.effective_polygon.centroid.coords[0]
        
        if data.rebars:
            x_s = np.array([rb.x for rb in data.rebars])
            As = np.array([rb.area_eff for rb in data.rebars])
            psi_bond = np.array([rb.psi_bond for rb in data.rebars])
            min_xs, max_xs = np.min(x_s), np.max(x_s)
        else:
            min_xs, max_xs = np.min(x_c), np.max(x_c)
            x_s = As = psi_bond = np.array([])
            
        min_x, max_x = np.min(x_c), np.max(x_c)
        eps_bu, eps_su = data.concrete_props['eps_bu'], data.steel_props['eps_su']
        N_points, M_points = [], []
        
        def add_state(x1, x2, eps1, eps2):
            if abs(x1 - x2) < 1e-6: return
            ky = (eps1 - eps2) / (x1 - x2)
            eps0 = eps1 - ky * (x1 - cx)
            
            eps_b = eps0 + ky * (x_c - cx)
            if len(As) > 0:
                eps_s = (eps0 + ky * (x_s - cx)) * psi_bond
            else:
                eps_s = np.array([])
            
            sigma_b = self.solver._get_concrete_stress(eps_b, data.concrete_props, k_Rb, k_Eb, k_eps_bu)
            sigma_s = self.solver._get_steel_stress(eps_s, data.steel_props) if len(As) > 0 else np.array([])
            
            N_points.append((np.sum(sigma_b * dA) + np.sum(sigma_s * As)) / 1000.0)
            M_points.append((np.sum(sigma_b * dA * (x_c - cx)) + np.sum(sigma_s * As * (x_s - cx))) / 1000000.0)

        for es in np.linspace(-eps_bu, eps_su, points): add_state(max_x, min_xs, -eps_bu, es)
        for eb in np.linspace(-eps_bu, eps_su, points): add_state(max_x, min_xs, eb, eps_su)
        for es in np.linspace(-eps_bu, eps_su, points): add_state(min_x, max_xs, -eps_bu, es)
        for eb in np.linspace(-eps_bu, eps_su, points): add_state(min_x, max_xs, eb, eps_su)

        points_2d = np.column_stack((M_points, N_points))
        hull = ConvexHull(points_2d)
        hull_points = points_2d[hull.vertices]
        hull_points = np.vstack((hull_points, hull_points[0]))
        return hull_points[:, 1], hull_points[:, 0]

    def generate_3d_surface(self, data: NDMInput, angle_steps: int = 36, points: int = 40):
        x_c_orig, y_c_orig, dA, k_Rb, k_Eb, k_eps_bu = self.solver._rasterize_section(data.section)
        cx, cy = data.section.effective_polygon.centroid.coords[0]
        
        if data.rebars:
            x_s_orig = np.array([rb.x for rb in data.rebars])
            y_s_orig = np.array([rb.y for rb in data.rebars])
            As = np.array([rb.area_eff for rb in data.rebars])
            psi_bond = np.array([rb.psi_bond for rb in data.rebars])
        else:
            x_s_orig = y_s_orig = As = psi_bond = np.array([])
            
        eps_bu, eps_su = data.concrete_props['eps_bu'], data.steel_props['eps_su']
        N_all, Mx_all, My_all = [], [], []

        for theta in np.linspace(0, 2 * np.pi, angle_steps, endpoint=False):
            cos_t, sin_t = np.cos(theta), np.sin(theta)
            
            v_c = -(x_c_orig - cx) * sin_t + (y_c_orig - cy) * cos_t
            if len(As) > 0:
                v_s = -(x_s_orig - cx) * sin_t + (y_s_orig - cy) * cos_t
            else:
                v_s = np.array([])
            
            max_v, min_v = np.max(v_c), np.min(v_c)
            max_vs = np.max(v_s) if len(As) > 0 else max_v
            min_vs = np.min(v_s) if len(As) > 0 else min_v

            def add_state_3d(v1, v2, eps1, eps2):
                if abs(v1 - v2) < 1e-6: return
                kv = (eps1 - eps2) / (v1 - v2)
                eps0 = eps1 - kv * v1
                
                eps_b = eps0 + kv * v_c
                if len(As) > 0:
                    eps_s = (eps0 + kv * v_s) * psi_bond
                else:
                    eps_s = np.array([])
                
                sigma_b = self.solver._get_concrete_stress(eps_b, data.concrete_props, k_Rb, k_Eb, k_eps_bu)
                sigma_s = self.solver._get_steel_stress(eps_s, data.steel_props) if len(As) > 0 else np.array([])
                
                N_all.append((np.sum(sigma_b * dA) + np.sum(sigma_s * As)) / 1000.0)
                Mx_all.append((np.sum(sigma_b * dA * (y_c_orig - cy)) + np.sum(sigma_s * As * (y_s_orig - cy))) / 1000000.0)
                My_all.append((np.sum(sigma_b * dA * (x_c_orig - cx)) + np.sum(sigma_s * As * (x_s_orig - cx))) / 1000000.0)

            for es in np.linspace(-eps_bu, eps_su, points): add_state_3d(max_v, min_vs, -eps_bu, es)
            for eb in np.linspace(-eps_bu, eps_su, points): add_state_3d(max_v, min_vs, eb, eps_su)
            for es in np.linspace(-eps_bu, eps_su, points): add_state_3d(min_v, max_vs, -eps_bu, es)
            for eb in np.linspace(-eps_bu, eps_su, points): add_state_3d(min_v, max_vs, eb, eps_su)

        return np.array(N_all), np.array(Mx_all), np.array(My_all)