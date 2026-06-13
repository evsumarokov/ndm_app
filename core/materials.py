# Файл: core/materials.py
from dataclasses import dataclass

@dataclass
class ConcreteMaterial:
    class_name: str
    Rb: float       # МПа
    Eb: float       # МПа
    eps_b0: float = 0.002
    eps_bu: float = 0.0035
    eps_b1_red: float = 0.0015

@dataclass
class SteelMaterial:
    class_name: str
    Rs: float       # МПа
    Es: float = 200000.0  # МПа
    eps_su: float = 0.025

class MaterialRegistry:
    _concrete_db = {
        "B25": ConcreteMaterial("B25", Rb=14.5, Eb=30000.0),
        "B30": ConcreteMaterial("B30", Rb=17.0, Eb=32500.0),
        "B35": ConcreteMaterial("B35", Rb=19.5, Eb=34500.0),
    }
    
    _steel_db = {
        "A400": SteelMaterial("A400", Rs=355.0),
        "A500": SteelMaterial("A500", Rs=435.0),
    }

    @classmethod
    def get_concrete(cls, class_name: str) -> ConcreteMaterial:
        return cls._concrete_db.get(class_name, cls._concrete_db["B25"])

    @classmethod
    def get_steel(cls, class_name: str) -> SteelMaterial:
        return cls._steel_db.get(class_name, cls._steel_db["A500"])