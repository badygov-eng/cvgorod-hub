"""
Expectation analysis for chats using DeepSeek.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from config import settings
from services.database import db

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "expectations_cache.json"

try:
    from MCP.shared.llm import DeepSeekClient

    USE_MCP_CLIENT = True
except ImportError:
    USE_MCP_CLIENT = False


class DeepSeekExpectationAnalyzer:
    """Analyze chat context to extract customer expectations."""

    SYSTEM_PROMPT = (
        "Ты аналитик цветочной компании. Верни ТОЛЬКО JSON без markdown."
    )

    USER_PROMPT = """
Ты аналитик цветочной компании CVGorod. Проанализируй переписку клиента.

Контекст бизнеса:
- CVGorod — оптовая цветочная компания
- Клиенты — владельцы цветочных магазинов и салонов
- Бот шлёт напоминания о предзаказах
- Менеджеры обрабатывают заказы и отвечают на вопросы

Переписка с клиентом "{customer_label}":
---
{conversation}
---

Верни JSON:
{{
  "expectation": "Что клиент ожидает от нас (кратко)",
  "priority": "high|medium|low",
  "actions": ["Ровно 3 коротких действия для менеджера"]
}}
"""

    def __init__(self, api_key: str | None = None) -> None:
        self.model = settings.DEEPSEEK_MODEL

        if USE_MCP_CLIENT:
            self._client = DeepSeekClient(
                api_key=api_key or settings.DEEPSEEK_API_KEY,
                model=self.model,
            )
            logger.info("Using MCP.shared.llm.DeepSeekClient")
        else:
            self.api_key = api_key or settings.DEEPSEEK_API_KEY
            self.base_url = "https://api.deepseek.com/chat/completions"
            logger.warning("MCP client not available, using direct httpx implementation")

    async def analyze(self, customer_label: str, conversation: str) -> tuple[dict[str, Any], int]:
        prompt = self.USER_PROMPT.format(
            customer_label=customer_label,
            conversation=conversation,
        )

        if USE_MCP_CLIENT:
            content = await self._client.chat(
                message=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=300,
                response_format="json",
            )
            tokens_used = (
                self._client.last_usage.get("total_tokens", 0)
                if hasattr(self._client, "last_usage")
                else 0
            )
        else:
            timeout = httpx.Timeout(60.0, connect=30.0)
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            self.base_url,
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": self.model,
                                "messages": [
                                    {"role": "system", "content": self.SYSTEM_PROMPT},
                                    {"role": "user", "content": prompt},
                                ],
                                "temperature": 0.2,
                                "max_tokens": 300,
                            },
                        )
                        response.raise_for_status()
                        data = response.json()
                        content = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        usage = data.get("usage", {})
                        tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                        break
                except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                    if attempt == 2:
                        raise
                    logger.warning("DeepSeek timeout (attempt %d/3): %s", attempt + 1, exc)
                    await asyncio.sleep(2 ** attempt)

        try:
            clean = content.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
        except json.JSONDecodeError:
            result = {
                "expectation": "",
                "priority": "low",
                "actions": [],
            }

        actions = result.get("actions", [])
        if not isinstance(actions, list):
            actions = []
        while len(actions) < 3:
            actions.append("Уточнить детали запроса клиента")
        result["actions"] = actions[:3]

        if result.get("priority") not in {"high", "medium", "low"}:
            result["priority"] = "medium"

        return result, tokens_used


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"updated_at": None, "chats": {}}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read expectations cache: %s", exc)
        return {"updated_at": None, "chats": {}}


def write_cache(data: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, CACHE_PATH)


async def _fetch_active_chats(active_since: datetime) -> list[dict[str, Any]]:
    query = """
        SELECT
            m.chat_id,
            MAX(m.timestamp) AS last_message_at,
            c.name AS chat_name,
            cust.name AS customer_name,
            cust.sync_id AS customer_sync_id
        FROM messages m
        LEFT JOIN chats c ON m.chat_id = c.id
        LEFT JOIN customers cust ON c.customer_id = cust.id
        WHERE m.timestamp >= $1
        GROUP BY m.chat_id, c.name, cust.name, cust.sync_id
        ORDER BY MAX(m.timestamp) DESC
    """
    rows = await db.fetch(query, active_since)
    return [dict(row) for row in rows]


async def _fetch_context(chat_id: int, since: datetime, limit: int) -> list[dict[str, Any]]:
    role_expr = """
        CASE
            WHEN COALESCE(ur.is_bot, FALSE) = TRUE THEN 'BOT'
            WHEN COALESCE(ur.role_name, '') = 'director' THEN 'DIRECTOR'
            WHEN COALESCE(ur.role_name, '') = 'manager'
                OR COALESCE(u.is_manager, FALSE) = TRUE THEN 'MANAGER'
            ELSE 'CLIENT'
        END
    """

    query = f"""
        WITH recent AS (
            SELECT
                m.id,
                m.timestamp,
                m.text,
                u.username,
                u.first_name,
                u.last_name,
                {role_expr} AS role
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN user_roles ur ON u.role_id = ur.id
            WHERE m.chat_id = $1
                AND m.timestamp >= $2
                AND m.text IS NOT NULL
                AND m.text != ''
            ORDER BY m.timestamp DESC
            LIMIT $3
        )
        SELECT * FROM recent
        ORDER BY timestamp ASC
    """
    rows = await db.fetch(query, chat_id, since, limit)
    return [dict(row) for row in rows]


def _format_conversation(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "CLIENT")
        name_parts = [msg.get("first_name") or "", msg.get("last_name") or ""]
        name = " ".join([part for part in name_parts if part]).strip()
        if not name and msg.get("username"):
            name = msg.get("username")
        if not name:
            name = role
        text = (msg.get("text") or "").strip()
        lines.append(f"[{role}] {name}: {text}")
    return "\n".join(lines)


def _last_client_message(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "CLIENT" and msg.get("text"):
            return msg["text"]
    return ""


async def analyze_expectations(
    *,
    force: bool = False,
    active_hours: int = 24,
    context_days: int = 3,
    max_messages: int = 50,
    concurrency: int = 3,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not settings.DEEPSEEK_API_KEY and not dry_run:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    cache = load_cache()
    chats_cache: dict[str, Any] = cache.get("chats", {})

    active_since = datetime.utcnow() - timedelta(hours=active_hours)
    context_since = datetime.utcnow() - timedelta(days=context_days)

    active_chats = await _fetch_active_chats(active_since)
    if limit:
        active_chats = active_chats[:limit]

    analyzer = DeepSeekExpectationAnalyzer()
    semaphore = asyncio.Semaphore(concurrency)

    analyzed = 0
    skipped = 0

    async def process_chat(chat: dict[str, Any]) -> None:
        nonlocal analyzed, skipped

        chat_id = chat.get("chat_id")
        if chat_id is None:
            return
        chat_key = str(chat_id)

        last_message_at = chat.get("last_message_at")
        cached = chats_cache.get(chat_key, {})
        cached_last = _parse_dt(cached.get("last_analyzed_at"))

        if not force and cached_last and last_message_at and last_message_at <= cached_last:
            cached["last_message_at"] = last_message_at.isoformat()
            cached["skipped"] = True
            chats_cache[chat_key] = cached
            skipped += 1
            return

        context_messages = await _fetch_context(chat_id, context_since, max_messages)
        if not context_messages:
            cached["last_message_at"] = last_message_at.isoformat() if last_message_at else None
            cached["last_analyzed_at"] = datetime.utcnow().isoformat()
            cached["expectation"] = "Нет данных для анализа"
            cached["priority"] = "low"
            cached["actions"] = [
                "Проверить наличие сообщений",
                "Уточнить статус чата",
                "Обновить данные клиента",
            ]
            cached["skipped"] = False
            chats_cache[chat_key] = cached
            analyzed += 1
            return

        conversation = _format_conversation(context_messages)
        customer_label = chat.get("customer_name") or chat.get("chat_name") or str(chat_id)

        async with semaphore:
            analysis, tokens_used = await analyzer.analyze(customer_label, conversation)

        last_analyzed_at = datetime.utcnow().isoformat()

        cached.update(
            {
                "chat_name": chat.get("chat_name"),
                "customer_name": chat.get("customer_name"),
                "customer_sync_id": chat.get("customer_sync_id"),
                "expectation": analysis.get("expectation", ""),
                "priority": analysis.get("priority", "medium"),
                "actions": analysis.get("actions", [])[:3],
                "last_client_message": _last_client_message(context_messages),
                "last_message_at": last_message_at.isoformat() if last_message_at else None,
                "last_analyzed_at": last_analyzed_at,
                "tokens_used": tokens_used,
                "skipped": False,
            }
        )
        chats_cache[chat_key] = cached
        analyzed += 1

    tasks = [process_chat(chat) for chat in active_chats]
    await asyncio.gather(*tasks)

    cache["updated_at"] = datetime.utcnow().isoformat()
    cache["chats"] = chats_cache
    cache["stats"] = {
        "active_chats": len(active_chats),
        "analyzed": analyzed,
        "skipped": skipped,
    }

    if not dry_run:
        write_cache(cache)

    return cache
