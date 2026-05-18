# BeExpand-Fedeto-CRM-Email

## Stack
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Celery + Redis
- **Frontend**: React 19 + TypeScript, Vite 8 (Rolldown), Recharts, React Router 7
- **BD**: SQLite (dev) / PostgreSQL 16 (prod)
- **CRM**: VTiger REST API (via httpx)
- **IA Local**: Ollama (llama3.2:3b), DistilBERT multilingual cased
- **Contenedores**: Docker / docker-compose (previsto)
- **Auth**: JWT (python-jose + passlib + bcrypt < 5.0.0)

## Clasificación de Emails — Orquestador Multi-Agente en Paralelo

```
Email ──→ Orchestrator ──┬── Analyzer (LLM: info estructurada)
                         │
                         ├── RuleClassifierAgent (keywords ponderados, ~1ms)
                         ├── BertClassifierAgent (DistilBERT, ~50ms)    ← PARALELO
                         ├── LLMClassifierAgent (Ollama, ~1-3s)
                         │
                         ├── VoteResolver ──→ categoría final
                         │    ├─ CONSENSUS: los 3 coinciden
                         │    ├─ MAJORITY: 2 de 3 coinciden
                         │    ├─ LLM_JUDGE: 3 votos distintos → juez
                         │    └─ FALLBACK: mejor voto individual
                         │
                         ├── RouterAgent (departamento destino)
                         └── ActionExecutor (BD + historial + reenvío)
```

- **Los 3 clasificadores se ejecutan en paralelo** con `asyncio.gather()`
- **Cada uno tiene el MISMO peso**: todos los votos cuentan igual
- **RuleEngine ya NO filtra** — BERT y Ollama ven TODOS los emails
- Si 2 de 3 coinciden (MAJORITY) → gana esa categoría
- Si hay empate o los 3 son distintos → el LLM juez decide viendo los votos + el análisis
- Anti-spam: si 2+ votan "nulo" → nulo por mayoría
- El Analyzer extrae empresa, urgencia, acción, entidades, resumen (todo con Ollama)

## Estado del proyecto
- M1-M4 COMPLETADOS (IMAP, Parser, Classifier secuencial, API, Frontend)
- ✅ M5 (Orquestador Paralelo) — YA IMPLEMENTADO
- Pipeline completo: IMAP → Parse → Analyzer → 3 clasificadores paralelo → Voto → Router → ActionExecutor
- Tests backend: ~94 tests

## Ramas activas
- `main` — producción
- `feat/m3-classifier` — clasificador secuencial
- `feat/m3-crm-sync` — sincronización CRM
- `feature/m4-api-rest` — API REST
- `feature/m4-frontend` — dashboard React

## Comandos
```bash
# Backend
cd backend && uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd frontend && npx vite --port 5173

# Tests
cd backend && pytest -v

# Re-entrenar BERT
cd backend && python scripts/train_bert_hybrid.py

# Test clasificador
cd backend && python scripts/test_classifier.py --verbose

# Login demo
admin / admin123
```

## Convenciones
- **Commits**: convencionales (feat:, fix:, refactor:, chore:, docs:)
- **Ramas**: tipo/descripcion (feat/m3-classifier, fix/sync-error)
- **Python**: type hints obligatorios, SQLAlchemy async, Pydantic v2
- **Frontend**: React 19 con React Compiler (sin useMemo/useCallback), Tailwind CSS 4
- **Tests**: pytest-asyncio, respx para mock HTTP, TDD estricto
- **SDD**: Usar flujo SDD para cambios grandes (explore → propose → spec → design → tasks → apply → verify)

## Skills relevantes
- pytest (tests Python), playwright (E2E), typescript, react-19, tailwind-4
- code-architect, code-explorer (para diseñar features nuevas)
- git-master, work-unit-commits, branch-pr, chained-pr (para commits y PRs)
- sdd-* (para cambios estructurados)

## Servicios
- Ollama: http://127.0.0.1:11434 (ejecutar `ollama serve`)
- Backend: http://localhost:8001
- Frontend: http://localhost:5173
