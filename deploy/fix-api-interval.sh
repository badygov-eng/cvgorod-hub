#!/bin/bash
# Скрипт деплоя исправлений API на сервер

set -e

echo "=== Deploying API fixes to server ==="

# Копируем исправленные файлы
scp -i ~/.ssh/id_ed25519 api/routes/clients.py badygovd@158.160.153.14:/home/badygovdaniil/cvgorod-hub/api/routes/clients.py
scp -i ~/.ssh/id_ed25519 api/routes/intents.py badygovd@158.160.153.14:/home/badygovdaniil/cvgorod-hub/api/routes/intents.py

echo "=== Files copied successfully ==="
echo "=== Restarting container ==="
ssh -i ~/.ssh/id_ed25519 badygovd@158.160.153.14 "cd /home/badygovdaniil/cvgorod-hub && docker compose restart cvgorod-hub-api"

echo "=== Deploy complete ==="
