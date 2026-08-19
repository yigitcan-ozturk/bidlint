# Engineering unit conversion

`bidlint` keeps unit conversion inside the deterministic decision layer. The engine converts values only when both units are known members of the same physical dimension.

## Supported dimensions

| Dimension | Supported units | Base relationship |
| --- | --- | --- |
| Power | `W`, `kW`, `MW` | `1 kW = 1000 W` |
| Pressure | `Pa`, `kPa`, `MPa`, `bar` | `1 bar = 100 kPa` |
| Length | `mm`, `cm`, `m` | `1 m = 1000 mm` |
| Flow | `L/s`, `L/min`, `m³/s`, `m³/h` | `1 L/s = 60 L/min = 3.6 m³/h` |
| Temperature labels | `C`, `°C` | label-equivalent only |

Common textual aliases such as `kilowatt`, `millimetre`, `m3/h`, `lps` and `lpm` are canonicalized before comparison.

## Decision behavior

Specification:

```text
Motor power shall be minimum 10 kW.
```

Vendor:

```text
Motor power: 10000 W
```

Result:

```text
PASS — Offered 10000w (= 10kw) satisfies >= 10kw.
```

A dimension mismatch is never silently converted:

```text
Required: 10 kW
Offered : 10 bar
Result  : REVIEW
```

Missing unit evidence also stays explicit:

```text
Required: 10 kW
Offered : 12
Result  : REVIEW
```

Unknown unit pairs remain `REVIEW` as well. This prevents unsupported conversion or missing evidence from becoming a false compliance decision.

## Deliberate limits

- Fahrenheit/Celsius conversion is not yet implemented because offset conversions need a different model from multiplicative conversions.
- Compound engineering units beyond the listed flow units remain under review.
- Unit inference from context is not performed. The unit must be present in both parsed values when the comparison is unit-sensitive.

The rule is simple: **convert only when the physical dimension is explicit and known; otherwise surface uncertainty.**
