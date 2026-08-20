# IFC vendor property inputs

`bidlint` can use explicitly scoped IFC property-set values as vendor evidence.

IFC support is optional and uses IfcOpenShell. The normal package and development test suite do not require IfcOpenShell.

## Install

```bash
pip install -e '.[ifc]'
```

## Why IFC is vendor input, not a new decision engine

The adapter reads selected IFC property sets and converts scalar values into the existing `VendorFact` model. After that point, terminology matching, engineering-unit conversion and `PASS / DEVIATION / MISSING / REVIEW` evaluation are unchanged.

```text
Specification PDF ──> Requirement ───────────┐
                                             ├──> deterministic compare
Vendor PDF ─────────> VendorFact ────────────┤
Vendor IFC ──> scoped Psets ──> VendorFact ─┘
```

## Explicit element scope is required

An IFC file may contain many products. `bidlint` will not mix properties from unrelated occurrences and then choose whichever value gives the best compliance result.

Every IFC vendor extraction therefore requires one of:

- `--ifc-guid <GlobalId>` — select one occurrence directly
- `--ifc-class <IfcClass>` — allowed only when that class resolves to exactly one element in the model

If a class matches multiple elements, extraction stops and asks for a GlobalId.

You may additionally restrict extraction to one property set:

- `--ifc-pset <PsetName>`

## Compare a specification PDF with IFC vendor evidence

By GlobalId:

```bash
bidlint compare specification.pdf vendor.ifc \
  --ifc-guid 0EI0MSHbX9gg8Fxwar7lL8
```

By class when exactly one occurrence exists:

```bash
bidlint compare specification.pdf vendor.ifc \
  --ifc-class IfcPump
```

Restrict to one property set:

```bash
bidlint compare specification.pdf vendor.ifc \
  --ifc-guid 0EI0MSHbX9gg8Fxwar7lL8 \
  --ifc-pset Pset_PumpCommon
```

## Inspect IFC vendor facts

```bash
bidlint extract vendor.ifc \
  --kind vendor \
  --ifc-guid 0EI0MSHbX9gg8Fxwar7lL8
```

## Multi-vendor ranking

`rank` accepts PDF and IFC vendor inputs. The IFC selection flags apply to IFC inputs in the command; PDF vendors are parsed normally.

A class selector is useful when each IFC vendor model contains exactly one occurrence of the same equipment class:

```bash
bidlint rank specification.pdf vendor-a.ifc vendor-b.ifc \
  --ifc-class IfcPump
```

If vendor IFC files require different GlobalIds, compare them individually or prepare a project-specific extraction workflow rather than forcing one GUID across unrelated models.

## Property extraction rules

`bidlint` calls IfcOpenShell's property-set utility with inherited property sets enabled and property sets only.

For each selected element:

- property-set metadata key `id` is ignored
- property names are normalized from forms such as `MotorPower` to `motor power`
- strings, booleans and finite numeric primitives are accepted
- `None`, dictionaries, lists and other complex values are skipped
- numeric primitives remain numeric but **unitless**
- a unit is parsed only from an explicit scalar string such as `11 kW`

That last rule is deliberate. A numeric IFC value of `11` is not automatically assumed to mean kW, bar, mm or any other engineering unit.

## Provenance

IFC facts reuse the existing `SourceRef` contract. Since IFC has no PDF page/line, source identity is kept in `section` as:

```text
IfcClass:GlobalId/PsetName
```

Example:

```text
IfcPump:0EI0MSHbX9gg8Fxwar7lL8/Pset_PumpCommon
```

The source document remains the `.ifc` file name.

## Deliberate limits

- specification input remains PDF in this milestone
- one IFC extraction scope represents one vendor element occurrence
- a class matching multiple occurrences is rejected
- complex/list/nested IFC properties are not flattened
- IFC quantities are not included in this initial property-set adapter
- geometry is not evaluated
- units are not inferred from element type, property name or project context
- IFC property extraction does not change deterministic compliance rules

The governing rule remains: **explicit evidence before confidence**.
