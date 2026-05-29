"""
InvoiceAgent — extrae datos estructurados de facturas en PDF usando LLM.

Flujo:
1. Recibe ruta a un archivo PDF
2. Extrae el texto del PDF con pypdf
3. Envía el texto al LLM para extraer datos estructurados
4. Devuelve un dict con: numero, proveedor, importe, fecha, vencimiento

El LLM entiende facturas en múltiples formatos y proveedores,
lo que evita tener que programar reglas de extracción para cada uno.
"""

import json
import logging
import re
from datetime import date, datetime
from typing import Optional

from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Prompt para extracción de datos de factura
INVOICE_EXTRACT_PROMPT = """Eres un asistente especializado en extraer datos de facturas.

A continuación recibes el texto extraído de un PDF de factura.
Extrae la siguiente información y devuélvela SOLO como JSON válido, sin markdown ni etiquetas:

1. numero: Número de factura (factura nº, invoice number, Nº factura...). Si no encuentras, null.
2. proveedor: Nombre del proveedor/empresa que emite la factura. Si no encuentras, null.
3. importe: Importe TOTAL de la factura (solo el número, sin símbolos ni IVA). Si son varios importes, el total final. Número decimal con punto. Ej: 1234.50. Si no encuentras, null.
4. fecha: Fecha de la factura (fecha de emisión, invoice date). SOLO en formato YYYY-MM-DD. Si no encuentras, null.
5. vencimiento: Fecha de vencimiento (due date, fecha de pago, vence el...). SOLO en formato YYYY-MM-DD. Si no encuentras, null.
6. iva: Importe del IVA si aparece. Número decimal. Si no, null.
7. concepto: Descripción breve del concepto o servicio facturado. Si no, null.

IMPORTANTE:
- Los importes usa PUNTO como separador decimal (ej: 1250.50)
- Las fechas SOLO en formato YYYY-MM-DD
- Si un campo no aparece en la factura, pon null
- Responde ÚNICAMENTE con el JSON, sin explicaciones

Texto de la factura:
{text}

JSON:"""

# Prompt para cuando el texto del PDF es muy largo (se usa resumen)
INVOICE_SHORT_EXTRACT_PROMPT = """Extrae los datos de esta factura del texto proporcionado.
Devuelve SOLO JSON:

{{"numero": "..." o null, "proveedor": "..." o null, "importe": 1234.50 o null, "fecha": "YYYY-MM-DD" o null, "vencimiento": "YYYY-MM-DD" o null, "iva": 123.45 o null, "concepto": "..." o null}}

Usa punto como separador decimal. Fechas en YYYY-MM-DD.

Texto: {text}

JSON:"""


class InvoiceAgent:
    """Agente que extrae datos estructurados de facturas en PDF."""

    def __init__(self):
        self._client = LLMClient(use_chat_model=True, timeout=60)

    async def extract_invoice(
        self,
        pdf_path: str,
        filename: str,
        email_subject: str = "",
        sender_name: str = "",
        sender_email: str = "",
    ) -> dict | None:
        """Extrae datos estructurados de una factura PDF.

        Args:
            pdf_path: Ruta absoluta al archivo PDF.
            filename: Nombre del archivo (para logging).
            email_subject: Asunto del email asociado.
            sender_name: Nombre del remitente.
            sender_email: Email del remitente.

        Returns:
            Dict con los datos extraídos, o None si falla la extracción.
        """
        # 1. Extraer texto del PDF
        pdf_text = self._extract_pdf_text(pdf_path)
        if not pdf_text or len(pdf_text.strip()) < 10:
            logger.warning("No se pudo extraer texto del PDF: %s", filename)
            return None

        # 2. Truncar si es muy largo (el LLM tiene límite de tokens)
        max_chars = 6000
        if len(pdf_text) > max_chars:
            logger.info(
                "PDF largo (%d chars), truncando a %d: %s",
                len(pdf_text), max_chars, filename,
            )
            pdf_text = pdf_text[:max_chars]

        # 3. Llamar al LLM para extraer datos
        prompt = INVOICE_EXTRACT_PROMPT.format(text=pdf_text)
        try:
            response = await self._client.generate(
                prompt=prompt,
                temperature=0.05,  # Muy baja para extracción precisa
                max_tokens=512,
            )
        except Exception as e:
            logger.error("Error llamando al LLM para factura %s: %s", filename, e)
            return None

        # 4. Parsear la respuesta JSON
        invoice_data = self._parse_response(response)
        if not invoice_data:
            return None

        # 5. Añadir metadatos
        invoice_data["_source_filename"] = filename
        invoice_data["_source_email_subject"] = email_subject
        invoice_data["_source_sender"] = sender_email
        invoice_data["_extracted_at"] = datetime.now().isoformat()

        # 6. Validar y normalizar fechas
        self._normalize_dates(invoice_data)

        logger.info(
            "Factura extraída: %s | prov=%s | importe=%s | fecha=%s",
            invoice_data.get("numero", "?"),
            invoice_data.get("proveedor", "?"),
            invoice_data.get("importe", "?"),
            invoice_data.get("fecha", "?"),
        )

        return invoice_data

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extrae texto de un PDF usando pypdf."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n".join(text_parts)
        except ImportError:
            logger.error("pypdf no instalado. Instala: pip install pypdf")
            raise
        except Exception as e:
            logger.error("Error extrayendo texto de PDF %s: %s", pdf_path, e)
            return ""

    def _parse_response(self, response: str) -> dict | None:
        """Parsea la respuesta JSON del LLM."""
        # Intentar parsear directamente
        text = response.strip()

        # Quitar posible markdown ```json ... ``` o ``` ... ```
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        # Buscar el primer { y el último }
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end + 1]

        try:
            data = json.loads(text)
            return data
        except json.JSONDecodeError as e:
            logger.warning("Error parseando respuesta JSON del LLM: %s", e)
            logger.debug("Respuesta raw: %s", response)
            return None

    def _normalize_dates(self, data: dict):
        """Convierte fechas string a date objects donde sea posible."""
        for field in ("fecha", "vencimiento"):
            val = data.get(field)
            if val and isinstance(val, str):
                try:
                    # Ya debería venir en YYYY-MM-DD
                    parsed = date.fromisoformat(val)
                    data[field] = parsed
                except (ValueError, TypeError):
                    try:
                        # Intentar formato DD/MM/YYYY
                        parts = val.split("/")
                        if len(parts) == 3:
                            data[field] = date(int(parts[2]), int(parts[1]), int(parts[0]))
                    except (ValueError, IndexError):
                        logger.warning("No se pudo parsear fecha: %s = %s", field, val)
                        data[field] = None

        # Normalizar importe a float
        importe = data.get("importe")
        if importe is not None:
            try:
                # Si viene como string, limpiar
                if isinstance(importe, str):
                    importe = importe.replace("€", "").replace("EUR", "").strip()
                    importe = importe.replace(",", ".")  # 1.234,56 → 1.234.56
                    # Si tiene múltiples puntos, el último es separador decimal
                    if importe.count(".") > 1:
                        parts = importe.split(".")
                        importe = "".join(parts[:-1]) + "." + parts[-1]
                    importe = float(importe)
                data["importe"] = importe
            except (ValueError, TypeError):
                    data["importe"] = None
