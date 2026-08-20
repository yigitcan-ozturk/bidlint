# Engineering unit conversion

`bidlint` keeps unit conversion inside the deterministic decision layer. The engine converts values only when both units are known members of the same physical dimension.

## Supported dimensions

| Dimension | Supported units | Base relationship |
| --- | --- | --- |
| Power | `W`, `kW`, `MW` | `1 kW = 1000 W` |
| Voltage | `mV`, `V`, `kV` | `1 kV = 1000 V` |
| Current | `mA`, `A`, `kA` | `1 A = 1000 mA` |
| Frequency | `Hz`, `kHz`, `MHz` | `1 kHz = 1000 Hz` |
| Apparent power | `VA`, `kVA`, `MVA` | `1 kVA = 1000 VA` |
| Pressure | `Pa`, `kPa`, `MPa`, `mbar`, `bar`, `psi` | `1 bar = 100 kPa`; `1 psi ≈ 6.894757 kPa` |
| Length | `mm`, `cm`, `m`, `km`, `in`, `ft` | `1 in = 25.4 mm`; `1 ft = 0.3048 m` |
| Mass | `g`, `kg`, `t` | `1 t = 1000 kg` |
| Force | `N`, `kN` | `1 kN = 1000 N` |
| Flow | `L/s`, `L/min`, `m³/s`, `m³/h` | `1 L/s = 60 L/min = 3.6 m³/h` |
| Temperature | `°C`, `°F`, `K` | affine conversion with explicit temperature units |
| Rotational-speed labels | `rpm`, `r/min`, `rev/min` | canonicalized to `rpm`; no inferred motor-pole conversion |

Common textual aliases such as `kilowatt`, `kilovolt`, `ampere`, `hertz`, `kilonewton`, `millimetre`, `metric tonne`, `m3/h`, `lps` and `lpm` are canonicalized before comparison.

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

The same deterministic rule now applies to explicit electrical and temperature units:

```text
Required: Supply voltage >= 0.4 kV
Offered : Supply voltage 400 V
Result  : PASS
```

```text
Required: Operating temperature <= 40 °C
Offered : Operating temperature 104 °F
Result  : PASS
```

A dimension mismatch is never silently converted:

```text
Required: 10 kW
Offered : 10 kVA
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

- `psig` and `psia` are not collapsed into `psi`; gauge/absolute pressure semantics require explicit project context.
- Bare `F` is not treated as Fahrenheit because it can be ambiguous in engineering notation; use `°F`, `degF` or `fahrenheit`.
- `kW` and `kVA` remain different physical dimensions. No power-factor assumption is made.
- Rotational speed is not inferred from electrical frequency; `Hz -> rpm` depends on machine topology and is therefore not automatic.
- Torque, density, viscosity and other compound engineering units remain outside the current deterministic registry.
- Unit inference from context is not performed. The unit must be present in both parsed values when the comparison is unit-sensitive.

The rule is simple: **convert only when the physical dimension is explicit and known; otherwise surface uncertainty.**
