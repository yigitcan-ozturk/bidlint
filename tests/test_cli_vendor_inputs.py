from argparse import Namespace

import bidlint.cli as cli_module


def test_mixed_rank_routes_ifc_scope_only_to_ifc_inputs(monkeypatch):
    calls: list[tuple[str, dict[str, str | None]]] = []

    def fake_parse_vendor_input(vendor: str, **kwargs):
        calls.append((vendor, kwargs))
        return []

    monkeypatch.setattr(cli_module, "parse_vendor_input", fake_parse_vendor_input)
    args = Namespace(ifc_class="IfcPump", ifc_guid=None, ifc_pset="Pset_PumpCommon")

    cli_module._parse_cli_vendor("vendor.pdf", args, mixed_rank=True)
    cli_module._parse_cli_vendor("vendor.xlsx", args, mixed_rank=True)
    cli_module._parse_cli_vendor("pump.ifc", args, mixed_rank=True)

    assert calls == [
        ("vendor.pdf", {}),
        ("vendor.xlsx", {}),
        (
            "pump.ifc",
            {"ifc_class": "IfcPump", "ifc_guid": None, "ifc_pset": "Pset_PumpCommon"},
        ),
    ]


def test_cli_help_names_xlsx_as_supported_vendor_input():
    help_text = cli_module.build_parser().format_help()
    assert "PDF, XLSX or IFC" in help_text or "PDF/XLSX/IFC" in help_text
