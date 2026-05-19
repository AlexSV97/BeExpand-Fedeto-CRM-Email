"""Check what's in the database."""
import sys
sys.path.insert(0, '/app')

import asyncio
from sqlalchemy import select, func
from src.db.session import async_session_factory
from src.db.models import Email, Contact, ClassificationHistory

async def check():
    db = async_session_factory()
    for label, q in [
        ("Emails", select(func.count(Email.id))),
        ("Contacts", select(func.count(Contact.id))),
        ("Classification History", select(func.count(ClassificationHistory.id))),
    ]:
        result = await db.execute(q)
        print(f"{label}: {result.scalar()}")

    # Categories
    cat_result = await db.execute(
        select(Email.category, func.count(Email.id)).group_by(Email.category)
    )
    for row in cat_result:
        print(f"  Category '{row[0]}': {row[1]}")

    # Last 5 emails
    last = await db.execute(
        select(Email.subject, Email.category, Email.sender_name)
        .order_by(Email.received_at.desc()).limit(5)
    )
    print("\nLast 5 emails:")
    for row in last:
        print(f"  {str(row[0])[:50]:50s} | {str(row[1]):10s} | {str(row[2]):20s}")

    await db.close()

asyncio.run(check())
