"""Tiger broker helpers: CN symbol detection + normalization (no SDK/network)."""
from app.brokers.tiger_service import _is_chinese_symbol, normalize_tiger_symbol


def test_is_chinese_symbol():
    assert _is_chinese_symbol("600000") is True
    assert _is_chinese_symbol("000001") is True
    assert _is_chinese_symbol("300750") is True
    assert _is_chinese_symbol("AAPL") is False
    assert _is_chinese_symbol("12345") is False
    assert _is_chinese_symbol("60000X") is False
    assert _is_chinese_symbol("") is False


def test_normalize_tiger_symbol():
    assert normalize_tiger_symbol("600000") == "600000.SH"
    assert normalize_tiger_symbol("900000") == "900000.SH"
    assert normalize_tiger_symbol("000001") == "000001.SZ"
    assert normalize_tiger_symbol("300750") == "300750.SZ"
    assert normalize_tiger_symbol("AAPL") == "AAPL"
    assert normalize_tiger_symbol("aapl") == "AAPL"