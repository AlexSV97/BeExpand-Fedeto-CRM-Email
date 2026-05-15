"""
Test action executor DB save directly to see exact error
"""
import asyncio, uuid
from datetime import datetime, timezone
from src.db.session import async_session_factory
from src.agents.action_executor import ActionExecutor
from src.orchestrator.context import EmailData, EmailContext, ExtractedInfo, RoutingDecision, ClassifierVote

async def test():
    session = async_session_factory()
    executor = ActionExecutor(db=session)
    
    # Create a simple email context
    ctx = EmailContext(
        raw=EmailData(
            message_id=f"test-{uuid.uuid4()}",
            subject="Test email sujeto",
            body_plain="Este es un cuerpo de email de prueba para verificar el guardado en BD.",
            sender_name="Test Sender",
            sender_email="test@ejemplo.com",
            recipients=["destino@empresa.com"],
            has_attachments=False,
            received_at=datetime.now(timezone.utc),
        ),
        extracted=ExtractedInfo(
            company="TestCorp",
            position="CEO",
            urgency="alta",
            action_required="Responder presupuesto",
            entities=["presupuesto", "contrato"],
            tone="formal",
            summary="Email de prueba para debug del DB save",
        ),
        final_category="lead",
        final_confidence=0.85,
        resolution_method="consensus",
        votes=[
            ClassifierVote(agent_name="rule_engine", category="lead", confidence=0.85, reason="keyword match", details={}),
            ClassifierVote(agent_name="bert", category="nulo", confidence=0.0, reason="no confidence", details={}),
            ClassifierVote(agent_name="llm", category="nulo", confidence=0.0, reason="no confidence", details={}),
        ],
        routing=RoutingDecision(
            departments=["comercial"],
            persons=[],
            rationale="test routing",
        ),
        processing_start=datetime.now(timezone.utc),
    )
    
    # Save to DB
    result = await executor.execute_all(ctx)
    
    print("=== Action Results ===")
    for a in result:
        s = "OK" if a.success else "FALLO"
        print(f"  [{s}] {a.action}: {a.detail}")
    
    # Try saving a SECOND email with same sender (to test the contact reuse path)
    ctx2 = EmailContext(
        raw=EmailData(
            message_id=f"test-{uuid.uuid4()}",
            subject="Segundo email mismo remitente",
            body_plain="Segundo email para test.",
            sender_name="Test Sender",
            sender_email="test@ejemplo.com",  # same as first!
            recipients=["destino@empresa.com"],
            has_attachments=False,
            received_at=datetime.now(timezone.utc),
        ),
        extracted=None,
        final_category="cliente",
        final_confidence=0.9,
        resolution_method="majority",
        votes=[
            ClassifierVote(agent_name="rule_engine", category="cliente", confidence=0.9, reason="keyword", details={}),
        ],
        routing=RoutingDecision(
            departments=["contabilidad"],
            persons=[],
            rationale="test",
        ),
        processing_start=datetime.now(timezone.utc),
    )
    
    executor2 = ActionExecutor(db=session)
    result2 = await executor2.execute_all(ctx2)
    
    print("\n=== Second email (same sender) ===")
    for a in result2:
        s = "OK" if a.success else "FALLO"
        print(f"  [{s}] {a.action}: {a.detail}")
    
    # Check DB
    import sqlite3
    db = sqlite3.connect("backend/beexpand.db")
    print("\n=== DB State ===")
    emails = db.execute("SELECT subject, category, sender_email FROM emails").fetchall()
    print(f"Emails: {len(emails)}")
    for e in emails:
        print(f"  {e[2]:30s} | {e[1]:10s} | {e[0]}")
    
    contacts = db.execute("SELECT name, email, category, email_count FROM contacts").fetchall()
    print(f"Contacts: {len(contacts)}")
    for c in contacts:
        print(f"  {c[0]:20s} | {c[1]:30s} | {c[2]:10s} | count={c[3]}")
    
    db.close()
    await session.close()

asyncio.run(test())
