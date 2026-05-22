"""
Pipeline de re-entrenamiento de BERT integrado con la API.

Extrae datos de la BD (priorizando revisiones manuales),
construye dataset combinado (reales + aumentados + sintéticos),
entrena DistilBERT y guarda el modelo.

Uso desde API:
    POST /api/v1/classification-history/retrain

Uso standalone:
    from src.training.pipeline import retrain_from_db
    metrics = await retrain_from_db()
"""

import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from datasets import Dataset
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from src.config import get_settings

logger = logging.getLogger(__name__)

# ── Config ──

MODEL_NAME = "distilbert-base-multilingual-cased"
_MODEL_OUTPUT_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "classifier" / "model"
MODEL_OUTPUT_DIR = Path(
    get_settings().bert_model_path
) if get_settings().bert_model_path else _MODEL_OUTPUT_DIR_DEFAULT
NUM_LABELS = 4
LABEL_MAP = {"cliente": 0, "lead": 1, "proveedor": 2, "nulo": 3}
ID2LABEL = {v: k for k, v in LABEL_MAP.items()}
SEED = 42
TEST_SIZE = 0.15

random.seed(SEED)
np.random.seed(SEED)

# Sinónimos para aumentación
SYNONYM_MAP = {
    "factura": ["factura", "recibo", "boleta", "comprobante", "cuenta"],
    "pago": ["pago", "abono", "transferencia", "depósito", "cancelación"],
    "presupuesto": ["presupuesto", "cotización", "estimación", "proforma", "valoración"],
    "soporte": ["soporte", "asistencia", "ayuda", "apoyo", "atención"],
    "reunión": ["reunión", "encuentro", "junta", "sesión", "cita"],
    "proveedor": ["proveedor", "vendedor", "suministrador", "contratista"],
    "pedido": ["pedido", "orden", "solicitud", "requerimiento", "encargo"],
    "consulta": ["consulta", "pregunta", "solicitud", "indagación"],
    "contrato": ["contrato", "acuerdo", "convenio", "pacto"],
    "urgente": ["urgente", "prioritario", "inmediato", "apremiante"],
    "cliente": ["cliente", "usuario", "consumidor"],
    "servicio": ["servicio", "prestación", "asistencia", "atención"],
    "colaboración": ["colaboración", "cooperación", "asociación", "coordinación"],
    "materiales": ["materiales", "insumos", "suministros", "recursos"],
    "precio": ["precio", "tarifa", "costo", "importe", "valor"],
    "invoice": ["invoice", "bill", "receipt", "statement"],
    "payment": ["payment", "deposit", "transfer", "settlement"],
    "support": ["support", "assistance", "help", "aid"],
    "meeting": ["meeting", "appointment", "session", "gathering"],
    "supplier": ["supplier", "vendor", "provider", "contractor"],
    "purchase": ["purchase", "order", "acquisition", "buy"],
    "budget": ["budget", "quote", "estimate", "proposal"],
    "quote": ["quote", "quotation", "estimate", "price"],
    "urgent": ["urgent", "critical", "immediate", "pressing"],
    "collaboration": ["collaboration", "partnership", "cooperation", "alliance"],
    "partnership": ["partnership", "alliance", "joint venture", "collaboration"],
    "problem": ["problem", "issue", "incident", "trouble", "error"],
    "help": ["help", "assistance", "support", "aid"],
}


# ═══════════════════════════════════════════════════
#  EXTRACCIÓN DE DATOS (prioriza revisiones manuales)
# ═══════════════════════════════════════════════════


def _get_label_id(category: str) -> int | None:
    """Convierte categoría a label_id, o None si es inválida."""
    return LABEL_MAP.get(category)


def _email_to_text(email) -> str:
    """Concatena asunto + cuerpo del email."""
    text = f"{email.subject or ''} {email.body_plain or ''}"
    return text.strip()


def _best_classification(history_list: list) -> tuple | None:
    """
    Retorna la mejor clasificación de un email.
    
    Prioriza:
    1. Revisiones manuales (method='manual_review') — son ground truth
    2. Clasificación más reciente (cualquier método)
    
    Retorna (category, method, confidence, created_at) o None.
    """
    if not history_list:
        return None

    # Buscar revisión manual primero
    for ch in history_list:
        if ch.method == "manual_review":
            return (ch.category, ch.method, ch.confidence, ch.created_at)

    # Si no hay revisión manual, la más reciente
    latest = max(history_list, key=lambda x: x.created_at or x.id)
    return (latest.category, latest.method, latest.confidence, latest.created_at)


async def extract_training_data(
    db: AsyncSession,
) -> list[dict]:
    """
    Extrae datos de entrenamiento desde la BD.
    
    Para cada email:
    1. Si tiene revisión manual → esa es la etiqueta (ground truth)
    2. Si no → la clasificación más reciente
    
    Retorna lista de dicts con: text, label, category, method, source
    """
    from src.db.models import ClassificationHistory, Email

    samples = []

    result = await db.execute(
        select(Email)
        .options(selectinload(Email.classification_history))
        .order_by(desc(Email.processed_at))
    )
    emails = result.scalars().all()

    for email in emails:
        if not email.classification_history:
            continue

        text = _email_to_text(email)
        if not text:
            continue

        best = _best_classification(email.classification_history)
        if best is None:
            continue

        category, method, confidence, _ = best
        label_id = _get_label_id(category)
        if label_id is None:
            continue

        samples.append({
            "text": text,
            "label": label_id,
            "category": category,
            "method": method,
            "source": "manual_review" if method == "manual_review" else "real",
            "manual_weight": 5.0 if method == "manual_review" else 1.0,
        })

    logger.info("Extraídos %d registros reales de la BD", len(samples))
    manual_count = sum(1 for s in samples if s["source"] == "manual_review")
    logger.info("  → %d son revisiones manuales (ground truth)", manual_count)

    return samples


# ═══════════════════════════════════════════════════
#  AUMENTACIÓN DE DATOS
# ═══════════════════════════════════════════════════


def synonym_augment(text: str, p: float = 0.3) -> str:
    words = text.split()
    result = []
    for word in words:
        word_lower = word.lower().strip(".,!?;:()\"'")
        if word_lower in SYNONYM_MAP and random.random() < p:
            synonym = random.choice(SYNONYM_MAP[word_lower])
            if word[0].isupper():
                synonym = synonym.capitalize()
            result.append(synonym)
        else:
            result.append(word)
    return " ".join(result)


def shuffle_segments(text: str, n_segments: int = 3, p: float = 0.2) -> str:
    if random.random() >= p:
        return text
    words = text.split()
    if len(words) < 10:
        return text
    segment_size = max(1, len(words) // n_segments)
    segments = [words[i:i + segment_size] for i in range(0, len(words), segment_size)]
    random.shuffle(segments)
    return " ".join([" ".join(s) for s in segments])


def word_dropout(text: str, p: float = 0.1) -> str:
    words = text.split()
    if len(words) < 5:
        return text
    kept = [w for w in words if random.random() >= p]
    return " ".join(kept) if len(kept) > 3 else text


def augment_sample(sample: dict, multiplier: int = 5) -> list[dict]:
    augmented = []
    text = sample["text"]
    for i in range(multiplier):
        aug_text = text
        aug_text = synonym_augment(aug_text, p=random.uniform(0.2, 0.4))
        aug_text = shuffle_segments(aug_text, p=0.15)
        aug_text = word_dropout(aug_text, p=random.uniform(0.05, 0.15))
        if aug_text != text or i == 0:
            augmented.append({
                "text": aug_text,
                "label": sample["label"],
                "category": sample["category"],
                "source": f"augmented_{i}",
            })
    return augmented


# ═══════════════════════════════════════════════════
#  GENERACIÓN DE DATOS SINTÉTICOS
# ═══════════════════════════════════════════════════

SUBJECT_PATTERNS = {
    "cliente": [
        "Factura {mes}", "Pago {mes}", "Confirmación de pago",
        "Soporte técnico: {tema}", "Reunión de seguimiento {proyecto}",
        "Incidencia {tema}", "Renovación del servicio", "Contrato firmado",
        "Agradecimiento por el servicio", "Solicitud de soporte urgente",
        "Revisión del contrato", "Alta de nuevo usuario",
        "Notificación de pago recibido", "Factura rectificativa",
        "Solicitud de asistencia técnica", "Actualización de datos de facturación",
        "Devolución de producto", "Reclamación del servicio", "Baja del servicio",
        "Problema con {tema}", "Consulta sobre mi cuenta",
        "Error en la plataforma", "Solicitud de reembolso", "Cambio de plan contratado",
        "Informe de uso mensual",
    ],
    "lead": [
        "Solicitud de presupuesto", "Cotización {servicio}", "Consulta comercial",
        "Posible colaboración", "Presupuesto {servicio}", "Información sobre productos",
        "Quisiera recibir información", "Nuevo proyecto {tema}",
        "Solicitud de demo", "Proveedores para {servicio}",
        "Estamos buscando {servicio}", "Oferta solicitada",
        "Posible proyecto {tema}", "Contacto comercial",
        "Consulta sobre precios", "Solicitud de catálogo",
        "Quiero contratar {servicio}", "Estudio de mercado",
        "Necesitamos {servicio} urgente", "Propuesta comercial",
        "Posible inversión", "RFP - Request for Proposal", "Buscando socio tecnológico",
    ],
    "proveedor": [
        "Orden de compra #{num}", "Confirmación de pedido", "Albarán de entrega",
        "Factura proveedor {mes}", "Actualización de precios", "Nuevo catálogo {ano}",
        "Condiciones comerciales", "Aviso de envío", "Presupuesto proveedor",
        "Oferta de suministros", "Renovación de contrato proveedor",
        "Parte de trabajo", "Facturación mensual proveedores", "Nota de abono",
        "Modificación de pedido", "Incidente con proveedor", "Condiciones de pago",
        "Entrega pendiente", "Nuevos productos disponibles", "Resolución de incidencia",
        "Comunicado del proveedor", "Aviso de facturación",
    ],
    "nulo": [
        "Felicitaciones navidad", "Invitación a evento", "Comunicado interno",
        "Recordatorio: {tema}", "Información general", "Encuesta de satisfacción",
        "Boletín informativo", "Aviso importante", "Novedades del sector",
        "Feliz cumpleaños", "Cambio de normativa", "Convocatoria reunión",
        "Compartir documento", "Confirmación asistencia", "Invitación formación",
        "Noticias de la empresa", "Mensaje automático", "Confirmación de suscripción",
        "Cambio de contraseña", "Notificación del sistema", "Alerta de seguridad",
        "Verificación de cuenta",
    ],
}

BODY_TEMPLATES = {
    "cliente": [
        "Adjunto la factura correspondiente a {mes}. El importe total es de {importe} EUR. Rogamos procedan al pago en los próximos días.",
        "Buenos días, necesitamos soporte técnico urgente porque {tema}. Por favor, contacten con nosotros lo antes posible.",
        "Confirmamos la reunión del próximo {dia} a las {hora} para revisar el estado del {proyecto}.",
        "Quedamos a la espera de la resolución de la incidencia {num}. Llevamos {dias} días sin solución.",
        "Les informamos que hemos realizado el pago de la factura {num} por importe de {importe} EUR.",
        "Solicitamos la renovación del servicio contratado. Estamos muy satisfechos con el servicio recibido.",
        "Escribo para reportar un error en {tema}. No funciona correctamente desde ayer.",
        "Por medio de la presente, les comunico que hemos aprobado el presupuesto. Pueden proceder con los trabajos.",
        "Buenos días, quería reportar que {tema} ha estado teniendo problemas desde esta mañana. Agradecería una solución urgente.",
        "Hola, necesito ayuda con mi cuenta. No puedo acceder desde esta mañana. Gracias.",
        "Adjunto el justificante de pago correspondiente a la factura {num}. Quedo a la espera de confirmación.",
    ],
    "lead": [
        "Estamos interesados en recibir un presupuesto detallado para {servicio}. Por favor, indíquennos plazos y condiciones.",
        "Buenos días, me gustaría solicitar información sobre sus servicios de {servicio}.",
        "Somos una empresa del sector y estamos buscando un proveedor de {servicio} para un nuevo proyecto.",
        "Estimados, quisiera una cotización para {servicio}. Necesitamos saber precios, plazos y formas de pago.",
        "Hola, estoy explorando opciones para {servicio} y me gustaría saber si ofrecen este servicio.",
        "Nos gustaría concertar una reunión para explorar posibles vías de colaboración en {servicio}.",
        "Estamos desarrollando un proyecto de {tema} y creemos que su empresa podría ser el partner ideal.",
        "Buenos días, quisiera información sobre los precios de sus servicios de {servicio} para evaluar una posible contratación.",
        "Estamos buscando un proveedor de confianza para {servicio}. ¿Podrían enviarnos una propuesta?",
    ],
    "proveedor": [
        "Confirmamos el pedido de materiales según lo acordado. Nº de pedido: {num}.",
        "Adjuntamos la orden de compra {num} con los materiales solicitados.",
        "Les comunicamos nuestra nueva tarifa de precios para {ano}. Los incrementos son los siguientes: {detalles}",
        "Buenos días, les informamos del envío de la mercancía solicitada. Nº de albarán: {num}.",
        "Les remitimos nuestra factura {num} correspondiente a los trabajos realizados en {mes}. Importe: {importe} EUR.",
        "Les informamos de una incidencia con el pedido {num}: {tema}. Estamos trabajando para resolverlo.",
        "Actualizamos nuestras condiciones comerciales para {ano}. Los nuevos precios entrarán en vigor el {fecha}.",
        "Buenos días, adjuntamos la factura del mes de {mes} por los suministros entregados. Importe total: {importe} EUR.",
        "Les recordamos que el pedido {num} está pendiente de pago. Por favor, regularicen la situación a la mayor brevedad.",
    ],
    "nulo": [
        "Gracias por su confianza durante este año. Les deseamos unas felices fiestas y un próspero año nuevo.",
        "Le invitamos al evento anual del sector que tendrá lugar el {fecha}.",
        "Les recordamos que el plazo de presentación de {tema} finaliza el {fecha}.",
        "Adjuntamos la circular informativa con las últimas novedades del sector. Un saludo cordial.",
        "Nos encantaría conocer su opinión sobre nuestros servicios. La encuesta solo le llevará 5 minutos.",
        "Compartimos con ustedes el informe trimestral del departamento.",
        "Les convocamos a la reunión trimestral del {dia} a las {hora} en la sala {sala}.",
        "Este es un mensaje automático de confirmación. No responda a este correo.",
        "Se ha registrado un inicio de sesión en su cuenta desde un nuevo dispositivo.",
        "Alerta de seguridad: se ha creado una contraseña de aplicación para su cuenta.",
    ],
}


def fill_template(template: str) -> str:
    replacements = {
        "{mes}": random.choice(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]),
        "{ano}": str(random.randint(2024, 2026)),
        "{importe}": str(random.randint(50, 25000)),
        "{tema}": random.choice(["el servidor", "la aplicación", "la base de datos", "el sistema", "la conexión", "el software", "el portal", "la plataforma", "el módulo de facturación", "el panel de control"]),
        "{proyecto}": random.choice(["web corporativa", "app móvil", "CRM", "ERP", "intranet", "e-commerce", "plataforma cloud", "sistema interno", "portal del cliente"]),
        "{servicio}": random.choice(["consultoría", "desarrollo web", "marketing digital", "soporte técnico", "cloud computing", "ciberseguridad", "formación", "auditoría", "desarrollo a medida", "integración de sistemas"]),
        "{num}": str(random.randint(1000, 99999)),
        "{dia}": random.choice(["lunes", "martes", "miércoles", "jueves", "viernes", "lunes 15", "miércoles 20", "viernes 5"]),
        "{fecha}": f"{random.randint(1, 28)} de {random.choice(['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre'])} de 2026",
        "{hora}": f"{random.randint(9, 18)}:{random.choice(['00', '15', '30', '45'])}",
        "{dias}": str(random.randint(1, 30)),
        "{sala}": random.choice(["A", "B", "C", "principal", "multiusos", "sala de juntas"]),
        "{detalles}": random.choice(["3% en materiales, 2% en mano de obra", "subida general del 4%", "precios congelados otro año", "incremento selectivo del 5% en algunos productos"]),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def generate_synthetic_dataset(num_samples: int = 200) -> list[dict]:
    samples = []
    per_category = num_samples // NUM_LABELS

    for category, label_id in LABEL_MAP.items():
        for _ in range(per_category):
            subject = fill_template(random.choice(SUBJECT_PATTERNS[category]))
            body = fill_template(random.choice(BODY_TEMPLATES[category]))
            text = f"{subject} {body}"

            # 15% ruido controlado: palabras de otra categoría
            if random.random() < 0.15:
                other_cats = [c for c in LABEL_MAP if c != category]
                other = random.choice(other_cats)
                noise_body = fill_template(random.choice(BODY_TEMPLATES[other]))[:120]
                text = f"{text} {noise_body}"

            samples.append({
                "text": text,
                "label": label_id,
                "category": category,
                "source": "synthetic",
            })

    random.shuffle(samples)
    return samples


# ═══════════════════════════════════════════════════
#  CONSTRUCCIÓN DEL DATASET
# ═══════════════════════════════════════════════════


def build_dataset(
    real_samples: list[dict],
    synthetic_count: int = 200,
    augment_multiplier: int = 5,
    real_only: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Construye dataset combinado:
    - Datos reales (con revisiones manuales pesando más)
    - Datos reales aumentados (variaciones)
    - Datos sintéticos (para cobertura)
    
    Las revisiones manuales se duplican intencionalmente para darles
    mayor peso en el entrenamiento (se tratan como ground truth).
    """
    all_samples = []

    # 1) Separar revisiones manuales del resto
    manual_reviews = [s for s in real_samples if s.get("source") == "manual_review"]
    other_real = [s for s in real_samples if s.get("source") != "manual_review"]

    # 2) Revisiones manuales con peso extra (duplicadas)
    for review in manual_reviews:
        for _ in range(3):  # Aparecen 3x para más peso
            all_samples.append({**review, "source": "manual_review"})

    # 3) Datos reales normales
    all_samples.extend(other_real)

    logger.info("Reales totales: %d (manuales: %d, otras: %d)",
                len(real_samples), len(manual_reviews), len(other_real))

    # 4) Datos reales aumentados
    for sample in real_samples:
        augmented = augment_sample(sample, multiplier=augment_multiplier)
        all_samples.extend(augmented)

    real_augmented_count = sum(1 for s in all_samples if s.get("source", "").startswith("augmented"))
    logger.info("Reales aumentados: %d", real_augmented_count)

    # 5) Sintéticos
    if not real_only:
        synthetic = generate_synthetic_dataset(synthetic_count)
        all_samples.extend(synthetic)
        logger.info("Sintéticos: %d", len(synthetic))

    random.shuffle(all_samples)

    # Split train/test
    split_idx = int(len(all_samples) * (1 - TEST_SIZE))
    train_data = all_samples[:split_idx]
    test_data = all_samples[split_idx:]

    logger.info("Dataset final: %d train + %d test = %d total",
                len(train_data), len(test_data), len(all_samples))

    return train_data, test_data


# ═══════════════════════════════════════════════════
#  ENTRENAMIENTO
# ═══════════════════════════════════════════════════


def _tokenize(batch, tokenizer):
    return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


async def retrain_from_db(
    db: AsyncSession,
    epochs: int = 6,
    augment_multiplier: int = 5,
    synthetic_count: int = 200,
    learning_rate: float = 5e-5,
    real_only: bool = False,
) -> dict:
    """
    Pipeline completo de re-entrenamiento: extrae datos, entrena y guarda.
    
    Args:
        db: Sesión asíncrona de BD
        epochs: Número de épocas de entrenamiento
        augment_multiplier: Multiplicador de aumento de datos
        synthetic_count: Número de muestras sintéticas a generar
        learning_rate: Tasa de aprendizaje
        real_only: Si True, solo usa datos reales (sin sintéticos)
    
    Returns:
        Dict con métricas de entrenamiento
    """
    logger.info("=" * 60)
    logger.info("RE-ENTRENAMIENTO BERT desde BD")
    logger.info("=" * 60)

    start_time = time.time()

    # 1. Extraer datos
    logger.info("[1/6] Extrayendo datos de entrenamiento...")
    real_samples = await extract_training_data(db)
    if not real_samples:
        logger.warning("No se encontraron datos reales. Usando solo sintéticos.")

    # 2. Construir dataset
    logger.info("[2/6] Construyendo dataset combinado...")
    logger.info("  Real only: %s, Augment: %dx, Synthetic: %d",
                real_only, augment_multiplier, synthetic_count)

    train_data, test_data = build_dataset(
        real_samples,
        synthetic_count=synthetic_count,
        augment_multiplier=augment_multiplier,
        real_only=real_only,
    )

    if not train_data or not test_data:
        return {
            "status": "error",
            "detail": "No hay suficientes datos para entrenar",
            "steps_completed": 2,
        }

    # 3. Cargar modelo y tokenizer
    logger.info("[3/6] Cargando modelo base: %s...", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL_MAP,
        ignore_mismatched_sizes=True,
    )

    # 4. Tokenizar
    logger.info("[4/6] Tokenizando datasets...")
    train_dataset = Dataset.from_list(train_data)
    test_dataset = Dataset.from_list(test_data)

    train_dataset = train_dataset.map(
        lambda batch: _tokenize(batch, tokenizer), batched=True
    )
    test_dataset = test_dataset.map(
        lambda batch: _tokenize(batch, tokenizer), batched=True
    )

    # 5. Configurar entrenamiento
    output_dir = str(MODEL_OUTPUT_DIR)
    logger.info("[5/6] Configurando entrenamiento...")
    logger.info("  Output: %s", output_dir)
    logger.info("  Epochs: %d", epochs)
    logger.info("  Learning rate: %s", learning_rate)

    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        learning_rate=learning_rate,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=epochs,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=20,
        logging_dir=f"{output_dir}/logs",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        fp16=False,
        report_to="none",
        seed=SEED,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        processing_class=tokenizer,
        compute_metrics=_compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    # 6. Entrenar
    logger.info("[6/6] Entrenando modelo...")
    trainer.train()

    # Evaluar
    logger.info("Evaluando modelo...")
    eval_results = trainer.evaluate()

    # Reporte detallado
    predictions = trainer.predict(test_dataset)
    preds = np.argmax(predictions.predictions, axis=-1)

    class_report = classification_report(
        test_dataset["label"],
        preds,
        target_names=[ID2LABEL[i] for i in range(NUM_LABELS)],
        digits=4,
        output_dict=True,
    )

    # Guardar modelo
    logger.info("Guardando modelo en: %s", output_dir)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Guardar metadatos
    training_time = round(time.time() - start_time, 1)
    metadata = {
        "model": MODEL_NAME,
        "labels": LABEL_MAP,
        "id2label": ID2LABEL,
        "accuracy": eval_results["eval_accuracy"],
        "f1_macro": eval_results["eval_f1_macro"],
        "train_samples": len(train_data),
        "test_samples": len(test_data),
        "real_samples": len(real_samples),
        "real_only": real_only,
        "augment_multiplier": augment_multiplier,
        "training_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "training_time_seconds": training_time,
    }
    with open(f"{output_dir}/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("Entrenamiento completado en %.1f s", training_time)
    logger.info("Accuracy: %.2f%%", eval_results["eval_accuracy"] * 100)
    logger.info("F1 Macro: %.2f%%", eval_results["eval_f1_macro"] * 100)
    logger.info("=" * 60)

    return {
        "status": "success",
        "accuracy": eval_results["eval_accuracy"],
        "f1_macro": eval_results["eval_f1_macro"],
        "train_samples": len(train_data),
        "test_samples": len(test_data),
        "real_samples": len(real_samples),
        "training_time_seconds": training_time,
        "classification_report": class_report,
        "model_path": output_dir,
    }
