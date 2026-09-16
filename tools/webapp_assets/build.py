#!/usr/bin/env python3
"""Скачать локальные шрифты Mini App и собрать CSS без CDN.

Запуск из корня репозитория:

    python3 tools/webapp_assets/build.py

Нужны сеть (Google Fonts / gstatic) и npm. Готовые файлы пишутся в
src/shop_bot/webapp/static/ и коммитятся — Docker-образ Node не требует.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBAPP = ROOT / "src" / "shop_bot" / "webapp"
STATIC = WEBAPP / "static"
FONTS_DIR = STATIC / "fonts"
CSS_DIR = STATIC / "css"
ASSETS = Path(__file__).resolve().parent
ICON_LIST = ASSETS / "icon_names.txt"
FONTS_CSS = ASSETS / "fonts.css"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Ligature сразу после открывающего тега, не через полфайла до следующего `>`.
LIGATURE_RE = re.compile(
    r"material-symbols-rounded[^\n>]{0,240}>\s*([a-z][a-z0-9_]*)",
    re.IGNORECASE,
)
DICT_ICON_RE = re.compile(
    r"(?:methodIcons|_M_ICONS)\s*=\s*\{([^}]+)\}",
    re.DOTALL,
)
QUOTED_RE = re.compile(r"['\"]([a-z][a-z0-9_]{1,40})['\"]")
FACE_BLOCK_RE = re.compile(
    r"(?:/\*\s*([^*]+?)\s*\*/\s*)?@font-face\s*\{(.*?)\n\}",
    re.DOTALL,
)
URL_RE = re.compile(r"url\((https://fonts\.gstatic\.com/[^)]+)\)")

KEEP_INTER_SUBSETS = {"cyrillic-ext", "cyrillic", "latin-ext", "latin"}

LICENSE_HEADER = (
    "/* Inter: SIL Open Font License 1.1 (rsms.me/inter).\n"
    "   Material Symbols Rounded: Apache License 2.0 (Google).\n"
    "   Файлы скачиваются tools/webapp_assets/build.py и коммитятся рядом. */\n\n"
)

EXTRA_ICONS = {
    "account_balance",
    "account_balance_wallet",
    "add",
    "alternate_email",
    "block",
    "credit_card",
    "currency_bitcoin",
    "diamond",
    "group_add",
    "lock_person",
    "lock_reset",
    "pause_circle",
    "phone_android",
    "pin",
    "receipt",
    "star",
}


def _read_sources() -> str:
    chunks: list[str] = []
    for path in (
        list(WEBAPP.glob("*.html"))
        + list((WEBAPP / "module").glob("*.html"))
        + list((WEBAPP / "web_router").glob("*.py"))
    ):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def collect_icon_names() -> list[str]:
    blob = _read_sources()
    names = set(EXTRA_ICONS)
    names.update(LIGATURE_RE.findall(blob))
    for dict_match in DICT_ICON_RE.finditer(blob):
        names.update(QUOTED_RE.findall(dict_match.group(1)))
    cleaned = sorted(
        {
            n
            for n in names
            if n.isascii()
            and n[0].islower()
            and n.replace("_", "").isalnum()
            and not n.startswith("_")
        }
    )
    ICON_LIST.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    return cleaned


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _rewrite_faces(css_text: str, kind: str, *, keep_subsets: set[str] | None = None) -> str:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    rewritten: list[str] = []
    seen_urls: dict[str, str] = {}
    for comment, body in FACE_BLOCK_RE.findall(css_text):
        subset = (comment or "").strip().lower()
        if keep_subsets is not None and subset and subset not in keep_subsets:
            continue
        urls = URL_RE.findall(body)
        if not urls:
            continue
        url = urls[0].strip("\"'")
        if url in seen_urls:
            filename = seen_urls[url]
        else:
            digest = hashlib.sha256(url.encode()).hexdigest()[:10]
            filename = f"{kind}-{subset or 'all'}-{digest}.woff2"
            filename = filename.replace(" ", "-")
            target = FONTS_DIR / filename
            if not target.exists():
                target.write_bytes(_http_get(url))
            seen_urls[url] = filename
        face = "@font-face {" + body.replace(url, f"../fonts/{filename}") + "\n}"
        if subset:
            face = f"/* {subset} */\n" + face
        rewritten.append(face)
    return "\n\n".join(rewritten) + ("\n" if rewritten else "")


def fetch_inter_css() -> str:
    href = "https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap"
    css = _http_get(href).decode("utf-8")
    return _rewrite_faces(css, "inter", keep_subsets=KEEP_INTER_SUBSETS)


def fetch_material_symbols_css(icon_names: list[str]) -> str:
    names = ",".join(sorted(icon_names))
    href = (
        "https://fonts.googleapis.com/css2"
        "?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..600,0..1,-50..200"
        f"&icon_names={names}&display=block"
    )
    try:
        css = _http_get(href).decode("utf-8")
    except Exception:
        href = (
            "https://fonts.googleapis.com/css2"
            "?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0"
            f"&icon_names={names}&display=block"
        )
        css = _http_get(href).decode("utf-8")
    faces = _rewrite_faces(css, "material-symbols")
    faces += """
.material-symbols-rounded {
    font-family: 'Material Symbols Rounded';
    font-weight: normal;
    font-style: normal;
    font-size: 24px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    vertical-align: middle;
    user-select: none;
}

.nav-tab.active .material-symbols-rounded {
    font-variation-settings: 'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24;
}
"""
    return faces


def write_sha256_manifest() -> None:
    lines: list[str] = []
    for path in sorted(FONTS_DIR.glob("*.woff2")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (FONTS_DIR / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def npm_build() -> None:
    CSS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npm", "install"], cwd=ASSETS, check=True)
    subprocess.run(["npm", "run", "build"], cwd=ASSETS, check=True)
    built = CSS_DIR / "app.css"
    fonts = FONTS_CSS.read_text(encoding="utf-8")
    utilities = built.read_text(encoding="utf-8")
    built.write_text(fonts.rstrip() + "\n" + utilities, encoding="utf-8")


def main() -> int:
    if FONTS_DIR.exists():
        shutil.rmtree(FONTS_DIR)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    icons = collect_icon_names()
    print(f"icons: {len(icons)}")
    print(", ".join(icons))
    FONTS_CSS.write_text(
        LICENSE_HEADER + fetch_inter_css() + "\n" + fetch_material_symbols_css(icons),
        encoding="utf-8",
    )
    write_sha256_manifest()
    npm_build()
    css_path = CSS_DIR / "app.css"
    font_bytes = sum(p.stat().st_size for p in FONTS_DIR.glob("*.woff2"))
    print(f"wrote {css_path} ({css_path.stat().st_size} bytes)")
    print(f"fonts {FONTS_DIR} ({font_bytes} bytes, {len(list(FONTS_DIR.glob('*.woff2')))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
