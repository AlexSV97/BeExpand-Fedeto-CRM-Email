"""
Envía 5 emails de prueba a la cuenta Gmail para probar el Orchestrator.
Cada email simula un escenario real de negocio.
"""
import smtplib
import email.message
import email.utils
from datetime import datetime, timezone

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM_EMAIL = "beexpandcrmpoc@gmail.com"
FROM_PASS = "wdjqgpkkurdoxiqg"

emails = [
    {
        "to": FROM_EMAIL,
        "subject": "Factura mensual de servicios - Septiembre 2026",
        "body": """Hola,

Adjunto la factura correspondiente al mes de septiembre de 2026 por los servicios contratados.

Datos de la factura:
- Número: FAC-2026-0987
- Importe: 2.450,00 EUR
- Fecha de vencimiento: 15/10/2026
- Servicio: Mantenimiento plataforma web + hosting

Quedamos a la espera de la confirmación del pago. Si tenéis cualquier incidencia con la factura, no dudéis en contactarnos.

Un saludo,
María García
Departamento de Administración
TechSolutions España""",
    },
    {
        "to": FROM_EMAIL,
        "subject": "Solicitud de presupuesto para campaña de marketing digital",
        "body": """Buenos días,

Me interesaría recibir un presupuesto detallado para los siguientes servicios de marketing digital:

1. Gestión de redes sociales (Instagram, LinkedIn, Facebook) - 3 meses
2. Campaña de Google Ads con un presupuesto estimado de 3.000€/mes
3. Email marketing automatizado para base de 5.000 contactos

Somos una empresa del sector retail con 12 años de experiencia en el mercado español. Estamos buscando un partner para digitalizar nuestra estrategia de captación.

¿Podríais hacerme llegar una propuesta comercial antes del viernes?

Muchas gracias,
Carlos Mendoza
Director de Marketing - ModaTrend SL
carlos.mendoza@modatrend.es""",
    },
    {
        "to": FROM_EMAIL,
        "subject": "Orden de compra - Material de oficina lote 2026-03",
        "body": """Buenos días,

Procedemos a realizar el siguiente pedido de material según nuestro acuerdo de suministro:

Lote OP-2026-0356:
- 20 cajas de papel A4 (80g/m²) - Ref: PAP-1002
- 10 packs de tóner HP CF226X - Ref: TON-226
- 5 unidades de sillas ergonómicas modelo OfficePro - Ref: SILL-007
- 3 impresoras multifunción HP LaserJet Pro - Ref: IMP-452

Fecha estimada de entrega: 30 de septiembre de 2026
Lugar de entrega: Calle Industria 45, Polígono Industrial La Llanura, 45006 Toledo

Confirmadnos disponibilidad y plazos de entrega actualizados.

Atentamente,
Ana López
Departamento de Compras
Suministros Redondos SL""",
    },
    {
        "to": FROM_EMAIL,
        "subject": "Propuesta de colaboración tecnológica B2B",
        "body": """Hola,

Soy Javier Ruiz, CTO de InnovaTech Solutions. Os escribo porque hemos seguido vuestra trayectoria en el sector y creemos que hay una oportunidad interesante de colaboración.

Nuestra empresa desarrolla soluciones de IA para automatización de procesos empresariales. Hemos visto que trabajáis con integración CRM y gestión de correos, y nos gustaría explorar sinergias.

¿Os interesaría tener una reunión para explorar posibilidades de colaboración? Estaríamos encantados de hacer una demo de nuestra plataforma y ver cómo podríamos complementar vuestros servicios.

Quedo a la espera de vuestra respuesta.

Un cordial saludo,
Javier Ruiz
CTO - InnovaTech Solutions
javier.ruiz@innovatech.com""",
    },
    {
        "to": FROM_EMAIL,
        "subject": "Newsletter Semanal - Las mejores ofertas en tecnología",
        "body": """¡Hola!

Esta semana tenemos las mejores ofertas en tecnología para tu negocio:

🖥️ Monitores 4K desde 299€
📱 Móviles corporativos con 30% de descuento
💻 Portátiles con hasta 40% de descuento

Además, suscríbete a nuestro plan premium y llévate un mes GRATIS.

Ofertas válidas hasta fin de mes.

No te lo pierdas,
El equipo de TechDeals

Si no deseas recibir más correos, haz clic aquí para darte de baja.""",
    },
]


def send_test_emails():
    print(f"Conectando a SMTP {SMTP_HOST}:{SMTP_PORT}...")
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.starttls()
    server.login(FROM_EMAIL, FROM_PASS)
    print("Conectado. Enviando 5 emails de prueba...\n")

    for i, email_data in enumerate(emails, 1):
        msg = email.message.EmailMessage()
        msg["Subject"] = email_data["subject"]
        msg["From"] = email_data.get("from_header", f"Remitente {i} <test{i}@empresa-prueba.es>")
        msg["To"] = email_data["to"]
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content(email_data["body"])

        server.send_message(msg)
        subject_preview = email_data["subject"][:60]
        print(f"  [{i}/5] Enviado: {subject_preview}...")

    server.quit()
    print("\n✅ 5 emails enviados correctamente.")


# Definir from_headers específicos para cada email
emails[0]["from_header"] = "María García <maria.garcia@techsolutions.es>"
emails[1]["from_header"] = "Carlos Mendoza <carlos.mendoza@modatrend.es>"
emails[2]["from_header"] = "Ana López <compras@suministrosredondos.es>"
emails[3]["from_header"] = "Javier Ruiz <javier.ruiz@innovatech.com>"
emails[4]["from_header"] = "Newsletter TechDeals <newsletter@techdeals.com>"

if __name__ == "__main__":
    send_test_emails()
