"""Аутентификация: captcha, коды подтверждения email, auth-токены и запросы
авторизации из веб-приложения.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import hashlib
import hmac
import secrets
import uuid

__all__ = (
    "create_webapp_auth_request",
    "confirm_webapp_auth_request",
    "get_webapp_auth_request",
    "cleanup_old_webapp_auth_requests",
    "get_user_by_auth_token",
    "get_auth_token_by_user_id",
    "update_user_auth_token",
    "invalidate_all_user_auth_tokens",
    "hash_password",
    "verify_password",
    "update_user_password",
    "_hash_verification_code",
    "set_email_verification_code",
    "get_email_verification",
    "check_email_verification_code",
    "mark_email_verified",
    "update_email_code_last_sent",
    "update_user_password_by_id",
)


def create_webapp_auth_request(token: str) -> bool:
    """Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO webapp_auth_requests (token, user_id, created_at) VALUES (?, NULL, CURRENT_TIMESTAMP)",
                (str(token),),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to create webapp auth request {token}: {e}")
        return False


def confirm_webapp_auth_request(token: str, user_id: int) -> bool:
    """Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT token FROM webapp_auth_requests WHERE token = ?", (str(token),))
            if not cursor.fetchone():
                return False
            cursor.execute(
                "UPDATE webapp_auth_requests SET user_id = ? WHERE token = ?",
                (int(user_id), str(token)),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to confirm webapp auth request {token}: {e}")
        return False


def get_webapp_auth_request(token: str, *, consume: bool = False) -> int | None:
    """Возвращает user_id, если запрос уже подтверждён ботом, иначе None.

    Если consume=True и запрос подтверждён, удаляет запись (одноразовое использование).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM webapp_auth_requests WHERE token = ?", (str(token),))
            row = cursor.fetchone()
            if not row or row[0] is None:
                return None
            user_id = int(row[0])
            if consume:
                cursor.execute("DELETE FROM webapp_auth_requests WHERE token = ?", (str(token),))
                conn.commit()
            return user_id
    except sqlite3.Error as e:
        logging.error(f"Failed to get webapp auth request {token}: {e}")
        return None


def cleanup_old_webapp_auth_requests(max_age_minutes: int = 30) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM webapp_auth_requests WHERE created_at < datetime('now', ?)",
                (f"-{int(max_age_minutes)} minutes",),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to cleanup webapp auth requests: {e}")


def get_user_by_auth_token(token: str) -> dict | None:
    """Найти пользователя по постоянному auth-токену (webapp)."""
    if not token:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE auth_token = ?", (str(token),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user by auth token: {e}")
        return None


def get_auth_token_by_user_id(user_id: int) -> str | None:
    """Получить уже выданный постоянный auth-токен пользователя, если есть."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT auth_token FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    except Exception as e:
        logger.error(f"Failed to get auth token for user {user_id}: {e}")
        return None


def update_user_auth_token(user_id: int, token: str) -> bool:
    """Сохранить постоянный auth-токен для пользователя (webapp)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_token = ? WHERE telegram_id = ?", (str(token), int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update auth token for user {user_id}: {e}")
        return False


def invalidate_all_user_auth_tokens() -> int:
    """Перевыпустить все persistent auth_token пользователей (UUID4).

    Используется как remediation после компрометации токенов (например, через
    уязвимый /api/auth/telegram-direct). Старые токены в браузерах/клиентах
    перестают работать; пользователи должны войти заново.
    Возвращает число обновлённых строк.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT telegram_id FROM users WHERE auth_token IS NOT NULL AND TRIM(auth_token) != ''"
            )
            rows = cur.fetchall()
            updated = 0
            for (telegram_id,) in rows:
                cur.execute(
                    "UPDATE users SET auth_token = ? WHERE telegram_id = ?",
                    (str(uuid.uuid4()), int(telegram_id)),
                )
                updated += cur.rowcount
            conn.commit()
            return updated
    except Exception as e:
        logger.error(f"Failed to invalidate all user auth tokens: {e}")
        return 0


def hash_password(password: str) -> str:
    """Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    """Проверить пароль против сохранённого хэша.

    Поддерживает как новый формат (pbkdf2$salt$hash), так и старые аккаунты,
    у которых пароль ещё хранится в открытом виде (миграция «на лету»).
    """
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2$"):
            _, salt, digest = stored.split("$", 2)
            check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
            return hmac.compare_digest(check, digest)
    except Exception:
        return False
    # Legacy plaintext fallback for accounts created before hashing was introduced.
    return hmac.compare_digest(stored, password)


def update_user_password(email: str, new_password: str) -> bool:
    """Обновить (хэшированный) пароль локального webapp-аккаунта по email."""
    norm = _normalize_email(email)
    if not norm:
        return False
    try:
        password_hash = hash_password(new_password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_pass = ? WHERE auth_email = ?", (password_hash, norm))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update password for {email}: {e}")
        return False


def _hash_verification_code(user_id: int, code: str) -> str:
    return hashlib.sha256(f"{int(user_id)}:{code}".encode("utf-8")).hexdigest()


def set_email_verification_code(user_id: int, code: str, ttl_seconds: int = 600) -> bool:
    """Сохранить хэш одноразового кода подтверждения email и время его истечения."""
    try:
        code_hash = _hash_verification_code(user_id, code)
        expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET email_code_hash = ?, email_code_expires_at = ?, email_code_last_sent_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
                """,
                (code_hash, expires_at, int(user_id)),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to set email verification code for user {user_id}: {e}")
        return False


def get_email_verification(user_id: int) -> dict | None:
    """Вернуть данные о статусе подтверждения email и последнем отправленном коде."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT email_verified, email_code_hash, email_code_expires_at, email_code_last_sent_at, auth_email
                FROM users WHERE telegram_id = ?
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get email verification for user {user_id}: {e}")
        return None


def check_email_verification_code(user_id: int, code: str) -> bool:
    """Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия)."""
    info = get_email_verification(user_id)
    if not info or not info.get("email_code_hash") or not info.get("email_code_expires_at"):
        return False
    try:
        expires_at = datetime.strptime(str(info["email_code_expires_at"]), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    if datetime.utcnow() > expires_at:
        return False
    expected = _hash_verification_code(user_id, str(code).strip())
    return hmac.compare_digest(expected, str(info["email_code_hash"]))


def mark_email_verified(user_id: int) -> bool:
    """Отметить email пользователя как подтверждённый и очистить код."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET email_verified = 1, email_code_hash = NULL, email_code_expires_at = NULL
                WHERE telegram_id = ?
                """,
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to mark email verified for user {user_id}: {e}")
        return False


def update_email_code_last_sent(user_id: int) -> bool:
    """Обновить время последней отправки кода (для rate-limit повторной отправки)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET email_code_last_sent_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update email code last sent for user {user_id}: {e}")
        return False


def update_user_password_by_id(user_id: int, new_password: str) -> bool:
    """Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля,
    когда пользователь уже авторизован и email известен только по сессии, а не по вводу)."""
    try:
        password_hash = hash_password(new_password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_pass = ? WHERE telegram_id = ?", (password_hash, int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update password for user {user_id}: {e}")
        return False
