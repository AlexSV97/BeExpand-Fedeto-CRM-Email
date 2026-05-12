"""
Emails de ejemplo en formato raw (RFC822) para los tests.

Cada muestra representa un caso real:
- Cliente escribiendo (relevante)
- Lead pidiendo presupuesto (relevante)
- Proveedor enviando factura (relevante)
- Fuera de oficina (irrelevante)
- Notificación automática (irrelevante)
- Newsletter (irrelevante)
- Email con adjunto (relevante)
"""

# ── EMAIL 1: Cliente haciendo un pedido (RELEVANTE) ──
CLIENTE_PEDIDO = (
    b'From: "Ana Garc\xc3\xada" <ana@garcia-sl.com>\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Pedido #3842 - Confirmaci\xc3\xb3n materiales\r\n'
    b'Date: Mon, 11 May 2026 09:34:21 +0200\r\n'
    b'Message-ID: <abc123@mail.garcia-sl.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Hola,\r\n'
    b'Confirmamos el pedido #3842 de materiales de oficina.\r\n'
    b'Necesitamos 50 cajas de papel A4 y 20 toners.\r\n'
    b'Rogamos confirmar disponibilidad y fecha de entrega.\r\n'
    b'\r\n'
    b'Un saludo,\r\n'
    b'Ana Garc\xc3\xada\r\n'
    b'Directora Comercial - Garc\xc3\xada SL\r\n'
)

# ── EMAIL 2: Lead pidiendo presupuesto (RELEVANTE) ──
LEAD_PRESUPUESTO = (
    b'From: "Carlos M\xc3\xa9ndez" <carlos@techcorp.com>\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Presupuesto para reforma de oficinas\r\n'
    b'Date: Tue, 12 May 2026 11:15:00 +0200\r\n'
    b'Message-ID: <def456@mail.techcorp.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Buenos d\xc3\xadas,\r\n'
    b'Estamos buscando proveedor para la reforma integral de nuestras\r\n'
    b'oficinas en la Calle Mayor 23, Madrid. Necesitamos presupuesto\r\n'
    b'para materiales y mano de obra.\r\n'
    b'\r\n'
    b'Quedo a la espera de su respuesta.\r\n'
    b'Carlos M\xc3\xa9ndez\r\n'
    b'TechCorp Solutions\r\n'
)

# ── EMAIL 3: Proveedor enviando factura (RELEVANTE) ──
PROVEEDOR_FACTURA = (
    b'From: administracion@suministros-sa.com\r\n'
    b'To: contabilidad@beexpand.com\r\n'
    b'Subject: Factura mensual - Material de oficina - Mayo 2026\r\n'
    b'Date: Tue, 12 May 2026 08:00:00 +0200\r\n'
    b'Message-ID: <ghi789@suministros-sa.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Adjuntamos factura correspondiente al mes de mayo.\r\n'
    b'Total: 1.234,50\xe2\x82\xac\r\n'
    b'Periodo de pago: 30 d\xc3\xadas\r\n'
    b'\r\n'
    b'Un cordial saludo,\r\n'
    b'Dpto. Administraci\xc3\xb3n\r\n'
    b'Suministros SA\r\n'
)

# ── EMAIL 4: Fuera de oficina (IRRELEVANTE) ──
OUT_OF_OFFICE = (
    b'From: "Mar\xc3\xada L\xc3\xb3pez" <maria@techcorp.com>\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Fuera de la oficina - Mar\xc3\xada L\xc3\xb3pez\r\n'
    b'Date: Mon, 11 May 2026 07:00:00 +0200\r\n'
    b'Message-ID: <auto-ooo-123@mail.techcorp.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Estoy fuera de la oficina del 11 al 15 de mayo.\r\n'
    b'Para asuntos urgentes, contactar con juan@techcorp.com.\r\n'
    b'Volver\xc3\xa9 el 16 de mayo.\r\n'
)

# ── EMAIL 5: Auto-respuesta (IRRELEVANTE) ──
AUTO_REPLY = (
    b'From: mailer-daemon@ionos.es\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Auto-Reply: Presupuesto para reforma de oficinas\r\n'
    b'Date: Tue, 12 May 2026 11:15:05 +0200\r\n'
    b'Message-ID: <auto-456@ionos.es>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Gracias por su correo. Estoy fuera de la oficina\r\n'
    b'y responder\xc3\xa9 a su mensaje a la mayor brevedad posible.\r\n'
)

# ── EMAIL 6: Email con adjunto (RELEVANTE) ──
EMAIL_CON_ADJUNTO = (
    b'From: "Juan Ruiz" <juan.ruiz@email.com>\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Contrato de mantenimiento - Firma\r\n'
    b'Date: Tue, 12 May 2026 14:00:00 +0200\r\n'
    b'Message-ID: <juan-789@mail.juanruiz.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: multipart/mixed; boundary="boundary123"\r\n'
    b'\r\n'
    b'--boundary123\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'\r\n'
    b'Hola,\r\n'
    b'Adjunto el contrato de mantenimiento firmado.\r\n'
    b'Quedo a la espera de su confirmaci\xc3\xb3n.\r\n'
    b'Saludos,\r\n'
    b'Juan Ruiz\r\n'
    b'--boundary123\r\n'
    b'Content-Type: application/pdf\r\n'
    b'Content-Disposition: attachment; filename="contrato_firmado.pdf"\r\n'
    b'Content-Transfer-Encoding: base64\r\n'
    b'\r\n'
    b'JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4K\r\n'
    b'--boundary123--\r\n'
)

# ── EMAIL 7: Newsletter (IRRELEVANTE) ──
NEWSLETTER = (
    b'From: newsletter@grupoeditorial.com\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Newsletter - Novedades sector construcci\xc3\xb3n\r\n'
    b'Date: Tue, 12 May 2026 06:00:00 +0200\r\n'
    b'Message-ID: <news-555@grupoeditorial.com>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'Content-Transfer-Encoding: 7bit\r\n'
    b'\r\n'
    b'Descubre las \xc3\xbaltimas novedades del sector.\r\n'
    b'Si no deseas recibir este correo, puedes darte de baja\r\n'
    b'a trav\xc3\xa9s del siguiente enlace.\r\n'
    b'Has recibido este email porque est\xc3\xa1s suscrito a nuestro bolet\xc3\xadn.\r\n'
)

# ── EMAIL 8: Bounce / Fallo de entrega (IRRELEVANTE) ──
BOUNCE = (
    b'From: MAILER-DAEMON@ionos.es\r\n'
    b'To: comercial@beexpand.com\r\n'
    b'Subject: Undelivered Mail Returned to Sender\r\n'
    b'Date: Mon, 11 May 2026 10:00:00 +0200\r\n'
    b'Message-ID: <bounce-111@ionos.es>\r\n'
    b'MIME-Version: 1.0\r\n'
    b'Content-Type: text/plain; charset="UTF-8"\r\n'
    b'\r\n'
    b'This is the mail system at host mail.ionos.es.\r\n'
    b'\r\n'
    b"I'm sorry to have to inform you that your message could not\r\n"
    b'be delivered to one or more recipients. It has been bounced.\r\n'
)

# ── DICCIONARIO CON TODAS LAS MUESTRAS ──
ALL_SAMPLES = {
    "cliente_pedido": CLIENTE_PEDIDO,
    "lead_presupuesto": LEAD_PRESUPUESTO,
    "proveedor_factura": PROVEEDOR_FACTURA,
    "out_of_office": OUT_OF_OFFICE,
    "auto_reply": AUTO_REPLY,
    "con_adjunto": EMAIL_CON_ADJUNTO,
    "newsletter": NEWSLETTER,
    "bounce": BOUNCE,
}
