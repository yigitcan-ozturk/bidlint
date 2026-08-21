from __future__ import annotations

import sys
from collections.abc import Sequence

from .cli import main as cli_main
from .errors import CliErrorContract, ExitCode, classify_system_exit, contract_for_exception


def _emit_error(contract: CliErrorContract) -> None:
    print(f"bidlint: {contract.kind.value}: {contract.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Production CLI boundary with stable process exit codes.

    The internal ``bidlint.cli.main`` function keeps its historical behavior so
    library callers and pre-v1 tests remain compatible. The installed console
    script and ``python -m bidlint`` route through this boundary instead.
    """

    try:
        return int(cli_main(list(argv) if argv is not None else None))
    except SystemExit as exc:
        contract = classify_system_exit(exc)
        if contract is None:
            return ExitCode.SUCCESS
        if isinstance(exc.code, int):
            return int(exc.code)
        _emit_error(contract)
        return int(contract.exit_code)
    except (OSError, RuntimeError, ValueError) as exc:
        contract = contract_for_exception(exc)
        _emit_error(contract)
        return int(contract.exit_code)
    except KeyboardInterrupt:
        return 130
