from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path


TERMINOLOGY_PACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "core": {
        "ip rating": (
            "ingress protection",
            "ingress protection rating",
            "ip code",
            "ip protection rating",
        ),
        "operating temperature": (
            "operating temp",
            "operating-temperature",
        ),
        "noise level": (
            "acoustic noise level",
        ),
    },
    "mechanical": {
        "flow rate": (
            "flowrate",
            "flow-rate",
        ),
        "rotational speed": (
            "rotation speed",
            "rotational-speed",
        ),
        "mass flow rate": (
            "mass flowrate",
            "mass-flow-rate",
        ),
    },
    "electrical": {
        "motor power": (
            "motor rated power",
            "rated motor power",
        ),
    },
    "materials": {
        "construction material": (
            "material of construction",
            "construction material type",
        ),
    },
}


def normalize_parameter(text: str) -> str:
    """Normalize spelling-level variation without asserting semantic equivalence."""
    normalized = text.lower().strip()
    normalized = re.sub(r"[^a-z0-9%°]+", " ", normalized)
    return " ".join(normalized.split())


def builtin_alias_map() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for pack in TERMINOLOGY_PACKS.values():
        for canonical, variants in pack.items():
            canonical_normalized = normalize_parameter(canonical)
            aliases[canonical_normalized] = canonical_normalized
            for variant in variants:
                aliases[normalize_parameter(variant)] = canonical_normalized
    return aliases


def normalize_alias_map(aliases: Mapping[str, str] | None) -> dict[str, str]:
    if aliases is None:
        return {}
    normalized: dict[str, str] = {}
    for alias, canonical in aliases.items():
        if not isinstance(alias, str) or not isinstance(canonical, str):
            raise ValueError("terminology aliases must map strings to strings")
        alias_key = normalize_parameter(alias)
        canonical_value = normalize_parameter(canonical)
        if not alias_key or not canonical_value:
            raise ValueError("terminology aliases cannot contain empty keys or values")
        normalized[alias_key] = canonical_value
    return normalized


def canonical_parameter(text: str, aliases: Mapping[str, str] | None = None) -> str:
    normalized = normalize_parameter(text)
    registry = builtin_alias_map()
    registry.update(normalize_alias_map(aliases))
    return registry.get(normalized, normalized)


def load_alias_file(path: str | Path) -> dict[str, str]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid terminology JSON in {source}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("terminology alias file must contain a JSON object")
    return normalize_alias_map(payload)
