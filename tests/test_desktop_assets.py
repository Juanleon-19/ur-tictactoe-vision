from pathlib import Path

from ur_tictactoe.desktop.assets import optional_asset, resource_path


def test_missing_optional_logo_does_not_resolve(tmp_path: Path) -> None:
    assert optional_asset("assets/javeriana_logo.png", tmp_path) is None


def test_optional_logo_resolves_when_present(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    logo = assets / "javeriana_logo.png"
    logo.write_bytes(b"placeholder")
    assert optional_asset("assets/javeriana_logo.png", tmp_path) == logo
    assert resource_path("assets/javeriana_logo.png", tmp_path) == logo
