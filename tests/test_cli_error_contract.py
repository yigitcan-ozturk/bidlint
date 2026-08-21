from __future__ import annotations

from bidlint import entrypoint
from bidlint.errors import ExitCode


def _raise_system_exit(message: str):
    def fail(argv=None):
        raise SystemExit(message)

    return fail


def _raise_exception(exc: Exception):
    def fail(argv=None):
        raise exc

    return fail


def test_entrypoint_preserves_argparse_usage_code():
    assert entrypoint.main([]) == ExitCode.USAGE


def test_entrypoint_maps_config_errors(monkeypatch, capsys):
    monkeypatch.setattr(
        entrypoint,
        "cli_main",
        _raise_system_exit("--scorecard-output and --supplier-name must be supplied together"),
    )

    assert entrypoint.main(["compare"]) == ExitCode.CONFIG
    assert "config_error" in capsys.readouterr().err


def test_entrypoint_maps_input_errors(monkeypatch, capsys):
    monkeypatch.setattr(
        entrypoint,
        "cli_main",
        _raise_system_exit("unable to parse vendor input vendor.pdf: malformed PDF"),
    )

    assert entrypoint.main(["compare"]) == ExitCode.INPUT
    assert "input_error" in capsys.readouterr().err


def test_entrypoint_maps_io_errors(monkeypatch, capsys):
    monkeypatch.setattr(entrypoint, "cli_main", _raise_exception(OSError("permission denied")))

    assert entrypoint.main(["compare"]) == ExitCode.IO
    assert "io_error" in capsys.readouterr().err


def test_entrypoint_maps_uncaught_value_errors_to_input(monkeypatch, capsys):
    monkeypatch.setattr(entrypoint, "cli_main", _raise_exception(ValueError("malformed specification")))

    assert entrypoint.main(["compare"]) == ExitCode.INPUT
    assert "malformed specification" in capsys.readouterr().err
