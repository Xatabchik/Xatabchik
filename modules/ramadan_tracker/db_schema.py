import sqlite3
from pathlib import Path


def SCHEMA_SQL():
    """
    Генерирует SQL схему и автоматически выполняет миграции.
    """
    # Путь к базе данных
    db_file = Path(__file__).parent.parent.parent / "shop_bot" / "data" / "database.db"
    
    # Основная схема
    base_schema = """
CREATE TABLE IF NOT EXISTS ramadan_tracker_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    morning_adhkar INTEGER NOT NULL DEFAULT 0,
    evening_adhkar INTEGER NOT NULL DEFAULT 0,
    salawat_count INTEGER NOT NULL DEFAULT 0,
    taraweeh_place TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS ramadan_tracker_state (
    user_id INTEGER PRIMARY KEY,
    pending_action TEXT DEFAULT NULL,
    pending_day TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ramadan_tracker_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_end TEXT NOT NULL,
    rewarded_user_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    rewarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(period_end)
);

CREATE TABLE IF NOT EXISTS ramadan_tracker_reward_periods (
    period_end TEXT PRIMARY KEY,
    prize_fund REAL NOT NULL DEFAULT 0,
    winners_count INTEGER NOT NULL DEFAULT 1,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ramadan_tracker_reward_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_end TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    share REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    requested_at TIMESTAMP DEFAULT NULL,
    completed_at TIMESTAMP DEFAULT NULL,
    proof_file_id TEXT DEFAULT NULL,
    UNIQUE(period_end, user_id)
);

INSERT OR IGNORE INTO button_configs
    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
SELECT
    'main_menu',
    'ramadan_tracker',
    '🌙 Рамадан трекер',
    'mod:ramadan_tracker:menu',
    COALESCE(MAX(row_position), 0) + 1,
    0,
    COALESCE(MAX(sort_order), 0) + 1,
    2,
    1
FROM button_configs
WHERE menu_type = 'main_menu';

UPDATE button_configs
SET text = '🌙 Рамадан трекер',
    callback_data = 'mod:ramadan_tracker:menu',
    button_width = 2,
    is_active = 1
WHERE menu_type = 'main_menu' AND button_id = 'ramadan_tracker';
"""
    
    # Проверяем, нужна ли миграция
    migration_statements = []
    
    if db_file.exists():
        try:
            with sqlite3.connect(str(db_file)) as conn:
                cursor = conn.cursor()
                # Проверяем структуру таблицы ramadan_tracker_reward_users
                cursor.execute("PRAGMA table_info(ramadan_tracker_reward_users)")
                columns = [row[1] for row in cursor.fetchall()]
                
                # Добавляем недостающие колонки
                if "completed_at" not in columns:
                    migration_statements.append(
                        "ALTER TABLE ramadan_tracker_reward_users ADD COLUMN completed_at TIMESTAMP DEFAULT NULL;"
                    )
                
                if "proof_file_id" not in columns:
                    migration_statements.append(
                        "ALTER TABLE ramadan_tracker_reward_users ADD COLUMN proof_file_id TEXT DEFAULT NULL;"
                    )
        except Exception:
            # Если таблица не существует, миграция не нужна
            pass
    
    # Возвращаем список statements: основная схема + миграции
    result = [base_schema]
    if migration_statements:
        result.extend(migration_statements)
    
    return result
