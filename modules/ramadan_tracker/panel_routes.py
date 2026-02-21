import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash

from shop_bot.data_manager import database

bp = Blueprint(
    "ramadan_tracker",
    __name__,
    url_prefix="/modules/ramadan_tracker",
    template_folder="templates",
)


def _get_global_stats() -> dict[str, int]:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(COUNT(DISTINCT user_id), 0) AS users_total,
                COALESCE(SUM(CASE WHEN morning_adhkar = 1 THEN 1 ELSE 0 END), 0) AS morning_total,
                COALESCE(SUM(CASE WHEN evening_adhkar = 1 THEN 1 ELSE 0 END), 0) AS evening_total,
                COALESCE(SUM(salawat_count), 0) AS salawat_total,
                COALESCE(SUM(CASE WHEN taraweeh_place IN ('mosque', 'home') THEN 1 ELSE 0 END), 0) AS taraweeh_total
            FROM ramadan_tracker_daily
            """
        )
        row = cursor.fetchone() or (0, 0, 0, 0, 0)
        return {
            "users": int(row[0]),
            "morning_total": int(row[1]),
            "evening_total": int(row[2]),
            "salawat_total": int(row[3]),
            "taraweeh_total": int(row[4]),
            "adhkar_total": int(row[1]) + int(row[2]),
        }


def _get_top_rows(limit: int = 10) -> list[dict[str, int]]:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                user_id,
                COALESCE(
                    SUM(
                        CASE WHEN morning_adhkar = 1 THEN 1 ELSE 0 END
                        + CASE WHEN evening_adhkar = 1 THEN 1 ELSE 0 END
                        + salawat_count
                    ),
                    0
                ) AS score
            FROM ramadan_tracker_daily
            GROUP BY user_id
            ORDER BY score DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [dict(row) for row in cursor.fetchall()]


def _get_withdrawal_requests(limit: int = 200) -> list[dict[str, int]]:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Проверяем наличие новых колонок
        cursor.execute("PRAGMA table_info(ramadan_tracker_reward_users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        has_completed = 'completed_at' in columns
        has_proof = 'proof_file_id' in columns
        
        # Формируем запрос в зависимости от наличия колонок
        if has_completed and has_proof:
            query = """
                SELECT id, period_end, user_id, score, share, amount, requested_at, completed_at, proof_file_id
                FROM ramadan_tracker_reward_users
                WHERE requested_at IS NOT NULL
                ORDER BY 
                    CASE WHEN completed_at IS NULL THEN 0 ELSE 1 END,
                    requested_at DESC
                LIMIT ?
            """
        else:
            query = """
                SELECT id, period_end, user_id, score, share, amount, requested_at
                FROM ramadan_tracker_reward_users
                WHERE requested_at IS NOT NULL
                ORDER BY requested_at DESC
                LIMIT ?
            """
        
        cursor.execute(query, (int(limit),))
        rows = [dict(row) for row in cursor.fetchall()]
        
        # Добавляем пустые значения для отсутствующих колонок
        if not has_completed or not has_proof:
            for row in rows:
                if not has_completed:
                    row['completed_at'] = None
                if not has_proof:
                    row['proof_file_id'] = None
        
        return rows


@bp.route("/")
def index():
    stats = _get_global_stats()
    top_rows = _get_top_rows()
    return render_template(
        "modules/ramadan_tracker/index.html",
        stats=stats,
        top_rows=top_rows,
    )


@bp.route("/payouts")
def payouts():
    payouts_rows = _get_withdrawal_requests()
    return render_template(
        "modules/ramadan_tracker/payouts.html",
        payouts_rows=payouts_rows,
    )


@bp.route("/payouts/delete", methods=["POST"])
def payouts_delete():
    withdrawal_id = request.form.get("withdrawal_id")
    if withdrawal_id:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ramadan_tracker_reward_users SET requested_at = NULL WHERE id = ?",
                (int(withdrawal_id),)
            )
            conn.commit()
    return redirect("/modules/ramadan_tracker/payouts")


@bp.route("/payouts/complete", methods=["POST"])
def payouts_complete():
    withdrawal_id = request.form.get("withdrawal_id")
    if withdrawal_id:
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE ramadan_tracker_reward_users SET completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(withdrawal_id),)
                )
                conn.commit()
            except sqlite3.OperationalError:
                # Колонка completed_at еще не существует
                pass
    return redirect("/modules/ramadan_tracker/payouts")
    return redirect(url_for("ramadan_tracker.payouts"))
