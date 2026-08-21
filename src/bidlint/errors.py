from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class ExitCode(IntEnum):
    """Stable process exit codes for the public bidlint CLI."""

    SUCCESS = 0
    USAGE = 2
    INPUT = 3
    CONFIG = 4
    IO = 5
    INTERNAL = 70


class ErrorKind(StrEnum):
    USAGE = "usage_error"
    INPUT = "input_error"
    CONFIG = "config_error"
    IO = "io_error"
    INTERNAL = "internal_error"


@dataclass(frozen=True)
class CliErrorContract:
    kind: ErrorKind
    exit_code: ExitCode
    message: str


_CONFIG_MARKERS = (
    "--aliases",
    "--knockouts",
    "must be supplied together",
    "must end in",
    "requires --kind vendor",
    "requires at least one",
    "rank requires",
    "unknown knockout requirement id",
    "contract v1",
)
_INPUT_PREFIXES = (
    "unable to extract",
    "unable to parse vendor input",
)
_IO_PREFIXES = (
    "unable to write",
)


def classify_system_exit(exc: SystemExit) -> CliErrorContract | None:
    """Translate legacy ``SystemExit`` values into the public CLI contract.

    ``argparse`` already emits its own usage text before raising with integer
    status 2, so integer exits are preserved without re-rendering their output.
    String-valued exits come from the deterministic CLI validation layer and
    are classified here for stable automation semantics.
    """

    code = exc.code
    if code is None or code == 0:
        return None
    if isinstance(code, int):
        if code == ExitCode.USAGE:
            return CliErrorContract(ErrorKind.USAGE, ExitCode.USAGE, "invalid command-line usage")
        return CliErrorContract(ErrorKind.INTERNAL, ExitCode.INTERNAL, f"process exited with status {code}")

    message = str(code)
    lowered = message.lower()
    if any(marker in lowered for marker in _CONFIG_MARKERS):
        return CliErrorContract(ErrorKind.CONFIG, ExitCode.CONFIG, message)
    if lowered.startswith(_INPUT_PREFIXES):
        return CliErrorContract(ErrorKind.INPUT, ExitCode.INPUT, message)
    if lowered.startswith(_IO_PREFIXES):
        return CliErrorContract(ErrorKind.IO, ExitCode.IO, message)
    return CliErrorContract(ErrorKind.INTERNAL, ExitCode.INTERNAL, message)


def contract_for_exception(exc: Exception) -> CliErrorContract:
    if isinstance(exc, OSError):
        return CliErrorContract(ErrorKind.IO, ExitCode.IO, str(exc))
    if isinstance(exc, (RuntimeError, ValueError)):
        return CliErrorContract(ErrorKind.INPUT, ExitCode.INPUT, str(exc))
    return CliErrorContract(ErrorKind.INTERNAL, ExitCode.INTERNAL, str(exc))
