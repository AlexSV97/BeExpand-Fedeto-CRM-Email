"""
Orchestrator — coordinador central del sistema multi-agente.

Flujo completo:
1. Recibe EmailData (desde IMAP fetcher o API)
2. Crea EmailContext con los datos crudos
3. Lanza agentes en orden:
   a. Analyzer Agent (extrae info estructurada)
   b. Classifier sub-agentes (3 votos en paralelo)
   c. VoteResolver (decide categoría final)
   d. Router Agent (decide enrutamiento)
   e. Action Executor (persiste + reenvía + notifica)
4. Retorna EmailContext completo con resultados
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents import (
    ActionExecutor,
    AnalyzerAgent,
    BertClassifierAgent,
    LLMClassifierAgent,
    ReplySuggesterAgent,
    RouterAgent,
    RuleClassifierAgent,
)
from src.orchestrator.context import EmailData, EmailContext
from src.orchestrator.resolver import VoteResolver

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orquestador central del pipeline de agentes."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        analyzer: AnalyzerAgent | None = None,
        rule_classifier: RuleClassifierAgent | None = None,
        bert_classifier: BertClassifierAgent | None = None,
        llm_classifier: LLMClassifierAgent | None = None,
        resolver: VoteResolver | None = None,
        router: RouterAgent | None = None,
        reply_suggester: ReplySuggesterAgent | None = None,
    ):
        self.db = db
        self.analyzer = analyzer or AnalyzerAgent()
        self.rule_classifier = rule_classifier or RuleClassifierAgent()
        self.bert_classifier = bert_classifier or BertClassifierAgent()
        self.llm_classifier = llm_classifier or LLMClassifierAgent()
        self.resolver = resolver or VoteResolver()
        self.router = router or RouterAgent()
        self.reply_suggester = reply_suggester or ReplySuggesterAgent()

    async def process(
        self,
        email_data: EmailData,
        db: AsyncSession | None = None,
    ) -> EmailContext:
        """
        Procesa un email a través de todo el pipeline de agentes.

        Args:
            email_data: Datos crudos del email (desde IMAP fetcher o API).
            db: Sesión de BD (si no se pasó en el constructor).

        Returns:
            EmailContext completo con todos los resultados del pipeline.
        """
        ctx = EmailContext(
            raw=email_data,
            processing_start=datetime.now(timezone.utc),
        )

        session = db or self.db
        if session is None:
            raise ValueError(
                "Se requiere una sesión de BD (pasarla al constructor o al process())"
            )

        try:
            # ── Paso 1: Analyzer + 3 Classifiers en PARALELO ──
            # Analyzer extrae info estructurada; los 3 clasificadores votan.
            # Todo es independiente: ninguno necesita el resultado del otro.
            logger.info("⚡ Pipeline paralelo: Analyzer + 3 classifiers...")
            analyzer_coro = self.analyzer.analyze(
                subject=email_data.subject or "",
                body=email_data.body_plain or "",
                sender_name=email_data.sender_name,
                sender_email=email_data.sender_email,
            )
            rule_coro = self.rule_classifier.classify(
                email_data.subject or "", email_data.body_plain or "",
            )
            bert_coro = self.bert_classifier.classify(
                email_data.subject or "", email_data.body_plain or "",
            )
            llm_coro = self.llm_classifier.classify(
                email_data.subject or "", email_data.body_plain or "",
            )

            analyzer_result, vote_rule, vote_bert, vote_llm = await asyncio.gather(
                analyzer_coro, rule_coro, bert_coro, llm_coro,
            )

            ctx.analyzer_result = analyzer_result
            ctx.extracted = analyzer_result.extracted
            ctx.votes = [vote_rule, vote_bert, vote_llm]

            # ── Paso 3: VoteResolver (decide categoría final) ──
            logger.info("⚖️  Resolver: resolviendo %d votos...", len(votes))
            category, confidence, method = await self.resolver.resolve(ctx)
            ctx.final_category = category
            ctx.final_confidence = confidence
            ctx.resolution_method = method
            logger.info(
                "✅ Decisión: %s (%.0f%%) vía %s",
                category,
                confidence * 100,
                method,
            )

            # ── Paso 4: Router (enrutamiento a departamentos) ──
            if category != "nulo":
                logger.info("🧭 Router: determinando destino...")
                routing = await self.router.route(
                    email_data=email_data,
                    extracted=ctx.extracted,
                    category=category,
                )
                ctx.routing = routing
                logger.info(
                    "📍 Ruta: %s",
                    ", ".join(routing.departments) if routing.departments else "sin destino",
                )
            else:
                ctx.routing = None
                logger.info("🚫 Email nulo — sin enrutamiento")

            # ── Paso 5: Reply Suggester (borrador de respuesta) ──
            if category != "nulo":
                logger.info("✍️  ReplySuggester: generando borrador...")
                suggested_reply = await self.reply_suggester.generate(ctx)
            else:
                suggested_reply = ""
            ctx.suggested_reply = suggested_reply

            # ── Paso 6: Action Executor (persistir + reenviar) ──
            logger.info("💾 Action Executor: guardando en BD y reenviando...")
            executor = ActionExecutor(db=session)
            await executor.execute_all(ctx)

            ctx.processing_end = datetime.now(timezone.utc)
            logger.info(
                "✅ Pipeline completo: %s | categoría=%s (%.0f%%) | %.0fms",
                email_data.subject,
                ctx.final_category,
                ctx.final_confidence * 100,
                ctx.processing_time_ms,
            )

        except Exception as e:
            ctx.processing_end = datetime.now(timezone.utc)
            ctx.error = str(e)
            logger.error("❌ Error en pipeline: %s", e, exc_info=True)

        return ctx

    async def process_raw_email(
        self,
        subject: str,
        body_plain: str,
        sender_name: str,
        sender_email: str,
        message_id: str | None = None,
        recipients: list[str] | None = None,
        received_at: datetime | None = None,
        has_attachments: bool = False,
        body_html: str | None = None,
        db: AsyncSession | None = None,
    ) -> EmailContext:
        """
        Procesa un email directamente desde parámetros (conveniencia).

        Útil para llamadas desde la API o desde scripts de prueba.
        """
        email_data = EmailData(
            message_id=message_id,
            subject=subject,
            body_plain=body_plain,
            body_html=body_html,
            sender_name=sender_name,
            sender_email=sender_email,
            recipients=recipients or [],
            has_attachments=has_attachments,
            received_at=received_at,
        )
        return await self.process(email_data, db=db)
