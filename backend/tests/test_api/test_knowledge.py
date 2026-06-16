from __future__ import annotations

from src.api.main import app
from src.services.knowledge_vault import KnowledgeDocument, KnowledgeVaultService


async def test_search_knowledge_endpoint(client, auth_headers):
    app.state.knowledge_vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-1",
                title="SLA breach in WAF queue",
                body="The customer faced a breach risk and needed escalation.",
                customer="Aiuken",
                tags=["sla", "waf", "escalation"],
            ),
        ]
    )

    response = await client.get(
        "/api/v1/search/knowledge",
        params={"query": "sla breach", "limit": 5},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["document"]["id"] == "doc-1"


async def test_similar_cases_endpoint(client, auth_headers):
    app.state.knowledge_vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="case-1",
                title="WAF false positive on login",
                body="The ticket was resolved by updating the WAF rule.",
                document_type="case",
                customer="Aiuken",
                tags=["waf", "login"],
            ),
        ]
    )

    response = await client.post(
        "/api/v1/search/similar-cases",
        json={"subject": "WAF login issue", "body_text": "False positive on login", "customer": "Aiuken"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["document"]["id"] == "case-1"
