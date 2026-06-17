# Design: IN-05 — Evitar tickets duplicados

## Technical Approach

Two-phase dedup guard en `ActionExecutor._create_ticket()`, usando los nuevos campos `otrs_ticket_id` / `otrs_ticket_created_at` en el modelo `Email`:

1. **Pre-check** (post-guards, pre-try): si `ctx.raw.message_id` existe, consulta `Email` por `message_id`. Si ya tiene `otrs_ticket_id` → retorna early con `ActionResult(success=True)`, sin llamar a OTRS.
2. **Post-save** (post-ingest, pre-return): tras crear el ticket exitosamente, actualiza el `Email` con `otrs_ticket_id = ticket.id` y `otrs_ticket_created_at = now()`.

Estrategia **fail-open**: si la query pre-check falla, continúa y crea el ticket. Si el post-save falla, log.warning sin afectar el `ActionResult` (el ticket ya existe en OTRS).

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| DB query vs in-memory cache | Cache es más rápido pero no sobrevive reinicios; DB query es consistente | **DB query** — el pipeline ya tiene la sesión abierta, sin overhead adicional |
| Pre-check antes vs después de guards | Antes de guards es innecesario si OTRS no está configurado | **Después de guards** — solo tiene sentido verificar duplicado si vamos a crear ticket |
| Post-save bloqueante vs fire-and-forget | Bloqueante asegura consistencia; fire-and-forget podría perder el update | **Bloqueante** — es una operación local rápida en la misma sesión DB |
| Fail-open vs fail-closed en pre-check | Fail-closed podría bloquear tickets legítimos si DB falla | **Fail-open** — si no podemos verificar, mejor crear que arriesgar pérdida |
| message_id vs (message_id, account_id) | UniqueConstraint es compuesta | **message_id solo** — es suficientemente discriminante para MVP (1 cuenta) |

## Data Flow

```
_create_ticket(ctx)
  │
  ├─ Guards: ¿OTRS configurado? ¿nulo? → early return
  │
  ├─ PRE-CHECK: ¿ctx.raw.message_id?
  │     │
  │     ├─ SELECT Email WHERE message_id = ?
  │     │     │
  │     │     ├─ otrs_ticket_id IS NOT NULL → return "Ticket ya existe: {id}"
  │     │     │
  │     │     └─ NOT FOUND / otrs_ticket_id IS NULL → continue
  │     │
  │     └─ DB error → log.warning, continue (fail-open)
  │
  ├─ try:
  │     input = _build_ticket_input(ctx)
  │     ticket = await service.ingest_email(input)    ← OTRS API call
  │     │
  │     ├─ POST-SAVE: actualizar Email.otrs_ticket_id
  │     │     │
  │     │     ├─ SELECT Email WHERE message_id = ?
  │     │     ├─ email.otrs_ticket_id = ticket.id
  │     │     ├─ email.otrs_ticket_created_at = now()
  │     │     ├─ await db.commit()
  │     │     └─ Error → log.warning (no re-lanzar)
  │     │
  │     └─ return ActionResult(success=True, detail="Ticket {id} ...")
  │
  └─ except → return ActionResult(success=False, detail=str(e))
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/db/models.py` | Modify | +2 campos: `otrs_ticket_id`, `otrs_ticket_created_at` en `Email` |
| `backend/src/agents/action_executor.py` | Modify | Pre-check + post-save en `_create_ticket()` |
| `backend/alembic/versions/` | Create | Migration auto-generada con `op.add_column()` x2 |
| `backend/tests/test_action_executor.py` | Modify | +3 casos de test para dedup |

## Model Changes

```python
# En Email class (models.py)
otrs_ticket_id: Mapped[Optional[str]] = mapped_column(
    String(100), nullable=True, default=None
)
otrs_ticket_created_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
```

Ambos campos **nullable** — los registros existentes quedan con `NULL`. Sin índice adicional: la búsqueda pre-check usa `message_id` (único por account), no estos campos.

## Migration

```bash
cd backend
alembic revision --autogenerate -m "add_otrs_ticket_fields_to_emails"
```

Revisar el migration generado: debe contener únicamente:

```python
def upgrade():
    op.add_column("emails", sa.Column("otrs_ticket_id", sa.String(100), nullable=True))
    op.add_column("emails", sa.Column("otrs_ticket_created_at", sa.DateTime(timezone=True), nullable=True))
```

`down_revision` apunta a `f75fefbd4a00` (última migration existente).

## Testing Strategy

| Caso | Approach | Verificación |
|------|----------|--------------|
| Skip on existing ticket | Mock `self.db.execute` → retorna Email con `otrs_ticket_id="TCK-1"` | `ActionResult.success=True`, `"ya existe"` en detail, `ingest_email` NO es llamado |
| Create when no ticket exists | Mock `self.db.execute` → retorna Email sin `otrs_ticket_id` | `ingest_email` es llamado, post-save asigna `otrs_ticket_id` |
| Missing `message_id` | `ctx.raw.message_id = None` | Pre-check salta (no hay message_id), ticket se crea normalmente |
| DB error en pre-check | Mock `self.db.execute` → lanza excepción | No interrumpe flujo, ticket se crea (fail-open) |
| DB error en post-save | Mock `self.db.execute` / `commit` → lanza excepción | `log.warning` emitido, ActionResult sigue siendo `success=True` |
| All existing tests pass | Run test suite completo | No regresiones en T2.1–T2.3 |

Los nuevos tests usan `monkeypatch` sobre `self.db.execute` y `AsyncMock` para simular resultados del SELECT, siguiendo el patrón existente en `test_action_executor.py`.

## Migration / Rollout

No requiere migración de datos. Los registros existentes tienen `NULL` en ambos campos — el pre-check simplemente no encuentra `otrs_ticket_id` y procede a crear ticket (comportamiento actual). Rollback: `alembic downgrade -1` + revertir cambios de código.

## Open Questions

None.