from __future__ import annotations

from src.services.knowledge_vault import (
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeVaultService,
    SimilarCaseRequest,
)


def test_knowledge_search_ranks_sla_cases_first():
    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-1",
                title="SLA breach in WAF queue",
                body="The customer faced a breach risk and needed escalation.",
                customer="Aiuken",
                tags=["sla", "waf", "escalation"],
            ),
            KnowledgeDocument(
                id="doc-2",
                title="Password reset playbook",
                body="How to reset a user password.",
                customer="Ops",
                tags=["account", "password"],
            ),
        ]
    )

    result = vault.search(KnowledgeSearchRequest(query="sla breach escalation", limit=5))

    assert result.total == 1
    assert result.items[0].document.id == "doc-1"
    assert "sla" in result.items[0].matched_terms


def test_knowledge_search_filters_by_customer_and_type():
    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="doc-1",
                title="Case A",
                body="Issue A",
                customer="Aiuken",
                document_type="case",
            ),
            KnowledgeDocument(
                id="doc-2",
                title="Runbook B",
                body="Issue B",
                customer="Aiuken",
                document_type="runbook",
            ),
        ]
    )

    result = vault.search(
        KnowledgeSearchRequest(query="issue", customer="Aiuken", document_type="case")
    )

    assert result.total == 1
    assert result.items[0].document.id == "doc-1"


def test_similarity_lookup_uses_ticket_like_text():
    vault = KnowledgeVaultService(
        [
            KnowledgeDocument(
                id="case-1",
                title="WAF false positive on login",
                body="The ticket was resolved by updating the WAF rule.",
                document_type="case",
                customer="Aiuken",
                tags=["waf", "login"],
            ),
            KnowledgeDocument(
                id="case-2",
                title="Patch management reminder",
                body="Install pending updates.",
                document_type="case",
            ),
        ]
    )

    result = vault.similar_cases(
        SimilarCaseRequest(subject="WAF login issue", body_text="False positive on login", customer="Aiuken")
    )

    assert result.total == 1
    assert result.items[0].document.id == "case-1"
