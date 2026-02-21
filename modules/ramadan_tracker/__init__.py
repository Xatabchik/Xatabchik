from shop_bot.core.module_types import ModuleMeta

MODULE_META = ModuleMeta(
    id="ramadan_tracker",
    name="Ramadan Tracker",
    version="1.0.0",
    description="Ramadan tracker for adhkar, salawat, and taraweeh.",
    author="Custom Module",
    requires=[],
    bot_entry="bot_handlers",
    panel_entry="panel_routes",
    db_schema="db_schema",
    db_cleanup="db_cleanup",
    settings_schema="settings_schema",
    menu_items=[
        {"label": "Ramadan Tracker", "url": "/modules/ramadan_tracker/", "icon": "moon"}
    ],
)
