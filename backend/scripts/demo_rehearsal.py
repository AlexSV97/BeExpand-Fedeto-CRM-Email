#!/usr/bin/env python3
"""Timed demo rehearsal for Aiuken SOC.

Runs the 10 demo scenes (docs/DEMO_AIUKEN_SOC.md) in order against a live
deployment, times each scene's API readiness, and prints the representative data
point the presenter would show. Helps rehearse pacing and catch slow/cold calls.

    python backend/scripts/demo_rehearsal.py
    DEMO_BASE_URL=... DEMO_USER=admin DEMO_PASS=admin123 python backend/scripts/demo_rehearsal.py

Note: timings are API/data readiness, NOT talk time. The "budget" column is the
guion's allotted talking minutes.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = os.getenv("DEMO_BASE_URL", "https://beexpand-fedeto-crm-email.onrender.com").rstrip("/")
USER = os.getenv("DEMO_USER", "admin")
PASS = os.getenv("DEMO_PASS", "admin123")
TICKET = os.getenv("DEMO_TICKET", "TICKET-1000")
API = f"{BASE}/api/v1"

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


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
            return r.status, json.loads(r.read().decode("utf-8", "replace")), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, {}, time.time() - t
    except Exception as e:  # noqa: BLE001
        return "ERR", {"error": repr(e)}, time.time() - t


def main() -> int:
    print(f"{BOLD}Aiuken SOC — ensayo cronometrado{RESET}  {DIM}{BASE}{RESET}\n")
    code, body, dt = _call("POST", "/auth/login", body={"username": USER, "password": PASS})
    if code != 200:
        print(f"{RED}login failed ({code}){RESET}")
        return 1
    tok = body["access_token"]
    print(f"{DIM}login {dt:.1f}s{RESET}\n")

    def G(p):
        return _call("GET", p, token=tok)

    def P(p, b=None):
        return _call("POST", p, token=tok, body=b)

    scenes = []  # (n, title, budget_min, runner)

    def scene(n, title, budget, runner):
        scenes.append((n, title, budget, runner))

    scene(1, "Login + modo", 1, lambda: ("operatingMode via command-center", G("/soc/command-center")))
    scene(2, "Command Center", 2, lambda: G("/soc/command-center"))
    scene(3, "Smart Inbox", 2, lambda: G("/soc/tickets"))
    scene(4, "Ticket Copilot", 3, lambda: G(f"/soc/tickets/{TICKET}/copilot"))
    scene(5, "Borrador IA + aprobación", 2, lambda: P(f"/soc/tickets/{TICKET}/draft?kind=customer_reply"))
    scene(6, "RAG con citas", 2, lambda: P("/search/knowledge/answer", {"query": "password reset", "limit": 3}))
    scene(7, "SLA War Room + alertas", 2, lambda: ("war+scan", _sla(P, G)))
    scene(8, "Escalado N-niveles + externo", 2, lambda: ("escalate", _escal(P)))
    scene(9, "Agentes + gobierno", 2, lambda: ("governance", _gov(P, G)))
    scene(10, "Observabilidad", 1, lambda: G("/reporting/observability"))

    total_api = 0.0
    total_budget = 0
    all_ok = True
    print(f"{BOLD}{'#':<2} {'Escena':<32} {'API':>7} {'Budget':>7}  Dato representativo{RESET}")
    print(f"{DIM}{'-'*92}{RESET}")
    for n, title, budget, runner in scenes:
        t0 = time.time()
        result = runner()
        # runner returns either (code, body, dt) or (label, (code, body, dt))
        if isinstance(result, tuple) and len(result) == 3 and isinstance(result[0], (int, str)) and isinstance(result[2], float):
            code, body, dt = result
        else:
            _label, inner = result
            code, body, dt = inner
        api = time.time() - t0
        total_api += api
        total_budget += budget
        ok = code == 200
        all_ok = all_ok and ok
        mark = f"{GREEN}OK{RESET}" if ok else f"{RED}{code}{RESET}"
        highlight = _highlight(n, body)
        print(f"{n:<2} {title:<32} {api:>6.1f}s {budget:>5}m   [{mark}] {highlight}")

    print(f"{DIM}{'-'*92}{RESET}")
    mm = total_budget
    print(f"{BOLD}Total: API {total_api:.1f}s · talk budget ~{mm} min{RESET}")
    print(f"{DIM}(La API está lista en segundos; el tiempo de demo lo marca el discurso, no las llamadas.){RESET}")
    print((f"{GREEN}Ensayo OK — todas las escenas respondieron 200.{RESET}" if all_ok
           else f"{RED}Alguna escena falló — revisa antes de la demo.{RESET}"))
    return 0 if all_ok else 1


def _sla(P, G):
    G("/soc/sla")
    return P("/soc/sla/alerts/scan")


def _escal(P):
    P(f"/soc/tickets/{TICKET}/escalate", {"reason": "demo", "target_tier": "n2"})
    return P(f"/soc/tickets/{TICKET}/escalate-external", {"destination": "fabricante"})


def _gov(P, G):
    P("/agents/recommendation", {"subject": "Critical incident", "body_text": "error timeout incident"})
    return G("/agents/approvals/pending")


def _highlight(n, b):
    try:
        if n in (1, 2):
            return f"{len(b.get('kpiCards', []))} KPIs, {len(b.get('recentAlerts', []))} alertas, modo={b.get('operatingMode')}"
        if n == 3:
            t = (b.get("tickets") or [{}])[0]
            return f"{b.get('total')} tickets · fila: riesgoSLA={t.get('slaRisk')} colaSug={t.get('suggestedQueue')} owner={t.get('owner')}"
        if n == 4:
            return f"{len(b.get('suggestedActions', []))} acciones sugeridas · modo={b.get('operatingMode')}"
        if n == 5:
            return f"source={b.get('source')} requiresApproval={b.get('requires_approval')} chars={len(b.get('text',''))}"
        if n == 6:
            return f"source={b.get('source')} grounded={b.get('grounded')} fuentes={len(b.get('sources', []))}"
        if n == 7:
            return f"scan: {b.get('generated')} alertas generadas / {b.get('scanned')} escaneados"
        if n == 8:
            ref = (b.get("tracking_ref") or {}).get("external_id")
            return f"handoff externo → cola={b.get('queue_slug')} trackingRef={ref}"
        if n == 9:
            return f"{b.get('total')} aprobaciones pendientes en cola"
        if n == 10:
            ints = {i.get('name'): i.get('status') for i in b.get('integrations', [])}
            return f"modo={b.get('operatingMode')} integraciones={ints} fallos={b.get('failures')}"
    except Exception:  # noqa: BLE001
        pass
    return ""


if __name__ == "__main__":
    sys.exit(main())
