"""Головний скрипт: забрати графік -> порівняти -> намалювати -> опублікувати/оновити в Telegram.

Запуск:  python -m bot.main            (бойовий режим, потрібні BOT_TOKEN і CHANNEL_ID)
         python -m bot.main --dry-run  (без Telegram, картинки в папку out/)
         python -m bot.main --fixture page.html   (брати дані з файлу, а не з сайту)
"""
import argparse
import html as H
import json
import os
import sys
from pathlib import Path

from . import telegram as tg
from .fetch import fetch_html
from .render import render_many
from .schedule import (GROUPS, ParseError, day_label, diff_groups, has_any_outage,
                       ivs_text, parse_fact)

STATE_PATH = Path(os.environ.get("STATE_PATH", "state.json"))
KEEP_DAYS = 4
CAPTION_LIMIT = 1024
FAIL_ALERT_AFTER = 3


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"days": {}, "failures": 0}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def changes_lines(changes: dict) -> list:
    lines = []
    for g, c in changes.items():
        lines.append(f"• <b>{g}</b>: <s>{H.escape(ivs_text(c['prev']))}</s> → <b>{H.escape(ivs_text(c['new']))}</b>")
    return lines


def build_caption(date_iso: str, update: str, groups: dict, changes: dict) -> str:
    date_txt, weekday = day_label(date_iso)
    if changes:
        head = (f"🔄 <b>Оновлення графіка вмикань на {date_txt}</b> ({weekday})\n"
                f"🕒 Оновлено ДТЕК: {H.escape(update)}")
    else:
        head = (f"💡 <b>Графік вмикань світла на {date_txt}</b> ({weekday})\n"
                f"🕒 Оновлено ДТЕК: {H.escape(update)}")
    parts = [head]
    if changes:
        lines = changes_lines(changes)
        names = ", ".join(changes)
        parts.append(f"❗ <b>Змінилися черги: {names}</b>\n(було → стало)\n" + "\n".join(lines))
    full = "\n".join(f"<b>{g}</b>: {H.escape(ivs_text(groups[g]))}" for g in GROUPS)
    parts.append("⚡ <b>Світло є:</b>\n" + full)
    caption = "\n\n".join(parts)
    if len(caption) > CAPTION_LIMIT and changes:          # спершу прибираємо повний список
        caption = "\n\n".join(parts[:2])
    if len(caption) > CAPTION_LIMIT:                       # потім скорочуємо перелік змін
        lines = changes_lines(changes)
        mk = lambda ls: "\n\n".join([head, f"❗ <b>Змінилися черги: {', '.join(changes)}</b>\n(було → стало)\n"
                                    + "\n".join(ls) + ("\n…" if len(ls) < len(lines) else "")])
        while lines and len(mk(lines)) > CAPTION_LIMIT:
            lines.pop()
        caption = mk(lines)
    return caption[:CAPTION_LIMIT]


def alert(token, admin_chat, text):
    print("ALERT:", text)
    if token and admin_chat:
        try:
            tg.send_text(token, admin_chat, text)
        except Exception as e:  # noqa: BLE001
            print("Не вдалося надіслати сповіщення адміну:", e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture")
    args = ap.parse_args(argv)

    token = os.environ.get("BOT_TOKEN")
    chat = os.environ.get("CHANNEL_ID")
    admin = os.environ.get("ADMIN_CHAT_ID")
    dry = args.dry_run
    if not dry and not (token and chat):
        print("Не задано BOT_TOKEN або CHANNEL_ID", file=sys.stderr)
        return 1

    state = load_state()

    # 1. Забираємо й розбираємо дані
    try:
        html = Path(args.fixture).read_text(encoding="utf-8") if args.fixture else fetch_html()
        data = parse_fact(html)
    except (ParseError, RuntimeError, Exception) as e:  # noqa: BLE001
        state["failures"] = state.get("failures", 0) + 1
        print(f"Помилка отримання даних (поспіль: {state['failures']}): {e}")
        if state["failures"] == FAIL_ALERT_AFTER:
            alert(token, admin, f"⚠️ Бот графіка не може отримати дані ДТЕК вже {FAIL_ALERT_AFTER} запуски поспіль.\n"
                                f"Остання помилка: {e}")
        if not dry:
            save_state(state)
        return 0
    if state.get("failures", 0) >= FAIL_ALERT_AFTER:
        alert(token, admin, "✅ Бот графіка знову отримує дані ДТЕК.")
    state["failures"] = 0

    update = data["update"]
    days_state = state.setdefault("days", {})

    # 2. Вирішуємо, що публікувати
    plan = []   # (date_iso, groups, changes, action, message_id)
    for date_iso in sorted(data["days"]):
        groups = data["days"][date_iso]
        old = days_state.get(date_iso)
        if old is None:
            if not has_any_outage(groups):
                continue                       # графік на цей день ще не опубліковано / відключень немає
            plan.append((date_iso, groups, {}, "new", None))
        else:
            changes = diff_groups(old["groups"], groups)
            if changes:
                plan.append((date_iso, groups, changes, "edit", old.get("message_id")))
            else:
                old["update"] = update         # лише оновилась дата — нічого не публікуємо

    if not plan:
        print("Змін немає.")
        if not dry:
            save_state(state)
        return 0

    # 3. Малюємо
    images = render_many([(d, update, g, ch) for d, g, ch, _, _ in plan])

    # 4. Публікуємо
    outdir = Path("out")
    if dry:
        outdir.mkdir(exist_ok=True)
    for (date_iso, groups, changes, action, mid), jpg in zip(plan, images):
        caption = build_caption(date_iso, update, groups, changes)
        if dry:
            (outdir / f"{date_iso}_{action}.jpg").write_bytes(jpg)
            print(f"[dry-run] {date_iso} {action}\n{caption}\n---")
            days_state[date_iso] = {"groups": groups, "message_id": mid or 0, "update": update}
            continue
        # Кожна зміна графіка — окремий новий пост (старі пости не чіпаємо)
        message_id = tg.send_photo(token, chat, jpg, caption)
        print(f"Опубліковано {'оновлення' if changes else 'графік'} {date_iso} (message {message_id})")
        days_state[date_iso] = {"groups": groups, "message_id": message_id, "update": update}

    # 5. Прибираємо старі дні зі стану
    for old_date in sorted(days_state)[:-KEEP_DAYS]:
        days_state.pop(old_date, None)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
