from __future__ import annotations


def test_account_health_package_imports_cleanly() -> None:
    import account_health

    assert isinstance(account_health.__version__, str)
    assert account_health.__version__
