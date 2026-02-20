def cleanup(db_conn) -> None:
    cursor = db_conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS example_module_items")
    cursor.execute("DELETE FROM bot_settings WHERE key LIKE 'example_module_%'")
    db_conn.commit()
