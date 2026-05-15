"""
BertClassifierAgent — sub-agente de clasificación basado en DistilBERT fine-tuned.

Vota usando el modelo de ML local (~50ms/inferencia).
El modelo debe estar entrenado en scripts/train_bert_hybrid.py.
Si el modelo no está disponible, vota con confianza 0 (se ignora).
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from src.agents.classifier.base import BaseClassifierAgent
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "classifier" / "model"


class BertClassifierAgent(BaseClassifierAgent):
    """Clasificador BERT que vota en el sistema multi-agente."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.model = None
        self.tokenizer = None
        self.labels = {"cliente": 0, "lead": 1, "proveedor": 2, "nulo": 3}
        self.id2label = {v: k for k, v in self.labels.items()}
        self._loaded = False

    @property
    def agent_name(self) -> str:
        return "bert"

    def _ensure_loaded(self):
        """Carga el modelo bajo demanda (lazy loading)."""
        if self._loaded:
            return

        if not self.model_dir.exists():
            logger.warning(
                "Modelo BERT no encontrado en %s. El agente BERT votará con confianza 0.",
                self.model_dir,
            )
            self._loaded = False
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info("Cargando modelo BERT desde %s...", self.model_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
            self.model = AutoModelForSequenceClassification.from_pretrained(
                str(self.model_dir)
            )
            self.model.eval()
            self._loaded = True
            logger.info("Modelo BERT cargado correctamente")
        except Exception as e:
            logger.error("Error cargando modelo BERT: %s", e)
            self._loaded = False

    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """Clasifica usando BERT. Retorna un voto."""
        start = time.time()

        if not self.model_dir.exists():
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason="modelo BERT no disponible (ejecutar train_bert_hybrid.py)",
            )

        self._ensure_loaded()
        if not self._loaded:
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason="modelo BERT no cargado",
            )

        try:
            text = f"{subject or ''} {body or ''}"[:512]

            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding="max_length",
                truncation=True,
                max_length=128,
            )

            import torch

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=-1)
                confidence, predicted = torch.max(probabilities, dim=-1)

            label_id = predicted.item()
            confidence_score = round(confidence.item(), 2)
            category = self.id2label.get(label_id, "nulo")

            elapsed = (time.time() - start) * 1000
            logger.debug(
                "BERT votó: %s -> %s (%.0f%%) en %.0fms",
                subject[:50] if subject else "",
                category,
                confidence_score * 100,
                elapsed,
            )

            return ClassifierVote(
                agent_name=self.agent_name,
                category=category,
                confidence=confidence_score,
                reason=f"distilBERT: {confidence_score:.0%} para '{category}'",
                details={
                    "label_id": label_id,
                    "probabilities": probabilities[0].tolist(),
                    "processing_ms": round(elapsed, 1),
                },
            )

        except Exception as e:
            logger.error("Error en clasificación BERT: %s", e)
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=f"error BERT: {e}",
            )

    @property
    def is_available(self) -> bool:
        return self.model_dir.exists() and (self.model_dir / "config.json").exists()
