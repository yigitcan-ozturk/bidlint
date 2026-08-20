from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable

from .models import SourceRef, VendorFact

_NUMERIC_WITH_UNIT = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z0-9%°/^\-²³]+)\s*$")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _load_ifc_api() -> tuple[Any, Callable[..., dict[str, dict[str, Any]]]]:
    try:
        import ifcopenshell
        from ifcopenshell.util.element import get_psets
    except ImportError as exc:
        raise RuntimeError(
            "IFC support requires the optional dependency; install bidlint with the 'ifc' extra"
        ) from exc
    return ifcopenshell, get_psets


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace("º", "°")


def _parameter_name(name: Any) -> str:
    text = str(name).strip().replace("_", " ").replace("-", " ")
    text = _CAMEL_BOUNDARY.sub(" ", text)
    return " ".join(text.lower().split())


def _scalar_value(value: Any) -> tuple[str, float | None, str | None] | None:
    """Convert only scalar IFC property values without fabricating engineering units."""
    if value is None:
        return None
    if isinstance(value, bool):
        return ("true" if value else "false"), None, None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        raw = f"{numeric:g}"
        return raw, numeric, None
    if not isinstance(value, str):
        return None

    raw = " ".join(value.split()).strip()
    if not raw:
        return None
    match = _NUMERIC_WITH_UNIT.fullmatch(raw)
    if match:
        numeric = float(match.group(1))
        if math.isfinite(numeric):
            return raw, numeric, _normalize_unit(match.group(2))
    return raw, None, None


def _entity_label(entity: Any) -> tuple[str, str | None, str | None]:
    ifc_class = str(entity.is_a())
    global_id = getattr(entity, "GlobalId", None)
    name = getattr(entity, "Name", None)
    return ifc_class, str(global_id) if global_id else None, str(name) if name else None


def _source_section(entity: Any, pset_name: str) -> str:
    ifc_class, global_id, name = _entity_label(entity)
    identity = global_id or name or "unidentified"
    return f"{ifc_class}:{identity}/{pset_name}"


def _select_entities(model: Any, *, ifc_class: str | None, global_id: str | None) -> list[Any]:
    if not ifc_class and not global_id:
        raise ValueError("IFC extraction requires --ifc-class or --ifc-guid to scope the vendor element")

    if global_id:
        try:
            entity = model.by_guid(global_id)
        except RuntimeError as exc:
            raise ValueError(f"IFC GlobalId not found: {global_id}") from exc
        if ifc_class and not entity.is_a(ifc_class):
            raise ValueError(f"IFC GlobalId {global_id} is {entity.is_a()}, not {ifc_class}")
        return [entity]

    try:
        entities = list(model.by_type(ifc_class))
    except RuntimeError as exc:
        raise ValueError(f"IFC class is not available in this schema: {ifc_class}") from exc
    if not entities:
        raise ValueError(f"no IFC elements found for class {ifc_class}")
    if len(entities) > 1:
        raise ValueError(
            f"IFC class {ifc_class} matched {len(entities)} elements; use --ifc-guid to select one vendor element"
        )
    return entities


def parse_ifc_facts(
    path: str | Path,
    *,
    ifc_class: str | None = None,
    global_id: str | None = None,
    pset: str | None = None,
) -> list[VendorFact]:
    """Extract scalar IFC property-set values as source-traceable vendor facts.

    The caller must explicitly scope the model by IFC class or GlobalId. Property
    values are read through IfcOpenShell's property-set utility. Numeric primitives
    remain numeric but unitless; a unit is accepted only when it is explicitly
    present in a scalar string such as ``11 kW``.
    """
    file_path = Path(path)
    if file_path.suffix.lower() != ".ifc":
        raise ValueError("IFC input must end in .ifc")
    if not file_path.is_file():
        raise ValueError(f"IFC file does not exist: {file_path}")
    if ifc_class is not None and (not isinstance(ifc_class, str) or not ifc_class.strip()):
        raise ValueError("ifc_class must be non-empty text when supplied")
    if global_id is not None and (not isinstance(global_id, str) or not global_id.strip()):
        raise ValueError("global_id must be non-empty text when supplied")
    if pset is not None and (not isinstance(pset, str) or not pset.strip()):
        raise ValueError("pset must be non-empty text when supplied")

    ifc_class = ifc_class.strip() if ifc_class else None
    global_id = global_id.strip() if global_id else None
    pset = pset.strip() if pset else None

    ifcopenshell, get_psets = _load_ifc_api()
    try:
        model = ifcopenshell.open(str(file_path))
    except Exception as exc:
        raise ValueError(f"unable to open IFC file: {file_path.name}") from exc
    if model is None:
        raise ValueError(f"unable to open IFC file: {file_path.name}")

    entities = _select_entities(model, ifc_class=ifc_class, global_id=global_id)
    facts: list[VendorFact] = []

    for entity in entities:
        property_sets = get_psets(entity, psets_only=True, should_inherit=True)
        if pset:
            selected = property_sets.get(pset)
            if selected is None:
                continue
            property_sets = {pset: selected}

        for pset_name in sorted(property_sets, key=str.casefold):
            properties = property_sets[pset_name]
            if not isinstance(properties, dict):
                continue
            for property_name in sorted(properties, key=str.casefold):
                if property_name == "id":
                    continue
                parameter = _parameter_name(property_name)
                if not parameter:
                    continue
                parsed = _scalar_value(properties[property_name])
                if parsed is None:
                    continue
                raw_value, numeric_value, unit = parsed
                facts.append(
                    VendorFact(
                        parameter=parameter,
                        raw_value=raw_value,
                        value=numeric_value,
                        unit=unit,
                        source=SourceRef(
                            document=file_path.name,
                            section=_source_section(entity, str(pset_name)),
                        ),
                    )
                )

    if pset and not facts:
        raise ValueError(f"no scalar IFC properties found for property set {pset}")
    if not facts:
        scope = global_id or ifc_class or "selection"
        raise ValueError(f"no scalar IFC properties found for {scope}")
    return facts
