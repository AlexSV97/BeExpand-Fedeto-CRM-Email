"""
Test DB save - same sender, null message_ids
"""
import asyncio, uuid
from datetime import datetime, timezone
from src.db.session import async_session_factory
from src.db.models import Email, Contact, Account

async def test():
    session = async_session_factory()
    
    # Helper
    async def save_email(contact, subject, msg_id=None):
        from sqlalchemy import select
        result = await session.execute(select(Account).where(Account.email_user == "beexpandcrmpoc@gmail.com"))
        account = result.scalar_one_or_none()
        if account is None:
            account = Account(id=str(uuid.uuid4()), name="Test", email_host="imap.gmail.com",
                             email_port=993, email_user="beexpandcrmpoc@gmail.com",
                             email_pass="xxx", provider="gmail", active=True)
            session.add(account)
            await session.flush()
        
        email = Email(id=str(uuid.uuid4()), account_id=account.id, message_id=msg_id,
                     subject=subject, body_plain="test", sender_email=contact.email,
                     sender_name=contact.name, recipients=[], received_at=datetime.now(timezone.utc),
                     processed_at=datetime.now(timezone.utc), category="lead", extra_data={})
        session.add(email)
        await session.flush()
        return email
    
    # Test: 5 same sender
    print("=== 5 emails SAME sender + UNIQUE message_ids ===")
    msg_ids = [f"msg-{uuid.uuid4()}" for _ in range(5)]
    for i in range(5):
        result = await session.execute(
            __import__("sqlalchemy").select(Contact).where(Contact.email == "mismo@test.com")
        )
        c = result.scalar_one_or_none()
        if c is None:
            c = Contact(id=str(uuid.uuid4()), name=f"User{i}", email="mismo@test.com", category="lead", source="email")
            session.add(c)
            await session.flush()
        await save_email(c, f"Email #{i}", msg_ids[i])
    await session.commit()
    print("  5 emails with unique message_ids: OK")
    
    # Now test with NULL message_ids (SIMULATING the real test emails)
    print("\n=== 5 emails SAME sender + NULL message_ids ===")
    for i in range(5):
        result = await session.execute(
            __import__("sqlalchemy").select(Contact).where(Contact.email == "nulmsg@test.com")
        )
        c = result.scalar_one_or_none()
        if c is None:
            c = Contact(id=str(uuid.uuid4()), name=f"NullUser{i}", email="nulmsg@test.com", category="lead", source="email")
            session.add(c)
            await session.flush()
        await save_email(c, f"Null Email #{i}", msg_id=None)
    await session.commit()
    print("  5 emails with NULL message_ids: OK")
    
    # Check DB
    import sqlite3
    db = sqlite3.connect("backend/beexpand.db")
    emails = db.execute("SELECT subject, category, sender_email, message_id FROM emails").fetchall()
    print(f"\nTotal emails: {len(emails)}")
    for e in emails:
        mid = (e[3] or "NULL")[:20]
        print(f"  {e[2]:20s} | {e[1]:8s} | msg_id={mid} | {e[0][:40]}")
    contacts = db.execute("SELECT name, email, email_count FROM contacts").fetchall()
    print(f"\nTotal contacts: {len(contacts)}")
    for c in contacts:
        print(f"  {c[0]:15s} | {c[1]:25s} | count={c[2]}")
    db.close()
    await session.close()

asyncio.run(test())
