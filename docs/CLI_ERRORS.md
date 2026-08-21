# CLI error contract

BidLint v0.9 defines stable process exit codes for the installed `bidlint` command and `python -m bidlint`.

The deterministic comparison engine and `bidlint.cli.main` keep their pre-v1 library behavior. Production command execution is routed through `bidlint.entrypoint.main`, which translates operational failures into stable process statuses.

| Exit code | Kind | Meaning |
| ---: | --- | --- |
| `0` | success | Command completed successfully. |
| `2` | usage_error | Invalid command-line syntax or argparse validation failure. |
| `3` | input_error | Malformed, unsupported, or semantically invalid specification/vendor input. |
| `4` | config_error | Invalid aliases, knockout policy, option combination, or output-format configuration. |
| `5` | io_error | Filesystem or other I/O failure while reading or writing command data. |
| `70` | internal_error | Unexpected legacy `SystemExit` state that cannot be classified safely. |
| `130` | interrupted | Command interrupted by the operator (`Ctrl-C`). |

Operational errors emitted by the production entry point use a stable text prefix:

```text
bidlint: <kind>: <message>
```

Examples:

```text
bidlint: config_error: --scorecard-output and --supplier-name must be supplied together
bidlint: input_error: unable to parse vendor input supplier.pdf: malformed PDF
bidlint: io_error: permission denied
```

## Compatibility boundary

- `argparse` keeps exit code `2` and its native usage/error rendering.
- Existing successful commands still return `0`.
- Existing `bidlint.cli.main` callers are not forced onto the new wrapper before v1.0.
- Error categories are intentionally broad; they describe automation action, not parser implementation details.
- The v1.0 compatibility freeze will decide whether this contract becomes part of the permanent public API.
