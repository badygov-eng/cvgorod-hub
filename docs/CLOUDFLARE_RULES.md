# ☁️ Правила Cloudflare для cvgorod-hub

> **Полная документация**: `~/MCP/CLOUDFLARE_RULES.md`

---

## 🇷🇺 КРИТИЧЕСКИ ВАЖНО: Блокировка Cloudflare в России

> **С 2024 года Cloudflare Proxy и Tunnel БЛОКИРУЮТСЯ российскими провайдерами!**
>
> Все публичные сайты для пользователей из РФ должны работать **БЕЗ проксирования**.

### Правило для публичных сайтов (пользователи из РФ)

```
┌─────────────────────────────────────────────────────────────────┐
│  ✅ ПРАВИЛЬНО                  │  ❌ НЕПРАВИЛЬНО               │
├────────────────────────────────┼────────────────────────────────┤
│  DNS: A → 158.160.153.14       │  DNS: CNAME → tunnel           │
│  Proxy: OFF (серое облако)     │  Proxy: ON (оранжевое облако)  │
│  SSL: Let's Encrypt + nginx    │  SSL: Cloudflare               │
│  Доступ: ПРЯМОЙ к серверу      │  Доступ: через Cloudflare      │
└────────────────────────────────┴────────────────────────────────┘
```

---

## 📋 Домен проекта

| Домен | Порт | DNS | Proxy | SSL |
|-------|------|-----|-------|-----|
| `cvgorod.testbotgigachat.org` | 8300 | A → 158.160.153.14 | ❌ OFF | Let's Encrypt |

---

## 🛠️ Как добавить новый публичный сайт

### 1. На сервере: создать nginx конфиг

```bash
ssh -i ~/.ssh/yandex_vm_key badygovdaniil@158.160.153.14
sudo nano /etc/nginx/sites-available/{subdomain}.testbotgigachat.org
```

### 2. Шаблон nginx конфига

```nginx
# {subdomain}.testbotgigachat.org
# Порт: {port} | ПРЯМОЙ ДОСТУП (A → IP, Proxy OFF)

server {
    listen 80;
    server_name {subdomain}.testbotgigachat.org;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name {subdomain}.testbotgigachat.org;

    # SSL (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/{subdomain}.testbotgigachat.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{subdomain}.testbotgigachat.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Proxy
    location / {
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Активировать и получить SSL

```bash
sudo ln -sf /etc/nginx/sites-available/{subdomain}.testbotgigachat.org /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d {subdomain}.testbotgigachat.org
```

### 4. В Cloudflare DNS

```bash
# Type: A
# Name: {subdomain}
# Content: 158.160.153.14
# Proxy: OFF (серое облако!)
```

---

## 🔧 Cloudflare API (если нужно)

```bash
# Zone ID
ZONE_ID=dbf38d294742ad70b09ab96b3578cc70

# Получить DNS записи
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"

# Обновить DNS запись (A → IP, Proxy OFF)
curl -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/{record_id}" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "A",
    "name": "{subdomain}",
    "content": "158.160.153.14",
    "proxied": false,
    "ttl": 1
  }'
```

---

## ⚠️ Запрещено

1. **Включать Proxy** (оранжевое облако) для публичных сайтов
2. **Использовать CNAME → tunnel** для сайтов с пользователями из РФ
3. **Использовать Cloudflare SSL** — только Let's Encrypt через nginx

---

*Скопировано из ~/MCP/CLOUDFLARE_RULES.md | Январь 2026*
