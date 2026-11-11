"""Малює картинку 1:1 «Графік відключень світла»: HTML/CSS -> JPEG через Playwright.

Усі передані сюди інтервали — це періоди БЕЗ світла.
"""
import base64
import html as H
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from .schedule import GROUPS, day_label, pretty, total_hours_text

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZE, SCALE = 1080, 1.5

SOURCE_TEXT = "Джерело: ДТЕК"
CHANNEL_TEXT = "t.me/your_boryspil"

BLUE = "#0B4BAE"      # синій з логотипа
YELLOW = "#FFEB1F"    # жовтий з логотипа
INK = "#262B33"
RED = "#C62828"


def _b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# Перекреслена блискавка (світла немає)
BOLT_OFF = ('<svg class="bolt" viewBox="0 0 24 24">'
            f'<path d="M13.5 1 4 13.5h6.2L9 23l10-13.2h-6.4z" fill="{INK}"/>'
            '<path d="M3 3 21 22" stroke="#fff" stroke-width="3.8" stroke-linecap="round"/>'
            f'<path d="M3 3 21 22" stroke="{INK}" stroke-width="1.9" stroke-linecap="round"/></svg>')
MOON = ('<svg class="moon" viewBox="0 0 24 24"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" '
        'fill="#7b8794"/></svg>')

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{SIZE}px;height:{SIZE}px}}
body{{font-family:'Montserrat','Inter','DejaVu Sans',sans-serif;color:{INK};
  background:#cfe0f3 url('__BG__') center/cover no-repeat;position:relative;overflow:hidden}}
.header{{position:absolute;left:34px;right:34px;top:24px;height:150px;display:flex;
  align-items:center;justify-content:space-between;gap:24px}}
.title{{flex:1;min-width:0}}
.title h1{{font-size:50px;font-weight:800;line-height:1.1;letter-spacing:-.5px;white-space:nowrap}}
.title .day{{display:flex;align-items:center;gap:14px;font-size:33px;font-weight:700;color:{BLUE};margin-top:6px}}
.badge{{background:{YELLOW};color:{INK};font-size:17px;font-weight:800;padding:4px 14px;border-radius:12px;
  letter-spacing:.4px}}
.title .upd{{font-size:21px;font-weight:500;color:#4a5568;margin-top:8px}}
.logo{{height:128px;width:auto;flex:none;position:relative;z-index:2}}
.header{{z-index:2}}
.glow{{position:absolute;left:640px;top:-40px;width:480px;height:270px;z-index:1;pointer-events:none;background:radial-gradient(ellipse at 62% 52%,rgba(60,120,200,.38) 0%,rgba(60,120,200,.18) 45%,transparent 75%),url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='260' height='260'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.1' numOctaves='3' stitchTiles='stitch'/><feColorMatrix type='matrix' values='0 0 0 0 0.15  0 0 0 0 0.30  0 0 0 0 0.55  0 0 0 1.6 -0.35'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");background-size:auto,260px 260px;-webkit-mask-image:radial-gradient(ellipse at 62% 52%,#000 25%,transparent 72%);mask-image:radial-gradient(ellipse at 62% 52%,#000 25%,transparent 72%)}}
.grid{{z-index:3;position:absolute;left:34px;right:34px;top:188px;bottom:68px;display:grid;
  grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(3,1fr);gap:13px}}
.card{{position:relative;background:rgba(255,255,255,.88);border-radius:20px;padding:12px 11px 10px 13px;
  display:flex;flex-direction:column;box-shadow:0 5px 16px rgba(20,50,100,.14);min-width:0}}
.card.changed{{box-shadow:0 0 0 4px {YELLOW},0 5px 16px rgba(20,50,100,.18)}}
.tag{{position:absolute;top:-11px;right:12px;background:{YELLOW};color:{INK};font-size:13px;
  font-weight:800;padding:2px 10px;border-radius:10px;letter-spacing:.3px}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:6px}}
.pill{{background:{BLUE};color:#fff;font-size:30px;font-weight:800;padding:1px 13px;border-radius:12px}}
.hrs{{display:flex;align-items:center;gap:5px;line-height:1.15}}
.moon{{width:19px;height:19px;flex:none}}
.hrs .tx{{font-size:13.5px;font-weight:500;color:#5b6575}}
.hrs .tx b{{display:block;font-size:15.5px;font-weight:800;color:{RED};white-space:nowrap}}
.hrs.ok .tx b{{color:#1b7f3b}}
.list{{flex:1;display:flex;flex-direction:column;justify-content:center;gap:9px;margin-top:4px}}
.row{{display:flex;align-items:center;gap:8px;font-size:28.5px;font-weight:700;
  font-variant-numeric:tabular-nums;white-space:nowrap;letter-spacing:-.3px}}
.bolt{{width:25px;height:25px;flex:none}}
.row.new .t{{text-decoration:underline;text-decoration-thickness:4px;text-decoration-color:{RED};
  text-underline-offset:5px;background:rgba(255,235,31,.75);padding:0 5px;margin:0 -5px;border-radius:5px}}
.row.none{{font-size:20px;color:#1b7f3b;font-weight:700;justify-content:center;text-align:center}}
.footer{{z-index:3;position:absolute;left:34px;right:34px;bottom:22px;display:flex;align-items:center;
  justify-content:space-between;font-size:20px;font-weight:600;color:#3b4656}}
.footer .ch{{color:{BLUE};font-weight:700}}
.legend span.u{{text-decoration:underline;text-decoration-thickness:3px;text-decoration-color:{RED};
  text-underline-offset:4px;background:rgba(255,235,31,.75);padding:0 5px;border-radius:5px;color:{INK}}}
"""


FIT_JS = """() => {
  const fit = (sel, min) => {
    const els = [...document.querySelectorAll(sel)];
    if (!els.length) return;
    let fs = parseFloat(getComputedStyle(els[0]).fontSize);
    const ok = () => els.every(e => e.scrollWidth <= e.clientWidth + 1);
    while (!ok() && fs > min) { fs -= 0.5; els.forEach(e => e.style.fontSize = fs + 'px'); }
  };
  fit('.row:not(.none)', 20);
  fit('h1', 34);
}"""


def build_html(date_iso: str, update: str, groups_off: dict, changes: dict = None) -> str:
    changes = changes or {}
    date_txt, weekday = day_label(date_iso)
    cards = []
    for g in GROUPS:
        ivs = groups_off[g]
        added = set(changes.get(g, {}).get("added", []))
        if ivs:
            rows = "".join(
                f'<div class="row{" new" if i in added else ""}">{BOLT_OFF}'
                f'<span class="t">{H.escape(pretty(i))}</span></div>' for i in ivs)
            hrs = (f'<div class="hrs">{MOON}<div class="tx">без світла'
                   f'<b>{H.escape(total_hours_text(ivs))}</b></div></div>')
        else:
            rows = '<div class="row none">Відключень немає</div>'
            hrs = '<div class="hrs ok"><div class="tx"><b>світло є</b></div></div>'
        tag = '<div class="tag">ЗМІНЕНО</div>' if g in changes else ""
        cards.append(f'<div class="card{" changed" if g in changes else ""}">{tag}'
                     f'<div class="top"><div class="pill">{g}</div>{hrs}</div>'
                     f'<div class="list">{rows}</div></div>')

    badge = '<span class="badge">ОНОВЛЕННЯ</span>' if changes else ""
    legend = ('<div class="legend"><span class="u">Підкреслено</span> — нові години</div>' if changes else "")
    css = CSS.replace("__BG__", _b64(ASSETS / "background.png", "image/png"))
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&display=swap&subset=cyrillic" rel="stylesheet">
<style>{css}</style></head><body>
<div class="glow"></div>
<div class="header">
  <div class="title"><h1>Графік відключень світла</h1>
    <div class="day"><span>{H.escape(date_txt)} · {H.escape(weekday)}</span>{badge}</div>
    <div class="upd">Оновлено ДТЕК: {H.escape(update)}</div></div>
  <img class="logo" src="{_b64(ASSETS / 'logo.png', 'image/png')}">
</div>
<div class="grid">{''.join(cards)}</div>
<div class="footer"><span>{H.escape(SOURCE_TEXT)}</span>{legend}<span class="ch">{H.escape(CHANNEL_TEXT)}</span></div>
</body></html>"""


def render_many(jobs: list) -> list:
    """jobs: [(date_iso, update, groups_off, changes)] -> [jpeg bytes]. Один запуск браузера на всі картинки."""
    out = []
    with sync_playwright() as p:
        launch_args = {"headless": True}
        if os.environ.get("CHROME_PATH"):
            launch_args["executable_path"] = os.environ["CHROME_PATH"]
        browser = p.chromium.launch(**launch_args)
        try:
            ctx = browser.new_context(viewport={"width": SIZE, "height": SIZE}, device_scale_factor=SCALE,
                                      locale="uk-UA")
            for date_iso, update, groups_off, changes in jobs:
                page = ctx.new_page()
                try:
                    page.set_content(build_html(date_iso, update, groups_off, changes),
                                     wait_until="load", timeout=30000)
                except Exception:  # noqa: BLE001  (наприклад, не завантажився шрифт — малюємо запасним)
                    pass
                try:
                    page.evaluate("document.fonts.ready.then(() => true)")
                except Exception:  # noqa: BLE001
                    pass
                try:
                    page.evaluate(FIT_JS)
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(300)
                out.append(page.screenshot(type="jpeg", quality=92,
                                           clip={"x": 0, "y": 0, "width": SIZE, "height": SIZE}))
                page.close()
        finally:
            browser.close()
    return out
