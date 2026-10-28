#!/usr/bin/env bash
# Шаг 1. Ввод токена бота: токен не показывается на экране и сохраняется только в .env на сервере.
set -euo pipefail
cd "$(dirname "$0")"

echo "Вставьте токен бота из @BotFather (символы не будут видны) и нажмите Enter:"
read -rs TOKEN
echo
TOKEN="$(echo -n "$TOKEN" | tr -d '[:space:]')"

if [[ ! "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then
    echo "❌ Это не похоже на токен (получено символов: ${#TOKEN}, а нужно около 46, вида 123456789:AA...)."
    echo "   Если 0 — вставка не сработала: попробуйте Ctrl+Shift+V или правую кнопку мыши."
    exit 1
fi

INFO="$(curl -s -m 15 "https://api.telegram.org/bot${TOKEN}/getMe" || true)"
USERNAME="$(echo "$INFO" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["result"]["username"] if d.get("ok") else "")' 2>/dev/null || true)"
if [[ -z "$USERNAME" ]]; then
    echo "❌ Telegram не принял токен. Проверьте, что скопировали его полностью."
    exit 1
fi

ADMIN_CODE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
umask 077
[[ -f .env ]] && grep -vE '^(BOT_TOKEN|ADMIN_CODE|BOT_API_URL)=' .env > .env.new || true
touch .env.new
{ echo "BOT_TOKEN=${TOKEN}"; echo "ADMIN_CODE=${ADMIN_CODE}"; cat .env.new; } > .env.tmp
mv .env.tmp .env && rm -f .env.new
chmod 600 .env
unset TOKEN

sudo systemctl enable --now lecture-bot >/dev/null 2>&1
sudo systemctl restart lecture-bot
sleep 20
if systemctl is-active --quiet lecture-bot; then
    echo "✅ Токен сохранён, бот @${USERNAME} запущен (пока файлы до 20 МБ)."
    echo
    echo "Откройте ЭТУ ссылку со своего Telegram — вы станете владельцем бота (сработает один раз):"
    echo "   https://t.me/${USERNAME}?start=admin_${ADMIN_CODE}"
    echo
    echo "Шаг 2 (файлы до 2 ГБ): bash /opt/lecture-bot/set_api.sh"
else
    echo "❌ Бот не запустился. Журнал: sudo journalctl -u lecture-bot -n 30"
fi
