from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    factor_to_base: float


_ALIASES = {
    "percent": "%",
    "percentage": "%",
    "watt": "w",
    "watts": "w",
    "kilowatt": "kw",
    "kilowatts": "kw",
    "megawatt": "mw",
    "megawatts": "mw",
    "volt": "v",
    "volts": "v",
    "millivolt": "mv",
    "millivolts": "mv",
    "kilovolt": "kv",
    "kilovolts": "kv",
    "amp": "a",
    "amps": "a",
    "ampere": "a",
    "amperes": "a",
    "milliamp": "ma",
    "milliamps": "ma",
    "milliampere": "ma",
    "milliamperes": "ma",
    "kiloamp": "ka",
    "kiloamps": "ka",
    "kiloampere": "ka",
    "kiloamperes": "ka",
    "hertz": "hz",
    "kilohertz": "khz",
    "megahertz": "mhz",
    "voltampere": "va",
    "volt-amperes": "va",
    "volt-ampere": "va",
    "voltamperes": "va",
    "kilovoltampere": "kva",
    "kilovolt-amperes": "kva",
    "kilovolt-ampere": "kva",
    "kilovoltamperes": "kva",
    "megavoltampere": "mva",
    "megavolt-amperes": "mva",
    "megavolt-ampere": "mva",
    "megavoltamperes": "mva",
    "pascal": "pa",
    "pascals": "pa",
    "kilopascal": "kpa",
    "kilopascals": "kpa",
    "megapascal": "mpa",
    "megapascals": "mpa",
    "millibar": "mbar",
    "millibars": "mbar",
    "poundspersquareinch": "psi",
    "poundpersquareinch": "psi",
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
    "kilometer": "km",
    "kilometers": "km",
    "kilometre": "km",
    "kilometres": "km",
    "inch": "in",
    "inches": "in",
    "foot": "ft",
    "feet": "ft",
    "gram": "g",
    "grams": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "tonne": "t",
    "tonnes": "t",
    "metrictonne": "t",
    "metrictonnes": "t",
    "newton": "n",
    "newtons": "n",
    "kilonewton": "kn",
    "kilonewtons": "kn",
    "m3/h": "m³/h",
    "m^3/h": "m³/h",
    "m3/s": "m³/s",
    "m^3/s": "m³/s",
    "l/sec": "l/s",
    "lps": "l/s",
    "l/minute": "l/min",
    "lpm": "l/min",
    "c": "°c",
    "degc": "°c",
    "celsius": "°c",
    "degf": "°f",
    "fahrenheit": "°f",
    "kelvin": "k",
    "r/min": "rpm",
    "rev/min": "rpm",
    "rev/minute": "rpm",
    "revolutionsperminute": "rpm",
}

_UNITS = {
    "w": UnitDefinition("power", 1.0),
    "kw": UnitDefinition("power", 1_000.0),
    "mw": UnitDefinition("power", 1_000_000.0),
    "mv": UnitDefinition("voltage", 0.001),
    "v": UnitDefinition("voltage", 1.0),
    "kv": UnitDefinition("voltage", 1_000.0),
    "ma": UnitDefinition("current", 0.001),
    "a": UnitDefinition("current", 1.0),
    "ka": UnitDefinition("current", 1_000.0),
    "hz": UnitDefinition("frequency", 1.0),
    "khz": UnitDefinition("frequency", 1_000.0),
    "mhz": UnitDefinition("frequency", 1_000_000.0),
    "va": UnitDefinition("apparent_power", 1.0),
    "kva": UnitDefinition("apparent_power", 1_000.0),
    "mva": UnitDefinition("apparent_power", 1_000_000.0),
    "pa": UnitDefinition("pressure", 1.0),
    "kpa": UnitDefinition("pressure", 1_000.0),
    "mpa": UnitDefinition("pressure", 1_000_000.0),
    "mbar": UnitDefinition("pressure", 100.0),
    "bar": UnitDefinition("pressure", 100_000.0),
    "psi": UnitDefinition("pressure", 6_894.757293168),
    "mm": UnitDefinition("length", 0.001),
    "cm": UnitDefinition("length", 0.01),
    "m": UnitDefinition("length", 1.0),
    "km": UnitDefinition("length", 1_000.0),
    "in": UnitDefinition("length", 0.0254),
    "ft": UnitDefinition("length", 0.3048),
    "g": UnitDefinition("mass", 0.001),
    "kg": UnitDefinition("mass", 1.0),
    "t": UnitDefinition("mass", 1_000.0),
    "n": UnitDefinition("force", 1.0),
    "kn": UnitDefinition("force", 1_000.0),
    "l/s": UnitDefinition("flow", 0.001),
    "l/min": UnitDefinition("flow", 0.001 / 60.0),
    "m³/s": UnitDefinition("flow", 1.0),
    "m³/h": UnitDefinition("flow", 1.0 / 3600.0),
}

_TEMPERATURE_UNITS = {"°c", "°f", "k"}


def canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    canonical = unit.strip().lower().replace("º", "°")
    canonical = canonical.replace(" ", "")
    return _ALIASES.get(canonical, canonical)


def _temperature_to_celsius(value: float, unit: str) -> float:
    if unit == "°c":
        return value
    if unit == "°f":
        return (value - 32.0) * 5.0 / 9.0
    return value - 273.15


def _temperature_from_celsius(value: float, unit: str) -> float:
    if unit == "°c":
        return value
    if unit == "°f":
        return value * 9.0 / 5.0 + 32.0
    return value + 273.15


def convert_value(value: float, from_unit: str | None, to_unit: str | None) -> float | None:
    source = canonical_unit(from_unit)
    target = canonical_unit(to_unit)

    if source is None and target is None:
        return value
    if source is None or target is None:
        return None
    if source == target:
        return value

    if source in _TEMPERATURE_UNITS or target in _TEMPERATURE_UNITS:
        if source not in _TEMPERATURE_UNITS or target not in _TEMPERATURE_UNITS:
            return None
        celsius = _temperature_to_celsius(value, source)
        return _temperature_from_celsius(celsius, target)

    source_def = _UNITS.get(source)
    target_def = _UNITS.get(target)
    if source_def is None or target_def is None:
        return None
    if source_def.dimension != target_def.dimension:
        return None

    base_value = value * source_def.factor_to_base
    return base_value / target_def.factor_to_base
