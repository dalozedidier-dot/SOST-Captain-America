from __future__ import annotations


def test_import_sost_and_version() -> None:
    import sost  # noqa: F401

    assert hasattr(sost, "__version__")
    assert isinstance(sost.__version__, str)
    assert sost.__version__, "empty version string"
