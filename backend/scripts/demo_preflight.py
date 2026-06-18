#!/usr/bin/env python3
"""Demo pre-flight check for Aiuken SOC.

Logs into a running deployment and exercises every surface used in the demo,
printing a green/red checklist. Run this right before showing the platform to
Aiuken so nothing breaks live.

Usage:
    python backend/scripts/demo_preflight.py
    DEMO_BASE_URL=https://beexpand-fedeto-crm-email.onrender.com \
        DEMO_USER=admin DEMO_PASS=admin123 python backend/scripts/demo_preflight.py

Exit code 0 if all checks pass, 1 otherwise. Read-mostly; a few POST checks write
demo records (synthetic data), which is safe.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASE = os.getenv("DEMO_BASE_URL", "https://beexpand-fedeto-crm-email.onrender.com").rstrip("/")
USER = os.getenv("DEMO_USER", "admin")
PASS = os.getenv("DEMO_PASS", "admin123")
TICKET = os.getenv("DEMO_TICKET", "TICKET-1000")
API = f"{BASE}/api/v1"

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"

try:  # ensure unicode/ANSI output works on Windows consoles (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _call(method, path, token=None, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t
    except Exception as e:  # noqa: BLE001
        return "ERR", repr(e), time.time() - t


def main() -> int:
    print(f"{DIM}Aiuken SOC demo pre-flight -> {BASE}{RESET}\n")

    code, body, dt = _call("POST", "/auth/login", body={"username": USER, "password": PASS})
    if code != 200:
        print(f"{RED}[X] login failed ({code}){RESET}  {body[:160]}")
        return 1
    token = json.loads(body)["access_token"]
    print(f"{GREEN}[OK] login{RESET} ({dt:.1f}s)\n")

    # (scene, method, path, body) — maps to the demo guion.
    checks = [
        ("Command Center (KPIs/alertas)", "GET", "/soc/command-center", None),
        ("Smart Inbox (riesgo SLA + cola sugerida)", "GET", "/soc/tickets", None),
        ("Ticket Copilot + Knowledge", "GET", f"/soc/tickets/{TICKET}/copilot", None),
        ("RAG con citas", "POST", "/search/knowledge/answer", {"query": "password reset", "limit": 3}),
        ("Casos similares", "POST", "/search/similar-cases", {"subject": "password reset request"}),
        ("Knowledge Vault", "GET", "/soc/knowledge?search=password", None),
        ("SLA War Room", "GET", "/soc/sla", None),
        ("SLA alertas (scan)", "POST", "/soc/sla/alerts/scan", None),
        ("SLA alertas (lista)", "GET", "/soc/sla/alerts", None),
        ("Sugerencia de cola IA", "POST", "/queues/suggestion", {"subject": "Critical incident: error and timeout", "body_text": "production down"}),
        ("Escalado N-niveles", "POST", "/queues/escalate", {"current_tier": "n1", "target_tier": "n3", "reason": "demo"}),
        ("SOC escalate", "POST", f"/soc/tickets/{TICKET}/escalate", {"reason": "demo escalation", "target_tier": "n2"}),
        ("Historial de escalados", "GET", f"/soc/tickets/{TICKET}/escalations", None),
        ("Borrador IA (respuesta cliente)", "POST", f"/soc/tickets/{TICKET}/draft?kind=customer_reply", None),
        ("Owner/lock (assign)", "POST", f"/soc/tickets/{TICKET}/assign", {"owner": "alice"}),
        ("Owner/lock (estado)", "GET", f"/soc/tickets/{TICKET}/ownership", None),
        ("Escalado externo (fabricante)", "POST", f"/soc/tickets/{TICKET}/escalate-external", {"destination": "fabricante"}),
        ("Gobierno: recomendación", "POST", "/agents/recommendation", {"subject": "Critical incident", "body_text": "error timeout incident"}),
        ("Gobierno: cola de aprobaciones", "GET", "/agents/approvals/pending", None),
        ("Observabilidad", "GET", "/reporting/observability", None),
    ]

    ok = 0
    for scene, method, path, payload in checks:
        code, body, dt = _call(method, path, token=token, body=payload)
        passed = code == 200
        ok += passed
        mark = f"{GREEN}[OK]{RESET}" if passed else f"{RED}[X ]{RESET}"
        extra = "" if passed else f"  {RED}{code}{RESET} {body[:100]}"
        print(f"{mark} {scene:<42} {DIM}{method} {path.split('?')[0]}{RESET} ({dt:.1f}s){extra}")

    total = len(checks)
    print()
    if ok == total:
        print(f"{GREEN}ALL GREEN — {ok}/{total} checks passed. Listo para la demo.{RESET}")
        return 0
    print(f"{RED}{total - ok} check(s) failed ({ok}/{total}).{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
