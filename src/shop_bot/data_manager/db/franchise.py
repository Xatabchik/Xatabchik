"""Франшиза и партнёрские клоны бота: настройки клонов, кабинет партнёра и выводы.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
import hashlib
import hmac
import json

__all__ = (
    "REFERRAL_WITHDRAWAL_STATUSES",
    "REFERRAL_PAYOUT_METHOD_LABELS",
    "REFERRAL_WITHDRAW_METHOD_SETTINGS",
    "MAX_OPEN_REFERRAL_WITHDRAWAL_REQUESTS",
    "is_referral_withdraw_method_type_enabled",
    "format_referral_withdrawal_admin_notice",
    "create_referral_withdrawal_request",
    "has_open_referral_withdrawal_request",
    "list_referral_withdrawal_requests",
    "get_referral_withdrawal_request",
    "update_referral_withdrawal_request_status",
    "get_referral_withdrawable_stats",
    "get_franchise_percent_default",
    "get_franchise_min_withdraw",
    "resolve_factory_bot_id",
    "_managed_bot_token_pad",
    "_row_with_decrypted_token",
    "get_managed_bot",
    "get_managed_bot_by_telegram_id",
    "list_active_managed_bots",
    "update_managed_bot_active",
    "get_managed_bots_by_owner",
    "purge_managed_bot_stats",
    "_purge_managed_bot_stats_on_cursor",
    "delete_managed_bot",
    "get_factory_cabinet",
    "create_managed_bot",
    "record_factory_activity",
    "_is_card_payment_method",
    "accrue_partner_commission",
    "get_partner_cabinet",
    "list_partner_requisites",
    "get_default_partner_requisite",
    "add_partner_requisite",
    "set_default_partner_requisite",
    "delete_partner_requisite",
    "create_withdraw_request",
)


REFERRAL_WITHDRAWAL_STATUSES = ("new", "processing", "paid", "rejected")
REFERRAL_PAYOUT_METHOD_LABELS = {"sbp": "СБП", "card": "Номер карты", "usdt_trc20": "USDT TRC20"}
REFERRAL_WITHDRAW_METHOD_SETTINGS = {
    "sbp": "referral_withdraw_sbp_enabled",
    "card": "referral_withdraw_card_enabled",
    "usdt_trc20": "referral_withdraw_usdt_enabled",
}
MAX_OPEN_REFERRAL_WITHDRAWAL_REQUESTS = 1


def is_referral_withdraw_method_type_enabled(method_type: str) -> bool:
    setting_key = REFERRAL_WITHDRAW_METHOD_SETTINGS.get((method_type or "").strip().lower())
    if not setting_key:
        return False
    return _referral_setting_is_true(setting_key)


def format_referral_withdrawal_admin_notice(
    *,
    request_id: int,
    user_id: int,
    username: str | None,
    amount: float,
    method_type: str | None,
    bank_name: str | None,
    requisite_value: str | None,
) -> str:
    """Текст уведомления админам о новой заявке на вывод."""
    from html import escape as html_escape

    label = REFERRAL_PAYOUT_METHOD_LABELS.get(method_type, method_type or "—")
    bank_line = f"{html_escape(str(bank_name))} — " if bank_name else ""
    requisite = html_escape(str(requisite_value or ""))
    uname = f"@{html_escape(str(username))}" if username else str(int(user_id))
    return (
        "💸 <b>Новая заявка на вывод (реферальная программа)</b>\n"
        f"Заявка: #{int(request_id)}\n"
        f"Пользователь: {uname} (<code>{int(user_id)}</code>)\n"
        f"Сумма: <b>{float(amount):.2f} ₽</b>\n"
        f"Способ: {html_escape(str(label))}\n"
        f"Реквизиты: {bank_line}<code>{requisite}</code>"
    )


def create_referral_withdrawal_request(user_id: int, amount: float, method_id: int) -> tuple[bool, str, int | None]:
    """Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод."""
    raw_enabled = str(get_setting("referral_withdraw_enabled") or "false").strip().lower()
    if raw_enabled not in {"1", "true", "yes", "on", "y"}:
        return False, "Вывод средств временно недоступен.", None
    try:
        amount = float(amount or 0)
    except Exception:
        return False, "Некорректная сумма.", None
    if amount <= 0:
        return False, "Некорректная сумма.", None
    try:
        min_withdraw = float(get_setting("minimum_withdrawal") or 100)
    except Exception:
        min_withdraw = 100.0
    if amount < min_withdraw:
        return False, f"Минимальная сумма для вывода — {min_withdraw:.0f} ₽", None
    method = get_referral_payout_method(method_id, user_id)
    if not method:
        return False, "Метод получения не найден.", None
    method_type = (method.get("method_type") or "").strip().lower()
    if not is_referral_withdraw_method_type_enabled(method_type):
        return False, "Этот способ получения временно недоступен.", None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                """
                SELECT COUNT(*) FROM referral_withdrawal_requests
                WHERE user_id = ? AND status IN ('new', 'processing')
                """,
                (int(user_id),),
            )
            open_count = int((cursor.fetchone() or [0])[0] or 0)
            if open_count >= MAX_OPEN_REFERRAL_WITHDRAWAL_REQUESTS:
                conn.rollback()
                return False, "У вас уже есть заявка на вывод. Дождитесь её обработки.", None
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cursor.fetchone()
            current = float(row[0] or 0.0) if row else 0.0
            if current < amount:
                conn.rollback()
                return False, "Сумма в заявке превышает остаток на реферальном балансе.", None
            cursor.execute(
                "UPDATE users SET referral_balance = referral_balance - ? WHERE telegram_id = ?",
                (amount, int(user_id)),
            )
            cursor.execute(
                """
                INSERT INTO referral_withdrawal_requests (user_id, amount, method_type, bank_name, requisite_value, status)
                VALUES (?, ?, ?, ?, ?, 'new')
                """,
                (int(user_id), amount, method.get("method_type"), method.get("bank_name"), method.get("requisite_value")),
            )
            new_id = cursor.lastrowid
            conn.commit()
            return True, "Заявка на вывод создана.", int(new_id)
    except sqlite3.Error as e:
        logging.error(f"Failed to create referral withdrawal request for {user_id}: {e}")
        return False, "Ошибка базы данных.", None


def has_open_referral_withdrawal_request(user_id: int) -> bool:
    """Есть ли у пользователя незакрытая заявка (new/processing)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1 FROM referral_withdrawal_requests
                WHERE user_id = ? AND status IN ('new', 'processing')
                LIMIT 1
                """,
                (int(user_id),),
            )
            return cur.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Failed to check open referral withdrawal for {user_id}: {e}")
        return False


def list_referral_withdrawal_requests(status: str | None = None, user_id: int | None = None) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = """
                SELECT r.*, u.username AS username
                FROM referral_withdrawal_requests r
                LEFT JOIN users u ON u.telegram_id = r.user_id
            """
            conditions: list[str] = []
            params: list = []
            if status:
                conditions.append("r.status = ?")
                params.append(status)
            if user_id is not None:
                conditions.append("r.user_id = ?")
                params.append(int(user_id))
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY r.created_at DESC"
            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list referral withdrawal requests: {e}")
        return []


def get_referral_withdrawal_request(request_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.*, u.username AS username
                FROM referral_withdrawal_requests r
                LEFT JOIN users u ON u.telegram_id = r.user_id
                WHERE r.id = ?
                """,
                (int(request_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral withdrawal request {request_id}: {e}")
        return None


def update_referral_withdrawal_request_status(request_id: int, new_status: str, *, reject_reason: str | None = None) -> tuple[bool, str, dict | None]:
    """Меняет статус заявки на вывод.

    - 'paid': сумма уже была списана с referral_balance при создании заявки; дополнительно
      списывается та же сумма из общего дохода бота — созданием отрицательной "технической"
      транзакции (status='paid', payment_method='referral_payout'), чтобы доходы/аналитика
      (которые считаются как SUM(amount_rub) по успешным транзакциям) автоматически уменьшились
      без рассинхронизации данных.
    - 'rejected': сумма возвращается обратно на referral_balance пользователя.
    """
    new_status = (new_status or "").strip().lower()
    if new_status not in REFERRAL_WITHDRAWAL_STATUSES:
        return False, "Некорректный статус.", None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT * FROM referral_withdrawal_requests WHERE id = ?", (int(request_id),))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "Заявка не найдена.", None
            cols = [d[0] for d in cursor.description]
            req = dict(zip(cols, row))
            current_status = req.get("status")

            if current_status in ("paid", "rejected"):
                conn.rollback()
                return False, f"Заявка уже в финальном статусе «{current_status}».", None

            if new_status == "rejected":
                cursor.execute(
                    "UPDATE users SET referral_balance = COALESCE(referral_balance, 0) + ? WHERE telegram_id = ?",
                    (float(req["amount"]), int(req["user_id"])),
                )
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = 'rejected', reject_reason = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reject_reason, int(request_id)),
                )
            elif new_status == "paid":
                username = None
                try:
                    cursor.execute("SELECT username FROM users WHERE telegram_id = ?", (int(req["user_id"]),))
                    u = cursor.fetchone()
                    username = u[0] if u else None
                except Exception:
                    username = None
                meta = json.dumps({
                    "action": "referral_payout",
                    "withdrawal_request_id": int(request_id),
                    "method_type": req.get("method_type"),
                    "bank_name": req.get("bank_name"),
                    "requisite_value": req.get("requisite_value"),
                })
                cursor.execute(
                    """
                    INSERT INTO transactions (username, payment_id, user_id, status, amount_rub, payment_method, metadata)
                    VALUES (?, ?, ?, 'paid', ?, 'referral_payout', ?)
                    """,
                    (username, f"refpayout:{request_id}", int(req["user_id"]), -float(req["amount"]), meta),
                )
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = 'paid', processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(request_id),),
                )
            else:
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = ? WHERE id = ?",
                    (new_status, int(request_id)),
                )

            conn.commit()

        updated = get_referral_withdrawal_request(request_id)
        return True, "Статус заявки обновлён.", updated
    except sqlite3.Error as e:
        logging.error(f"Failed to update referral withdrawal request {request_id}: {e}")
        return False, "Ошибка базы данных.", None


def get_referral_withdrawable_stats() -> dict:
    """Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы."""
    out = {"new": 0, "processing": 0, "paid": 0, "rejected": 0, "new_amount": 0.0, "processing_amount": 0.0, "paid_amount": 0.0}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(*), COALESCE(SUM(amount),0) FROM referral_withdrawal_requests GROUP BY status")
            for status, cnt, amt in cur.fetchall() or []:
                if status in out or f"{status}_amount" in out:
                    out[status] = int(cnt or 0)
                    out[f"{status}_amount"] = float(amt or 0.0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral withdrawable stats: {e}")
    return out

# =============================
# Franchise (managed clone bots)
# =============================

# Константы больше не используются, значения берутся из настроек
# DEPRECATED: FRANCHISE_PERCENT_DEFAULT = 35.0
# DEPRECATED: FRANCHISE_MIN_WITHDRAW_RUB = 1500.0

def get_franchise_percent_default() -> float:
    """Получить процент комиссии франшизы из настроек."""
    try:
        val = (get_setting('franchise_commission_percent') or '35.0').strip()
        return float(val)
    except Exception:
        return 35.0


def get_franchise_min_withdraw() -> float:
    """Получить минимум для вывода франшизников из настроек."""
    try:
        val = (get_setting('franchise_min_withdraw_rub') or '1500.0').strip()
        return float(val)
    except Exception:
        return 1500.0


def resolve_factory_bot_id(telegram_bot_user_id: int | None) -> int:
    """Return internal managed bot id for a Telegram bot user id.

    Root (main) bot => 0.
    """
    try:
        tg_id = int(telegram_bot_user_id or 0)
    except Exception:
        return 0
    if tg_id <= 0:
        return 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM managed_bots WHERE telegram_bot_user_id = ? AND COALESCE(is_active,1)=1 LIMIT 1", (tg_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def _managed_bot_token_pad(secret: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hmac.new(secret, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:n])


def _row_with_decrypted_token(row: dict | None) -> dict | None:
    if not row:
        return row
    data = dict(row)
    if data.get("token"):
        data["token"] = decrypt_managed_bot_token(str(data["token"]))
    return data


def get_managed_bot(bot_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE id = ? LIMIT 1", (int(bot_id),))
            row = cur.fetchone()
            return _row_with_decrypted_token(dict(row) if row else None)
    except Exception as e:
        logger.error(f"get_managed_bot failed: {e}")
        return None


def get_managed_bot_by_telegram_id(telegram_bot_user_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE telegram_bot_user_id = ? LIMIT 1", (int(telegram_bot_user_id),))
            row = cur.fetchone()
            return _row_with_decrypted_token(dict(row) if row else None)
    except Exception as e:
        logger.error(f"get_managed_bot_by_telegram_id failed: {e}")
        return None


def list_active_managed_bots() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE COALESCE(is_active,1)=1 ORDER BY id ASC")
            return [_row_with_decrypted_token(dict(r)) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"list_active_managed_bots failed: {e}")
        return []


def update_managed_bot_active(bot_id: int, is_active: int) -> bool:
    """Параметризованно выставить is_active (0/1). Схему таблицы не меняет."""
    try:
        bid = int(bot_id)
        active = 1 if int(is_active) else 0
    except Exception:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE managed_bots SET is_active = ? WHERE id = ?", (active, bid))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"update_managed_bot_active failed: {e}")
        return False


def get_managed_bots_by_owner(owner_telegram_id: int) -> list[dict]:
    """Список клонов владельца без токена (токен не отдаём в UI)."""
    try:
        owner_id = int(owner_telegram_id)
    except Exception:
        return []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, telegram_bot_user_id, username, owner_telegram_id,
                       referrer_bot_id, is_active, created_at
                FROM managed_bots
                WHERE owner_telegram_id = ?
                ORDER BY id DESC
                """,
                (owner_id,),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    except sqlite3.Error as e:
        logger.error(f"get_managed_bots_by_owner failed: {e}")
        return []


def purge_managed_bot_stats(bot_id: int) -> None:
    """Удалить активность и комиссии клона. Идемпотентно, ошибки не пробрасывает."""
    try:
        bid = int(bot_id)
    except Exception:
        return
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            _purge_managed_bot_stats_on_cursor(cur, bid)
            conn.commit()
    except sqlite3.Error as e:
        logger.warning(f"purge_managed_bot_stats failed for bot_id={bot_id}: {e}")


def _purge_managed_bot_stats_on_cursor(cur: sqlite3.Cursor, bot_id: int) -> None:
    cur.execute("DELETE FROM factory_user_activity WHERE bot_id = ?", (bot_id,))
    cur.execute("DELETE FROM partner_commissions WHERE bot_id = ?", (bot_id,))


def delete_managed_bot(bot_id: int, owner_telegram_id: int | None = None) -> bool:
    """Удалить строку managed_bots и статистику клона.

    factory_user_activity и partner_commissions очищаются. Заявки на вывод
    (partner_withdraw_requests), включая approved/paid, сохраняются для аудита.

    Если передан owner_telegram_id — удаляем только при совпадении владельца.
    Сбой очистки статистики не блокирует удаление самой записи.
    """
    try:
        bid = int(bot_id)
    except Exception:
        return False
    owner_id = None
    if owner_telegram_id is not None:
        try:
            owner_id = int(owner_telegram_id)
        except Exception:
            return False
        if owner_id <= 0:
            return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            if owner_id is None:
                cur.execute("SELECT id FROM managed_bots WHERE id = ? LIMIT 1", (bid,))
            else:
                cur.execute(
                    "SELECT id FROM managed_bots WHERE id = ? AND owner_telegram_id = ? LIMIT 1",
                    (bid, owner_id),
                )
            if not cur.fetchone():
                return False
            try:
                _purge_managed_bot_stats_on_cursor(cur, bid)
            except sqlite3.Error as e:
                logger.warning(f"purge_managed_bot_stats failed for bot_id={bid}: {e}")
            if owner_id is None:
                cur.execute("DELETE FROM managed_bots WHERE id = ?", (bid,))
            else:
                cur.execute(
                    "DELETE FROM managed_bots WHERE id = ? AND owner_telegram_id = ?",
                    (bid, owner_id),
                )
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"delete_managed_bot failed: {e}")
        return False


def get_factory_cabinet(bot_id: int) -> dict:
    """Статистика кабинета клона (пользователи/сообщения/прямые клоны/баланс)."""
    partner = get_partner_cabinet(bot_id)
    res = {
        "total_users": int(partner.get("total_users") or 0),
        "total_messages": 0,
        "direct_bots": 0,
        "balance": float(partner.get("available") or 0.0),
        "gross_paid_card": float(partner.get("gross_paid_card") or 0.0),
        "commission_total": float(partner.get("commission_total") or 0.0),
        "available": float(partner.get("available") or 0.0),
    }
    try:
        b = int(bot_id or 0)
    except Exception:
        return res
    if b <= 0:
        return res
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(SUM(messages_count),0) FROM factory_user_activity WHERE bot_id = ?",
                (b,),
            )
            res["total_messages"] = int((cur.fetchone() or [0])[0] or 0)
            cur.execute(
                "SELECT COUNT(1) FROM managed_bots WHERE COALESCE(referrer_bot_id,0) = ?",
                (b,),
            )
            res["direct_bots"] = int((cur.fetchone() or [0])[0] or 0)
    except sqlite3.Error as e:
        logger.error(f"get_factory_cabinet failed: {e}")
    return res


def create_managed_bot(
    *,
    token: str,
    telegram_bot_user_id: int,
    username: str | None,
    owner_telegram_id: int,
    referrer_bot_id: int = 0,
) -> tuple[bool, str, int | None]:
    """Register a managed bot.

    If the telegram bot user id already exists, the current owner may rotate
    token/username. A different user cannot take over ``owner_telegram_id``.
    """
    token_s = encrypt_managed_bot_token((token or "").strip())
    if not token_s:
        return False, "Токен пустой.", None
    try:
        tg_bot_id = int(telegram_bot_user_id)
        owner_id = int(owner_telegram_id)
        ref_bot_id = int(referrer_bot_id or 0)
    except Exception:
        return False, "Некорректные параметры.", None

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            # uniqueness by telegram_bot_user_id
            cur.execute("SELECT id, owner_telegram_id FROM managed_bots WHERE telegram_bot_user_id = ? LIMIT 1", (tg_bot_id,))
            row = cur.fetchone()
            if row:
                bot_id = int(row[0])
                existing_owner = int(row[1] or 0)
                if existing_owner != owner_id:
                    return False, "Этот бот уже зарегистрирован другим владельцем.", None
                # Same owner: allow token rotation. Owner is pinned in WHERE
                # so a concurrent takeover cannot win the UPDATE.
                cur.execute(
                    """
                    UPDATE managed_bots
                    SET token = ?, username = ?, referrer_bot_id = COALESCE(?, referrer_bot_id), is_active = 1
                    WHERE id = ? AND owner_telegram_id = ?
                    """,
                    (token_s, (username or None), ref_bot_id, bot_id, owner_id),
                )
                conn.commit()
                if cur.rowcount <= 0:
                    return False, "Этот бот уже зарегистрирован другим владельцем.", None
                return True, "Бот обновлён.", bot_id

            cur.execute(
                """
                INSERT INTO managed_bots (telegram_bot_user_id, username, token, owner_telegram_id, referrer_bot_id, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (tg_bot_id, (username or None), token_s, owner_id, ref_bot_id),
            )
            conn.commit()
            bot_id = int(cur.lastrowid)
            return True, "Бот создан.", bot_id
    except sqlite3.IntegrityError:
        # Параллельный INSERT с тем же telegram_bot_user_id (UNIQUE).
        return False, "Этот бот уже зарегистрирован другим владельцем.", None
    except sqlite3.Error as e:
        logger.error(f"create_managed_bot failed: {e}")
        return False, "Ошибка БД при создании бота.", None


def record_factory_activity(bot_id: int, user_id: int) -> None:
    """Upsert activity row (unique users + messages count)."""
    try:
        b = int(bot_id or 0)
        u = int(user_id or 0)
    except Exception:
        return
    # Root (main) bot is not tracked as a franchise bot.
    if b <= 0:
        return
    if u <= 0:
        return
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO factory_user_activity (bot_id, user_id, first_seen, last_seen, messages_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(bot_id, user_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    messages_count = COALESCE(messages_count,0) + 1
                """,
                (b, u),
            )
            conn.commit()
    except Exception:
        return


def _is_card_payment_method(method: str | None) -> bool:
    m = (method or "").strip().lower()
    if not m:
        return False
    if m in {"balance", "баланс"}:
        return False
    # Card-like providers (as configured in this project)
    return m in {"yookassa", "platega", "heleket", "yoomoney"}


def accrue_partner_commission(
    bot_id: int,
    payment_id: str,
    user_id: int,
    amount_rub: float,
    payment_method: str | None,
    percent: float | None = None,
) -> bool:
    """Accrue partner commission for a managed bot.

    Only card payments are counted. Internal balance payments are ignored.
    Idempotent by (bot_id, payment_id).
    """
    try:
        b = int(bot_id or 0)
    except Exception:
        b = 0
    if b <= 0:
        return False

    if not _is_card_payment_method(payment_method):
        return False

    pid = (payment_id or "").strip()
    if not pid:
        return False

    try:
        u = int(user_id)
    except Exception:
        return False

    try:
        amt = float(amount_rub)
    except Exception:
        return False
    if amt <= 0:
        return False

    p = float(percent if percent is not None else get_franchise_percent_default())
    if p <= 0:
        return False

    com = round(amt * p / 100.0, 2)
    if com <= 0:
        return False

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()

            # --- Self-purchase guard ---
            # 1. Direct: buyer == owner of this bot
            # 2. Indirect: buyer was referred by the owner (owner recruited their own customer)
            # 3. Referrer-bot chain: buyer == owner of the parent bot that created this bot
            cur.execute(
                "SELECT owner_telegram_id, COALESCE(referrer_bot_id, 0) FROM managed_bots WHERE id = ? LIMIT 1",
                (b,),
            )
            row = cur.fetchone()
            if row:
                owner_id = int(row[0] or 0)
                referrer_bot_id = int(row[1] or 0)

                if owner_id and u == owner_id:
                    logging.warning(
                        "accrue_partner_commission: skipped — self-purchase (user %d == owner %d, bot %d)",
                        u, owner_id, b,
                    )
                    return False

                # Check if buyer was referred by the owner
                cur.execute("SELECT referred_by FROM users WHERE telegram_id = ? LIMIT 1", (u,))
                user_row = cur.fetchone()
                referred_by = int((user_row[0] or 0)) if user_row else 0
                if owner_id and referred_by == owner_id:
                    logging.warning(
                        "accrue_partner_commission: skipped — buyer %d referred by owner %d (bot %d)",
                        u, owner_id, b,
                    )
                    return False

                # Check if buyer is the owner of the referrer/parent bot
                if referrer_bot_id > 0:
                    cur.execute(
                        "SELECT owner_telegram_id FROM managed_bots WHERE id = ? LIMIT 1",
                        (referrer_bot_id,),
                    )
                    ref_row = cur.fetchone()
                    ref_owner_id = int((ref_row[0] or 0)) if ref_row else 0
                    if ref_owner_id and u == ref_owner_id:
                        logging.warning(
                            "accrue_partner_commission: skipped — buyer %d is owner of referrer bot %d (bot %d)",
                            u, referrer_bot_id, b,
                        )
                        return False

            cur.execute(
                """
                INSERT OR IGNORE INTO partner_commissions
                (bot_id, payment_id, user_id, amount_rub, commission_percent, commission_rub, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (b, pid, u, amt, p, com, (payment_method or None)),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"accrue_partner_commission failed: {e}")
        return False


def get_partner_cabinet(bot_id: int) -> dict:
    """Return partner cabinet stats for managed bot."""
    try:
        b = int(bot_id or 0)
    except Exception:
        b = 0
    res = {
        "total_users": 0,
        "gross_paid_card": 0.0,
        "commission_total": 0.0,
        "commission_percent": get_franchise_percent_default(),
        "requested_withdraw": 0.0,
        "available": 0.0,
    }
    if b <= 0:
        return res

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(1) FROM factory_user_activity WHERE bot_id = ?", (b,))
            res["total_users"] = int(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(amount_rub),0), COALESCE(SUM(commission_rub),0) FROM partner_commissions WHERE bot_id = ?", (b,))
            row = cur.fetchone() or (0, 0)
            res["gross_paid_card"] = float(row[0] or 0)
            res["commission_total"] = float(row[1] or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(amount_rub),0)
                FROM partner_withdraw_requests
                WHERE bot_id = ? AND status IN ('pending','approved','paid')
                """,
                (b,),
            )
            res["requested_withdraw"] = float(cur.fetchone()[0] or 0)

        res["available"] = max(0.0, float(res["commission_total"]) - float(res["requested_withdraw"]))
        return res
    except Exception as e:
        logger.error(f"get_partner_cabinet failed: {e}")
        return res




def list_partner_requisites(bot_id: int, owner_telegram_id: int) -> list[dict]:
    """Return all payout requisites for a partner (owner) within a managed bot."""
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return []
    if b <= 0 or owner <= 0:
        return []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, bot_id, owner_telegram_id, bank, requisite_type, requisite_value, is_default, created_at "
                "FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ? "
                "ORDER BY is_default DESC, created_at DESC",
                (b, owner),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.error(f"list_partner_requisites failed: {e}")
        return []


def get_default_partner_requisite(bot_id: int, owner_telegram_id: int) -> dict | None:
    """Return the default payout requisite for a partner, if any."""
    items = list_partner_requisites(bot_id, owner_telegram_id)
    for r in items:
        try:
            if int(r.get('is_default') or 0) == 1:
                return r
        except Exception:
            continue
    return items[0] if items else None


def add_partner_requisite(
    bot_id: int,
    owner_telegram_id: int,
    bank: str,
    requisite_value: str,
    requisite_type: str,
    *,
    make_default: bool | None = None,
) -> tuple[bool, str, int | None]:
    """Add a payout requisite for a partner.

    requisite_type: 'card' or 'phone'
    """
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.', None

    bank_s = (bank or '').strip()
    value_s = (requisite_value or '').strip()
    rtype = (requisite_type or '').strip().lower()

    if b <= 0 or owner <= 0:
        return False, 'Некорректные данные.', None
    if not bank_s or len(bank_s) > 120:
        return False, 'Укажите банк (до 120 символов).', None
    if not value_s or len(value_s) > 64:
        return False, 'Укажите корректные реквизиты.', None
    if rtype not in {'card', 'phone'}:
        rtype = 'card'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # If it's the first one - force default
            cur.execute(
                "SELECT COUNT(1) FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ?",
                (b, owner),
            )
            count = int((cur.fetchone() or [0])[0] or 0)
            if count == 0:
                make_def = True
            elif make_default is None:
                make_def = False
            else:
                make_def = bool(make_default)

            if make_def:
                cur.execute(
                    "UPDATE partner_payout_requisites SET is_default = 0 WHERE bot_id = ? AND owner_telegram_id = ?",
                    (b, owner),
                )

            cur.execute(
                "INSERT INTO partner_payout_requisites (bot_id, owner_telegram_id, bank, requisite_type, requisite_value, is_default) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (b, owner, bank_s, rtype, value_s, 1 if make_def else 0),
            )
            new_id = int(cur.lastrowid or 0)
            conn.commit()

        return True, 'Реквизиты добавлены.', (new_id if new_id > 0 else None)
    except Exception as e:
        logger.error(f"add_partner_requisite failed: {e}")
        return False, 'Ошибка при сохранении реквизитов.', None


def set_default_partner_requisite(req_id: int, bot_id: int, owner_telegram_id: int) -> tuple[bool, str]:
    """Set given requisite as default for this bot/owner."""
    try:
        rid = int(req_id or 0)
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.'
    if rid <= 0 or b <= 0 or owner <= 0:
        return False, 'Некорректные данные.'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )
            row = cur.fetchone()
            if not row:
                return False, 'Реквизиты не найдены.'

            cur.execute(
                "UPDATE partner_payout_requisites SET is_default = 0 WHERE bot_id = ? AND owner_telegram_id = ?",
                (b, owner),
            )
            cur.execute(
                "UPDATE partner_payout_requisites SET is_default = 1 WHERE id = ?",
                (rid,),
            )
            conn.commit()
        return True, 'Основные реквизиты обновлены.'
    except Exception as e:
        logger.error(f"set_default_partner_requisite failed: {e}")
        return False, 'Ошибка при обновлении.'


def delete_partner_requisite(req_id: int, bot_id: int, owner_telegram_id: int) -> tuple[bool, str]:
    """Delete a payout requisite."""
    try:
        rid = int(req_id or 0)
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.'
    if rid <= 0 or b <= 0 or owner <= 0:
        return False, 'Некорректные данные.'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, is_default FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )
            row = cur.fetchone()
            if not row:
                return False, 'Реквизиты не найдены.'
            was_default = int(row['is_default'] or 0) == 1

            cur.execute(
                "DELETE FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )

            if was_default:
                # Promote newest to default if any remains
                cur.execute(
                    "SELECT id FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ? ORDER BY created_at DESC LIMIT 1",
                    (b, owner),
                )
                row2 = cur.fetchone()
                if row2:
                    cur.execute(
                        "UPDATE partner_payout_requisites SET is_default = 1 WHERE id = ?",
                        (int(row2[0]),),
                    )
            conn.commit()
        return True, 'Реквизиты удалены.'
    except Exception as e:
        logger.error(f"delete_partner_requisite failed: {e}")
        return False, 'Ошибка при удалении.'


def create_withdraw_request(
    bot_id: int,
    owner_telegram_id: int,
    amount_rub: float,
    comment: str | None = None,
    *,
    bank: str | None = None,
    requisite_type: str | None = None,
    requisite_value: str | None = None,
    requisite_id: int | None = None,
) -> tuple[bool, str]:
    """Create a partner withdraw request.

    Enforces minimum (1500 RUB) and available balance.
    """
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
        amt = float(amount_rub)
    except Exception:
        return False, "Некорректные данные."

    if b <= 0:
        return False, "Вывод доступен только во клонах."

    min_withdraw = get_franchise_min_withdraw()
    if amt < min_withdraw:
        return False, f"Минимальная сумма вывода: {min_withdraw:.0f} RUB."

    stats = get_partner_cabinet(b)
    available = float(stats.get("available", 0.0) or 0.0)
    if amt > available + 1e-9:
        return False, f"Недостаточно средств. Доступно: {available:.2f} RUB."

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO partner_withdraw_requests (bot_id, owner_telegram_id, amount_rub, status, comment, bank, requisite_type, requisite_value, requisite_id)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                """,
                (b, owner, amt, (comment or None), (bank or None), (requisite_type or None), (requisite_value or None), (int(requisite_id) if requisite_id is not None else None)),
            )
            conn.commit()
        return True, "Заявка на вывод создана и отправлена администратору."
    except Exception as e:
        logger.error(f"create_withdraw_request failed: {e}")
        return False, "Ошибка при создании заявки."
