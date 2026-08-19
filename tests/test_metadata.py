import json

from bidlint import __version__
from bidlint.models import ComplianceReport
from bidlint.report import portfolio_to_json, to_html


def test_report_contract_uses_package_version():
    report = ComplianceReport("spec.pdf", "vendor.pdf")
    assert report.to_dict()["version"] == __version__


def test_portfolio_and_html_use_package_version():
    report = ComplianceReport("spec.pdf", "vendor.pdf")
    payload = json.loads(portfolio_to_json([report]))
    assert payload["version"] == __version__
    assert f"bidlint v{__version__}" in to_html(report)
