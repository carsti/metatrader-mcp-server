import importlib

import pytest


get_account_type_module = importlib.import_module(
    "metatrader_client.account.get_account_type"
)


@pytest.mark.parametrize(
    ("trade_mode", "expected"),
    [
        (0, "demo"),
        (1, "contest"),
        (2, "real"),
    ],
)
def test_get_account_type_maps_mt5_trade_modes(monkeypatch, trade_mode, expected):
    monkeypatch.setattr(
        get_account_type_module,
        "get_account_info",
        lambda connection: {"trade_mode": trade_mode},
    )

    assert get_account_type_module.get_account_type(object()) == expected
