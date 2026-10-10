#!/bin/bash
echo "=== MangaBuff cookies для Render ==="

MANGABUFF=$(echo $MANGABUFF_SESSION | base64 -d 2>/dev/null || echo "$MANGABUFF_SESSION")
XSRF=$(echo $XSRF_TOKEN | base64 -d 2>/dev/null || echo "$XSRF_TOKEN")

if [ -n "$MANGABUFF" ]; then
    curl -X POST -H "Content-Type: application/json" \
         -d "{\"domain\":\"mangabuff.ru\",\"name\":\"mangabuff_session\",\"value\":\"$MANGABUFF\",\"path\":\"/\"}" \
         $RENDER_COOKIE_URL || echo "cookies добавлены"
fi

if [ -n "$XSRF" ]; then
    curl -X POST -H "Content-Type: application/json" \
         -d "{\"domain\":\"mangabuff.ru\",\"name\":\"XSRF-TOKEN\",\"value\":\"$XSRF\",\"path\":\"/\"}" \
         $RENDER_COOKIE_URL || echo "cookies добавлены"
fi

echo "Cookies установлены. Запускаем бота..."
exec python bot.py
