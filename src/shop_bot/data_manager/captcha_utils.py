"""Утилиты для работы с системой капчи."""

import random
import sqlite3
from datetime import datetime, timedelta
import logging

from shop_bot.data_manager import database

logger = logging.getLogger(__name__)

# Путь к БД берём напрямую из database.DB_FILE (а не вычисляем повторно
# здесь же — раньше был отдельный, идентичный по логике блок определения пути,
# который вычислялся один раз при импорте модуля и мог разойтись с БД, которую
# реально использует остальное приложение, например в тестах, подставляющих
# свой путь через monkeypatch.setattr(database, "DB_FILE", ...)). Обращаемся
# через `database.DB_FILE` (а не через `from ... import DB_FILE`), чтобы всегда
# видеть актуальное значение, а не значение на момент импорта этого модуля.


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _expire_time_str(minutes: int) -> str:
    """Возвращает время истечения капчи (через N минут)."""
    expire_dt = datetime.utcnow() + timedelta(minutes=minutes)
    return expire_dt.strftime("%Y-%m-%d %H:%M:%S")


def generate_math_captcha() -> tuple[str, str]:
    """Генерирует математическую задачу и правильный ответ.
    
    Возвращает: (вопрос, правильный_ответ)
    """
    a = random.randint(1, 99)
    b = random.randint(1, 99)
    operations = [
        (lambda x, y: x + y, "+"),
        (lambda x, y: x - y, "-"),
        (lambda x, y: x * y, "*"),
    ]
    
    op_func, op_symbol = random.choice(operations)
    result = op_func(a, b)
    
    if result < 0:
        a, b = b, a
        result = op_func(a, b)
    
    question = f"❓ {a} {op_symbol} {b} = ?"
    return question, str(result)


def generate_button_captcha() -> tuple[str, str]:
    """Генерирует капчу с нажатием на кнопку.
    
    Возвращает: (вопрос, правильный_ответ)
    """
    questions = [
        ("Какой смайлик означает улыбку?", "😊"),
        ("Какой смайлик означает большой палец вверх?", "👍"),
        ("Какой смайлик означает огонь/класс?", "🔥"),
        ("Какой смайлик означает сердце?", "❤️"),
        ("Какой смайлик означает звездочку?", "⭐"),
        ("Какой смайлик означает проверка/галочка?", "✅"),
        ("Какой смайлик означает кот?", "🐱"),
        ("Какой смайлик означает робот/бот?", "🤖"),
    ]
    
    question, answer = random.choice(questions)
    return question, answer


def create_captcha_challenge(user_id: int, challenge_type: str = "math", timeout_minutes: int = 15) -> dict | None:
    """Создаёт новый капча-вызов для пользователя.
    
    Args:
        user_id: ID пользователя Telegram
        challenge_type: тип капчи ("math" или "button")
        timeout_minutes: время истечения капчи в минутах
    
    Возвращает: словарь с данными капчи или None при ошибке
    """
    try:
        if challenge_type == "math":
            question, answer = generate_math_captcha()
        elif challenge_type == "button":
            question, answer = generate_button_captcha()
        else:
            logger.warning(f"Unknown captcha type: {challenge_type}")
            question, answer = generate_math_captcha()
        
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO captcha_challenges (user_id, challenge_type, question, correct_answer, expired_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, challenge_type, question, answer, _expire_time_str(timeout_minutes))
            )
            conn.commit()
            challenge_id = cursor.lastrowid
        
        return {
            "id": challenge_id,
            "user_id": user_id,
            "challenge_type": challenge_type,
            "question": question,
            "correct_answer": answer,
        }
    except Exception as e:
        logger.error(f"Failed to create captcha challenge: {e}")
        return None


def check_captcha_answer(challenge_id: int, user_answer: str, max_attempts: int = 3) -> tuple[bool, str]:
    """Проверяет ответ на капчу.
    
    Возвращает: (успешно_ли, сообщение)
    """
    try:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Проверяем, не истекла ли капча
            cursor.execute(
                "SELECT passed, attempts, max_attempts, correct_answer, expired_at FROM captcha_challenges WHERE id = ?",
                (challenge_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return False, "Капча не найдена. Пожалуйста, начните сначала."
            
            passed, attempts, cap_max_attempts, correct_answer, expired_at = row
            
            if passed:
                return False, "Капча уже пройдена."
            
            if expired_at:
                expire_dt = datetime.strptime(expired_at, "%Y-%m-%d %H:%M:%S")
                if datetime.utcnow() > expire_dt:
                    return False, "Капча истекла. Начните сначала /start"
            
            if attempts >= cap_max_attempts:
                return False, f"Вы исчерпали все {cap_max_attempts} попытки. Напишите /start для новой попытки."
            
            # Проверяем ответ
            attempts += 1
            if str(user_answer).strip().lower() == str(correct_answer).strip().lower():
                # Успех! Само отмечание "капча пройдена" в user_captcha_status делает
                # вызывающий код через mark_user_passed_captcha(real_user_id, challenge_id) —
                # здесь эта таблица больше не трогается (раньше сюда вставлялась строка
                # с user_id=None, что для INTEGER PRIMARY KEY означало автоназначенный
                # ROWID, никак не привязанный к реальному telegram_id — мёртвый код,
                # только оставлявший в таблице лишние "осиротевшие" записи).
                cursor.execute(
                    "UPDATE captcha_challenges SET passed = 1, attempts = ? WHERE id = ?",
                    (attempts, challenge_id)
                )
                conn.commit()
                return True, "✅ Капча пройдена успешно!"
            else:
                # Ошибка
                remaining = cap_max_attempts - attempts
                cursor.execute(
                    "UPDATE captcha_challenges SET attempts = ? WHERE id = ?",
                    (attempts, challenge_id)
                )
                conn.commit()
                
                if remaining > 0:
                    return False, f"❌ Неверный ответ. Осталось попыток: {remaining}"
                else:
                    return False, f"❌ Неверный ответ. Все попытки исчерпаны. Напишите /start для новой попытки."
    
    except Exception as e:
        logger.error(f"Failed to check captcha answer: {e}")
        return False, "Ошибка при проверке капчи. Попробуйте снова."


def get_active_captcha_challenge(user_id: int) -> dict | None:
    """Получает активный капча-вызов для пользователя.
    
    Возвращает: словарь с данными капчи или None
    """
    try:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, challenge_type, question, correct_answer, attempts, max_attempts, 
                       passed, expired_at
                FROM captcha_challenges
                WHERE user_id = ? AND passed = 0
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            challenge_id, ch_type, question, correct_answer, attempts, max_attempts, passed, expired_at = row
            
            # Проверяем истечение
            if expired_at:
                expire_dt = datetime.strptime(expired_at, "%Y-%m-%d %H:%M:%S")
                if datetime.utcnow() > expire_dt:
                    # Капча истекла
                    cursor.execute("UPDATE captcha_challenges SET passed = 0 WHERE id = ?", (challenge_id,))
                    conn.commit()
                    return None
            
            return {
                "id": challenge_id,
                "user_id": user_id,
                "challenge_type": ch_type,
                "question": question,
                "attempts": attempts,
                "max_attempts": max_attempts,
            }
    
    except Exception as e:
        logger.error(f"Failed to get active captcha challenge: {e}")
        return None


def has_passed_captcha(user_id: int) -> bool:
    """Проверяет, прошла ли капчу пользователь при регистрации.
    
    Возвращает: True если капча пройдена, False иначе
    """
    try:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM user_captcha_status WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check captcha status: {e}")
        return False


def mark_user_passed_captcha(user_id: int, challenge_id: int) -> bool:
    """Помечает пользователя как прошедшего капчу.
    
    Возвращает: True если успешно, False при ошибке
    """
    try:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_captcha_status (user_id, passed_at, challenge_id) VALUES (?, ?, ?)",
                (user_id, _now_str(), challenge_id)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to mark user passed captcha: {e}")
        return False
