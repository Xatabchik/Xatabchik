from shop_bot.core.module_types import ModuleMeta

MODULE_META = ModuleMeta(
    id="example_module",
    name="Example Module",
    version="1.0.0",
    description="Sample module with bot and panel hooks.",
    author="Xatabchik Team",
    requires=[],
    bot_entry="bot_handlers",
    panel_entry="panel_routes",
    db_schema="db_schema",
    db_cleanup="db_cleanup",
    settings_schema="settings_schema",
    menu_items=[
        {"label": "Example Module", "url": "/modules/example_module/", "icon": "plug"}
    ],
)
