# Конспектор лекций — Telegram-бот

Бесплатный Telegram-бот: присылаете голосовое, аудио или видео лекции, вебинара или урока — получаете конспект по разделам, термины с пояснениями, выводы, черновик статьи и файл Word с полной расшифровкой.

Бот: [@KonspektLectureBot](https://t.me/KonspektLectureBot)

*English: a free Telegram bot that turns lecture/webinar recordings into structured notes, a glossary, key takeaways, a draft blog article and a Word file with the full transcript. Self-hosted: Whisper + a local LLM via Ollama. Works with Russian and English.*

## Как работает

1. **Приём.** Бот ставит запись в очередь: у каждого пользователя одновременно одна запись, видно место в очереди и процент готовности.
2. **Расшифровка.** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (модель large-v3-turbo) переводит речь в текст и определяет язык записи.
3. **Конспект.** Локальная модель Qwen3-VL 8B в [Ollama](https://ollama.com) читает длинную расшифровку по частям, выписывает тезисы и термины, затем собирает итоговый конспект и выводы.
4. **Статья.** По конспекту пишется черновик статьи для блога.
5. **Выдача.** Конспект и статья приходят в чат, файл Word — отдельно. После этого запись и тексты удаляются.

После отправки записи бот спрашивает, что сделать: **«🧠 Конспект и статья»** (всё по шагам выше) или **«📄 Только расшифровка»** — дословный текст без обработки нейросетью: в чат (если запись короткая) и файлом Word. Второй режим быстрее, потому что пропускает шаги 3–4.

Нейросеть может ошибиться в терминах — бот честно об этом предупреждает и показывает список сомнительных слов: те, в которых не уверен Whisper, и те, что модель пометила «(?)».

## Приватность

- Всё работает на своём сервере, без облачных ИИ.
- Файл, расшифровка и конспект удаляются сразу после отправки.
- В базе (SQLite) хранятся только Telegram ID и счётчики; для статистики источников — только количество пришедших по каждой метке `?start=...`.

## Файлы

| Файл | Что делает |
|---|---|
| `bot.py` | Telegram-бот (aiogram 3): очередь, команды, выдача результата |
| `transcribe.py` | Расшифровка: ffmpeg → faster-whisper (видеокарта, а если её нет — процессор) |
| `notes.py` | Конспект, термины, выводы и статья через Ollama (русский и английский) |
| `render.py` | Markdown → HTML для Telegram и файл Word (python-docx) |
| `i18n.py` | Тексты бота на русском и английском |
| `e2e_test.py` | Проверка всей цепочки без Telegram: `python e2e_test.py запись.mp3 папка` |
| `set_token.sh` | Скрытый ввод токена бота и запуск службы |
| `set_api.sh` | Свой сервер Telegram Bot API (файлы до 2 ГБ вместо 20 МБ) |
| `*.service` | Службы systemd |
| `promo/` | Тексты для продвижения |

## Установка (Ubuntu)

```bash
sudo apt install ffmpeg
sudo mkdir -p /opt/lecture-bot && sudo chown $USER /opt/lecture-bot
cp -r . /opt/lecture-bot && cd /opt/lecture-bot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo cp lecture-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload
bash set_token.sh          # токен из @BotFather
bash set_api.sh            # необязательно: api_id/api_hash с my.telegram.org для файлов до 2 ГБ
```

Нужна запущенная Ollama с моделью (по умолчанию `qwen3-vl:8b-instruct`, меняется переменной `MODEL` в `.env`). Для `set_api.sh` сначала соберите [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) в `/usr/local/bin`.

Настройки в `.env`: `MODEL`, `NUM_CTX`, `WHISPER_MODEL`, `WHISPER_DEVICE` (auto/cuda/cpu), `WHISPER_INDEX`, `MAX_MINUTES`, `BOT_API_URL`, `PRIVATE` (1 — бот отвечает только владельцу, остальным пишет, что закрыт), `OWNER_IDS` (Telegram ID владельцев через запятую).
