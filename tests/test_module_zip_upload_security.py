"""
Security tests for module ZIP import (CWE-22 zip-slip) and panel upload auth.

/modules/upload is admin-only (@login_required / session['logged_in']).
import_module_from_zip must reject path-traversal members and not write
outside the modules directory.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from conftest import temp_db  # noqa: F401


def _build_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _minimal_module_init(module_id: str = "safe_mod") -> bytes:
    return (
        "from shop_bot.core.module_types import ModuleMeta\n"
        f"MODULE_META = ModuleMeta(id={module_id!r}, name='Safe', version='1.0.0', "
        "description='t', author='t')\n"
    ).encode()


@pytest.fixture()
def modules_loader(temp_db, tmp_path, monkeypatch):
    """Fresh ModuleLoader pointed at an empty modules dir + temp DB."""
    from shop_bot.core import module_loader as ml

    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    loader = ml.ModuleLoader(modules_path=modules_dir, db_file=temp_db.DB_FILE)
    monkeypatch.setattr(ml, "_global_loader", loader)
    return loader, modules_dir


def test_import_module_from_zip_rejects_path_traversal(modules_loader, tmp_path):
    """ZIP with ../../../ traversal must fail; nothing written outside modules_dir."""
    loader, modules_dir = modules_loader
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    evil_marker = outside_dir / "evil.py"

    # Classic zip-slip: member escapes the intended module root.
    payload = _build_zip(
        {
            "safe_mod/__init__.py": _minimal_module_init("safe_mod"),
            "safe_mod/../../../outside/evil.py": b'print("pwned")\n',
        }
    )
    zip_path = tmp_path / "evil.zip"
    zip_path.write_bytes(payload)

    ok, message = loader.import_module_from_zip(zip_path, auto_enable=False)

    assert ok is False
    assert "Unsafe path" in message or "traversal" in message.lower() or "Path" in message
    assert not evil_marker.exists()
    # No escaped write under tmp_path/outside and no partial module install.
    assert list(outside_dir.iterdir()) == []
    assert not (modules_dir / "safe_mod").exists()
    # Nothing unexpected created beside modules_dir under tmp_path.
    for path in tmp_path.rglob("evil.py"):
        assert False, f"evil.py was written to {path}"


def test_import_module_from_zip_rejects_absolute_path_member(modules_loader, tmp_path):
    loader, modules_dir = modules_loader
    payload = _build_zip(
        {
            "/tmp/absolute_evil.py": b"print(1)\n",
            "absmod/__init__.py": _minimal_module_init("absmod"),
        }
    )
    zip_path = tmp_path / "abs.zip"
    zip_path.write_bytes(payload)

    ok, message = loader.import_module_from_zip(zip_path, auto_enable=False)
    assert ok is False
    assert "Unsafe path" in message or "outside" in message.lower() or "Invalid" in message
    assert not (modules_dir / "absmod").exists()


def test_import_module_from_zip_rejects_disallowed_extension(modules_loader, tmp_path):
    loader, modules_dir = modules_loader
    payload = _build_zip(
        {
            "binmod/__init__.py": _minimal_module_init("binmod"),
            "binmod/payload.sh": b"#!/bin/sh\necho pwned\n",
        }
    )
    zip_path = tmp_path / "bin.zip"
    zip_path.write_bytes(payload)

    ok, message = loader.import_module_from_zip(zip_path, auto_enable=False)
    assert ok is False
    assert "Disallowed" in message
    assert not (modules_dir / "binmod").exists()


def test_import_module_from_zip_rejects_too_many_files(modules_loader, tmp_path, monkeypatch):
    from shop_bot.core import module_loader as ml

    monkeypatch.setattr(ml, "MAX_MODULE_ZIP_FILES", 5)
    loader, modules_dir = modules_loader

    entries = {"many_mod/__init__.py": _minimal_module_init("many_mod")}
    for i in range(10):
        entries[f"many_mod/f{i}.py"] = b"x = 1\n"
    zip_path = tmp_path / "many.zip"
    zip_path.write_bytes(_build_zip(entries))

    ok, message = loader.import_module_from_zip(zip_path, auto_enable=False)
    assert ok is False
    assert "too many" in message.lower()
    assert not (modules_dir / "many_mod").exists()


def test_import_module_from_zip_accepts_valid_module(modules_loader, tmp_path):
    loader, modules_dir = modules_loader
    payload = _build_zip(
        {
            "ok_mod/__init__.py": _minimal_module_init("ok_mod"),
            "ok_mod/README.md": b"# ok\n",
        }
    )
    zip_path = tmp_path / "ok.zip"
    zip_path.write_bytes(payload)

    ok, message = loader.import_module_from_zip(zip_path, auto_enable=False)
    assert ok is True, message
    assert (modules_dir / "ok_mod" / "__init__.py").is_file()
    assert (modules_dir / "ok_mod" / "README.md").is_file()


class _FakeBot:
    def get_status(self):
        return {"is_running": False}


def test_modules_upload_requires_login(temp_db, monkeypatch):
    """Unauthenticated POST /modules/upload must not install; redirect to login."""
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()

    # Ensure session has no panel admin flag (webapp auth_token is unrelated).
    with client.session_transaction() as sess:
        sess.pop("logged_in", None)
        sess["auth_token"] = "stolen-user-token-must-not-grant-panel"

    data = {
        "module_file": (io.BytesIO(_build_zip({"x/__init__.py": b"MODULE_META={}"})), "x.zip"),
    }
    resp = client.post(
        "/modules/upload",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    # login_required redirects to /login (302/303); never 200 success.
    assert resp.status_code in (301, 302, 303, 401)
    location = (resp.headers.get("Location") or "").lower()
    assert "login" in location or resp.status_code == 401
