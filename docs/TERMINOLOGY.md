# Engineering terminology

Different manufacturers often use different labels for the same technical parameter. `bidlint` normalizes a deliberately small set of low-risk terminology variants before fuzzy matching.

The terminology layer is **not** a general engineering ontology. It does not assume that similar-sounding concepts are technically equivalent.

## Built-in packs

Built-in aliases are grouped by domain:

- `core` — explicit ingress-protection, operating-temperature and lexical noise variants
- `mechanical` — spelling/format variants for flow and rotational speed
- `electrical` — conservative motor-power naming variants
- `materials` — material-of-construction naming variants

Examples:

```text
ingress protection rating -> ip rating
ip code                   -> ip rating
flow-rate                 -> flow rate
rotation speed            -> rotational speed
rated motor power         -> motor power
material of construction  -> construction material
```

## Deliberate non-equivalences

Some terms are intentionally **not** aliases even when they may be related in a particular project.

For example:

```text
protection class      != ip rating
sound pressure level  != noise level
```

`protection class` can refer to electrical protection or insulation classes, while an IP rating specifically describes ingress protection. `sound pressure level` is a specific acoustic quantity, while a generic `noise level` label may be defined differently by a specification. Mapping either pair automatically could create a false compliance result.

Similar caution applies to concepts such as design pressure vs. working pressure, nominal voltage vs. rated voltage, and ambient temperature vs. operating temperature.

## Project- or vendor-specific aliases

Use `--aliases` when a project, specification or manufacturer explicitly defines a local equivalence.

Create a JSON object:

```json
{
  "rated output": "motor power",
  "supplier ip code": "ip rating",
  "project noise label": "sound pressure level"
}
```

Then run:

```bash
bidlint compare specification.pdf vendor.pdf --aliases aliases.json
```

or:

```bash
bidlint rank specification.pdf vendor-a.pdf vendor-b.pdf --aliases aliases.json
```

Keys are aliases and values are canonical parameter names. Both sides are normalized for case, punctuation and whitespace before use.

Custom aliases override the built-in registry for the exact normalized alias. This makes project-specific semantic decisions explicit and reviewable instead of hiding them inside fuzzy matching.

## Matching order

1. normalize case, punctuation and whitespace
2. apply conservative built-in terminology aliases
3. apply explicit custom aliases
4. if canonical names are identical, match confidence is `1.0`
5. otherwise fall back to transparent token/sequence similarity

The guiding rule is: **normalize nomenclature aggressively only when equivalence is explicit; otherwise keep semantic uncertainty visible.**
