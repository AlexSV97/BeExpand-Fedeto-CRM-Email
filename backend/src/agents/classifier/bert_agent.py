"""
BertClassifierAgent — sub-agente de clasificacion basado en DistilBERT fine-tuned.

Vota usando el modelo de ML local (~50ms/inferencia).
El modelo debe estar entrenado en scripts/train_bert_hybrid.py.

Estrategia de carga (por orden de prioridad):
1. Modelo fine-tuneado local (BEST, ~541MB, necesita entrenamiento previo)
2. DistilBERT base desde HuggingFace (FALLBACK, ~260MB, primera descarga lenta)
3. Si todo falla, vota con confianza 0 (el VoteResolver usa Rule + LLM)

La ruta del modelo fine-tuneado se resuelve asi:
1. Parametro explicito `model_dir`
2. Variable de entorno BERT_MODEL_PATH
3. Ruta por defecto: backend/src/classifier/model/
"""

import logging
import time
from pathlib import Path
from typing import Optional

from src.agents.classifier.base import BaseClassifierAgent
from src.config import get_settings
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "classifier" / "model"
_FALLBACK_HF_MODEL = "distilbert-base-multilingual-cased"


def _resolve_model_dir(override: Optional[Path] = None) -> Path:
    """Resuelve la ruta del modelo con prioridad: override > env > default."""
    if override is not None:
        return override
    env_path = get_settings().bert_model_path
    if env_path:
        return Path(env_path)
    return _DEFAULT_MODEL_DIR


class BertClassifierAgent(BaseClassifierAgent):
    """Clasificador BERT que vota en el sistema multi-agente.

    Usa modelo fine-tuneado local si existe (541MB, alta precision).
    Si no, descarga DistilBERT base de HuggingFace (260MB, precision media).
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = _resolve_model_dir(model_dir)
        self.model = None
        self.tokenizer = None
        self.labels = {"cliente": 0, "lead": 1, "proveedor": 2, "nulo": 3}
        self.id2label = {v: k for k, v in self.labels.items()}
        self._loaded = False
        self._using_fallback = False

    @property
    def agent_name(self) -> str:
        return "bert"

    def _ensure_loaded(self):
        """Carga el modelo bajo demanda (lazy loading)."""
        if self._loaded:
            return

        # Intento 1: modelo fine-tuneado local
        if self.model_dir.exists():
            self._using_fallback = False
            if self._load_from_dir(self.model_dir):
                return

        # Intento 2: fallback a DistilBERT base desde HuggingFace
        logger.warning(
            "Modelo fine-tuneado no encontrado en %s. "
            "Descargando DistilBERT base desde HuggingFace como fallback...",
            self.model_dir,
        )
        self._using_fallback = True
        if self._load_from_hf():
            return

        # Si llegamos aqui, ambos intentos fallaron
        logger.error(
            "BERT no disponible: ni modelo local ni fallback HuggingFace. "
            "El sistema funcionara sin voto BERT."
        )
        self._loaded = False

    def _load_from_dir(self, model_dir: Path) -> bool:
        """Carga modelo fine-tuneado desde directorio local."""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info("Cargando modelo BERT fine-tuneado desde %s...", model_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
            self.model = AutoModelForSequenceClassification.from_pretrained(
                str(model_dir)
            )
            self.model.eval()
            self._loaded = True
            logger.info("Modelo BERT fine-tuneado cargado correctamente")
            return True
        except Exception as e:
            logger.error("Error cargando modelo BERT local: %s", e)
            self._loaded = False
            return False

    def _load_from_hf(self) -> bool:
        """Descarga y carga DistilBERT base desde HuggingFace como fallback."""
        try:
            from transformers import (
                AutoConfig,
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            logger.info("Descargando DistilBERT base desde HuggingFace (%s)...", _FALLBACK_HF_MODEL)

            # Configurar con 4 labels para que coincida con nuestras categorias
            config = AutoConfig.from_pretrained(
                _FALLBACK_HF_MODEL,
                num_labels=4,
                id2label=self.id2label,
                label2id=self.labels,
            )
            self.tokenizer = AutoTokenizer.from_pretrained(_FALLBACK_HF_MODEL)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                _FALLBACK_HF_MODEL,
                config=config,
                ignore_mismatched_sizes=True,
            )
            self.model.eval()
            self._loaded = True
            logger.info(
                "DistilBERT base cargado desde HuggingFace (precision reducida - "
                "no fine-tuneado). Entrena con scripts/train_bert_hybrid.py para "
                "mejorar precision."
            )
            return True
        except Exception as e:
            logger.error("Error descargando DistilBERT base desde HuggingFace: %s", e)
            self._loaded = False
            return False

    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """Clasifica usando BERT. Retorna un voto."""
        start = time.time()

        self._ensure_loaded()
        if not self._loaded:
            elapsed = (time.time() - start) * 1000
            reason = (
                "modelo BERT no disponible - ejecuta scripts/train_bert_hybrid.py "
                "para entrenar modelo fine-tuneado, o "
                "configura BERT_MODEL_PATH apuntando al directorio del modelo"
            )
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=reason,
                details={
                    "processing_ms": round(elapsed, 1),
                    "model_source": "none",
                    "model_path": str(self.model_dir),
                    "fallback_model": _FALLBACK_HF_MODEL,
                },
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
            model_source = "fallback-hf" if self._using_fallback else "fine-tuned"
            more_info = (
                ""
                if not self._using_fallback
                else " (base model, entrena fine-tuneado para mejor precision)"
            )
            logger.info(
                "BERT voto: %s -> %s (%.0f%%) en %.0fms [%s]%s",
                subject[:50] if subject else "",
                category,
                confidence_score * 100,
                elapsed,
                model_source,
                more_info,
            )

            return ClassifierVote(
                agent_name=self.agent_name,
                category=category,
                confidence=confidence_score,
                reason=f"distilBERT {'(fallback)' if self._using_fallback else ''}: "
                       f"{confidence_score:.0%} para '{category}'",
                details={
                    "label_id": label_id,
                    "probabilities": probabilities[0].tolist(),
                    "processing_ms": round(elapsed, 1),
                    "model_source": model_source,
                },
            )

        except Exception as e:
            logger.error("Error en clasificacion BERT: %s", e)
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=f"error BERT: {e}",
            )

    @property
    def is_available(self) -> bool:
        return self.model_dir.exists() and (self.model_dir / "config.json").exists()
