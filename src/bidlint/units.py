from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    factor_to_base: float


_ALIASES = {
    "watt": "w",
    "watts": "w",
    "kilowatt": "kw",
    "kilowatts": "kw",
    "megawatt": "mw",
    "megawatts": "mw",
    "pascal": "pa",
    "pascals": "pa",
    "kilopascal": "kpa",
    "kilopascals": "kpa",
    "megapascal": "mpa",
    "megapascals": "mpa",
    "millimeter": "mm",
    "millimeters": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "m3/h": "m³/h",
    "m^3/h": "m³/h",
    "m3/s": "m³/s",
    "m^3/s": "m³/s",
    "l/sec": "l/s",
    "lps": "l/s",
    "l/minute": "l/min",
    "lpm": "l/min",
}

_UNITS = {
    "w": UnitDefinition("power", 1.0),
    "kw": UnitDefinition("power", 1_000.0),
    "mw": UnitDefinition("power", 1_000_000.0),
    "pa": UnitDefinition("pressure", 1.0),
    "kpa": UnitDefinition("pressure", 1_000.0),
    "mpa": UnitDefinition("pressure", 1_000_000.0),
    "bar": UnitDefinition("pressure", 100_000.0),
    "mm": UnitDefinition("length", 0.001),
    "cm": UnitDefinition("length", 0.01),
    "m": UnitDefinition("length", 1.0),
    "l/s": UnitDefinition("flow", 0.001),
    "l/min": UnitDefinition("flow", 0.001 / 60.0),
    "m³/s": UnitDefinition("flow", 1.0),
    "m³/h": UnitDefinition("flow", 1.0 / 3600.0),
}


def canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    canonical = unit.strip().lower().replace("º", "°")
    canonical = canonical.replace(" ", "")
    return _ALIASES.get(canonical, canonical)


def convert_value(value: float, from_unit: str | None, to_unit: str | None) -> float | None:
    source = canonical_unit(from_unit)
    target = canonical_unit(to_unit)

    if source is None and target is None:
        return value
    if source is None or target is None:
        return None
    if source == target:
        return value

    # Celsius is intentionally treated only as a label-equivalence case.
    # Offset temperature conversions (for example °F -> °C) require a
    # different conversion model and are therefore not silently inferred.
    if {source, target} <= {"c", "°c"}:
        return value

    source_def = _UNITS.get(source)
    target_def = _UNITS.get(target)
    if source_def is None or target_def is None:
        return None
    if source_def.dimension != target_def.dimension:
        return None

    base_value = value * source_def.factor_to_base
    return base_value / target_def.factor_to_base
