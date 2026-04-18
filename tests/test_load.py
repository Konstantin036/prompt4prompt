# tests/test_load.py
from vizualizacija.load import _color_load


def test_color_load_normal():
    assert _color_load(50.0) == "Normalno"


def test_color_load_warning():
    assert _color_load(75.0) == "Upozorenje"


def test_color_load_critical():
    assert _color_load(90.0) == "Kritično"


def test_color_load_boundary_70():
    # exactly 70 → Upozorenje
    assert _color_load(70.0) == "Upozorenje"


def test_color_load_boundary_85():
    # exactly 85 → Kritično
    assert _color_load(85.0) == "Kritično"


def test_color_load_zero():
    assert _color_load(0.0) == "Normalno"
