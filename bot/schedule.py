"""Розбір даних ДТЕК і порівняння графіків."""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")

# Статус години -> (перші 30 хв світло є?, другі 30 хв світло є?)
SLOT_MAP = {
    "yes": (1, 1),
    "no": (0, 0),
    "first": (0, 1),    # перші 30 хв світла немає
    "second": (1, 0),   # другі 30 хв світла немає
    "maybe": (1, 1),    # можливе відключення: вважаємо, що світло є
    "mfirst": (0, 1),
    "msecond": (1, 0),
}

GROUPS = [f"{a}.{b}" for a in range(1, 7) for b in (1, 2)]

MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
          "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
WEEKDAYS = ["понеділок", "вівторок", "середа", "четвер", "пʼятниця", "субота", "неділя"]


class ParseError(Exception):
    pass


def parse_fact(html: str) -> dict:
    """Дістає DisconSchedule.fact зі сторінки. Повертає {'update': str, 'days': {date_iso: {group: [interval,...]}}}."""
    m = re.search(r"DisconSchedule\.fact\s*=\s*", html)
    if not m:
        raise ParseError("На сторінці немає DisconSchedule.fact (можливо, блокування або зміна розмітки)")
    try:
        fact, _ = json.JSONDecoder().raw_decode(html[m.end():])
        raw_days = fact["data"]
        update = fact["update"]
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Не вдалося розібрати JSON графіка: {e}")

    days = {}
    for ts, groups in raw_days.items():
        date_iso = datetime.fromtimestamp(int(ts), KYIV).date().isoformat()
        missing = [g for g in GROUPS if f"GPV{g}" not in groups]
        if missing:
            raise ParseError(f"Немає черг {missing} за {date_iso}")
        days[date_iso] = {g: slots_to_intervals(groups[f"GPV{g}"]) for g in GROUPS}
    if not days:
        raise ParseError("Порожній список днів")
    return {"update": update, "days": days}


def _fmt(slot: int) -> str:
    return f"{slot // 2:02d}:{'30' if slot % 2 else '00'}"


def slots_to_intervals(hours: dict) -> list:
    """{'1': 'yes', ..., '24': 'no'} -> ['00:00-03:00', ...] — інтервали, коли світло Є."""
    on = []
    for h in range(1, 25):
        v = hours.get(str(h))
        if v not in SLOT_MAP:
            raise ParseError(f"Невідомий статус години: {v!r}")
        on.extend(SLOT_MAP[v])
    out, start = [], None
    for i, x in enumerate(on + [0]):
        if x and start is None:
            start = i
        elif not x and start is not None:
            end = "24:00" if i == 48 else _fmt(i)
            out.append(f"{_fmt(start)}-{end}")
            start = None
    return out


def minutes(interval: str) -> int:
    a, b = interval.split("-")
    f = lambda s: int(s[:2]) * 60 + int(s[3:])
    return f(b) - f(a)


def total_hours_text(intervals: list) -> str:
    m = sum(minutes(i) for i in intervals)
    h, r = divmod(m, 60)
    if h and r:
        return f"{h} год {r} хв"
    if h:
        return f"{h} год"
    return f"{r} хв" if r else "0 год"


def pretty(interval: str) -> str:
    return interval.replace("-", "–")


def day_label(date_iso: str):
    d = datetime.fromisoformat(date_iso)
    return f"{d.day} {MONTHS[d.month - 1]}", WEEKDAYS[d.weekday()]


def has_any_outage(groups: dict) -> bool:
    return any(iv != ["00:00-24:00"] for iv in groups.values())


def diff_groups(prev: dict, new: dict) -> dict:
    """{група: {'prev': [...], 'new': [...], 'added': [...]}} лише для змінених черг."""
    changes = {}
    for g in GROUPS:
        p, n = prev.get(g, []), new.get(g, [])
        if p != n:
            changes[g] = {"prev": p, "new": n, "added": [i for i in n if i not in p]}
    return changes
