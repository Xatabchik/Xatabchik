"""Проверка пароля и кода сброса.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


import hashlib


import hmac


def _hash_password_reset_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.strip().lower()}:{str(code).strip()}".encode("utf-8")).hexdigest()


def _password_reset_code_matches(email: str, code: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    expected = _hash_password_reset_code(email, code or "")
    try:
        return hmac.compare_digest(expected, str(stored_hash))
    except Exception:
        return False


def _validate_password(password: str) -> str | None:
    """Проверка пароля при регистрации / сбросе / смене.

    Раньше хватало 5 символов без цифр («ababa») — это принималось.
    Существующие аккаунты с таким паролем по-прежнему входят (login
    политику не применяет); новые пароли должны быть длиннее и смешанные.
    """
    if not isinstance(password, str):
        password = str(password or "")
    if len(password) < 8:
        return "Пароль должен содержать минимум 8 символов"
    if password.isdigit():
        return "Пароль не должен состоять только из цифр"
    if not any(c.isalpha() for c in password):
        return "Пароль должен содержать хотя бы одну букву"
    if not any(c.isdigit() for c in password):
        return "Пароль должен содержать хотя бы одну цифру"
    if len(set(password)) < 2:
        return "Пароль слишком простой — используйте разные символы"
    return None


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_hash_password_reset_code",
    "_password_reset_code_matches",
    "_validate_password",
]
