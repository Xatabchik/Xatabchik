"""F-07: установщик пиннится на release tag / SHA256, без curl|bash и git reset --hard."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_does_not_pipe_remote_script_to_bash():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "install.sh | bash" not in text
    assert "raw.githubusercontent.com/Xatabchik/Xatabchik/main/install.sh" not in text
    assert "XATABCHIK_TARBALL_SHA256" in text
    assert "XATABCHIK_INSTALL_TAG" in text


def test_install_sh_pins_release_and_checks_sha256():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "git reset --hard" not in text
    assert "XATABCHIK_TARBALL_SHA256" in text
    assert "resolve_install_tag" in text
    assert "sha256sum" in text
    assert "archive/refs/tags/" in text
    assert "git checkout --force" in text
