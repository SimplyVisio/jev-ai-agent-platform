from importlib.metadata import version


def test_package_is_importable() -> None:
    import jev_ai

    assert jev_ai.__doc__


def test_package_is_installed() -> None:
    assert version("jev-ai") == "0.1.0"
