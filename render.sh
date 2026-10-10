#!/bin/bash
echo "=== Добавляем cookies для MangaBuff ==="

# Получаем cookies из окружения Render
MANGABUFF=$(echo $MANGABUFF_SESSION | base64 -d 2>/dev/null || echo "$MANGABUFF_SESSION")
XSRF=$(echo $XSRF_TOKEN | base64 -d 2>/dev/null || echo "$XSRF_TOKEN")

if [ -n "$MANGABUFF" ]; then
    echo "mangabuff_session добавлен"
    curl -X POST -H "Content-Type: application/json" -d "{\"domain\":\"mangabuff.ru\",\"name\":\"mangabuff_session\",\"value\":\"$MANGABUFF\",\"path\":\"/\"}" $RENDER_COOKIE_URL || echo "cookies добавлены"
fi

if [ -n "$XSRF" ]; then
    echo "XSRF-TOKEN добавлен"
    curl -X POST -H "Content-Type: application/json" -d "{\"domain\":\"mangabuff.ru\",\"name\":\"XSRF-TOKEN\",\"value\":\"$XSRF\",\"path\":\"/\"}" $RENDER_COOKIE_URL || echo "cookies добавлены"
fi

echo "Cookies установлены. Запускаем бота..."

# Запуск бота
exec python bot.py
