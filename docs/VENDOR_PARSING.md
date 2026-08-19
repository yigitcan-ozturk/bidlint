# Vendor datasheet parsing

`bidlint` extracts vendor facts conservatively. The parser supports a small set of explicit layouts that are common in technical datasheets without attempting to reconstruct arbitrary PDF tables.

## Supported layouts

### Colon-delimited field

```text
Motor power: 11 kW
Design pressure: 10 bar
```

### Two-column row

A tab or at least two spaces may separate the field name and value.

```text
Motor power        11 kW
Design pressure    10 bar
Housing material   316L stainless steel
```

### Label followed by numeric value

```text
Motor power
11000 W
```

This fallback is intentionally limited to values that are fully numeric with an optional unit. That prevents ordinary headings and prose from being paired accidentally.

### Explicit label followed by qualitative value

A trailing colon provides enough structure to accept a qualitative value from the next non-empty line.

```text
Housing material:
316L stainless steel
```

The result is kept as a qualitative vendor fact and can participate in matching while remaining `REVIEW` unless a deterministic comparison rule exists.

## Numeric safety

Numeric extraction uses a full-value match. Descriptive material grades are not silently converted into numbers.

```text
Housing: 316L stainless steel
```

is stored as:

```text
raw_value = "316L stainless steel"
value     = null
unit      = null
```

It is **not** interpreted as the numeric value `316`.

## Deliberate limits

- arbitrary table-cell reconstruction is not implemented
- merged cells and visually aligned multi-column PDF layouts may still need preprocessing
- wrapped paragraphs are not guessed into fields
- plain-text label/value pairing without structural or numeric evidence is intentionally conservative
- OCR remains outside the deterministic parser

The rule is the same as the rest of `bidlint`: **extract when structure is explicit; surface uncertainty when it is not.**
