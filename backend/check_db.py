"""
Check database state directly
"""
import asyncio
from sqlalchemy import text
from src.db.session import async_session_factory

async def check_db():
    session = async_session_factory()
    
    # Emails
    result = await session.execute(
        text("SELECT id, subject, category, sender_name, sender_email FROM emails ORDER BY received_at DESC")
    )
    emails = result.fetchall()
    print(f"=== EMAILS EN BD: {len(emails)} ===")
    for row in emails:
        subject = row.subject[:70] if row.subject else "N/A"
        print(f"  {row.category:12s} | {row.sender_name:20s} | {subject}")
    
    if len(emails) > 1:
        print("\nMas de 1 email en BD! Solo se mostraron los ultimos.")
    
    print()
    
    # Contacts
    result = await session.execute(
        text("SELECT id, name, email, category, company FROM contacts ORDER BY created_at DESC")
    )
    contacts = result.fetchall()
    print(f"=== CONTACTOS EN BD: {len(contacts)} ===")
    for row in contacts:
        print(f"  {row.name:20s} | {row.email:30s} | {row.category:12s} | {row.company or 'N/A'}")
    
    print()
    
    # Classification history
    result = await session.execute(
        text("SELECT ch.id, ch.email_id, ch.category, ch.method FROM classification_history ch ORDER BY ch.created_at DESC")
    )
    entries = result.fetchall()
    print(f"=== CLASSIFICATION HISTORY: {len(entries)} entries ===")
    for row in entries[:15]:
        eid = row.email_id[:8] if row.email_id else "?"
        print(f"  email={eid} | {row.category:10s} | {row.method}")
    
    await session.close()

asyncio.run(check_db())
