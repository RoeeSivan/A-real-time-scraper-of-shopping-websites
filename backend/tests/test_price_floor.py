"""Per-category plausible-price floor.

Backs the validator gate that rejects accessory / installment leaks like
"$9.99 iPhone 16" or "$0.50 GeForce RTX 4070".
"""

from app.price_floor import DEFAULT_FLOOR, floor_for


def test_smartphone_floor():
    assert floor_for("iPhone 16 Pro Max") == 200.0
    assert floor_for("Samsung Galaxy S24") == 200.0
    assert floor_for("Pixel 9") == 200.0


def test_laptop_floor():
    assert floor_for("MacBook Pro 14") == 250.0
    assert floor_for("Lenovo ThinkPad X1") == 250.0


def test_tablet_floor():
    assert floor_for("iPad Pro 11") == 80.0
    assert floor_for("Lenovo Tab P12-2024") == 80.0


def test_headphones_floor():
    assert floor_for("Sony WH-1000XM5") == 30.0
    assert floor_for("AirPods Pro 2") == 30.0


def test_gpu_floor():
    assert floor_for("GeForce RTX 4070") == 150.0


def test_console_floor():
    assert floor_for("PS5 Slim") == 150.0
    assert floor_for("Nintendo Switch OLED") == 150.0


def test_default_floor_for_unrecognised_query():
    assert floor_for("xyzzy gadget") == DEFAULT_FLOOR


def test_floor_is_case_insensitive():
    assert floor_for("IPHONE 16") == 200.0
    assert floor_for("rtx 4070") == 150.0
