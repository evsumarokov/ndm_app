# Файл: core/geometry.py
import numpy as np
from shapely.geometry import Polygon
from dataclasses import dataclass

class ConcreteSection:
    def __init__(self, exterior_coords: list):
        """
        Принимает произвольный список координат контура: [(x1,y1), (x2,y2)...]
        """
        self.base_polygon = Polygon(exterior_coords)
        self.effective_polygon = self.base_polygon

    def apply_defect(self, defect_coords: list):
        """
        Вычитает дефект произвольной формы (заданный массивом координат)
        """
        defect_poly = Polygon(defect_coords)
        # Булево вычитание произвольных форм
        self.effective_polygon = self.effective_polygon.difference(defect_poly)

    @property
    def area(self) -> float:
        return self.effective_polygon.area

@dataclass
class Rebar:
    x: float
    y: float
    d: float

    @property
    def area(self) -> float:
        return (np.pi * self.d**2) / 4