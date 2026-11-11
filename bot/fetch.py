"""Завантаження сторінки ДТЕК через браузер (потрібен для проходження антибот-перевірки)."""
import os
from playwright.sync_api import sync_playwright

URL = "https://www.dtek-krem.com.ua/ua/shutdowns"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch_html(attempts: int = 3) -> str:
    last_error = "невідомо"
    with sync_playwright() as p:
        launch_args = {"headless": True}
        if os.environ.get("CHROME_PATH"):          # лише для локальних тестів
            launch_args["executable_path"] = os.environ["CHROME_PATH"]
        browser = p.chromium.launch(**launch_args)
        try:
            for attempt in range(1, attempts + 1):
                ctx = browser.new_context(locale="uk-UA", timezone_id="Europe/Kyiv",
                                          viewport={"width": 1400, "height": 900}, user_agent=UA)
                page = ctx.new_page()
                try:
                    resp = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                    status = resp.status if resp else None
                    for _ in range(8):                      # до ~40 с на антибот-перевірку
                        page.wait_for_timeout(5000)
                        html = page.content()
                        if "DisconSchedule.fact" in html:
                            return html
                    last_error = f"спроба {attempt}: HTTP {status}, графіка на сторінці немає"
                except Exception as e:  # noqa: BLE001
                    last_error = f"спроба {attempt}: {type(e).__name__}: {e}"
                finally:
                    ctx.close()
        finally:
            browser.close()
    raise RuntimeError(last_error)
