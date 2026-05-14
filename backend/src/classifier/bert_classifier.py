"""
Clasificador BERT (DistilBERT multilingual fine-tuned).

Segunda capa del sistema híbrido:
1. RuleEngine (instantáneo, confianza >= 70%)
2. → BERT (rápido, ~50ms, confianza >= 50%)
3. → Ollama/LLM (lento, ~1-3s, último recurso)

Uso:
    from src.classifier.bert_classifier import BertClassifier
    classifier = BertClassifier()
    cat, conf = classifier.classify("asunto", "cuerpo")
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "model"


class BertClassifier:
    """Clasificador basado en DistilBERT fine-tuned para categorías de correo."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.model = None
        self.tokenizer = None
        self.labels = {"cliente": 0, "lead": 1, "proveedor": 2, "pendiente": 3}
        self.id2label = {v: k for k, v in self.labels.items()}
        self._loaded = False

    def _ensure_loaded(self):
        """Carga el modelo bajo demanda (lazy loading)."""
        if self._loaded:
            return

        if not self.model_dir.exists():
            logger.warning(
                "Modelo BERT no encontrado en %s. "
                "Ejecuta 'python scripts/train_bert_classifier.py' primero.",
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
            self.model.eval()  # Modo evaluación
            self._loaded = True
            logger.info("Modelo BERT cargado correctamente")
        except Exception as e:
            logger.error("Error cargando modelo BERT: %s", e)
            self._loaded = False

    def classify(self, subject: str, body: str) -> tuple[str, float]:
        """
        Clasifica un correo usando BERT.
        Retorna (categoría, confianza).
        Si el modelo no está disponible, retorna ("pendiente", 0.0).
        """
        self._ensure_loaded()
        if not self._loaded:
            return "pendiente", 0.0

        try:
            text = f"{subject or ''} {body or ''}"[:512]  # Limitar longitud

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
            category = self.id2label.get(label_id, "pendiente")

            logger.debug(
                "BERT: %s -> %s (%.0f%%)",
                subject[:50],
                category,
                confidence_score * 100,
            )
            return category, confidence_score

        except Exception as e:
            logger.error("Error en clasificación BERT: %s", e)
            return "pendiente", 0.0

    @property
    def is_available(self) -> bool:
        """Verifica si el modelo está disponible sin cargarlo."""
        return self.model_dir.exists() and (self.model_dir / "config.json").exists()


# Singleton para reutilizar entre llamadas
_instance: Optional[BertClassifier] = None


def get_classifier() -> BertClassifier:
    """Obtiene o crea la instancia singleton del clasificador BERT."""
    global _instance
    if _instance is None:
        _instance = BertClassifier()
    return _instance


def classify_with_bert(subject: str, body: str) -> tuple[str, float]:
    """Función de conveniencia: clasifica usando BERT (devuelve categoría y confianza)."""
    clf = get_classifier()
    return clf.classify(subject, body)
