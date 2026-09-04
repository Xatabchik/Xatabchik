"""Пользователи: регистрация, профиль, баланс, бан, UTM-метки и настройки
уведомлений.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import json
import re

__all__ = (
    "get_utm_links",
    "create_utm_link",
    "delete_utm_link",
    "log_utm_visit",
    "set_user_utm_slug_if_absent",
    "get_utm_analytics",
    "is_email_only_user",
    "get_admin_ids",
    "is_admin",
    "register_user_if_not_exists",
    "get_user",
    "get_user_by_username",
    "set_terms_agreed",
    "is_subscription_expiry_notifications_enabled",
    "toggle_subscription_expiry_notifications",
    "get_user_count",
    "set_trial_used",
    "get_all_users",
    "get_users_paginated",
    "ban_user",
    "unban_user",
    "mark_user_unreachable",
    "mark_user_reachable",
    "delete_user_completely",
    "_registration_age_seconds",
    "get_seller_user",
    "get_user_by_email",
    "create_user_by_email",
)


def get_utm_links(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM utm_links"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get utm links: {e}")
        return []


def create_utm_link(
    slug: str,
    *,
    source: str | None = None,
    medium: str | None = None,
    campaign: str | None = None,
    content: str | None = None,
    term: str | None = None,
    label: str | None = None,
    comment: str | None = None,
    budget: float | None = None,
    created_by: int | None = None,
) -> bool:
    slug_s = re.sub(r"[^a-zA-Z0-9_\-]", "", (slug or "").strip())
    if not slug_s:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO utm_links (slug, source, medium, campaign, content, term, label, comment, budget, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (slug_s, source, medium, campaign, content, term, label, comment,
                 float(budget) if budget is not None else None, created_by),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        logging.error(f"Failed to create utm link '{slug_s}': {e}")
        return False


def delete_utm_link(slug: str) -> bool:
    """Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits)."""
    slug_s = (slug or "").strip()
    if not slug_s:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM utm_visits WHERE slug = ?", (slug_s,))
            cursor.execute("DELETE FROM utm_links WHERE slug = ?", (slug_s,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete utm link '{slug_s}': {e}")
        return False


def log_utm_visit(slug: str, user_id: int | None, event_type: str) -> None:
    """Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO utm_visits (slug, user_id, event_type) VALUES (?, ?, ?)",
                ((slug or "").strip(), user_id, (event_type or "").strip()),
            )
            conn.commit()
    except Exception as e:
        logging.warning(f"log_utm_visit failed for slug={slug}: {e}")


def set_user_utm_slug_if_absent(user_id: int, slug: str) -> bool:
    """First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET utm_slug = ? WHERE telegram_id = ? AND (utm_slug IS NULL OR utm_slug = '')",
                ((slug or "").strip(), int(user_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set utm_slug for user {user_id}: {e}")
        return False


def get_utm_analytics() -> list[dict]:
    """Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget)."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            links = [dict(r) for r in cursor.execute("SELECT * FROM utm_links ORDER BY created_at DESC").fetchall()]

            cursor.execute("SELECT slug, COUNT(*) FROM utm_visits WHERE event_type = 'start' GROUP BY slug")
            clicks_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT utm_slug, COUNT(*) FROM users WHERE utm_slug IS NOT NULL AND utm_slug <> '' GROUP BY utm_slug")
            regs_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                f"""
                SELECT u.utm_slug, COUNT(*), COALESCE(SUM(t.amount_rub), 0)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.utm_slug IS NOT NULL AND u.utm_slug <> '' AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                GROUP BY u.utm_slug
                """
            )
            payments_map = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            for link in links:
                slug = link["slug"]
                clicks = int(clicks_map.get(slug, 0))
                regs = int(regs_map.get(slug, 0))
                pays_cnt, pays_sum = payments_map.get(slug, (0, 0.0))
                link["clicks"] = clicks
                link["registrations"] = regs
                link["payments"] = int(pays_cnt or 0)
                link["revenue"] = float(pays_sum or 0.0)
                budget = link.get("budget")
                link["roi_pct"] = ((link["revenue"] - budget) / budget * 100.0) if budget else None
                result.append(link)

            result.sort(key=lambda l: l["revenue"], reverse=True)
    except sqlite3.Error as e:
        logging.error(f"Failed to get utm analytics: {e}")
    return result


def is_email_only_user(telegram_id: int | None) -> bool:
    """True, если пользователь зарегистрирован по email и ещё не авторизовался
    через Telegram (синтетический telegram_id с префиксом 999)."""
    try:
        tid = int(telegram_id)
    except (TypeError, ValueError):
        return False
    return EMAIL_ONLY_TELEGRAM_ID_MIN <= tid <= EMAIL_ONLY_TELEGRAM_ID_MAX

def get_admin_ids() -> set[int]:
    """Возвращает множество ID администраторов из настроек.
    Поддерживает оба варианта: одиночный 'admin_telegram_id' и список 'admin_telegram_ids'
    через запятую/пробелы или JSON-массив.
    """
    ids: set[int] = set()
    try:
        single = get_setting("admin_telegram_id")
        if single:
            try:
                ids.add(int(single))
            except Exception:
                pass
        multi_raw = get_setting("admin_telegram_ids")
        if multi_raw:
            s = (multi_raw or "").strip()

            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    for v in arr:
                        try:
                            ids.add(int(v))
                        except Exception:
                            pass
                    return ids
            except Exception:
                pass

            parts = [p for p in re.split(r"[\s,]+", s) if p]
            for p in parts:
                try:
                    ids.add(int(p))
                except Exception:
                    pass
    except Exception as e:
        logging.warning(f"get_admin_ids failed: {e}")
    return ids

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора по списку ID из настроек."""
    try:
        return int(user_id) in get_admin_ids()
    except Exception:
        return False


def register_user_if_not_exists(telegram_id: int, username: str, referrer_id):
    """Зарегистрировать пользователя, если его ещё нет.

    ``referred_by`` выставляется только на INSERT. Уже существующая строка
    обновляет username и никогда не late-bind'ит реферера — иначе любой
    ``/start ref_<id>`` мог привязать аккаунт, у которого поле ещё пустое.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if not row:

                cursor.execute(
                    "INSERT INTO users (telegram_id, username, registration_date, referred_by) VALUES (?, ?, ?, ?)",
                    (telegram_id, username, datetime.now(), referrer_id)
                )
            else:

                cursor.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to register user {telegram_id}: {e}")

def get_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user {telegram_id}: {e}")
        return None


def get_user_by_username(username: str):
    """Возвращает пользователя по username (без @), регистр не важен."""
    try:
        uname = (username or "").lstrip("@").strip()
        if not uname:
            return None
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) LIMIT 1", (uname,))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("DB: get_user_by_username failed: %s", e)
        return None

def set_terms_agreed(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET agreed_to_terms = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Пользователь {telegram_id} согласился с условиями.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")

def is_subscription_expiry_notifications_enabled(telegram_id: int) -> bool:
    """Проверить, включены ли уведомления об истечении срока ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subscription_expiry_notifications_enabled FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return True  # По умолчанию включены
            return bool(row[0])
    except sqlite3.Error as e:
        logging.error(f"Failed to check notification status for user {telegram_id}: {e}")
        return True  # По умолчанию включены при ошибке

def toggle_subscription_expiry_notifications(telegram_id: int) -> bool:
    """Переключить статус уведомлений об истечении срока. Возвращает новое состояние."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Получаем текущее состояние
            cursor.execute(
                "SELECT subscription_expiry_notifications_enabled FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            current_state = row[0] if row else 1
            new_state = 1 - current_state  # Переключаем
            
            # Обновляем
            cursor.execute(
                "UPDATE users SET subscription_expiry_notifications_enabled = ? WHERE telegram_id = ?",
                (new_state, telegram_id)
            )
            conn.commit()
            logging.info(f"Пользователь {telegram_id}: уведомления об истечении ключей {'включены' if new_state else 'отключены'}")
            return bool(new_state)
    except sqlite3.Error as e:
        logging.error(f"Failed to toggle notification status for user {telegram_id}: {e}")
        return True

def get_user_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get user count: {e}")
        return 0

def set_trial_used(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET trial_used = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Trial period marked as used for user {telegram_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set trial used for user {telegram_id}: {e}")


def get_all_users() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY registration_date DESC")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all users: {e}")
        return []

def get_users_paginated(
    page: int = 1,
    per_page: int = 30,
    q: str | None = None,
    *,
    sort: str | None = None,
) -> tuple[list[dict], int]:
    """Вернуть пользователей постранично и общее количество (с учётом фильтра).

    Фильтр q ищет по username (LIKE) и по текстовому представлению telegram_id.
    """
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 30))
    offset = (page - 1) * per_page

    sort_key = (sort or "").strip().lower()
    order_by = "u.registration_date DESC"
    if sort_key in ("balance", "balance_desc"):
        order_by = "COALESCE(u.balance, 0) DESC, u.registration_date DESC"
    elif sort_key in ("balance_asc",):
        order_by = "COALESCE(u.balance, 0) ASC, u.registration_date DESC"
    elif sort_key in ("referral_balance", "referral_balance_desc"):
        order_by = "COALESCE(u.referral_balance, 0) DESC, u.registration_date DESC"
    elif sort_key in ("referral_balance_asc",):
        order_by = "COALESCE(u.referral_balance, 0) ASC, u.registration_date DESC"
    elif sort_key in ("active_keys", "active_keys_desc"):
        order_by = "active_keys_count DESC, u.registration_date DESC"
    elif sort_key in ("active_keys_asc",):
        order_by = "active_keys_count ASC, u.registration_date DESC"
    elif sort_key in ("total_spent", "total_spent_desc", "spent", "spent_desc"):
        order_by = "COALESCE(u.total_spent, 0) DESC, u.registration_date DESC"
    elif sort_key in ("total_spent_asc", "spent_asc"):
        order_by = "COALESCE(u.total_spent, 0) ASC, u.registration_date DESC"
    elif sort_key in ("registration_date", "registration_date_desc", "reg_desc"):
        order_by = "u.registration_date DESC"
    elif sort_key in ("registration_date_asc", "reg_asc"):
        order_by = "u.registration_date ASC"
    elif sort_key in ("telegram_id", "telegram_id_desc", "id_desc"):
        order_by = "u.telegram_id DESC"
    elif sort_key in ("telegram_id_asc", "id_asc"):
        order_by = "u.telegram_id ASC"
    elif sort_key in ("username", "username_desc"):
        order_by = "LOWER(COALESCE(u.username, '')) DESC, u.registration_date DESC"
    elif sort_key in ("username_asc",):
        order_by = "LOWER(COALESCE(u.username, '')) ASC, u.registration_date DESC"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if q:
                q_like = f"%{q.strip()}%"

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE (username LIKE ?)
                       OR (CAST(telegram_id AS TEXT) LIKE ?)
                    """,
                    (q_like, q_like),
                )
                total = cursor.fetchone()[0] or 0

                cursor.execute(
                    f"""
                    SELECT
                        u.*,
                        COUNT(k.key_id) AS keys_count,
                        COALESCE(SUM(
                            CASE
                                WHEN k.key_id IS NOT NULL
                                 AND k.missing_from_server_at IS NULL
                                 AND k.expire_at IS NOT NULL
                                 AND datetime(k.expire_at) > CURRENT_TIMESTAMP
                                THEN 1 ELSE 0
                            END
                        ), 0) AS active_keys_count
                    FROM users u
                    LEFT JOIN vpn_keys k ON k.user_id = u.telegram_id
                    WHERE (u.username LIKE ?)
                       OR (CAST(u.telegram_id AS TEXT) LIKE ?)
                    GROUP BY u.telegram_id
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    (q_like, q_like, per_page, offset),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM users")
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    f"""
                    SELECT
                        u.*,
                        COUNT(k.key_id) AS keys_count,
                        COALESCE(SUM(
                            CASE
                                WHEN k.key_id IS NOT NULL
                                 AND k.missing_from_server_at IS NULL
                                 AND k.expire_at IS NOT NULL
                                 AND datetime(k.expire_at) > CURRENT_TIMESTAMP
                                THEN 1 ELSE 0
                            END
                        ), 0) AS active_keys_count
                    FROM users u
                    LEFT JOIN vpn_keys k ON k.user_id = u.telegram_id
                    GROUP BY u.telegram_id
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    (per_page, offset),
                )
            users = [dict(row) for row in cursor.fetchall()]
            return users, total
    except sqlite3.Error as e:
        logging.error(f"Failed to get users paginated: {e}")
        return [], 0

def ban_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to ban user {telegram_id}: {e}")

def unban_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 0 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to unban user {telegram_id}: {e}")

def mark_user_unreachable(telegram_id: int, reason: str) -> bool:
    """Отметить пользователя как недоступного в Telegram.

    `reason` — 'blocked' (заблокировал бота) или 'deactivated' (аккаунт удалён/деактивирован).
    Пользователь будет исключён из последующих рассылок, пока не напишет боту снова
    (см. mark_user_reachable — вызывается автоматически при любом входящем сообщении/callback).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_unreachable = 1,
                    unreachable_reason = ?,
                    unreachable_since = COALESCE(unreachable_since, CURRENT_TIMESTAMP)
                WHERE telegram_id = ?
                """,
                (reason, int(telegram_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to mark user {telegram_id} unreachable: {e}")
        return False

def mark_user_reachable(telegram_id: int) -> bool:
    """Снять отметку недоступности — пользователь снова взаимодействовал с ботом
    (значит, разблокировал его или его аккаунт снова активен)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_unreachable = 0, unreachable_reason = NULL, unreachable_since = NULL
                WHERE telegram_id = ? AND is_unreachable = 1
                """,
                (int(telegram_id),),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to mark user {telegram_id} reachable: {e}")
        return False


def delete_user_completely(user_id: int) -> bool:
    """Полностью удалить пользователя и все связанные с ним данные.

    :param user_id: Telegram ID пользователя (users.telegram_id, а также user_id в связанных таблицах).
    :return: True при успешном удалении, False при ошибке.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Сначала удалить сообщения поддержки по тикетам пользователя
            cursor.execute(
                "SELECT ticket_id FROM support_tickets WHERE user_id = ?",
                (user_id,),
            )
            support_ticket_ids = [int(row[0]) for row in cursor.fetchall() if row and row[0]]
            cursor.execute(
                """
                DELETE FROM support_messages
                WHERE ticket_id IN (
                    SELECT ticket_id FROM support_tickets WHERE user_id = ?
                )
                """,
                (user_id,),
            )

            # Удалить тикеты поддержки
            cursor.execute(
                "DELETE FROM support_tickets WHERE user_id = ?",
                (user_id,),
            )

            # Удалить неактивированные подарки, привязанные к ключам пользователя
            cursor.execute(
                """
                DELETE FROM user_gifts
                WHERE is_activated = 0 AND key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)
                """,
                (user_id,),
            )

            # Удалить мониторинг использования ключей (иначе останутся "осиротевшие"
            # записи, ссылающиеся на уже удалённые key_id ниже)
            cursor.execute(
                "DELETE FROM key_usage_monitor WHERE key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)",
                (user_id,),
            )

            # Удалить VPN-ключи пользователя
            cursor.execute(
                "DELETE FROM vpn_keys WHERE user_id = ?",
                (user_id,),
            )

            # Удалить записи о платёжных заявках и транзакциях
            cursor.execute(
                "DELETE FROM pending_transactions WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM transactions WHERE user_id = ?",
                (user_id,),
            )

            # Удалить историю по подарочным токенам и промокодам
            cursor.execute(
                "DELETE FROM gift_token_claims WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM promo_code_usages WHERE user_id = ?",
                (user_id,),
            )

            # Методы получения удаляем (это сохранённые реквизиты пользователя).
            # Заявки на вывод оставляем: у админа должна остаться история выплат
            # и незакрытые заявки, по которым сумма уже списана с реф. баланса.
            cursor.execute(
                "DELETE FROM referral_payout_methods WHERE user_id = ?",
                (user_id,),
            )

            # Удалить просроченные/неиспользованные заявки на вход через webapp
            cursor.execute(
                "DELETE FROM webapp_auth_requests WHERE user_id = ?",
                (user_id,),
            )

            # Удалить статус и историю прохождения капчи — иначе при повторной
            # регистрации того же telegram_id (после "удаления") has_passed_captcha()
            # найдёт старую запись и капча будет молча пропущена.
            cursor.execute(
                "DELETE FROM user_captcha_status WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM captcha_challenges WHERE user_id = ?",
                (user_id,),
            )

            # Обнулить ссылки на этого пользователя как реферала
            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                (user_id,),
            )

            # Удалить самого пользователя (по telegram_id)
            cursor.execute(
                "DELETE FROM users WHERE telegram_id = ?",
                (user_id,),
            )

            conn.commit()
            for ticket_id in support_ticket_ids:
                _cleanup_ticket_media(ticket_id)
            logger.info("User %s fully deleted with all related data", user_id)
            return True
    except sqlite3.Error as e:
        logger.error("Failed to delete user %s completely: %s", user_id, e)
        return False


def _registration_age_seconds(reg_date_raw) -> float | None:
    """Возраст аккаунта в секундах, либо None если даты нет / она не парсится."""
    if not reg_date_raw:
        return None
    try:
        reg_dt = datetime.fromisoformat(str(reg_date_raw).replace("Z", "+00:00"))
        if reg_dt.tzinfo is not None:
            reg_dt = reg_dt.replace(tzinfo=None)
        return (datetime.now() - reg_dt).total_seconds()
    except Exception:
        return None


def get_seller_user(user_id: int) -> dict | None:
    """Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя.

    В текущей версии проекта отдельной "seller"-подсистемы нет (есть колонки-заглушки
    users.seller_active/seller_sale, по умолчанию выключены), функция возвращает
    запись пользователя, если seller_active включён вручную в БД, иначе None.
    """
    try:
        user = get_user(user_id)
        if user and user.get('seller_active'):
            return user
        return None
    except Exception as e:
        logger.error(f"Failed to get seller user {user_id}: {e}")
        return None


def get_user_by_email(email: str) -> dict | None:
    """Найти локального пользователя webapp по email (для входа по email+паролю)."""
    norm = _normalize_email(email)
    if not norm:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE auth_email = ?", (norm,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user by email {email}: {e}")
        return None


def create_user_by_email(email: str, password: str) -> dict | None:
    """Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю.

    Использует псевдо-telegram_id с префиксом 999, чтобы не пересекаться с реальными
    Telegram ID (см. handlers.py: str(user_id).startswith("999") — признак несинхронизированного аккаунта).
    Пароль сохраняется в виде хэша (см. hash_password/verify_password).
    Аккаунт создаётся неподтверждённым (email_verified=0) до прохождения проверки кода.
    """
    norm = _normalize_email(email)
    if not norm:
        return None
    try:
        password_hash = hash_password(password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT MAX(telegram_id) FROM users WHERE telegram_id BETWEEN ? AND ?",
                (EMAIL_ONLY_TELEGRAM_ID_MIN, EMAIL_ONLY_TELEGRAM_ID_MAX),
            )
            row = cur.fetchone()
            next_id = int(row[0]) + 1 if row and row[0] else EMAIL_ONLY_TELEGRAM_ID_MIN + 1
            cur.execute(
                """
                INSERT INTO users (telegram_id, username, agreed_to_terms, auth_email, auth_pass, email_verified, registration_date)
                VALUES (?, ?, 1, ?, ?, 0, CURRENT_TIMESTAMP)
                """,
                (next_id, norm.split('@')[0], norm, password_hash),
            )
            conn.commit()
        return get_user(next_id)
    except Exception as e:
        logger.error(f"Failed to create user by email {email}: {e}")
        return None
