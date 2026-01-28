
import sys, re, pathlib

if len(sys.argv) != 2:
    print("Usage: python3 apply_app_fix.py <path_to_app.py>")
    sys.exit(1)

p = pathlib.Path(sys.argv[1])
src = p.read_text(encoding="utf-8")
backup = p.with_suffix(p.suffix + ".bak")
backup.write_text(src, encoding="utf-8")

def normalize_list(block, must_have):
    # Убираем любые запятые в начале строки перед закрывающей скобкой
    block = re.sub(r'(?m)^\s*,\s*\]', '\n]', block)
    # Разворачиваем элементы
    items = re.findall(r'"([^"]+)"', block)
    s = set(items)
    for k in must_have:
        s.add(k)
    # Соберём красиво: по одному на строку, с запятыми только между
    inner = ",\n    ".join(f'"{k}"' for k in sorted(s))
    return "[\n    " + inner + "\n]"

# Исправляем ALL_SETTINGS_KEYS
src = re.sub(
    r'(ALL_SETTINGS_KEYS\s*=\s*)\[(.*?)\]',
    lambda m: m.group(1) + normalize_list(m.group(2), {"enable_referral_days_bonus"}),
    src, flags=re.S
)

# Исправляем checkbox_keys (это может быть list или set)
# Приведём к списку для простоты.
src = re.sub(
    r'(checkbox_keys\s*=\s*)(\[[^\]]*\]|\{[^}]*\})',
    lambda m: m.group(1) + normalize_list(m.group(2), {"enable_referral_days_bonus"}),
    src, flags=re.S
)

p.write_text(src, encoding="utf-8")
print(f"Patched {p}. Backup saved to {backup}")
