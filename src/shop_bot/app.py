#!/usr/bin/env python3
# coding: utf-8
"""
Hotfix for shop_bot/webhook_server/app.py to resolve several syntax/runtime issues:
1) Replace erroneous decorator "@flask_@app.route" -> "@flask_app.route"
2) Fix unterminated f-string near the revoke message.
3) Ensure "enable_referral_days_bonus" is present in ALLOWED_BOOL_SETTINGS-style arrays with proper syntax.
Usage:
    python3 fix_app.py /path/to/app.py
Creates a backup app.py.bak before modifying.
"""
import sys, io, os, re

def patch_file(path):
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()

    original = src

    # 1) decorator typo
    src = src.replace("@flask_@app.route", "@flask_app.route")

    # 2) unterminated f-string for revoke message; make a robust regex fix
    # We try to normalize a fragment like: else f"Удалось отозвать { ..."
    # into a full conditional expression string with both branches.
    src = re.sub(
        r'else f"Удалось отозвать\s*\{([^}]*)\}',
        r'else f"Удалось отозвать {\1}"',
        src
    )

    # 3) ensure enable_referral_days_bonus is in the allowed boolean settings list(s)
    def ensure_flag_in_list(src, list_name_pattern):
        m = re.search(list_name_pattern, src)
        if not m:
            return src
        # find the full list boundaries (rudimentary: the first '[' after the name and its matching ']')
        start = src.find('[', m.end())
        if start == -1: 
            return src
        # naive scan to matching bracket
        depth = 0
        end = None
        for i in range(start, len(src)):
            if src[i] == '[':
                depth += 1
            elif src[i] == ']':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            return src
        list_text = src[start:end+1]
        if '"enable_referral_days_bonus"' not in list_text and "'enable_referral_days_bonus'" not in list_text:
            # insert before closing bracket, keep formatting
            if list_text.endswith(']'):
                new_list_text = list_text[:-1].rstrip()
                if not new_list_text.endswith('['):
                    new_list_text += ", "
                new_list_text += '"enable_referral_days_bonus"]'
            else:
                new_list_text = list_text
            src = src[:start] + new_list_text + src[end+1:]
        return src

    # Try common list names
    for name in [r'ALLOWED_BOOL_SETTINGS\s*=\s*', r'BOOLEAN_SETTINGS\s*=\s*', r'ALLOWED_SETTINGS\s*=\s*']:
        src = ensure_flag_in_list(src, name)

    if src != original:
        backup = path + ".bak"
        with io.open(backup, "w", encoding="utf-8") as f:
            f.write(original)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print("Patched:", path, "Backup at:", backup)
    else:
        print("No changes made (patterns not found).")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 fix_app.py <path_to_app.py>")
        sys.exit(1)
    patch_file(sys.argv[1])
