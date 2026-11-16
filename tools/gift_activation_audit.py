#!/usr/bin/env python3
"""Поиск и точечная починка подарков «активирован, но ключ не передан».

Такие записи оставляла прежняя двухшаговая активация: флаг в user_gifts
ставился отдельным commit, а перенос vpn_keys мог не выполниться.

Usage:
  python tools/gift_activation_audit.py [--db PATH]            # только отчёт
  python tools/gift_activation_audit.py [--db PATH] --repair 12 15

По умолчанию ничего не меняет. --repair переносит ключ на пользователя из
activated_by_user_id только для problem=not_transferred (ключ всё ещё у
дарителя с тегом user_gift). Флаги активации не сбрасываются, чужие ключи
не переназначаются, коды подарков не печатаются.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="путь к SQLite (по умолчанию — как у бота)")
    parser.add_argument("--repair", nargs="*", type=int, default=[], metavar="GIFT_ID",
                        help="gift_id для починки (только recoverable)")
    args = parser.parse_args()

    from shop_bot.data_manager import database

    if args.db:
        database.DB_FILE = Path(args.db)
    if not Path(database.DB_FILE).exists():
        print(f"DB not found: {database.DB_FILE}")
        return 1
    print(f"Using DB: {database.DB_FILE}")

    report = database.find_stuck_gift_activations()
    if not report:
        print("Зависших активаций нет.")
    for item in report:
        print(
            f"gift_id={item['gift_id']} problem={item['problem']} recoverable={item['recoverable']} "
            f"from_user_id={item['from_user_id']} activated_by={item['activated_by_user_id']} "
            f"key_id={item['key_id']} key_owner={item['key_user_id']} key_tag={item['key_tag']!r} "
            f"activated_at={item['activated_at']}"
        )

    failed = 0
    for gift_id in args.repair:
        result = database.repair_stuck_gift_activation(gift_id)
        print(f"repair gift_id={gift_id}: {result['status']} (key_id={result['key_id']}, user_id={result['user_id']})")
        failed += 0 if result["ok"] else 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
