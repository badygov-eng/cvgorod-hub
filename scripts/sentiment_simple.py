#!/usr/bin/env python3
"""
Sentiment Analysis - Simple version for Docker
"""
import os
import sys
import asyncio
import httpx
import asyncpg

# API Key из переменной окружения
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    with open("/root/.secrets/cloud/deepseek.env") as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()
                break

print(f"API Key: {DEEPSEEK_API_KEY[:15] if DEEPSEEK_API_KEY else 'NONE'}...", file=sys.stderr)

SYSTEM_PROMPT = "Определи sentiment: positive/negative/neutral. Ответ: одно слово."

async def get_messages(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, text FROM messages
            WHERE timestamp >= '2026-01-12 00:00:00' AND timestamp < '2026-01-13 00:00:00'
            AND text IS NOT NULL AND text != '' AND sentiment IS NULL
            ORDER BY id LIMIT 50
        """)

async def analyze(text):
    if not DEEPSEEK_API_KEY:
        return "neutral"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text[:400]}
                ], "temperature": 0.1, "max_tokens": 10}
            )
            if r.status_code == 401:
                print("401 Unauthorized!", file=sys.stderr)
                return "neutral"
            r.raise_for_status()
            s = r.json()["choices"][0]["message"]["content"].strip().lower()
            s = ''.join(c for c in s if c.isalpha())
            return s if s in ["positive", "negative", "neutral"] else "neutral"
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return "neutral"

async def main():
    pool = await asyncpg.create_pool("postgresql://cvgorod:cvgorod_secret_2024@postgres:5432/cvgorod_hub", min_size=2, max_size=5)
    msgs = await get_messages(pool)
    print(f"Found {len(msgs)} messages", file=sys.stderr)
    
    stats = {"positive": 0, "negative": 0, "neutral": 0}
    for i, msg in enumerate(msgs):
        print(f"[{i+1}/{len(msgs)}] {msg['text'][:50]}...", file=sys.stderr)
        sent = await analyze(msg["text"])
        await pool.execute("UPDATE messages SET sentiment=$1 WHERE id=$2", sent, msg["id"])
        stats[sent] += 1
        print(f"  -> {sent}", file=sys.stderr)
        await asyncio.sleep(0.2)
    
    print(f"\nResults: P:{stats['positive']} N:{stats['negative']} U:{stats['neutral']}", file=sys.stderr)
    await pool.close()

asyncio.run(main())
