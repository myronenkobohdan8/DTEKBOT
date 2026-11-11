"""Тест: чи відкриває ДТЕК сторінку графіка з сервера GitHub Actions."""
import re
from playwright.sync_api import sync_playwright

URL = "https://www.dtek-krem.com.ua/ua/shutdowns"
BLOCK_MARKERS = ["Incapsula", "_Incapsula_Resource", "Access Denied", "captcha", "Request unsuccessful"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        locale="uk-UA",
        timezone_id="Europe/Kyiv",
        viewport={"width": 1400, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()
    resp = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    status = resp.status if resp else None
    page.wait_for_timeout(10000)  # час на проходження антибот-перевірки

    html = page.content()
    title = page.title()
    open("page.html", "w", encoding="utf-8").write(html)
    page.screenshot(path="page.png", full_page=False)

    blocked = [m for m in BLOCK_MARKERS if m.lower() in html.lower()]
    has_schedule = "DisconnectScheduleData" in html or "fact" in html and "data" in html
    ajax = re.search(r'name="ajaxUrl"\s+content="([^"]+)"', html)

    print("=" * 50)
    print("HTTP статус:", status)
    print("Заголовок:", title)
    print("Розмір HTML:", len(html))
    print("Ознаки блокування:", blocked or "немає")
    print("ajaxUrl:", ajax.group(1) if ajax else "не знайдено")
    print("Є дані графіка (DisconnectScheduleData):", "DisconnectScheduleData" in html)

    m = re.search(r"DisconnectScheduleData\s*=\s*(\{.{0,600})", html, re.S)
    if m:
        print("Початок даних:", m.group(1)[:600])

    if status == 200 and not blocked and len(html) > 20000:
        print("ВЕРДИКТ: ДОСТУП Є")
    else:
        print("ВЕРДИКТ: ПОХОЖЕ, ЗАБЛОКОВАНО (дивіться page.png)")
    print("=" * 50)
    browser.close()
