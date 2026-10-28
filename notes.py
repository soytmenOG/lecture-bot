"""Конспект, термины, выводы и черновик статьи из расшифровки — локальная модель в Ollama.

Модель и num_ctx те же, что у BookAppraiser, чтобы не вытеснять её из видеопамяти.
Длинная расшифровка режется на куски: по каждому — тезисы и термины, потом общий итог.
Язык результата — язык записи: русский или английский (остальные языки — по-английски).
"""
import os
import re

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("MODEL", "qwen3-vl:8b-instruct")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
CHUNK = int(os.getenv("CHUNK_CHARS", "7000"))          # ≈2,5 тыс. токенов текста
REDUCE_LIMIT = int(os.getenv("REDUCE_LIMIT_CHARS", "12000"))

P = {
    "ru": {
        "system": ("Ты помогаешь составить конспект лекции или вебинара по автоматической расшифровке. "
                   "В расшифровке бывают ошибки распознавания: явные опечатки исправляй по смыслу, "
                   "но не выдумывай фактов, цифр и терминов, которых нет в тексте. "
                   "Если слово или аббревиатура похожи на ошибку распознавания и ты не уверен в правильном "
                   "варианте — оставь как есть и поставь сразу после него (?), например «спамочник (?)». "
                   "Никогда не придумывай расшифровку аббревиатур, которую лектор не назвал. "
                   "Пиши по-русски, без вступлений."),
        "map": """Фрагмент {i} из {n} расшифровки:
\"\"\"
{text}
\"\"\"

Выпиши строго в таком виде:
ТЕЗИСЫ:
- ключевые мысли фрагмента (5–12 пунктов, коротко, сохраняй цифры, примеры и формулы)
ТЕРМИНЫ:
- термин — пояснение так, как его объясняет лектор (только термины, которые есть в тексте; если нет — «нет»)""",
        "merge": """Ниже заметки по нескольким частям одной лекции. Объедини их в один список без повторов,
сохранив тот же вид (ТЕЗИСЫ: и ТЕРМИНЫ:), самое важное, цифры и примеры.

{text}""",
        "final": """Ниже заметки по частям лекции (по порядку). Составь итог в Markdown строго по шаблону:

# Название лекции (одной строкой, по смыслу)

## Конспект
### Название раздела (по смыслу, не «Раздел 1»)
- пункт
(3–7 смысловых разделов по ходу лекции, в каждом 3–8 пунктов, с цифрами и примерами)

## Термины
- **Термин** — пояснение (все специальные понятия, имена методов, законов и инструментов из лекции; без повторов, по алфавиту)

## Выводы
- 3–7 главных выводов лекции

Заметки:
{text}""",
        "article": """По этому конспекту лекции напиши черновик статьи для блога в Markdown:
заголовок (#), лид на 2–3 предложения, 3–5 разделов с подзаголовками (##), короткое заключение.
Объём 3500–6000 знаков. Живым понятным языком, без воды и канцелярита, к читателю на «вы».
Слова с пометкой (?) оставь с этой пометкой.
Не добавляй фактов, цифр и утверждений, которых нет в конспекте.

Конспект:
{text}""",
    },
    "en": {
        "system": ("You help write notes for a lecture or webinar from an automatic transcript. "
                   "The transcript may contain speech recognition errors: fix obvious typos by meaning, "
                   "but never invent facts, numbers or terms that are not in the text. "
                   "If a word or abbreviation looks like a recognition error and you are not sure of the correct "
                   "form, keep it and put (?) right after it, e.g. \"flux capacitator (?)\". "
                   "Never invent what an abbreviation stands for if the lecturer did not say it. "
                   "Write in English, no introductions."),
        "map": """Part {i} of {n} of the transcript:
\"\"\"
{text}
\"\"\"

Write exactly in this format:
KEY POINTS:
- key ideas of this part (5–12 bullets, short, keep numbers, examples and formulas)
TERMS:
- term — explanation as the lecturer gives it (only terms present in the text; if none — "none")""",
        "merge": """Below are notes on several parts of one lecture. Merge them into one list without repetition,
keeping the same format (KEY POINTS: and TERMS:), the most important ideas, numbers and examples.

{text}""",
        "final": """Below are notes on the parts of a lecture (in order). Write the result in Markdown strictly in this template:

# Lecture title (one line, by meaning)

## Notes
### Section title (by meaning, not "Section 1")
- bullet
(3–7 sections following the lecture, 3–8 bullets each, with numbers and examples)

## Terms
- **Term** — explanation (every special concept, named method, law, algorithm or tool from the lecture; no repetition, alphabetical)

## Takeaways
- 3–7 main takeaways of the lecture

Notes:
{text}""",
        "article": """Using these lecture notes, write a draft blog article in Markdown:
a title (#), a 2–3 sentence lead, 3–5 sections with subheadings (##), a short conclusion.
Length 3500–6000 characters. Lively, clear language, no fluff or jargon.
Keep words marked (?) with that mark.
Do not add facts, numbers or claims that are not in the notes.

Notes:
{text}""",
    },
}


def lang_of(whisper_lang: str | None) -> str:
    return "ru" if whisper_lang in ("ru", "uk", "be") else "en"


async def ask(prompt: str, lang: str, max_tokens: int = 1500) -> str:
    body = {
        "model": MODEL, "stream": False, "keep_alive": -1,
        "messages": [{"role": "system", "content": P[lang]["system"]}, {"role": "user", "content": prompt}],
        "options": {"num_ctx": NUM_CTX, "num_predict": max_tokens, "temperature": 0.3, "repeat_penalty": 1.1},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(1800, connect=10)) as c:
        r = await c.post(f"{OLLAMA_URL}/api/chat", json=body)
        r.raise_for_status()
        return dedupe(r.json()["message"]["content"].strip())


def dedupe(text: str) -> str:
    """Убирает повтор строк подряд — защита от зацикливания модели."""
    out, seen = [], set()
    for line in text.splitlines():
        key = line.strip().lower()
        if key and len(key) > 15 and key in seen:
            continue
        seen.add(key)
        out.append(line)
    return "\n".join(out).strip()


def split(text: str, size: int = CHUNK) -> list[str]:
    """Режет по абзацам, а слишком длинный абзац — по предложениям."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        pieces = [para] if len(para) <= size else re.split(r"(?<=[.!?…])\s+", para)
        for p in pieces:
            if cur and len(cur) + len(p) + 2 > size:
                parts.append(cur)
                cur = ""
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        parts.append(cur)
    return parts


async def make(transcript: str, lang: str = "ru", on_step=None) -> tuple[str, str]:
    """Возвращает (конспект с терминами и выводами, черновик статьи) в Markdown.

    on_step(ключ, **параметры) — ключи read/merge/final/article для сообщения о ходе работы.
    """
    p = P[lang]

    async def step(key: str, **kw) -> None:
        if on_step:
            await on_step(key, **kw)

    chunks = split(transcript)
    if len(chunks) == 1:
        notes = [chunks[0]]
    else:
        notes = []
        for i, ch in enumerate(chunks, 1):
            await step("read", i=i, n=len(chunks))
            notes.append(await ask(p["map"].format(i=i, n=len(chunks), text=ch), lang, 900))
    # заметок слишком много для одного запроса — сжимаем попарно
    while len(notes) > 1 and sum(len(n) for n in notes) > REDUCE_LIMIT:
        await step("merge")
        notes = [await ask(p["merge"].format(text="\n\n---\n\n".join(notes[i:i + 2])), lang, 1200)
                 if i + 1 < len(notes) else notes[i] for i in range(0, len(notes), 2)]
    await step("final")
    summary = await ask(p["final"].format(text="\n\n---\n\n".join(notes)), lang, 2200)
    await step("article")
    article = await ask(p["article"].format(text=summary), lang, 2600)
    return summary, article
