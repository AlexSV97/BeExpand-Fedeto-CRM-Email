"""
Fine-tune DistilBERT multilingual para clasificar correos en:
- cliente
- lead
- proveedor
- pendiente

Genera datos sintéticos basados en reglas de negocio + variaciones realistas,
entrena el modelo, y lo guarda en backend/src/classifier/model/.
"""

import json
import os
import random
import sys
from pathlib import Path

# Añadir backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from datasets import Dataset, DatasetDict
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


# ── Generación de datos sintéticos ──

# Patrones de asunto por categoría
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
        "Cambio en la configuración",
        "Notificación de pago recibido",
        "Factura rectificativa",
        "Solicitud de asistencia técnica",
        "Actualización de datos de facturación",
        "Devolución de producto",
        "Reclamación del servicio",
        "Baja del servicio",
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
        "Webinar informativo",
        "Solicitud de catálogo",
        "Quiero contratar {servicio}",
        "Estudio de mercado",
        "Necesitamos {servicio} urgente",
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
    ],
}

# Palabras clave y frases de cuerpo por categoría
BODY_TEMPLATES = {
    "cliente": [
        "Adjunto la factura correspondiente a {mes}. El importe total es de {importe} EUR. Rogamos procedan al pago en los próximos días.",
        "Buenos días, necesitamos soporte técnico urgente porque {tema}. Por favor, contacten con nosotros lo antes posible.",
        "Confirmamos la reunión del próximo {dia} a las {hora} para revisar el estado del {proyecto}. Por favor, confirmen asistencia.",
        "Quedamos a la espera de la resolución de la incidencia {num}. Llevamos {dias} días sin solución y esto está afectando a nuestra operativa.",
        "Les informamos que hemos realizado el pago de la factura {num} por importe de {importe} EUR. Adjuntamos justificante.",
        "Solicitamos la renovación del servicio contratado. Estamos muy satisfechos con el servicio recibido hasta ahora.",
        "Escribo para reportar un error en {tema}. No funciona correctamente desde ayer. Agradeceríamos una solución urgente.",
        "Por medio de la presente, les comunico que hemos aprobado el presupuesto. Pueden proceder con los trabajos acordados.",
    ],
    "lead": [
        "Estamos interesados en recibir un presupuesto detallado para {servicio}. Por favor, indíquennos plazos y condiciones.",
        "Buenos días, me gustaría solicitar información sobre sus servicios de {servicio}. Quedamos a la espera de su respuesta.",
        "Somos una empresa del sector y estamos buscando un proveedor de {servicio} para un nuevo proyecto. ¿Podrían enviarnos información?",
        "Estimados, quisiera una cotización para {servicio}. Necesitamos saber precios, plazos de entrega y formas de pago.",
        "Hola, estoy explorando opciones para {servicio} y me gustaría saber si ofrecen este servicio. ¿Podrían darme más detalles?",
        "Buenos días, nos gustaría concertar una reunión para explorar posibles vías de colaboración en {servicio}.",
        "Estamos desarrollando un proyecto de {tema} y creemos que su empresa podría ser el partner ideal. ¿Podemos hablar?",
    ],
    "proveedor": [
        "Confirmamos el pedido de materiales según lo acordado. Nº de pedido: {num}. Por favor, confirmen fecha de entrega.",
        "Adjuntamos la orden de compra {num} con los materiales solicitados. Rogamos sirvan a la mayor brevedad posible.",
        "Les comunicamos nuestra nueva tarifa de precios para {ano}. Los incrementos son los siguientes: {detalles}",
        "Buenos días, les informamos del envío de la mercancía solicitada. Nº de albarán: {num}. Fecha prevista de entrega: {fecha}.",
        "Les remitimos nuestra factura {num} correspondiente a los trabajos realizados en {mes}. Importe: {importe} EUR.",
        "Les informamos de una incidencia con el pedido {num}: {tema}. Estamos trabajando para resolverlo a la mayor brevedad.",
        "Actualizamos nuestras condiciones comerciales para {ano}. Los nuevos precios entrarán en vigor el {fecha}.",
    ],
    "pendiente": [
        "Gracias por su confianza durante este año. Les deseamos unas felices fiestas y un próspero año nuevo.",
        "Le invitamos al evento anual del sector que tendrá lugar el {fecha}. Confirmar asistencia antes del {fecha_limite}.",
        "Les recordamos que el plazo de presentación de {tema} finaliza el {fecha}. Rogamos no dejen para última hora.",
        "Adjuntamos la circular informativa con las últimas novedades del sector. Un saludo cordial.",
        "Nos encantaría conocer su opinión sobre nuestros servicios. La encuesta solo le llevará 5 minutos.",
        "Compartimos con ustedes el informe trimestral del departamento. Cualquier duda, no duden en contactarnos.",
        "Les convocamos a la reunión trimestral del {dia} a las {hora} en la sala {sala}. Orden del día adjunto.",
    ],
}


def fill_template(template: str) -> str:
    """Rellena un template con valores realistas."""
    replacements = {
        "{mes}": random.choice(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]),
        "{ano}": str(random.randint(2025, 2026)),
        "{importe}": str(random.randint(50, 15000)),
        "{tema}": random.choice(["el servidor", "la aplicación", "la base de datos", "el sistema", "la conexión", "el software", "el portal", "la plataforma"]),
        "{proyecto}": random.choice(["web corporativa", "app móvil", "CRM", "ERP", "intranet", "e-commerce", "plataforma cloud", "sistema interno"]),
        "{servicio}": random.choice(["consultoría", "desarrollo web", "marketing digital", "soporte técnico", "cloud computing", "ciberseguridad", "formación", "auditoría"]),
        "{num}": str(random.randint(1000, 99999)),
        "{dia}": random.choice(["lunes", "martes", "miércoles", "jueves", "viernes", "lunes 15", "miércoles 20"]),
        "{fecha}": f"{random.randint(1, 28)} de {random.choice(['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio'])} de 2026",
        "{fecha_limite}": f"{random.randint(1, 28)} de {random.choice(['enero', 'febrero', 'marzo'])} de 2026",
        "{hora}": f"{random.randint(9, 17)}:{random.choice(['00', '30'])}",
        "{dias}": str(random.randint(2, 30)),
        "{sala}": random.choice(["A", "B", "C", "principal", "multiusos"]),
        "{detalles}": random.choice(["3% en materiales, 2% en mano de obra", "subida general del 4%", "precios congelados otro año"]),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def generate_email_subject(category: str) -> str:
    return fill_template(random.choice(SUBJECT_PATTERNS[category]))


def generate_email_body(category: str) -> str:
    return fill_template(random.choice(BODY_TEMPLATES[category]))


def generate_dataset(num_samples: int = 400) -> list[dict]:
    """Genera dataset sintético balanceado."""
    samples = []
    per_category = num_samples // NUM_LABELS

    for category, label_id in LABEL_MAP.items():
        for _ in range(per_category):
            subject = generate_email_subject(category)
            body = generate_email_body(category)
            text = f"{subject} {body}"

            # Añadir variación: a veces mezclar palabras de otra categoría (ruido controlado)
            if random.random() < 0.1:
                other_cats = [c for c in LABEL_MAP if c != category]
                other = random.choice(other_cats)
                noise = generate_email_body(other)[:100]
                text = f"{text} {noise}"

            samples.append({"text": text, "label": label_id, "category": category})

    # Mezclar
    random.shuffle(samples)
    return samples


# ── Entrenamiento ──


def tokenize(batch):
    return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Fase 2: Fine-tune DistilBERT para clasificación de correos")
    print("=" * 60)

    # 1. Generar datos
    print("\n[1/5] Generando datos sintéticos...")
    data = generate_dataset(400)

    # Split train/test
    split_idx = int(len(data) * (1 - TEST_SIZE))
    train_data = data[:split_idx]
    test_data = data[split_idx:]

    print(f"  Train: {len(train_data)} muestras")
    print(f"  Test:  {len(test_data)} muestras")
    print(f"  Categorías: {LABEL_MAP}")

    # 2. Cargar tokenizer y modelo
    print(f"\n[2/5] Cargando modelo base: {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL_MAP,
        ignore_mismatched_sizes=True,
    )

    # 3. Preparar datasets
    print("\n[3/5] Tokenizando datasets...")
    train_dataset = Dataset.from_list(train_data)
    test_dataset = Dataset.from_list(test_data)

    train_dataset = train_dataset.map(tokenize, batched=True)
    test_dataset = test_dataset.map(tokenize, batched=True)

    # 4. Configurar entrenamiento
    output_dir = str(MODEL_OUTPUT_DIR)
    print(f"\n[4/5] Configurando entrenamiento...")
    print(f"  Output: {output_dir}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        learning_rate=3e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=4,
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

    # 5. Entrenar
    print("\n[5/5] Entrenando modelo...")
    print("  (Esto tarda unos minutos en CPU)")
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
    }
    with open(f"{output_dir}/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("Fase 2 completada!")
    print(f"Modelo guardado en: {output_dir}")
    print(f"Accuracy: {eval_results['eval_accuracy']:.2%}")
    print(f"F1 Macro: {eval_results['eval_f1_macro']:.2%}")
    print(f"{'=' * 60}")
