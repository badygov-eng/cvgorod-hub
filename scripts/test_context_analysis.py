#!/usr/bin/env python3
"""
Тестирование DeepSeek для анализа контекста переписки клиентов.

Цель: понять что клиент ожидает и какие действия нужно предпринять.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Setup project path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from config import settings

# Примеры реальных переписок из базы
CONVERSATIONS = {
    "Опакай Малина (Кызыл) — активный заказчик": [
        {"role": "client", "name": "Светлана", "text": "Доброе утро! минуточку"},
        {"role": "client", "name": "Светлана", "text": "эвкалипт закончился?"},
        {"role": "bot", "name": "Менеджер", "text": "сколько нужно ?"},
        {"role": "client", "name": "Светлана", "text": "Малина Шири-базыровна беби блу 2 пучка\nсинерея 2 пучка\nКежик Мадыр-оолович беби -1 пуч\nсинерея 1 пуч"},
        {"role": "bot", "name": "Менеджер", "text": "только синерея\nпоставил"},
        {"role": "client", "name": "Светлана", "text": "Малина синерея 3 пучка\nКежик-2 пучка"},
        {"role": "client", "name": "Светлана", "text": "хорошо"},
        {"role": "client", "name": "Светлана", "text": "Малина альстромерия белая-10\nрозовая-10\nмалин-10\nтолько такие цвета нужны\nирисы бел -20шт"},
        {"role": "client", "name": "Светлана", "text": "Кежик-тюльпан бел- 10шт\nрозовые-20\nкрасн-20\nМалина -тюльпан бел-10\nкрасн-20\nжелт-10\nрозовые-10\nКрасивые !"},
        {"role": "bot", "name": "Бот", "text": "Напоминаю!!!\nтолько сегодня принимаем предзаказ на 28 января 2026 года покрашанный розе\nВы будете делать заказ?"},
        {"role": "client", "name": "Светлана", "text": "Малина поставьте эти сорта"},
        {"role": "client", "name": "Светлана", "text": "да правильно"},
    ],
    
    "Янгиев Шерзод — передумал и заказал": [
        {"role": "bot", "name": "Бот", "text": "Напоминаю!!!\nтолько сегодня принимаем предзаказ на 28 января 2026 года покрашанный розе\nВы будете делать заказ?"},
        {"role": "client", "name": "Шерзод", "text": "Нет спасибо суваботка вазму"},
        {"role": "client", "name": "Шерзод", "text": "Хорош эта роза"},
        {"role": "client", "name": "Шерзод", "text": "Буду заказ"},
        {"role": "client", "name": "Шерзод", "text": "Брат"},
        {"role": "client", "name": "Шерзод", "text": "28 января"},
        {"role": "client", "name": "Шерзод", "text": "75 шутик"},
    ],
    
    "Сфинкс — вопрос о сроках": [
        {"role": "client", "name": "Юлия", "text": "Здравствуйте подскажите когда цветы планируются ?"},
    ],
    
    "Котова Марина — доп заказ": [
        {"role": "bot", "name": "Бот", "text": "Напоминаю!!!\nтолько сегодня принимаем предзаказ на 28 января 2026 года покрашанный розе\nВы будете делать заказ?"},
        {"role": "client", "name": "Марина", "text": "Здравствуйте, нет"},
        {"role": "bot", "name": "Бот", "text": "Благодарю за информацию"},
        {"role": "bot", "name": "Менеджер", "text": "Добрый день!\nЕсть на свободном остатке на эту неделю"},
        {"role": "client", "name": "Марина", "text": "Гвоздику красную 75 добавьте"},
        {"role": "bot", "name": "Менеджер", "text": "ок"},
    ],
    
    "Вдовина Надежда — планы на будущее": [
        {"role": "client", "name": "Aldynay", "text": "На эту неделю можно предварительно узнать наш заказ?"},
        {"role": "client", "name": "Aldynay", "text": "Доброе утро!"},
        {"role": "bot", "name": "Бот", "text": "Напоминаю!!!\nтолько сегодня принимаем предзаказ на 28 января 2026 года покрашанный розе\nВы будете делать заказ?"},
        {"role": "client", "name": "Aldynay", "text": "Нет спасибо)"},
        {"role": "client", "name": "Aldynay", "text": "С февраля как обычно будем заказывать"},
        {"role": "client", "name": "Aldynay", "text": "2 микса 40 джозафлор"},
    ],
}

ANALYSIS_PROMPT = """Ты аналитик цветочной оптовой компании CVGorod. Проанализируй переписку с клиентом.

Контекст бизнеса:
- CVGorod — оптовая цветочная компания, продаёт цветы мелким оптом флористам и магазинам
- Клиенты — владельцы цветочных магазинов и салонов в разных городах России
- Бот автоматически рассылает напоминания о предзаказах
- Менеджеры обрабатывают заказы и отвечают на вопросы

ПЕРЕПИСКА С КЛИЕНТОМ "{customer_name}":
---
{conversation}
---

Проанализируй и верни JSON:
{{
    "customer_expectation": "Что клиент ожидает/хочет получить (кратко)",
    "required_actions": ["Список конкретных действий для менеджера"],
    "priority": "high|medium|low",
    "sentiment": "positive|neutral|negative",
    "intent_summary": "Краткое описание намерения клиента",
    "open_questions": ["Нерешённые вопросы/запросы клиента"],
    "order_details": {{
        "has_order": true/false,
        "items": ["Список товаров если есть"],
        "quantity_info": "Информация о количествах"
    }},
    "follow_up_needed": true/false,
    "follow_up_reason": "Почему нужен follow-up (если нужен)"
}}
"""


def format_conversation(messages: list[dict]) -> str:
    """Форматирует переписку в читаемый вид."""
    lines = []
    for msg in messages:
        role_label = "🤖 " if msg["role"] == "bot" else "👤 "
        lines.append(f'{role_label}{msg["name"]}: {msg["text"]}')
    return "\n".join(lines)


async def analyze_conversation(customer_name: str, messages: list[dict]) -> dict:
    """Отправляет переписку в DeepSeek для анализа."""
    
    conversation_text = format_conversation(messages)
    prompt = ANALYSIS_PROMPT.format(
        customer_name=customer_name,
        conversation=conversation_text
    )
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.DEEPSEEK_MODEL,
                "messages": [
                    {
                        "role": "system", 
                        "content": "Ты аналитик. Отвечай ТОЛЬКО валидным JSON без markdown."
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            },
        )
        response.raise_for_status()
        data = response.json()
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        
        # Parse JSON
        try:
            clean = content.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
        except json.JSONDecodeError:
            result = {"error": "Failed to parse response", "raw": content}
        
        return {
            "analysis": result,
            "tokens": usage.get("total_tokens", 0),
        }


async def main():
    if not settings.DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY не задан!")
        return
    
    print("=" * 80)
    print("🔬 ИССЛЕДОВАНИЕ: Анализ ожиданий клиентов через DeepSeek")
    print("=" * 80)
    
    for customer_name, messages in CONVERSATIONS.items():
        print(f"\n{'='*80}")
        print(f"📋 КЛИЕНТ: {customer_name}")
        print("-" * 80)
        
        # Показываем переписку
        print("📝 ПЕРЕПИСКА:")
        for msg in messages:
            icon = "🤖" if msg["role"] == "bot" else "👤"
            print(f"   {icon} {msg['name']}: {msg['text'][:60]}{'...' if len(msg['text']) > 60 else ''}")
        
        print("\n🤖 АНАЛИЗ DeepSeek:")
        print("-" * 40)
        
        try:
            result = await analyze_conversation(customer_name, messages)
            analysis = result["analysis"]
            
            if "error" in analysis:
                print(f"   ❌ Ошибка: {analysis}")
            else:
                print(f"   🎯 Ожидание клиента: {analysis.get('customer_expectation', 'N/A')}")
                print(f"   📊 Приоритет: {analysis.get('priority', 'N/A')}")
                print(f"   💭 Настроение: {analysis.get('sentiment', 'N/A')}")
                print(f"   📌 Intent: {analysis.get('intent_summary', 'N/A')}")
                
                actions = analysis.get("required_actions", [])
                if actions:
                    print(f"   \n   ✅ ДЕЙСТВИЯ ДЛЯ МЕНЕДЖЕРА:")
                    for i, action in enumerate(actions, 1):
                        print(f"      {i}. {action}")
                
                questions = analysis.get("open_questions", [])
                if questions:
                    print(f"   \n   ❓ ОТКРЫТЫЕ ВОПРОСЫ:")
                    for q in questions:
                        print(f"      • {q}")
                
                order = analysis.get("order_details", {})
                if order.get("has_order"):
                    print(f"   \n   📦 ЗАКАЗ:")
                    print(f"      Товары: {', '.join(order.get('items', []))}")
                    print(f"      Количество: {order.get('quantity_info', 'N/A')}")
                
                if analysis.get("follow_up_needed"):
                    print(f"   \n   🔔 НУЖЕН FOLLOW-UP: {analysis.get('follow_up_reason', 'Да')}")
            
            print(f"\n   📊 Токенов использовано: {result['tokens']}")
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        print()
    
    print("\n" + "=" * 80)
    print("✅ ИССЛЕДОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
