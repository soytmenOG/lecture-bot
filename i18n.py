"""Тексты бота на русском и английском. Язык интерфейса — по языку Telegram пользователя."""

RU_LANGS = ("ru", "uk", "be", "kk", "uz", "ky", "tg", "hy", "az", "ka")


def ui_lang(code: str | None) -> str:
    return "ru" if (code or "ru").split("-")[0].lower() in RU_LANGS else "en"


T = {
    "ru": {
        "hello": ("👋 Я делаю конспекты лекций и вебинаров.\n\n"
                  "Пришлите <b>голосовое, аудио или видео</b> (можно файлом) — в ответ получите:\n"
                  "• структурированный конспект по разделам\n"
                  "• термины с пояснениями\n"
                  "• главные выводы\n"
                  "• черновик статьи для блога\n"
                  "• файл Word со всем этим и полной расшифровкой\n\n"
                  "Нужен только текст? После отправки записи нажмите «📄 Только расшифровка» — "
                  "получите дословный текст без конспекта, так быстрее.\n\n"
                  "Понимаю русский и английский: конспект будет на языке записи.\n"
                  "Бесплатно. Запись до {max_min} мин, файл до {max_mb}.\n\n"
                  "⚠️ Нейросеть может ошибаться в терминах, именах и цифрах — проверяйте их.\n"
                  "🔒 Запись и тексты удаляются сразу после отправки результата. Подробнее: /privacy"),
        "owner": "✅ Вы владелец бота. Статистика: /stats",
        "privacy": ("🔒 <b>Приватность</b>\n\n"
                    "• Всё считается на нашем собственном сервере, записи никуда не передаются.\n"
                    "• Файл, расшифровка и конспект удаляются сразу после отправки вам.\n"
                    "• Сама переписка с ботом стирается через сутки.\n"
                    "• Храним только ваш Telegram ID и счётчики: сколько записей и минут обработано.\n"
                    "• Поэтому сохраните результат у себя — повторно мы его выдать не сможем."),
        "nothing": "Сейчас у вас ничего не обрабатывается.",
        "stopping": "Останавливаю…",
        "not_media": "Это не похоже на аудио или видео. Пришлите запись лекции: mp3, m4a, wav, ogg, mp4, mov и т.п.",
        "busy": "У вас уже есть запись в работе. Дождитесь результата или отмените её: /cancel",
        "too_big": ("❌ Файл слишком большой ({size} МБ), можно до {max} МБ.\n"
                    "Совет: пришлите только звук (mp3/m4a) — он в разы меньше видео."),
        "too_long": "❌ Запись длиннее {max} минут. Разрежьте её на части и пришлите по очереди.",
        "queued": "⏳ В очереди: вы {n}-й. Начну, как только освободится место.",
        "accepted": "⏳ Принято, начинаю…",
        "other": "Пришлите голосовое, аудио или видео лекции — я сделаю конспект. Подробнее: /help",
        "getting": "📥 Получаю файл…",
        "too_long_real": "❌ Запись длиннее {max} минут ({len}). Разрежьте её на части и пришлите по очереди.",
        "preparing": "🎧 Готовлю звук ({len})…",
        "no_sound": "❌ В файле нет звука или он короче 3 секунд.",
        "transcribing": "✍️ Расшифровываю ({dev})…",
        "progress": "✍️ Расшифровываю: {p}%{left}",
        "left": ", осталось ≈{t}",
        "little_text": ("❌ Почти не удалось разобрать речь — слишком мало текста для конспекта. "
                        "Проверьте, что в записи есть речь."),
        "done": "✅ Готово: {len} записи обработаны за {work}.",
        "doubt": "🔎 Распознавание не уверено в словах: ",
        "article": "📝 ЧЕРНОВИК СТАТЬИ",
        "docx_caption": "Всё в одном файле Word: конспект, статья и полная расшифровка.",
        "share_ask": "Пригодилось? Поделитесь ботом с одногруппниками, коллегами или учениками — это бесплатно 🙌",
        "share_btn": "📤 Поделиться ботом",
        "share_text": "Бот делает конспект лекции из аудио или видео: тезисы, термины, выводы и статья. Бесплатно.",
        "cancelled": "⏹ Отменено.",
        "failed": "❌ Не получилось обработать запись: {err}\nПопробуйте ещё раз или пришлите другой файл.",
        "file_too_big": "файл больше {max} МБ",
        "min": "мин", "h": "ч", "gb": "ГБ", "mb": "МБ",
        "steps": {"read": "Читаю расшифровку: часть {i} из {n}", "merge": "Объединяю заметки",
                  "final": "Пишу конспект, термины и выводы", "article": "Пишу черновик статьи"},
        "cpu": "процессор", "gpu": "видеокарта",
        "closed": "🔒 Бот сейчас закрыт и работает только для владельца.",
        "autodel": "🕓 Через {h} ч вся эта переписка будет стёрта — сохраните файл Word у себя.",
        "choose": "Что сделать с записью?",
        "btn_notes": "🧠 Конспект и статья",
        "btn_text": "📄 Только расшифровка",
        "expired": "Эта кнопка устарела — пришлите запись ещё раз.",
        "no_speech": "❌ Не удалось разобрать речь в записи.",
        "text_done": "✅ Расшифровка готова: {len} записи за {work}.",
        "text_warn": ("⚠️ Дословная автоматическая расшифровка, нейросеть текст не правила. "
                      "Возможны ошибки в терминах, именах и цифрах."),
        "text_long": "Текст длинный, поэтому целиком он в файле ниже.",
        "text_caption": "Дословная расшифровка в файле Word.",
    },
    "en": {
        "hello": ("👋 I turn lectures and webinars into notes.\n\n"
                  "Send a <b>voice message, audio or video</b> (a file is fine too) and get back:\n"
                  "• structured notes by section\n"
                  "• key terms with explanations\n"
                  "• main takeaways\n"
                  "• a draft blog article\n"
                  "• a Word file with all of the above plus the full transcript\n\n"
                  "Only need the text? After sending a recording, tap \"📄 Transcript only\" — "
                  "you'll get a word-for-word transcript without notes, which is faster.\n\n"
                  "Works with English and Russian: notes come in the language of the recording.\n"
                  "Free. Recordings up to {max_min} min, files up to {max_mb}.\n\n"
                  "⚠️ AI can get terms, names and numbers wrong — please double-check them.\n"
                  "🔒 Your recording and texts are deleted right after you get the result. More: /privacy"),
        "owner": "✅ You are the bot owner. Stats: /stats",
        "privacy": ("🔒 <b>Privacy</b>\n\n"
                    "• Everything runs on our own server; recordings are never sent anywhere else.\n"
                    "• The file, transcript and notes are deleted right after they are sent to you.\n"
                    "• The chat with the bot itself is erased after 24 hours.\n"
                    "• We only keep your Telegram ID and counters: how many recordings and minutes.\n"
                    "• So save the result — we can't send it again."),
        "nothing": "Nothing of yours is being processed right now.",
        "stopping": "Stopping…",
        "not_media": "This doesn't look like audio or video. Send a lecture recording: mp3, m4a, wav, ogg, mp4, mov, etc.",
        "busy": "You already have a recording in progress. Wait for the result or cancel it: /cancel",
        "too_big": ("❌ The file is too large ({size} MB), the limit is {max} MB.\n"
                    "Tip: send audio only (mp3/m4a) — it is much smaller than video."),
        "too_long": "❌ The recording is longer than {max} minutes. Please split it and send the parts one by one.",
        "queued": "⏳ You are #{n} in the queue. I'll start as soon as a slot is free.",
        "accepted": "⏳ Got it, starting…",
        "other": "Send a voice message, audio or video of a lecture and I'll make notes. More: /help",
        "getting": "📥 Getting the file…",
        "too_long_real": "❌ The recording is longer than {max} minutes ({len}). Please split it and send the parts.",
        "preparing": "🎧 Preparing audio ({len})…",
        "no_sound": "❌ The file has no sound or is shorter than 3 seconds.",
        "transcribing": "✍️ Transcribing ({dev})…",
        "progress": "✍️ Transcribing: {p}%{left}",
        "left": ", ≈{t} left",
        "little_text": ("❌ Could hardly recognise any speech — not enough text for notes. "
                        "Please check that the recording contains speech."),
        "done": "✅ Done: {len} of audio processed in {work}.",
        "doubt": "🔎 Speech recognition is unsure about: ",
        "article": "📝 DRAFT ARTICLE",
        "docx_caption": "Everything in one Word file: notes, article and the full transcript.",
        "share_ask": "Found it useful? Share the bot with classmates, colleagues or students — it's free 🙌",
        "share_btn": "📤 Share the bot",
        "share_text": "A free bot that turns lecture audio or video into notes: key points, terms, takeaways and an article.",
        "cancelled": "⏹ Cancelled.",
        "failed": "❌ Couldn't process the recording: {err}\nPlease try again or send another file.",
        "file_too_big": "file is larger than {max} MB",
        "min": "min", "h": "h", "gb": "GB", "mb": "MB",
        "steps": {"read": "Reading the transcript: part {i} of {n}", "merge": "Merging notes",
                  "final": "Writing notes, terms and takeaways", "article": "Writing the draft article"},
        "cpu": "CPU", "gpu": "GPU",
        "closed": "🔒 This bot is currently private and works only for its owner.",
        "autodel": "🕓 This whole chat will be erased in {h} h — save the Word file.",
        "choose": "What should I do with the recording?",
        "btn_notes": "🧠 Notes and article",
        "btn_text": "📄 Transcript only",
        "expired": "This button has expired — please send the recording again.",
        "no_speech": "❌ Couldn't recognise any speech in the recording.",
        "text_done": "✅ Transcript ready: {len} of audio in {work}.",
        "text_warn": ("⚠️ Word-for-word automatic transcript, not edited by AI. "
                      "Terms, names and numbers may contain errors."),
        "text_long": "The text is long, so the full version is in the file below.",
        "text_caption": "Word-for-word transcript in a Word file.",
    },
}

WARN = {
    "ru": ("⚠️ Конспект сделан нейросетью по автоматической расшифровке. "
           "Она может ошибаться в терминах, именах, цифрах и формулах — проверьте их перед публикацией."),
    "en": ("⚠️ These notes were written by AI from an automatic transcript. "
           "It can get terms, names, numbers and formulas wrong — please check them before publishing."),
}
