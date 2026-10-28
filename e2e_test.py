"""Проверка цепочки без Telegram: файл → расшифровка → конспект → docx.

    .venv/bin/python e2e_test.py запись.mp3 [папка_для_результата]
"""
import asyncio
import os
import sys
import time

import notes
import render
import transcribe


async def main(path: str, out: str) -> None:
    t = time.time()
    if path.endswith(".txt"):                 # готовая расшифровка — проверяем только конспект
        text, doubt = open(path, encoding="utf-8").read(), []
        spoken = "ru" if sum("а" <= ch.lower() <= "я" for ch in text) > len(text) / 4 else "en"
    else:
        transcribe.load()
        print("расшифровка:", transcribe.device())
        audio = transcribe.decode(path)
        print(f"запись {len(audio) / transcribe.SR:.0f} с")
        text, doubt, spoken = transcribe.transcribe(audio, lambda f: print(f"\r  {f:.0%}", end="", flush=True))
        print(f"\nрасшифровано за {time.time() - t:.0f} с, язык {spoken}, сомнительные слова: {doubt}")
    lang = notes.lang_of(spoken)
    t2 = time.time()

    async def step(key, **kw):
        print(" ", key, kw)
    summary, article = await notes.make(text, lang, step)
    print(f"конспект за {time.time() - t2:.0f} с")
    doubt = render.marked(summary, article) + doubt
    print("проверить:", doubt)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "transcript.txt"), "w", encoding="utf-8").write(text)
    open(os.path.join(out, "summary.md"), "w", encoding="utf-8").write(summary)
    open(os.path.join(out, "article.md"), "w", encoding="utf-8").write(article)
    open(os.path.join(out, "telegram.html"), "w", encoding="utf-8").write(
        "\n\n=====\n\n".join(render.split_html(render.to_html(summary))))
    open(os.path.join(out, "result.docx"), "wb").write(
        render.make_docx(render.title_of(summary), summary, article, text, doubt, "KonspektLectureBot", lang))
    print("готово:", out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/tmp/lecture-test"))
