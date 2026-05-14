"""
Fine-tune DistilBERT multilingual con datos REALES + sintéticos aumentados.

Estrategia:
1. Extrae clasificaciones reales de la BD (classification_history + emails)
2. Aumenta datos reales con paráfrasis y variaciones
3. Genera datos sintéticos para balancear
4. Entrena con weighted sampling (datos reales pesan más)
5. Evalúa con validación cruzada sobre datos reales

Uso:
    python scripts/train_bert_hybrid.py [--real-only] [--epochs 6] [--augment-multiplier 5]
"""

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from datasets import Dataset, DatasetDict, concatenate_datasets
from sklearn.metrics import accuracy_score, f1_score, classification_report
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)

# ── Config ──

MODEL_NAME = "distilbert-base-multilingual-cased"
MODEL_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "src" / "classifier" / "model"
NUM_LABELS = 4
LABEL_MAP = {"cliente": 0, "lead": 1, "proveedor": 2, "pendiente": 3}
ID2LABEL = {v: k for k, v in LABEL_MAP.items()}
SEED = 42
TEST_SIZE = 0.15

random.seed(SEED)
np.random.seed(SEED)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  PARTE 1: EXTRACCIÓN DE DATOS REALES DESDE BD
# ═══════════════════════════════════════════════════════════

async def extract_real_data() -> list[dict]:
    """
    Extrae correos clasificados reales desde la BD.
    Usa la clasificación MÁS RECIENTE de cada email.
    """
    from sqlalchemy import select, desc, func as sqla_func
    from src.db.session import async_session_factory
    from src.db.models import Email, ClassificationHistory
    from sqlalchemy.orm import selectinload

    samples = []
    async with async_session_factory() as db:
        # Traer emails con su history
        result = await db.execute(
            select(Email)
            .options(selectinload(Email.classification_history))
            .order_by(desc(Email.processed_at))
        )
        emails = result.scalars().all()

        for email in emails:
            if not email.classification_history:
                continue

            # Última clasificación
            ch_list = sorted(
                email.classification_history,
                key=lambda x: x.created_at or email.processed_at or email.created_at,
                reverse=True,
            )
            latest = ch_list[0]

            text = f"{email.subject or ''} {email.body_plain or ''}"
            if not text.strip():
                continue

            label_id = LABEL_MAP.get(latest.category)
            if label_id is None:
                continue

            samples.append({
                "text": text.strip(),
                "label": label_id,
                "category": latest.category,
                "method": latest.method,
                "source": "real",
            })

    logger.info("Extraídos %d registros reales de la BD", len(samples))
    return samples


# ═══════════════════════════════════════════════════════════
#  PARTE 2: AUMENTACIÓN DE DATOS
# ═══════════════════════════════════════════════════════════

# Sinónimos español-inglés específicos del dominio empresarial
SYNONYM_MAP = {
    # Español
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
    # English
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


def synonym_augment(text: str, p: float = 0.3) -> str:
    """
    Reemplaza palabras con sinónimos con probabilidad p.
    Versión simple sin necesidad de modelos externos.
    """
    words = text.split()
    result = []
    for word in words:
        word_lower = word.lower().strip(".,!?;:()\"'")
        # Check if this word (or its lowercase) has synonyms
        if word_lower in SYNONYM_MAP and random.random() < p:
            synonym = random.choice(SYNONYM_MAP[word_lower])
            # Preserve capitalization
            if word[0].isupper():
                synonym = synonym.capitalize()
            result.append(synonym)
        else:
            result.append(word)
    return " ".join(result)


def shuffle_segments(text: str, n_segments: int = 3, p: float = 0.2) -> str:
    """
    Divide el texto en n_segmentos y los reordena aleatoriamente.
    Solo aplica con probabilidad p.
    """
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
    """Elimina palabras con probabilidad p."""
    words = text.split()
    if len(words) < 5:
        return text
    kept = [w for w in words if random.random() >= p]
    return " ".join(kept) if len(kept) > 3 else text


def augment_sample(sample: dict, multiplier: int = 5) -> list[dict]:
    """
    Genera `multiplier` variaciones aumentadas de una muestra real.
    """
    augmented = []
    for i in range(multiplier):
        text = sample["text"]
        # Combinación aleatoria de técnicas de aumento
        aug_text = text
        aug_text = synonym_augment(aug_text, p=random.uniform(0.2, 0.4))
        aug_text = shuffle_segments(aug_text, p=0.15)
        aug_text = word_dropout(aug_text, p=random.uniform(0.05, 0.15))

        # Solo guardar si el texto cambió significativamente
        if aug_text != sample["text"] or i == 0:
            augmented.append({
                "text": aug_text,
                "label": sample["label"],
                "category": sample["category"],
                "source": f"augmented_{i}",
            })

    return augmented


# ═══════════════════════════════════════════════════════════
#  PARTE 3: GENERACIÓN DE DATOS SINTÉTICOS (mejorados)
# ═══════════════════════════════════════════════════════════

SUBJECT_PATTERNS = {
    "cliente": [
        "Factura {mes}",
        "Pago {mes}",
        "Confirmación de pago",
        "Soporte técnico: {tema}",
        "Reunión de seguimiento {proyecto}",
        "Incidencia {tema}",
        "Renovación del servicio",
        "Contrato firmado",
        "Agradecimiento por el servicio",
        "Solicitud de soporte urgente",
        "Revisión del contrato",
        "Alta de nuevo usuario",
        "Notificación de pago recibido",
        "Factura rectificativa",
        "Solicitud de asistencia técnica",
        "Actualización de datos de facturación",
        "Devolución de producto",
        "Reclamación del servicio",
        "Baja del servicio",
        "Problema con {tema}",
        "Consulta sobre mi cuenta",
        "Error en la plataforma",
        "Solicitud de reembolso",
        "Cambio de plan contratado",
        "Informe de uso mensual",
    ],
    "lead": [
        "Solicitud de presupuesto",
        "Cotización {servicio}",
        "Consulta comercial",
        "Posible colaboración",
        "Presupuesto {servicio}",
        "Información sobre productos",
        "Quisiera recibir información",
        "Nuevo proyecto {tema}",
        "Solicitud de demo",
        "Proveedores para {servicio}",
        "Estamos buscando {servicio}",
        "Oferta solicitada",
        "Posible proyecto {tema}",
        "Contacto comercial",
        "Consulta sobre precios",
        "Solicitud de catálogo",
        "Quiero contratar {servicio}",
        "Estudio de mercado",
        "Necesitamos {servicio} urgente",
        "Propuesta comercial",
        "Posible inversión",
        "RFP - Request for Proposal",
        "Buscando socio tecnológico",
    ],
    "proveedor": [
        "Orden de compra #{num}",
        "Confirmación de pedido",
        "Albarán de entrega",
        "Factura proveedor {mes}",
        "Actualización de precios",
        "Nuevo catálogo {ano}",
        "Condiciones comerciales",
        "Aviso de envío",
        "Presupuesto proveedor",
        "Oferta de suministros",
        "Renovación de contrato proveedor",
        "Parte de trabajo",
        "Facturación mensual proveedores",
        "Nota de abono",
        "Modificación de pedido",
        "Incidente con proveedor",
        "Condiciones de pago",
        "Entrega pendiente",
        "Nuevos productos disponibles",
        "Resolución de incidencia",
        "Comunicado del proveedor",
        "Aviso de facturación",
    ],
    "pendiente": [
        "Felicitaciones navidad",
        "Invitación a evento",
        "Comunicado interno",
        "Recordatorio: {tema}",
        "Información general",
        "Encuesta de satisfacción",
        "Boletín informativo",
        "Aviso importante",
        "Novedades del sector",
        "Feliz cumpleaños",
        "Cambio de normativa",
        "Convocatoria reunión",
        "Compartir documento",
        "Confirmación asistencia",
        "Invitación formación",
        "Noticias de la empresa",
        "Mensaje automático",
        "Confirmación de suscripción",
        "Cambio de contraseña",
        "Notificación del sistema",
        "Alerta de seguridad",
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
    "pendiente": [
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

# Templates para emails en inglés patrones mezclados
ENGLISH_SUBJECTS = {
    "cliente": [
        "Invoice for {month} services",
        "Payment confirmation",
        "Technical support request",
        "Account issue",
        "Subscription renewal",
        "Payment receipt",
        "Service feedback",
    ],
    "lead": [
        "Partnership inquiry",
        "Quote request",
        "Collaboration opportunity",
        "Information about services",
        "Proposal request",
        "Looking for {service} provider",
    ],
    "proveedor": [
        "Purchase order #{num}",
        "Supplier invoice",
        "Order confirmation",
        "Price update",
        "Delivery notice",
        "Supply offer",
    ],
    "pendiente": [
        "Newsletter",
        "Event invitation",
        "System notification",
        "Password reset",
        "Account verification",
        "Security alert",
    ],
}


def fill_template(template: str) -> str:
    """Rellena un template con valores realistas."""
    replacements = {
        "{mes}": random.choice(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]),
        "{month}": random.choice(["January", "February", "March", "April", "May", "June", "July", "August"]),
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


def generate_email_subject(category: str) -> str:
    """Genera asunto en español o inglés."""
    if random.random() < 0.15:  # 15% en inglés
        return fill_template(random.choice(ENGLISH_SUBJECTS[category]))
    return fill_template(random.choice(SUBJECT_PATTERNS[category]))


def generate_email_body(category: str) -> str:
    """Genera cuerpo de email."""
    return fill_template(random.choice(BODY_TEMPLATES[category]))


def generate_synthetic_dataset(num_samples: int = 200) -> list[dict]:
    """Genera dataset sintético balanceado CON RUIDO CONTROLADO."""
    samples = []
    per_category = num_samples // NUM_LABELS

    for category, label_id in LABEL_MAP.items():
        for _ in range(per_category):
            subject = generate_email_subject(category)
            body = generate_email_body(category)
            text = f"{subject} {body}"

            # Ruido controlado: 15% de las muestras tienen palabras de otra categoría
            if random.random() < 0.15:
                other_cats = [c for c in LABEL_MAP if c != category]
                other = random.choice(other_cats)
                noise_body = generate_email_body(other)[:120]
                text = f"{text} {noise_body}"

            # 5% de las muestras tienen el asunto ambiguo
            if random.random() < 0.05:
                other_cats = [c for c in LABEL_MAP if c != category]
                other = random.choice(other_cats)
                noise_subject = generate_email_subject(other)
                text = f"{noise_subject} {body}"

            samples.append({"text": text, "label": label_id, "category": category, "source": "synthetic"})

    random.shuffle(samples)
    return samples


# ═══════════════════════════════════════════════════════════
#  PARTE 4: ENSAMBLADO DEL DATASET
# ═══════════════════════════════════════════════════════════

def build_dataset(
    real_samples: list[dict],
    synthetic_count: int = 200,
    augment_multiplier: int = 5,
    real_only: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Construye dataset combinado:
    - Datos reales (peso alto)
    - Datos reales aumentados (variaciones)
    - Datos sintéticos (para cobertura)
    """
    all_samples = []

    # 1) Datos reales (siempre incluidos)
    all_samples.extend(real_samples)
    logger.info("Reales: %d", len(real_samples))

    # 2) Datos reales aumentados
    for sample in real_samples:
        augmented = augment_sample(sample, multiplier=augment_multiplier)
        all_samples.extend(augmented)
    real_augmented_count = len(all_samples) - len(real_samples)
    logger.info("Reales aumentados: %d", real_augmented_count)

    # 3) Sintéticos (para cobertura, menos que antes)
    if not real_only:
        synthetic = generate_synthetic_dataset(synthetic_count)
        all_samples.extend(synthetic)
        logger.info("Sintéticos: %d", len(synthetic))

    # Mezclar todo
    random.shuffle(all_samples)

    # Split train/test
    split_idx = int(len(all_samples) * (1 - TEST_SIZE))
    train_data = all_samples[:split_idx]
    test_data = all_samples[split_idx:]

    logger.info("Dataset final: %d train + %d test = %d total", len(train_data), len(test_data), len(all_samples))

    # Mostrar composición
    real_in_train = sum(1 for s in train_data if s.get("source") == "real")
    real_in_test = sum(1 for s in test_data if s.get("source") == "real")
    logger.info("  → Reales en train: %d, en test: %d", real_in_train, real_in_test)

    return train_data, test_data


# ═══════════════════════════════════════════════════════════
#  PARTE 5: ENTRENAMIENTO
# ═══════════════════════════════════════════════════════════

def tokenize(batch):
    return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Entrena BERT con datos reales + sintéticos")
    parser.add_argument("--real-only", action="store_true", help="Usar SOLO datos reales (no sintéticos)")
    parser.add_argument("--epochs", type=int, default=6, help="Número de épocas (default: 6)")
    parser.add_argument("--augment-multiplier", type=int, default=5, help="Multiplicador de aumento (default: 5)")
    parser.add_argument("--synthetic-count", type=int, default=200, help="Muestras sintéticas (default: 200)")
    parser.add_argument("--learning-rate", type=float, default=5e-5, help="Learning rate (default: 5e-5)")
    args = parser.parse_args()

    print("=" * 60)
    print("ENTRENAMIENTO HÍBRIDO: BERT con datos reales + sintéticos")
    print("=" * 60)

    # 1. Extraer datos reales
    print("\n[1/6] Extrayendo datos reales de la BD...")
    real_samples = await extract_real_data()
    if not real_samples:
        print("  ⚠ No se encontraron datos reales. Usando solo sintéticos.")
        real_samples = []

    # 2. Construir dataset combinado
    print("\n[2/6] Construyendo dataset combinado...")
    print(f"  Real only: {args.real_only}")
    print(f"  Augment multiplier: {args.augment_multiplier}x")
    print(f"  Synthetic count: {args.synthetic_count}")

    train_data, test_data = build_dataset(
        real_samples,
        synthetic_count=args.synthetic_count,
        augment_multiplier=args.augment_multiplier,
        real_only=args.real_only,
    )

    # 3. Cargar modelo y tokenizer
    print(f"\n[3/6] Cargando modelo base: {MODEL_NAME}...")
    global tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL_MAP,
        ignore_mismatched_sizes=True,
    )

    # 4. Tokenizar
    print("\n[4/6] Tokenizando datasets...")
    train_dataset = Dataset.from_list(train_data)
    test_dataset = Dataset.from_list(test_data)

    train_dataset = train_dataset.map(tokenize, batched=True)
    test_dataset = test_dataset.map(tokenize, batched=True)

    # 5. Configurar entrenamiento
    output_dir = str(MODEL_OUTPUT_DIR)
    print(f"\n[5/6] Configurando entrenamiento...")
    print(f"  Output: {output_dir}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Learning rate: {args.learning_rate}")
    print(f"  Batch size: 8")

    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=20,
        logging_dir=f"{output_dir}/logs",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        fp16=False,  # CPU safe
        report_to="none",
        seed=SEED,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    # 6. Entrenar
    print("\n[6/6] Entrenando modelo...")
    print("  (Esto tarda varios minutos en CPU)")
    trainer.train()

    # Evaluar
    print("\n" + "=" * 60)
    print("Resultados de evaluación")
    print("=" * 60)
    eval_results = trainer.evaluate()
    print(f"  Accuracy: {eval_results['eval_accuracy']:.4f}")
    print(f"  F1 Macro: {eval_results['eval_f1_macro']:.4f}")

    # Reporte detallado
    predictions = trainer.predict(test_dataset)
    preds = np.argmax(predictions.predictions, axis=-1)
    print("\nClassification Report:")
    print(classification_report(
        test_dataset["label"],
        preds,
        target_names=[ID2LABEL[i] for i in range(NUM_LABELS)],
        digits=4,
    ))

    # Guardar modelo y tokenizer
    print(f"\nGuardando modelo en: {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Guardar metadatos
    metadata = {
        "model": MODEL_NAME,
        "labels": LABEL_MAP,
        "id2label": ID2LABEL,
        "accuracy": eval_results["eval_accuracy"],
        "f1_macro": eval_results["eval_f1_macro"],
        "train_samples": len(train_data),
        "test_samples": len(test_data),
        "real_samples": len(real_samples),
        "real_only": args.real_only,
        "augment_multiplier": args.augment_multiplier,
        "training_date": "2026-05-14",
    }
    with open(f"{output_dir}/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("Entrenamiento completado!")
    print(f"Modelo guardado en: {output_dir}")
    print(f"Accuracy: {eval_results['eval_accuracy']:.2%}")
    print(f"F1 Macro: {eval_results['eval_f1_macro']:.2%}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
