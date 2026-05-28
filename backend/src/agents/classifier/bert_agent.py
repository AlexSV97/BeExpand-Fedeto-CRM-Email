"""
BertClassifierAgent — sub-agente de clasificación basado en DistilBERT fine-tuned.

Vota usando ONNX Runtime (sin PyTorch, ~130MB RAM en inferencia).

Estrategia de carga (por orden de prioridad):
1. Modelo ONNX desde HuggingFace Hub (INT8, ~130MB, descarga bajo demanda)
2. Modelo ONNX local (si existe en BERT_MODEL_PATH/onnx/)
3. Si todo falla, vota con confianza 0 (el VoteResolver usa Rule + LLM)

Requiere:
- HUGGINGFACE_TOKEN en entorno (para descargar modelo privado de HF Hub)
- onnxruntime (no necesita torch)
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from src.agents.classifier.base import BaseClassifierAgent
from src.config import get_settings
from src.orchestrator.context import ClassifierVote

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "classifier" / "model"
_ONNX_SUBDIR = "onnx"
_ONNX_FILENAME = "model_int8.onnx"


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

    Usa ONNX Runtime para inferencia. El modelo fine-tuneado se descarga
    desde HuggingFace Hub en formato ONNX INT8 (~130MB, ~130ms/inferencia).
    Sin PyTorch — ahorra ~300MB de RAM respecto a la versión original.
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = _resolve_model_dir(model_dir)
        self.session: Optional["onnxruntime.InferenceSession"] = None
        self.tokenizer = None
        self.labels = {"cliente": 0, "lead": 1, "proveedor": 2, "nulo": 3}
        self.id2label = {v: k for k, v in self.labels.items()}
        self._loaded = False
        self._model_source: Optional[str] = None

    @property
    def agent_name(self) -> str:
        return "bert"

    def _ensure_loaded(self):
        """Carga el modelo ONNX bajo demanda.

        Orden:
        1. ONNX local (model_dir/onnx/model_int8.onnx)
        2. Descarga ONNX desde HuggingFace Hub (usando token)
        3. Si todo falla, vota confianza 0
        """
        if self._loaded:
            return

        # ── 1. ONNX local ──
        local_onnx = self.model_dir / _ONNX_SUBDIR / _ONNX_FILENAME
        if local_onnx.exists():
            if self._load_onnx(str(local_onnx), str(self.model_dir / _ONNX_SUBDIR)):
                self._model_source = "local-onnx"
                return

        # ── 2. Descarga desde HuggingFace Hub ──
        settings = get_settings()
        hf_token = settings.huggingface_token
        hf_model_id = settings.bert_onnx_model_id
        if hf_token and hf_model_id:
            logger.info(
                "ONNX local no encontrado. Descargando desde HuggingFace Hub: %s ...",
                hf_model_id,
            )
            if self._load_from_hf_hub(hf_model_id, hf_token):
                self._model_source = "hub-onnx"
                return

        # Si llegamos aquí, todo falló
        logger.error(
            "BERT ONNX no disponible: ni local ni HuggingFace Hub. "
            "El sistema funcionará sin voto BERT."
        )
        self._loaded = False

    def _load_onnx(self, onnx_path: str, tokenizer_dir: str) -> bool:
        """Carga modelo ONNX y tokenizador desde directorio local."""
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)
            self.session = ort.InferenceSession(
                onnx_path,
                providers=["CPUExecutionProvider"],
            )
            self._loaded = True
            onnx_mb = os.path.getsize(onnx_path) / 1048576
            logger.info(
                "BERT ONNX cargado: %.0fMB | %s",
                onnx_mb,
                onnx_path,
            )
            return True
        except Exception as e:
            logger.error("Error cargando BERT ONNX: %s", e)
            self._loaded = False
            return False

    def _load_from_hf_hub(self, model_id: str, token: str) -> bool:
        """Descarga modelo ONNX + tokenizador desde HuggingFace Hub.

        Descarga solo los archivos necesarios (model_int8.onnx + tokenizer)
        al directorio HF_HOME, sin cargar torch.
        """
        try:
            from huggingface_hub import hf_hub_download
            from transformers import AutoTokenizer

            # Directorio temporal para tokenizador (usa HF cache)
            cache_dir = os.environ.get(
                "HF_HOME",
                os.path.expanduser("~/.cache/huggingface"),
            )

            # Descargar modelo ONNX
            onnx_path = hf_hub_download(
                repo_id=model_id,
                filename=f"{_ONNX_SUBDIR}/{_ONNX_FILENAME}",
                token=token,
                cache_dir=cache_dir,
            )

            # Descargar y cargar tokenizador (desde la raíz del repo, donde están los archivos)
            # El tokenizador está en la raíz del repo HF (no en onnx/)
            tokenizer_cache = hf_hub_download(
                repo_id=model_id,
                filename="tokenizer.json",
                token=token,
                cache_dir=cache_dir,
            )
            tokenizer_dir = str(Path(tokenizer_cache).parent)
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                token=token,
                cache_dir=cache_dir,
            )

            # Cargar con ONNX Runtime
            return self._load_onnx(onnx_path, tokenizer_dir)

        except Exception as e:
            logger.error("Error descargando BERT ONNX desde HuggingFace Hub: %s", e)
            self._loaded = False
            return False

    async def classify(self, subject: str, body: str) -> ClassifierVote:
        """Clasifica usando BERT vía ONNX Runtime. Retorna un voto."""
        start = time.time()

        self._ensure_loaded()
        if not self._loaded or self.session is None or self.tokenizer is None:
            elapsed = (time.time() - start) * 1000
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason="modelo BERT ONNX no disponible - configura HUGGINGFACE_TOKEN",
                details={
                    "processing_ms": round(elapsed, 1),
                    "model_source": "none",
                },
            )

        try:
            text = f"{subject or ''} {body or ''}"[:512]

            # Tokenizar con numpy (no torch)
            inputs = self.tokenizer(
                text,
                return_tensors="np",
                padding="max_length",
                truncation=True,
                max_length=128,
            )

            # Inferencia con ONNX Runtime
            onnx_inputs = {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "attention_mask": inputs["attention_mask"].astype(np.int64),
            }
            outputs = self.session.run(None, onnx_inputs)
            logits = outputs[0]

            # Softmax con numpy
            exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
            probabilities = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

            predicted = int(np.argmax(probabilities))
            confidence_score = round(float(np.max(probabilities)), 2)
            category = self.id2label.get(predicted, "nulo")

            elapsed = (time.time() - start) * 1000

            logger.info(
                "BERT voto: %s -> %s (%.0f%%) en %.0fms [%s]",
                subject[:50] if subject else "",
                category,
                confidence_score * 100,
                elapsed,
                self._model_source or "unknown",
            )

            return ClassifierVote(
                agent_name=self.agent_name,
                category=category,
                confidence=confidence_score,
                reason=f"distilBERT [ONNX INT8, {self._model_source}]: "
                       f"{confidence_score:.0%} para '{category}'",
                details={
                    "label_id": predicted,
                    "probabilities": probabilities[0].tolist(),
                    "processing_ms": round(elapsed, 1),
                    "model_source": self._model_source or "none",
                },
            )

        except Exception as e:
            logger.error("Error en clasificación BERT ONNX: %s", e, exc_info=True)
            return ClassifierVote(
                agent_name=self.agent_name,
                category="nulo",
                confidence=0.0,
                reason=f"error BERT ONNX: {e}",
            )

    @property
    def is_available(self) -> bool:
        """Verifica si el modelo está disponible sin cargarlo."""
        local_onnx = self.model_dir / _ONNX_SUBDIR / _ONNX_FILENAME
        if local_onnx.exists():
            return True
        # Podría estar en HF Hub — asumir disponible si hay token
        return bool(get_settings().huggingface_token)
