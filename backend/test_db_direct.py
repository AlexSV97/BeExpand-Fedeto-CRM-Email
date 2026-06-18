"""
Test DB save directly without circular imports
"""
import asyncio, uuid, os
from datetime import datetime, timezone
from src.db.session import async_session_factory
from src.db.models import Email, Contact, ClassificationHistory

async def test():
    session = async_session_factory()
    
    # Helper: simulate ActionExecutor._ensure_contact
    async def ensure_contact(email_addr, name, category="lead"):
        from sqlalchemy import select
        result = await session.execute(select(Contact).where(Contact.email == email_addr))
        contact = result.scalar_one_or_none()
        if contact is None:
            contact = Contact(
                id=str(uuid.uuid4()),
                name=name,
                email=email_addr,
                category=category,
                source="email",
            )
            session.add(contact)
            await session.flush()
            print(f"  Contact CREATED: {contact.name} <{contact.email}> cat={contact.category}")
        else:
            contact.category = category
            print(f"  Contact FOUND: {contact.name} <{contact.email}> cat={contact.category}")
        return contact

    # Helper: simulate _save_email
    async def save_email(contact, subject, body, message_id=None):
        # Get or create account
        from sqlalchemy import select
        from src.db.models import Account
        result = await session.execute(select(Account).where(Account.email_user == os.getenv("IMAP_USER", "<IMAP_USER_DEMO>")))
        account = result.scalar_one_or_none()
        if account is None:
            account = Account(
                id=str(uuid.uuid4()),
                name="Test",
                email_host="imap.gmail.com",
                email_port=993,
                email_user=os.getenv("IMAP_USER", "<IMAP_USER_DEMO>"),
                email_pass="xxx",
                provider="gmail",
                active=True,
            )
            session.add(account)
            await session.flush()
            print(f"  Account CREATED: {account.email_user}")
        
        email = Email(
            id=str(uuid.uuid4()),
            account_id=account.id,
            message_id=message_id,
            subject=subject,
            body_plain=body,
            sender_email=contact.email,
            sender_name=contact.name,
            recipients=["destino@test.com"],
            has_attachments=False,
            received_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            category="lead",
            relevance="alta",
            status="pendiente",
            extra_data={"test": True},
        )
        session.add(email)
        await session.flush()
        print(f"  SAVED: {subject[:50]}")
        return email

    # Test batch: 5 emails all from the same sender
    print("=== Test 1: 5 emails from same sender ===")
    contact = None
    for i in range(5):
        print(f"\n--- Email #{i+1} (para test@ejemplo.com) ---")
        contact = await ensure_contact("test@ejemplo.com", f"Sender {i}", "lead" if i % 2 == 0 else "cliente")
        email = await save_email(
            contact,
            f"Email de prueba #{i+1} - Asunto de test",
            f"Cuerpo del email #{i+1}",
            f"msg-{uuid.uuid4()}"
        )
    
    # Commit
    try:
        await session.commit()
        print("\n=== Commit OK! ===")
    except Exception as e:
        await session.rollback()
        print(f"\n=== Commit FAILED: {e} ===")
    
    # Check DB
    import sqlite3
    db = sqlite3.connect("backend/aiuken.db")
    emails = db.execute("SELECT subject, category, sender_email FROM emails").fetchall()
    print(f"\nEmails in DB: {len(emails)}")
    for e in emails:
        print(f"  {e[2]:30s} | {e[1]:10s} | {e[0][:50]}")
    contacts = db.execute("SELECT name, email, category, email_count FROM contacts").fetchall()
    print(f"Contacts in DB: {len(contacts)}")
    for c in contacts:
        print(f"  {c[0]:20s} | {c[1]:30s} | {c[2]:10s} | count={c[3]}")
    db.close()
    await session.close()

    # === Test 2: Null message_id ===
    print("\n\n=== Test 2: Null message_id ===")
    session2 = async_session_factory()
    # Save 3 emails with NULL message_id
    for i in range(3):
        contact2 = await ensure_contact(f"nullmsg{i}@test.com", f"Null MSG {i}", "lead")
        email_data = Email(
            id=str(uuid.uuid4()),
            account_id=account.id,  # reuse account
            message_id=None,  # NULL message_id!
            subject=f"Null msg_id email #{i+1}",
            body_plain="test",
            sender_email=contact2.email,
            sender_name=contact2.name,
            recipients=[],
            has_attachments=False,
            received_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            category="lead",
            extra_data={},
        )
        session2.add(email_data)
        await session2.flush()
    try:
        await session2.commit()
        print("Commit OK! 3 emails with NULL message_id saved fine")
    except Exception as e:
        await session2.rollback()
        print(f"Commit FAILED: {e}")
    await session2.close()

asyncio.run(test())
