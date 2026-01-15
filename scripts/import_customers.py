#!/usr/bin/env python3
"""
Import customers from JSON mapping and link to chats.
"""

import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.database import db


async def main():
    # Load mapping
    mapping_file = project_root / "data" / "customer_chat_mapping.json"
    with open(mapping_file) as f:
        mapping = json.load(f)

    print(f"Loaded {len(mapping)} customers from mapping")

    await db.connect()

    inserted = 0
    linked = 0

    for cust in mapping:
        # Insert customer
        phone = cust.get("phone")
        if phone is not None:
            phone = str(phone)
        
        customer_id = await db.fetchval(
            """
            INSERT INTO customers (sync_id, name, email, phone, cvgorod_chat_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (sync_id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                cvgorod_chat_id = EXCLUDED.cvgorod_chat_id
            RETURNING id
            """,
            cust["sync_id"],
            cust["customer_name"],
            cust.get("email"),
            phone,
            cust["cvgorod_chat_id"],
        )
        inserted += 1

        # Link chat to customer
        tg_chat_id = int(cust["telegram_chat_id"])
        result = await db.execute(
            """
            UPDATE chats SET customer_id = $1 WHERE id = $2
            """,
            customer_id,
            tg_chat_id,
        )
        if "UPDATE 1" in result:
            linked += 1

    await db.close()

    print(f"Inserted/updated: {inserted} customers")
    print(f"Linked to chats: {linked}")


if __name__ == "__main__":
    asyncio.run(main())
