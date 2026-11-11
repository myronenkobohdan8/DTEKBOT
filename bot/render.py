"""Малює картинку графіка вмикань: HTML/CSS -> JPEG через Playwright."""
import base64
import html as H
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from .schedule import GROUPS, day_label, pretty, total_hours_text

ASSETS = Path(__file__).resolve().parent.parent / "assets"
W, HGT, SCALE = 1080, 1440, 1.5

BLUE = "#0B4BAE"      # синій з логотипа
YELLOW = "#FFEB1F"    # жовтий з логотипа
INK = "#262B33"


def _b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


BOLT = ('<svg class="bolt" viewBox="0 0 24 24"><path d="M13.5 1 4 13.5h6.2L9 23l10-13.2h-6.4z" '
        f'fill="{YELLOW}" stroke="{INK}" stroke-width="1.4" stroke-linejoin="round"/></svg>')

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{HGT}px}}
body{{font-family:'Montserrat','Inter','DejaVu Sans',sans-serif;color:{INK};
  background:#cfe0f3 url('__BG__') center/cover no-repeat;position:relative;overflow:hidden}}
.header{{position:absolute;left:40px;right:40px;top:34px;height:170px;display:flex;align-items:center;gap:30px}}
.logo{{height:150px;width:auto;flex:none}}
.title{{flex:1}}
.title h1{{font-size:46px;font-weight:800;line-height:1.08;letter-spacing:-.5px}}
.title .day{{font-size:34px;font-weight:700;color:{BLUE};margin-top:6px}}
.title .upd{{font-size:22px;font-weight:500;color:#4a5568;margin-top:8px}}
.grid{{position:absolute;left:40px;right:40px;top:232px;bottom:76px;display:grid;
  grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(4,1fr);gap:16px}}
.card{{position:relative;background:rgba(255,255,255,.86);border-radius:24px;padding:16px 18px 14px;
  display:flex;flex-direction:column;box-shadow:0 6px 18px rgba(20,50,100,.14)}}
.card.changed{{box-shadow:0 0 0 4px {YELLOW},0 6px 18px rgba(20,50,100,.18)}}
.tag{{position:absolute;top:-12px;right:16px;background:{YELLOW};color:{INK};font-size:16px;
  font-weight:800;padding:3px 12px;border-radius:12px;letter-spacing:.3px}}
.top{{display:flex;align-items:center;justify-content:space-between}}
.pill{{background:{BLUE};color:#fff;font-size:34px;font-weight:800;padding:2px 18px;border-radius:15px}}
.hrs{{text-align:right;font-size:17px;font-weight:500;color:#5b6575;line-height:1.2}}
.hrs b{{display:block;font-size:19px;font-weight:700;color:{INK}}}
.list{{flex:1;display:flex;flex-direction:column;justify-content:center;gap:5px;margin-top:6px}}
.row{{display:flex;align-items:center;gap:10px;font-size:31px;font-weight:700;
  font-variant-numeric:tabular-nums;white-space:nowrap}}
.bolt{{width:24px;height:24px;flex:none}}
.row.new .t{{text-decoration:underline;text-decoration-thickness:5px;text-decoration-color:#E53935;
  text-underline-offset:6px;background:linear-gradient(transparent 0,rgba(255,235,31,.7) 0);
  padding:0 6px;margin:0 -6px;border-radius:6px}}
.row.all .t{{font-size:27px}}
.row.none{{font-size:25px;color:#6b7280;font-weight:600}}
.footer{{position:absolute;left:40px;right:40px;bottom:26px;display:flex;justify-content:space-between;
  align-items:center;font-size:20px;font-weight:600;color:#3b4656}}
.legend span.u{{text-decoration:underline;text-decoration-thickness:4px;text-decoration-color:#E53935;
  text-underline-offset:5px;background:rgba(255,235,31,.7);padding:0 6px;border-radius:5px;color:{INK}}}
"""


def build_html(date_iso: str, update: str, groups: dict, changes: dict = None) -> str:
    changes = changes or {}
    date_txt, weekday = day_label(date_iso)
    cards = []
    for g in GROUPS:
        ivs = groups[g]
        added = set(changes.get(g, {}).get("added", []))
        if not ivs:
            rows = '<div class="row none">Світла немає весь день</div>'
        elif ivs == ["00:00-24:00"]:
            cls = "row all new" if added else "row all"
            rows = f'<div class="{cls}">{BOLT}<span class="t">Світло є весь день</span></div>'
        else:
            rows = "".join(
                f'<div class="row{" new" if i in added else ""}">{BOLT}<span class="t">{H.escape(pretty(i))}</span></div>'
                for i in ivs)
        tag = '<div class="tag">ОНОВЛЕНО</div>' if g in changes else ""
        cards.append(
            f'<div class="card{" changed" if g in changes else ""}">{tag}'
            f'<div class="top"><div class="pill">{g}</div>'
            f'<div class="hrs">зі світлом<b>{H.escape(total_hours_text(ivs))}</b></div></div>'
            f'<div class="list">{rows}</div></div>')

    legend = ('<div class="legend"><span class="u">Підкреслено</span> — нові або змінені години</div>'
              if changes else "<div></div>")
    css = CSS.replace("__BG__", _b64(ASSETS / "background.png", "image/png"))
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&display=swap&subset=cyrillic" rel="stylesheet">
<style>{css}</style></head><body>
<div class="header">
  <img class="logo" src="{_b64(ASSETS / 'logo.png', 'image/png')}">
  <div class="title"><h1>Графік вмикань світла</h1>
    <div class="day">{H.escape(date_txt)} · {H.escape(weekday)}</div>
    <div class="upd">Оновлено ДТЕК: {H.escape(update)}</div></div>
</div>
<div class="grid">{''.join(cards)}</div>
<div class="footer">{legend}<div>Київська область · години, коли світло Є</div></div>
</body></html>"""


def render_many(jobs: list) -> list:
    """jobs: [(date_iso, update, groups, changes)] -> [jpeg bytes]. Один запуск браузера на всі картинки."""
    out = []
    with sync_playwright() as p:
        launch_args = {"headless": True}
        if os.environ.get("CHROME_PATH"):
            launch_args["executable_path"] = os.environ["CHROME_PATH"]
        browser = p.chromium.launch(**launch_args)
        try:
            ctx = browser.new_context(viewport={"width": W, "height": HGT}, device_scale_factor=SCALE,
                                      locale="uk-UA")
            for date_iso, update, groups, changes in jobs:
                page = ctx.new_page()
                try:
                    page.set_content(build_html(date_iso, update, groups, changes),
                                     wait_until="load", timeout=30000)
                except Exception:  # noqa: BLE001  (наприклад, не завантажився шрифт — малюємо запасним)
                    pass
                try:
                    page.evaluate("document.fonts.ready.then(() => true)")
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(300)
                out.append(page.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": W, "height": HGT}))
                page.close()
        finally:
            browser.close()
    return out
