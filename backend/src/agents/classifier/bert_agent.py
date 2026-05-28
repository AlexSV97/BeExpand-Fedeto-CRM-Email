"""
BertClassifierAgent — sub-agente de clasificacion basado en DistilBERT fine-tuned.

Vota usando el modelo de ML local (~50ms/inferencia).
El modelo debe estar entrenado en scripts/train_bert_hybrid.py.

Estrategia de carga (por orden de prioridad):
1. Modelo fine-tuneado LOCAL (BEST, ~541MB, entrenado con datos reales)
2. Modelo fine-tuneado desde HuggingFace Hub (BEST en produccion, ~541MB)
3. DistilBERT base desde HuggingFace (FALLBACK, ~260MB, precision reducida)
4. Si todo falla, vota con confianza 0 (el VoteResolver usa Rule + LLM)

La ruta del modelo fine-tuneado local se resuelve asi:
1. Parametro explicito `model_dir`
2. Variable de entorno BERT_MODEL_PATH
3. Ruta por defecto: backend/src/classifier/model/

El fallback via HuggingFace Hub se usa SOLO si:
- No existe modelo local
- Hay token configurado en settings.huggingface_token
- El repo ID esta configurado en settings.huggingface_model_id
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
    Si no, fallback a HuggingFace Hub (fine-tuneado, si hay token).
    Si no, descarga DistilBERT base de HuggingFace (260MB, precision media).
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = _resolve_model_dir(model_dir)
        self.model = None
        self.tokenizer = None
        self.labels = {"cliente": 0, "lead": 1, "proveedor": 2, "nulo": 3}
        self.id2label = {v: k for k, v in self.labels.items()}
        self._loaded = False
        self._using_fallback = False  # True si NO estamos usando fine-tuneado local

    @property
    def agent_name(self) -> str:
        return "bert"

    def _ensure_loaded(self):
        """Carga el modelo bajo demanda (lazy loading).

        Si bert_enabled=False (Render free tier con 512MB RAM),
        no carga nada — vota confianza 0.
        """
        settings = get_settings()
        if not settings.bert_enabled:
            if not self._loaded:
                logger.info(
                    "BERT desactivado por config (bert_enabled=false). "
                    "El sistema funciona sin voto BERT."
                )
            self._loaded = False
            return

        if self._loaded:
            return

        # ── Intento 1: modelo fine-tuneado local ──
        if self.model_dir.exists():
            self._using_fallback = False
            if self._load_from_dir(self.model_dir):
                return

        # ── Intento 2: fine-tuneado desde HuggingFace Hub ──
        settings = get_settings()
        hf_token = settings.huggingface_token
        hf_model_id = settings.huggingface_model_id
        if hf_token and hf_model_id:
            logger.info(
                "Modelo local no encontrado. Intentando descargar fine-tuneado "
                "desde HuggingFace Hub: %s ...",
                hf_model_id,
            )
            self._using_fallback = False  # Sigue siendo fine-tuneado
            if self._load_from_hf_hub(hf_model_id, hf_token):
                return

        # ── Intento 3: DistilBERT base desde HuggingFace (fallback clasico) ──
        logger.warning(
            "Modelo fine-tuneado no disponible. "
            "Descargando DistilBERT base desde HuggingFace como ultimo fallback..."
        )
        self._using_fallback = True
        if self._load_from_hf_base():
            return

        # Si llegamos aqui, todo fallo
        logger.error(
            "BERT no disponible: ni modelo local, ni HuggingFace Hub, "
            "ni fallback base. El sistema funcionara sin voto BERT."
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

    def _load_from_hf_hub(self, model_id: str, token: str) -> bool:
        """
        Descarga y carga el modelo fine-tuneado desde HuggingFace Hub.

        Args:
            model_id: ID del repo en HF (ej: 'AlexSV97/beexpand-bert-crm')
            token: Token de acceso a HuggingFace (lectura basta)
        """
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info("Descargando modelo fine-tuneado desde HuggingFace Hub (%s)...", model_id)
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_id,
                token=token,
            )
            self.model.eval()
            self._loaded = True
            logger.info(
                "Modelo BERT fine-tuneado cargado desde HuggingFace Hub correctamente"
            )
            return True
        except Exception as e:
            logger.error("Error descargando modelo desde HuggingFace Hub: %s", e)
            self._loaded = False
            return False

    def _load_from_hf_base(self) -> bool:
        """Descarga y carga DistilBERT base desde HuggingFace como ultimo fallback."""
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
            model_source = self._resolve_model_source()

            logger.info(
                "BERT voto: %s -> %s (%.0f%%) en %.0fms [%s]",
                subject[:50] if subject else "",
                category,
                confidence_score * 100,
                elapsed,
                model_source,
            )

            return ClassifierVote(
                agent_name=self.agent_name,
                category=category,
                confidence=confidence_score,
                reason=f"distilBERT [{model_source}]: "
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

    def _resolve_model_source(self) -> str:
        """Resuelve una etiqueta legible del origen del modelo."""
        if not self._loaded:
            return "none"
        if self._using_fallback:
            return "fallback-base-hf"
        # Es fine-tuneado — determinar si local o hub
        settings = get_settings()
        if settings.huggingface_token and not self.model_dir.exists():
            return "fine-tuned-hub"
        return "fine-tuned-local"

    @property
    def is_available(self) -> bool:
        """Verifica si el modelo esta disponible sin cargarlo."""
        return self.model_dir.exists() and (self.model_dir / "config.json").exists()
