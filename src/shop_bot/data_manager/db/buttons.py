"""Конфигурация кнопок интерфейса бота.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging

__all__ = (
    "get_button_configs",
    "get_button_configs_admin",
    "get_button_config_by_db_id",
    "get_button_config",
    "create_button_config",
    "update_button_config",
    "delete_button_config",
    "update_existing_my_keys_button",
    "ensure_main_menu_referral_button",
    "ensure_admin_plans_button",
    "ensure_admin_trial_button",
    "ensure_admin_auto_renew_button",
    "reorder_button_configs",
    "initialize_default_button_configs",
)


def get_button_configs(menu_type: str) -> list[dict]:
    """Get *active* button configurations for a specific menu type.

    Note: this function is used by the bot to build keyboards at runtime, so it
    intentionally filters by `is_active = 1`.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM button_configs 
                WHERE menu_type = ? AND is_active = 1 
                ORDER BY sort_order, row_position, column_position
            """, (menu_type,))
            results = [dict(row) for row in cursor.fetchall()]

            return results
    except sqlite3.Error as e:
        logging.error(f"Failed to get button configs for {menu_type}: {e}")
        return []


def get_button_configs_admin(menu_type: str, *, include_inactive: bool = True) -> list[dict]:
    """Get button configurations for admin/editor UIs.

    Unlike `get_button_configs`, this can return inactive buttons too, so that
    admins can re-enable them.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if include_inactive:
                cursor.execute(
                    """
                    SELECT * FROM button_configs
                    WHERE menu_type = ?
                    ORDER BY sort_order, row_position, column_position
                    """,
                    (menu_type,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM button_configs
                    WHERE menu_type = ? AND is_active = 1
                    ORDER BY sort_order, row_position, column_position
                    """,
                    (menu_type,),
                )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get (admin) button configs for {menu_type}: {e}")
        return []


def get_button_config_by_db_id(button_db_id: int) -> dict | None:
    """Get a button configuration by its numeric DB id."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM button_configs WHERE id = ?", (button_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get button config by id={button_db_id}: {e}")
        return None

def get_button_config(menu_type: str, button_id: str) -> dict | None:
    """Get a specific button configuration by menu_type and button_id"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM button_configs 
                WHERE menu_type = ? AND button_id = ?
            """, (menu_type, button_id))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        logging.error(f"Failed to get button config for {menu_type}/{button_id}: {e}")
        return None

def create_button_config(
    menu_type: str,
    button_id: str,
    text: str,
    callback_data: str = None,
    url: str = None,
    row_position: int = 0,
    column_position: int = 0,
    button_width: int = 1,
    is_active: bool | int = 1,
    sort_order: int = 0,
    metadata: str = None,
) -> bool:
    """Create a new button configuration"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            active_val = 1 if bool(is_active) else 0
            cursor.execute(
                """
                INSERT OR REPLACE INTO button_configs 
                (menu_type, button_id, text, callback_data, url, row_position, column_position, button_width, is_active, sort_order, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    menu_type,
                    button_id,
                    text,
                    callback_data,
                    url,
                    row_position,
                    column_position,
                    button_width,
                    active_val,
                    sort_order,
                    metadata,
                ),
            )
            conn.commit()
            logging.info(f"Button config created: {menu_type}/{button_id}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to create button config: {e}")
        return False

def update_button_config(button_id: int, text: str = None, callback_data: str = None, 
                        url: str = None, row_position: int = None, column_position: int = None, 
                        button_width: int = None, is_active: bool = None, sort_order: int = None, metadata: str = None) -> bool:
    """Update an existing button configuration"""
    try:
        logging.info(f"update_button_config called for {button_id}: text={text}, callback_data={callback_data}, url={url}, row={row_position}, col={column_position}, active={is_active}, sort={sort_order}")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            

            updates = []
            params = []
            
            if text is not None:
                updates.append("text = ?")
                params.append(text)
            if callback_data is not None:
                updates.append("callback_data = ?")
                params.append(callback_data)
            if url is not None:
                updates.append("url = ?")
                params.append(url)
            if row_position is not None:
                updates.append("row_position = ?")
                params.append(row_position)
            if column_position is not None:
                updates.append("column_position = ?")
                params.append(column_position)
            if button_width is not None:
                updates.append("button_width = ?")
                params.append(button_width)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            if sort_order is not None:
                updates.append("sort_order = ?")
                params.append(sort_order)
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(metadata)
            
            if not updates:
                return True
                
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(button_id)
            
            query = f"UPDATE button_configs SET {', '.join(updates)} WHERE id = ?"
            logging.info(f"Executing query: {query} with params: {params}")
            cursor.execute(query, params)
            
            if cursor.rowcount == 0:
                logging.warning(f"No button found with id {button_id}")
                return False
                
            conn.commit()
            logging.info(f"Button config {button_id} updated successfully")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to update button config {button_id}: {e}")
        return False

def delete_button_config(button_id: int) -> bool:
    """Delete a button configuration"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM button_configs WHERE id = ?", (button_id,))
            conn.commit()
            logging.info(f"Button config {button_id} deleted")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete button config {button_id}: {e}")
        return False

def update_existing_my_keys_button():
    """Update existing my_keys button to include key count template and set proper button widths"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE button_configs 
                SET text = '🔑 Мои ключи ({len(user_keys)})', updated_at = CURRENT_TIMESTAMP
                WHERE menu_type = 'main_menu' AND button_id = 'my_keys'
            """)
            if cursor.rowcount > 0:
                logging.info("Updated my_keys button text to include key count template")
            

            wide_buttons = [
                ("trial", 2),
                ("referral", 2),
                ("admin", 2),
            ]
            
            for button_id, width in wide_buttons:
                cursor.execute("""
                    UPDATE button_configs 
                    SET button_width = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE menu_type = 'main_menu' AND button_id = ?
                """, (width, button_id))
                if cursor.rowcount > 0:
                    logging.info(f"Updated {button_id} button width to {width}")
            
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update button configurations: {e}")


def ensure_main_menu_referral_button() -> None:
    """Ensure that the main menu has the referral program button in button configs,
    and that it's removed from the profile menu (moved from "Мой профиль" в главное меню).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Убираем кнопку из меню "Мой профиль" (перенесена в главное меню)
            cursor.execute(
                "DELETE FROM button_configs WHERE menu_type = 'profile_menu' AND button_id = 'referral'"
            )
            if cursor.rowcount > 0:
                logging.info("Removed referral button from profile_menu (moved to main_menu)")

            cursor.execute(
                "SELECT is_active FROM button_configs WHERE menu_type = 'main_menu' AND button_id = 'referral' LIMIT 1"
            )
            row = cursor.fetchone()
            if row is not None:
                if int(row[0] or 0) != 1:
                    cursor.execute(
                        "UPDATE button_configs SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE menu_type = 'main_menu' AND button_id = 'referral'"
                    )
                    logging.info("Re-activated referral button in main_menu")
                conn.commit()
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("main_menu", "referral", "🤝 Реферальная программа", "show_referral_program", row_pos, 0, next_sort, 2),
            )
            conn.commit()
            logging.info("Inserted missing main_menu button: referral")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure main menu referral button: {e}")


def ensure_admin_plans_button():
    """Ensure that the Admin menu has a button for managing тарифы (plans).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_menu' AND button_id = 'plans' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            row_pos = 0
            col_pos = 0
            try:
                cursor.execute(
                    "SELECT row_position, column_position FROM button_configs WHERE menu_type='admin_menu' AND button_id='back_to_menu' LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    row_pos = int(row[0] or 0)
                    back_col = int(row[1] or 0)

                    candidate_col = 1 if back_col == 0 else back_col + 1
                    cursor.execute(
                        "SELECT 1 FROM button_configs WHERE menu_type='admin_menu' AND row_position=? AND column_position=? LIMIT 1",
                        (row_pos, candidate_col),
                    )
                    if cursor.fetchone():
                        cursor.execute(
                            "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                        )
                        row_pos = int(cursor.fetchone()[0] or 0) + 1
                        col_pos = 0
                    else:
                        col_pos = candidate_col
                else:
                    cursor.execute(
                        "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                    )
                    row_pos = int(cursor.fetchone()[0] or 0) + 1
                    col_pos = 0
            except Exception:
                cursor.execute(
                    "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                )
                row_pos = int(cursor.fetchone()[0] or 0) + 1
                col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_menu", "plans", "🧾 Тарифы", "admin_plans", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_menu button: plans")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin plans button: {e}")




def ensure_admin_trial_button():
    """Ensure that the Admin menu has a button for managing Trial settings.

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_menu' AND button_id = 'trial_settings' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1
            col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_menu", "trial_settings", "🎁 Триал", "admin_trial", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_menu button: trial_settings")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin trial button: {e}")


def ensure_admin_auto_renew_button():
    """Ensure that the Admin settings submenu has a button for Автопродление (auto-renew).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty. Existing databases created before this button
    was introduced (button_configs already populated for admin_settings_menu) never get it
    backfilled by "CREATE TABLE IF NOT EXISTS", so we do it here on every startup instead.
    This only inserts the row if it is truly absent, so it never overwrites an admin's
    existing customization of this button.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_settings_menu' AND button_id = 'auto_renew' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_settings_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_settings_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1
            col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_settings_menu", "auto_renew", "🔄 Автопродление", "admin_auto_renew", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_settings_menu button: auto_renew")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin auto-renew button: {e}")


def reorder_button_configs(menu_type: str, button_orders: list[dict]) -> bool:
    """Reorder button configurations for a menu type"""
    try:
        logging.info(f"Reordering {len(button_orders)} buttons for {menu_type}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for order_data in button_orders:
                button_id = order_data.get('button_id')
                sort_order = order_data.get('sort_order', 0)
                row_position = order_data.get('row_position', 0)
                column_position = order_data.get('column_position', 0)
                button_width = order_data.get('button_width', None)
                
                logging.info(f"Updating {button_id}: sort={sort_order}, row={row_position}, col={column_position}, width={button_width}")
                

                if button_width is not None:
                    cursor.execute(
                        """
                        UPDATE button_configs 
                        SET sort_order = ?, row_position = ?, column_position = ?, button_width = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE menu_type = ? AND button_id = ?
                        """,
                        (sort_order, row_position, column_position, int(button_width), menu_type, button_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE button_configs 
                        SET sort_order = ?, row_position = ?, column_position = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE menu_type = ? AND button_id = ?
                        """,
                        (sort_order, row_position, column_position, menu_type, button_id),
                    )
                

                if cursor.rowcount == 0:
                    logging.warning(f"No button found with menu_type={menu_type}, button_id={button_id}")
                else:
                    logging.info(f"Updated button {button_id}")
                    
            conn.commit()
            logging.info(f"Button configs reordered for {menu_type}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to reorder button configs for {menu_type}: {e}")
        return False

def initialize_default_button_configs():
    """Initialize default button configurations for all menu types"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            

            cursor.execute("SELECT COUNT(*) FROM button_configs")
            count = cursor.fetchone()[0]
            if count > 0:
                logging.info("Button configs already exist, skipping initialization")
                return True
            

            main_menu_buttons = [
                ("trial", "🎁 Попробовать бесплатно", "get_trial", 0, 0, 0, 2),
                ("profile", "👤 Мой профиль", "show_profile", 1, 0, 1, 1),
                ("my_keys", "🔑 Мои ключи ({len(user_keys)})", "manage_keys", 1, 1, 2, 1),
                ("buy_key", "🛒 Купить ключ", "buy_new_key", 2, 0, 3, 1),
                ("topup", "💳 Пополнить баланс", "top_up_start", 2, 1, 4, 1),
                ("gift_new_key", "🎁 Подарить", "gift_new_key", 3, 0, 5, 2),
                ("referral", "🤝 Реферальная программа", "show_referral_program", 3, 1, 6, 2),
                ("support", "🆘 Поддержка", "show_help", 4, 0, 7, 1),
                ("about", "ℹ️ О проекте", "show_about", 4, 1, 8, 1),
                ("speed", "⚡ Скорость", "user_speedtest_last", 5, 0, 9, 1),
                ("howto", "❓ Как использовать", "howto_vless", 5, 1, 10, 1),
                ("admin", "⚙️ Админка", "admin_menu", 6, 0, 10, 2),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order, button_width in main_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, ("main_menu", button_id, text, callback_data, row_pos, col_pos, sort_order, button_width))
            

            admin_menu_buttons = [
                ("users", "👥 Пользователи", "admin_users", 0, 0, 0),
                ("host_keys", "🌍 Ключи на хосте", "admin_host_keys", 0, 1, 1),
                ("gift_key", "🎁 Выдать ключ", "admin_gift_key", 1, 0, 2),
                ("promo", "🎟 Промокоды", "admin_promo_menu", 1, 1, 3),
                ("speedtest", "⚡ Тест скорости", "admin_speedtest", 2, 0, 4),
                ("monitor", "📊 Мониторинг", "admin_monitor", 2, 1, 5),
                ("backup", "🗄 Бэкап БД", "admin_backup_db", 3, 0, 6),
                ("restore", "♻️ Восстановить БД", "admin_restore_db", 3, 1, 7),
                ("admins", "👮 Администраторы", "admin_admins_menu", 4, 0, 8),
                ("broadcast", "📢 Рассылка", "start_broadcast", 4, 1, 9),
                ("trial_settings", "🎁 Триал", "admin_trial", 5, 0, 10),
                ("plans", "🧾 Тарифы", "admin_plans", 5, 1, 11),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 6, 0, 12),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            

            profile_menu_buttons = [
                ("topup", "💳 Пополнить баланс", "top_up_start", 0, 0, 0),
                ("referral", "🤝 Реферальная программа", "show_referral_program", 1, 0, 1),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 2, 0, 2),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in profile_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("profile_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            

            support_menu_buttons = [
                ("new_ticket", "✍️ Новое обращение", "support_new_ticket", 0, 0, 0),
                ("my_tickets", "📨 Мои обращения", "support_my_tickets", 1, 0, 1),
                ("external", "🆘 Внешняя поддержка", "support_external", 2, 0, 2),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 3, 0, 3),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in support_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("support_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            # Admin System Menu (подменю)
            admin_system_menu_buttons = [
                ("speedtest", "⚡ Тест скорости", "admin_speedtest", 0, 0, 0),
                ("monitor", "📊 Мониторинг", "admin_monitor", 0, 1, 1),
                ("backup", "🗄 Бэкап БД", "admin_backup_db", 1, 0, 2),
                ("restore", "♻️ Восстановить БД", "admin_restore_db", 1, 1, 3),
                ("back_to_admin", "⬅️ Назад", "admin_menu", 2, 0, 4),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_system_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_system_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            # Admin Settings Menu (подменю)
            admin_settings_menu_buttons = [
                ("admins", "👮 Администраторы", "admin_admins_menu", 0, 0, 0),
                ("plans", "🧾 Тарифы", "admin_plans", 0, 1, 1),
                ("hosts", "🖥 Хосты", "admin_hosts_menu", 1, 0, 2),
                ("payments", "💳 Платежки", "admin_payments_menu", 1, 1, 3),
                ("referral", "👥 Рефералка", "admin_referral", 2, 0, 4),
                ("franchise", "💼 Франшиза", "admin_franchise", 2, 1, 5),
                ("modules", "🧩 Модули", "admin_modules", 3, 0, 6),
                ("trial", "🎁 Триал", "admin_trial", 3, 1, 7),
                ("notifications", "🔔 Уведомления", "admin_notifications_menu", 4, 0, 8),
                ("captcha", "🛡️ Капча", "admin_captcha_settings", 4, 1, 9),
                ("btn_constructor", "🧩 Конструктор кнопок", "admin_btn_constructor", 5, 0, 10),
                ("auto_renew", "🔄 Автопродление", "admin_auto_renew", 5, 1, 11),
                ("back_to_admin", "⬅️ Назад", "admin_menu", 6, 0, 12),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_settings_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_settings_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            conn.commit()
            logging.info("Default button configurations initialized")
            return True
            
    except sqlite3.Error as e:
        logging.error(f"Failed to initialize default button configs: {e}")
        return False
