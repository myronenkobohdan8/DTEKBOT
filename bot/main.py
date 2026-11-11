"""Головний скрипт: забрати графік -> порівняти -> намалювати -> опублікувати новий пост у Telegram.

Запуск:  python -m bot.main            (бойовий режим, потрібні BOT_TOKEN і CHANNEL_ID)
         python -m bot.main --dry-run  (без Telegram, картинки в папку out/)
         python -m bot.main --fixture page.html   (брати дані з файлу, а не з сайту)

У state.json зберігаються інтервали «світло є» (так, як їх віддає ДТЕК); на картинці й у тексті
показуємо протилежне — періоди без світла.
"""
import argparse
import html as H
import json
import os
import re
import sys
from pathlib import Path

from . import telegram as tg
from .fetch import fetch_html
from .render import render_many
from .schedule import (GROUPS, ParseError, day_label_acc, diff_groups, has_any_outage,
                       invert, parse_fact)

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


# ---------- текст під фото ----------

def _iv(iv: str) -> str:
    return iv.replace("-", " – ")


def _group_block(g: str, ivs: list) -> str:
    lines = [f"<b>Черга {g}:</b>"]
    lines += [f"• {_iv(i)}" for i in ivs] if ivs else ["• відключень немає"]
    return "\n".join(lines)


def _groups_text(groups_off: dict, names: list) -> str:
    """Черги однієї пари (1.1 і 1.2) йдуть підряд, між парами — порожній рядок."""
    pairs = {}
    for g in names:
        pairs.setdefault(g.split(".")[0], []).append(_group_block(g, groups_off[g]))
    return "\n\n".join("\n".join(blocks) for blocks in pairs.values())


def build_caption(date_iso: str, update: str, groups_off: dict, changes: dict) -> str:
    label = day_label_acc(date_iso)
    if changes:
        head = f"💡 Оновлено графік відключень на {label}\n\nЗміни для наступних черг:\n"
        body = _groups_text(groups_off, [g for g in GROUPS if g in changes])
    else:
        head = f"💡 Графік відключень на {label}\n\n❌ Періоди вимкнень:\n\n"
        body = _groups_text(groups_off, GROUPS)
    return f"{head}{body}\n\n🕒 Оновлено ДТЕК: {H.escape(update)}"


def plain_len(text: str) -> int:
    return len(re.sub(r"<[^>]+>", "", H.unescape(text)))


def publish(token: str, chat: str, jpg: bytes, caption: str) -> int:
    """Фото з підписом. Якщо підпис довший за ліміт Telegram — фото з заголовком + повний текст відповіддю."""
    if plain_len(caption) <= CAPTION_LIMIT:
        return tg.send_photo(token, chat, jpg, caption)
    first_line = caption.split("\n", 1)[0]
    message_id = tg.send_photo(token, chat, jpg, first_line)
    tg.send_text(token, chat, caption, reply_to=message_id)
    return message_id


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
    except Exception as e:  # noqa: BLE001
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
    plan = []   # (date_iso, groups_on, changes, message_id)
    for date_iso in sorted(data["days"]):
        groups_on = data["days"][date_iso]
        old = days_state.get(date_iso)
        if old is None:
            if not has_any_outage(groups_on):
                continue                       # графік на цей день ще не опубліковано / відключень немає
            plan.append((date_iso, groups_on, {}, None))
        else:
            changes = diff_groups(old["groups"], groups_on)
            if changes:
                plan.append((date_iso, groups_on, changes, old.get("message_id")))
            else:
                old["update"] = update         # змінилась лише дата оновлення — нічого не публікуємо

    if not plan:
        print("Змін немає.")
        if not dry:
            save_state(state)
        return 0

    # 3. Малюємо (на картинці й у тексті — періоди БЕЗ світла)
    off = {d: {g: invert(iv) for g, iv in groups_on.items()} for d, groups_on, _, _ in plan}
    images = render_many([(d, update, off[d], ch) for d, _, ch, _ in plan])

    # 4. Публікуємо: кожна зміна — окремий новий пост
    outdir = Path("out")
    if dry:
        outdir.mkdir(exist_ok=True)
    for (date_iso, groups_on, changes, _), jpg in zip(plan, images):
        caption = build_caption(date_iso, update, off[date_iso], changes)
        kind = "update" if changes else "new"
        if dry:
            (outdir / f"{date_iso}_{kind}.jpg").write_bytes(jpg)
            print(f"[dry-run] {date_iso} {kind} (довжина підпису {plain_len(caption)})\n{caption}\n---")
            days_state[date_iso] = {"groups": groups_on, "message_id": 0, "update": update}
            continue
        message_id = publish(token, chat, jpg, caption)
        print(f"Опубліковано {'оновлення' if changes else 'графік'} {date_iso} (message {message_id})")
        days_state[date_iso] = {"groups": groups_on, "message_id": message_id, "update": update}

    # 5. Прибираємо старі дні зі стану
    for old_date in sorted(days_state)[:-KEEP_DAYS]:
        days_state.pop(old_date, None)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
