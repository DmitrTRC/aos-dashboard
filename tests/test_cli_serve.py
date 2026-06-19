from aos.cli import build_parser


def test_serve_parser_has_port_and_no_browser():
    parser = build_parser()
    args = parser.parse_args(["serve", "--port", "9999", "--no-browser"])
    assert args.port == 9999
    assert args.no_browser is True
    assert args.func.__name__ == "_cmd_serve"
