"""Регрессия: nginx -t падает, если сертификаты уже есть, а Certbot не писал TLS-сниппеты."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _extract_function(name: str) -> str:
    lines = (ROOT / "install.sh").read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}()"))
    depth = 0
    chunk: list[str] = []
    for line in lines[start:]:
        chunk.append(line)
        depth += line.count("{") - line.count("}")
        if chunk and depth == 0:
            break
    return "".join(chunk)


def _run_ensure(le_dir: Path) -> subprocess.CompletedProcess[str]:
    script = "\n".join(
        (
            "set -euo pipefail",
            'log_info() { echo "$1"; }',
            'log_warn() { echo "$1"; }',
            'log_success() { echo "$1"; }',
            'log_error() { echo "$1" >&2; }',
            _extract_function("_le_write_file"),
            _extract_function("ensure_letsencrypt_ssl_snippets"),
            f'ensure_letsencrypt_ssl_snippets "{le_dir}"',
        )
    )
    return subprocess.run(
        ["bash", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )


def test_ensure_letsencrypt_ssl_snippets_creates_missing_files(tmp_path: Path):
    le_dir = tmp_path / "letsencrypt"
    _run_ensure(le_dir)

    options = (le_dir / "options-ssl-nginx.conf").read_text(encoding="utf-8")
    dhparam = (le_dir / "ssl-dhparams.pem").read_text(encoding="utf-8")
    assert "ssl_protocols TLSv1.2 TLSv1.3" in options
    assert "ssl_session_tickets off" in options
    assert "BEGIN DH PARAMETERS" in dhparam
    assert "END DH PARAMETERS" in dhparam


def test_ensure_letsencrypt_ssl_snippets_keeps_existing_files(tmp_path: Path):
    le_dir = tmp_path / "letsencrypt"
    le_dir.mkdir()
    options = le_dir / "options-ssl-nginx.conf"
    dhparam = le_dir / "ssl-dhparams.pem"
    options.write_text("# custom-options\n", encoding="utf-8")
    dhparam.write_text("# custom-dh\n", encoding="utf-8")

    _run_ensure(le_dir)

    assert options.read_text(encoding="utf-8") == "# custom-options\n"
    assert dhparam.read_text(encoding="utf-8") == "# custom-dh\n"


def test_install_sh_creates_snippets_before_nginx_test():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "ensure_letsencrypt_ssl_snippets" in text
    assert text.index("ensure_letsencrypt_ssl_snippets") < text.index("sudo nginx -t")
    update_idx = text.index("Обнаружена существующая конфигурация")
    assert text.find("ensure_letsencrypt_ssl_snippets", update_idx) != -1
