# DTEK schedule bot

Бере графік з https://www.dtek-krem.com.ua/ua/shutdowns, малює картинку «Графік вмикань світла»
(години, коли світло **є**) і публікує/оновлює її в Telegram-каналі. Працює у GitHub Actions кожні ~10 хв.

## Налаштування (Settings → Secrets and variables → Actions)
| Назва | Що це | Обовʼязково |
|---|---|---|
| `BOT_TOKEN` (Secret) | токен від @BotFather | так |
| `CHANNEL_ID` (Secret) | `@назва_каналу` або `-100…` | так |
| `ADMIN_CHAT_ID` (Secret) | ваш особистий chat id для сповіщень про збої | ні |
| `NOTIFY_REPLY` (Variable) | `1` — після зміни додатково писати повідомлення-відповідь (воно дзвонить підписникам), `0` — лише редагувати пост | ні, за замовчуванням `1` |

## Як це працює
1. `bot/fetch.py` відкриває сторінку ДТЕК у браузері й бере JSON `DisconSchedule.fact`.
2. `bot/schedule.py` перетворює години на інтервали «світло є» та порівнює з `state.json`.
3. `bot/render.py` малює картинку (`assets/background.png`, `assets/logo.png`).
4. `bot/main.py` публікує новий пост або редагує існуючий; змінені інтервали підкреслено, у підписі — «було → стало».

## Локальний тест
```
pip install playwright && playwright install chromium
python -m bot.main --dry-run --fixture page.html   # картинки з'являться в out/
```
