"""F-06: панель биндится на localhost; в Nginx-шаблоне limit_req и security-заголовки."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_binds_panel_to_localhost():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:1488:1488"' in text
    assert '"1488:1488"' not in text


def test_install_nginx_template_has_login_limit_and_security_headers():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "limit_req_zone" in text
    assert "limit_req zone=xatabchik_login" in text
    assert "location = /login" in text
    assert "Strict-Transport-Security" in text
    assert "X-Content-Type-Options" in text
    assert "X-Frame-Options" in text
