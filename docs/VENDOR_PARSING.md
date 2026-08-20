# Vendor datasheet parsing

`bidlint` extracts vendor facts conservatively. The parser supports a small set of explicit layouts that are common in technical datasheets and preserves horizontal PDF layout when it can use that structure safely.

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

When more than one parameter-like header appears before one offered/value header, the nearest preceding semantic header is used. This allows a common `Item | Description | Unit | Offered` layout to use `Description` as the actual parameter column rather than interpreting the numeric item number as the parameter.

### Repeated explicit side-by-side header groups

Some datasheets place two independent technical tables on the same visual row. This layout is accepted only when each group repeats its own explicit parameter-like and offered/value headers.

```text
Parameter     Unit   Offered     Parameter        Unit   Offered
Motor power   kW     11          Flow rate        m3/h   125
Pressure      bar    10          Noise level      dB     68
```

Each complete body row produces one fact per explicit header group. Group boundaries come from the repeated headers, not from interpreting the body values or guessing column positions.

A repeated body row must retain the full header width and every group must produce a valid parameter/value pair. If one group is incomplete, the entire visual row is skipped rather than extracting one side and guessing how the remaining cells shifted.

### Coordinate-aligned sparse table row

Some PDFs visually leave an intermediate table cell blank. Plain whitespace splitting then shifts later cells left and can make a valid offered value look like the wrong column.

```text
Parameter          Unit        Required        Offered
Motor power        kW                          11
Design pressure    bar         >= 10           10
```

For an already recognized table, `bidlint` performs a supplementary positioned-text pass. The header cell x-positions become explicit column anchors. A sparse row is reconstructed only when the parameter and offered cells align closely enough to those anchors and at least one intermediate cell is visibly absent.

This coordinate pass is a fallback, not the primary parser. It does **not** infer a value merely because it is somewhere between two columns. Fragments close to a column boundary are rejected instead of assigned by guesswork. A genuinely blank `Unit` cell also remains blank; no unit is invented from the surrounding table.

### Explicit merged-cell rectangles

Some generated datasheets draw each table cell as an explicit PDF rectangle. If a body row merges intermediate cells, such as `Unit + Required`, whitespace and x-position alone can make the merged text look like it belongs to one semantic column.

`bidlint` can use explicit axis-aligned PDF `re` rectangle geometry as additional evidence, but only under an already recognized table header. A merged rectangle is accepted only when the `Parameter` and `Offered` columns still have their own distinct cell rectangles.

```text
| Parameter   |      Unit + Required       | Offered |
| Motor power |         kW / >= 10          |   11    |
```

In this case the fact can be recovered as `motor power -> 11`, but the merged middle text is **not** assigned to `Unit` or `Required`. The unit therefore remains unknown instead of becoming a fabricated value such as `kW / >= 10`.

If a merged rectangle touches `Parameter` or `Offered`, the row is rejected. Rotated/skewed rectangles are also ignored rather than converted to a misleading axis-aligned box. Arbitrary line drawings are not treated as cells; this feature currently requires explicit rectangle operators.

### Explicit wrapped offered value

If the offered/value column is the final table column, a row may be completed from the immediately following line only when that line contains one fully numeric value with an optional unit.

```text
Parameter          Unit        Required        Offered
Motor power        kW          >= 10
                                             11
```

This rule does not fill arbitrary missing cells. It applies only when every preceding header cell is present and the missing cell is specifically the final offered-value column.

### Explicitly hyphenated wrapped parameter

A parameter label may continue onto the immediately following line when the first fragment ends with an explicit hyphen.

```text
Parameter          Unit        Offered
Maximum allow-     bar         10
able working pressure
```

The reconstructed parameter is `Maximum allowable working pressure`. A plain single-cell line without the trailing hyphen marker is **not** guessed to be a continuation.

### Two side-by-side numeric fields

Some datasheets render two independent fields on the same visual row without a header.

```text
Motor power     11 kW        Flow rate       125 m3/h
Design pressure 10 bar       Noise level     68 dB
```

This legacy compact form is accepted only when both offered values are fully numeric with optional units. More complex multi-column layouts require explicit repeated headers instead of positional inference.

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

A visually separated row with three or more columns is not flattened into a two-column fact unless it matches a recognized table schema, repeated explicit header groups, the explicit side-by-side numeric pattern, a coordinate-aligned sparse row, or safe explicit rectangle geometry under an active header.

Repeated groups are all-or-nothing per visual row: incomplete groups are not partially recovered. Common `Note` / `Notes` / `Remark` rows terminate active table state instead of becoming vendor parameters.

Wrapped-cell handling follows the same evidence rule: a numeric continuation must complete the final offered column, and a label continuation must carry an explicit trailing hyphen. Ordinary headings or free text are never merged merely because they are adjacent.

## Deliberate limits

- complex multi-column body layouts without explicit repeated headers are not reconstructed by positional guessing
- merged-cell support currently requires explicit axis-aligned PDF rectangle (`re`) geometry
- merges touching `Parameter` or `Offered` are rejected
- content inside merged intermediate cells is not split into semantic sub-values
- arbitrary line-segment grids are not reconstructed into cells
- coordinate/geometry evidence is accepted only under an explicit recognized table header
- fragments too far from a header anchor or too close to a boundary are not assigned by positional guessing
- unmarked wrapped labels are not guessed
- wrapped qualitative offered values are not inferred
- arbitrary tables without recognizable headers are not guessed
- side-by-side qualitative pairs without explicit headers are not inferred
- plain-text label/value pairing without structural or numeric evidence is intentionally conservative
- OCR remains outside the deterministic parser

The rule is the same as the rest of `bidlint`: **extract when structure is explicit; surface uncertainty when it is not.**
