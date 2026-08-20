from bidlint.cli import build_parser


def test_compare_parser_accepts_xlsx_sheet_option():
    args = build_parser().parse_args(['compare', 'spec.pdf', 'vendor.xlsx', '--xlsx-sheet', 'Offer'])
    assert args.command == 'compare'
    assert args.vendor == 'vendor.xlsx'
    assert args.xlsx_sheet == 'Offer'


def test_rank_parser_accepts_mixed_vendor_inputs_and_xlsx_sheet():
    args = build_parser().parse_args(
        ['rank', 'spec.pdf', 'vendor-a.pdf', 'vendor-b.xlsx', '--xlsx-sheet', 'Offer']
    )
    assert args.vendors == ['vendor-a.pdf', 'vendor-b.xlsx']
    assert args.xlsx_sheet == 'Offer'


def test_extract_parser_accepts_xlsx_sheet_for_vendor_mode():
    args = build_parser().parse_args(['extract', 'vendor.xlsx', '--kind', 'vendor', '--xlsx-sheet', 'Offer'])
    assert args.kind == 'vendor'
    assert args.xlsx_sheet == 'Offer'
