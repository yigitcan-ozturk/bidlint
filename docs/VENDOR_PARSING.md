# Vendor datasheet parsing

`bidlint` extracts vendor facts conservatively. The parser supports a small set of explicit layouts that are common in technical datasheets and now preserves horizontal PDF layout when it can use that structure safely.

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

### Layout-preserved table with explicit headers

Vendor PDF extraction uses pypdf layout mode so horizontal spacing is retained. A table is reconstructed only when its header explicitly identifies a parameter column and an offered/value column.

```text
Parameter          Unit        Required        Offered
Motor power        kW          >= 10           11
Design pressure    bar         >= 10           10
```

`bidlint` reads the `Offered` column rather than the requirement/reference column. When the numeric offered value and its unit are in separate cells, they are combined before deterministic numeric parsing.

Recognized parameter headers include `Parameter`, `Property`, `Description`, `Technical Parameter`, and `Item`. Recognized value headers include `Offered`, `Offered Value`, `Vendor Value`, `Supplier Value`, and `Value`.

### Two side-by-side numeric fields

Some datasheets render two independent fields on the same visual row.

```text
Motor power     11 kW        Flow rate       125 m3/h
Design pressure 10 bar       Noise level     68 dB
```

This form is accepted only when both offered values are fully numeric with optional units. The restriction prevents arbitrary four-column text from being interpreted as technical facts.

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

## Multi-column safety

A visually separated row with three or more columns is not flattened into a two-column fact unless it matches a recognized table schema or the explicit side-by-side numeric pattern.

Table state is also dropped when a row no longer matches the active schema. Common `Note` / `Notes` / `Remark` rows terminate the table instead of becoming vendor parameters.

## Deliberate limits

- merged cells are not reconstructed
- wrapped table cells may still need preprocessing
- arbitrary tables without recognizable headers are not guessed
- side-by-side qualitative pairs are not inferred
- plain-text label/value pairing without structural or numeric evidence is intentionally conservative
- OCR remains outside the deterministic parser

The rule is the same as the rest of `bidlint`: **extract when structure is explicit; surface uncertainty when it is not.**
