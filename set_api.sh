#!/usr/bin/env bash
# Шаг 2. Свой сервер Telegram Bot API — бот сможет принимать файлы до 2 ГБ.
# api_id и api_hash берутся бесплатно на https://my.telegram.org → API development tools.
set -euo pipefail
cd "$(dirname "$0")"
[[ -f .env ]] && grep -q '^BOT_TOKEN=' .env || { echo "❌ Сначала шаг 1: bash set_token.sh"; exit 1; }

read -rp "api_id (только цифры): " API_ID
API_ID="$(echo -n "$API_ID" | tr -d '[:space:]')"
[[ "$API_ID" =~ ^[0-9]{4,12}$ ]] || { echo "❌ api_id — это число из 5–10 цифр."; exit 1; }
echo "api_hash (32 символа, не будет виден):"
read -rs API_HASH
echo
API_HASH="$(echo -n "$API_HASH" | tr -d '[:space:]')"
[[ "$API_HASH" =~ ^[0-9a-f]{32}$ ]] || { echo "❌ api_hash — 32 символа из цифр и букв a–f (получено ${#API_HASH})."; exit 1; }

umask 077
printf 'TELEGRAM_API_ID=%s\nTELEGRAM_API_HASH=%s\n' "$API_ID" "$API_HASH" > .botapi.env
chmod 600 .botapi.env
unset API_HASH

sudo mkdir -p /var/lib/telegram-bot-api/tmp
sudo chown -R user:user /var/lib/telegram-bot-api
sudo chmod 700 /var/lib/telegram-bot-api
sudo systemctl enable --now telegram-bot-api >/dev/null 2>&1
sudo systemctl restart telegram-bot-api
sleep 3
systemctl is-active --quiet telegram-bot-api || { echo "❌ Сервер Bot API не запустился: sudo journalctl -u telegram-bot-api -n 30"; exit 1; }

# бот «переезжает» с облачного сервера Telegram на свой (обратно — не раньше чем через 10 минут)
TOKEN="$(grep '^BOT_TOKEN=' .env | cut -d= -f2-)"
sudo systemctl stop lecture-bot
curl -s -m 15 "https://api.telegram.org/bot${TOKEN}/logOut" >/dev/null || true
unset TOKEN
grep -v '^BOT_API_URL=' .env > .env.new; echo "BOT_API_URL=http://127.0.0.1:8081" >> .env.new
mv .env.new .env && chmod 600 .env
sudo systemctl start lecture-bot
sleep 20
if systemctl is-active --quiet lecture-bot; then
    echo "✅ Готово: бот работает через свой сервер Bot API, файлы до 2 ГБ."
else
    echo "❌ Бот не запустился: sudo journalctl -u lecture-bot -n 30"
fi
