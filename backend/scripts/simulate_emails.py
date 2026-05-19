"""
Simulacion: 40 emails (4 dias x ~10, 16-19 May 2026)
Pipeline completo con lotes concurrentes.

Uso: docker compose exec -w /app backend python /tmp/simulate_emails.py
"""
import sys; sys.path.insert(0, '/app')

import asyncio, time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from src.orchestrator.orchestrator import Orchestrator
from src.db.session import async_session_factory
from sqlalchemy import select as sel, func

@dataclass
class SimEmail:
    subject: str
    body: str
    sender_name: str
    sender_email: str

def eset1():
    """6 cliente"""
    return [
        SimEmail("Incidencia con la plataforma de facturacion",
            "Buenos dias, desde ayer no podemos acceder al modulo de facturacion. Error 503 al generar facturas del mes. Urgente por cierre mensual.",
            "Maria Garcia", "maria.garcia@importadora.es"),
        SimEmail("Solicitud de reunion para revisar servicio",
            "Queremos agendar reunion para revisar nuestro contrato de soporte. Llevamos 6 meses y queremos evaluar resultados y mejoras.",
            "Juan Rodriguez", "juan.rodriguez@logistica-global.com"),
        SimEmail("Pago de factura mensual confirmacion",
            "Adjuntamos comprobante de transferencia factura mayo. Pago realizado por importe total de 2.450EUR. Rogamos confirmen recepcion.",
            "Ana Torres", "ana.torres@distribuidora.net"),
        SimEmail("Problema con acceso al panel de control",
            "Desde esta manana no puedo acceder al panel de administracion. Sesion expirada y al iniciar sesion da error. Necesito acceso urgente.",
            "Maria Garcia", "maria.garcia@importadora.es"),
        SimEmail("Seguimiento incidencia INC-2026-0341",
            "Doy seguimiento a la incidencia de la semana pasada sobre modulo de reportes. Sigue sin funcionar. Necesitamos los informes para el jueves.",
            "Juan Rodriguez", "juan.rodriguez@logistica-global.com"),
        SimEmail("Renovacion de contrato de soporte",
            "Queremos proceder con renovacion de contrato de soporte anual. Las condiciones actuales nos parecen adecuadas. Esperamos confirmacion.",
            "Ana Torres", "ana.torres@distribuidora.net"),
    ]

def eset2():
    """6 lead"""
    return [
        SimEmail("Solicitud de presupuesto servicios consultoria TI",
            "Estamos interesados en presupuesto para servicios de consultoria tecnologica. Empresa mediana en crecimiento quiere externalizar gestion TI.",
            "Carlos Lopez", "carlos.lopez@startup-tech.com"),
        SimEmail("Consulta sobre integracion CRM",
            "Evaluamos opciones para integrar CRM con email marketing. Su solucion permite integracion con HubSpot? Coste del desarrollo? Tiempos estimados?",
            "Laura Sanchez", "laura.sanchez@innovacion.es"),
        SimEmail("Propuesta de colaboracion estrategica",
            "Desde Digital Solutions buscamos partners tecnologicos. Hemos visto su trabajo y creemos que hay sinergias. Interesados en explorar colaboracion?",
            "Sofia Perez", "sofia.perez@digital-solutions.com"),
        SimEmail("Tienen servicio de migracion a la nube?",
            "Evaluamos migrar infraestructura on-premise a la nube. Ofrecen migraciones cloud? Informacion y precios orientativos por favor.",
            "Carlos Lopez", "carlos.lopez@startup-tech.com"),
        SimEmail("Buscamos proveedor de formacion tecnologica",
            "Buscamos proveedor para formacion tecnologica para equipo de desarrollo. Cursos cloud y CI/CD para 8 personas. Presupuesto y temario por favor.",
            "Laura Sanchez", "laura.sanchez@innovacion.es"),
        SimEmail("Posible oportunidad de negocio conjunta",
            "Hemos identificado oportunidad en sector retail donde colaborar. Tenemos contacto con cliente y uds la tecnologia. Reunion la proxima semana?",
            "Sofia Perez", "sofia.perez@digital-solutions.com"),
    ]

def eset3():
    """4 proveedor"""
    return [
        SimEmail("Nueva orden de compra materiales oficina",
            "Orden de compra OC-2026-0893 por suministro materiales oficina trimestre. Papel, toner y fungibles segun acuerdo. Confirmen disponibilidad y plazo.",
            "Ana Martinez", "ana.martinez@proveedores.es"),
        SimEmail("Oferta especial suministros informaticos",
            "Nueva linea equipamiento informatico con descuentos por volumen. Stock inmediato monitores, teclados docks USB. Catalogo con precios especiales.",
            "Pedro Lopez", "pedro.lopez@suministros.com"),
        SimEmail("Notificacion envio Pedido P-2026-4521",
            "Pedido P-2026-4521 ha sido enviado. Transportista recoge el 18 de mayo. Adjuntamos albaran. Plazo entrega 48-72 horas.",
            "Ana Martinez", "ana.martinez@proveedores.es"),
        SimEmail("Actualizacion de precios proximo trimestre",
            "Precios ajuste del 3% desde 1 junio por incremento costes materias primas. Adjuntamos nuevo tarifario. Pedidos antes 31 mayo mantienen precios.",
            "Pedro Lopez", "pedro.lopez@suministros.com"),
    ]

def eset4():
    """4 nulo"""
    return [
        SimEmail("Newsletter Novedades gestion empresarial Mayo 2026",
            "Newsletter mensual: tendencias transformacion digital, casos de exito clientes, proximos webinars. Si no desea recibir, desuscribase.",
            "Newsletter", "newsletter@plataforma-marketing.com"),
        SimEmail("Tu factura de servicios cloud Mayo 2026",
            "Notificacion automatica: Factura cloud periodo 1-31 mayo disponible en portal. Importe 89.99EUR. Vencimiento 15 junio. Mensaje automatico no responder.",
            "Sistema Cloud", "no-reply@sistema-notificaciones.com"),
        SimEmail("Ofertas exclusivas para empresas",
            "Descuentos hasta 40% en plan premium. Mejore productividad con nuestras herramientas. Oferta por tiempo limitado. Si no desea recibir, desuscribase.",
            "Marketing Online", "info@tienda-online-marketing.com"),
        SimEmail("Confirmacion registro Webinar Tendencias TI 2026",
            "Confirmacion registro webinar Tendencias TI 2026. Evento jueves 16:00. Recibira enlace 1 hora antes. Mensaje automatico.",
            "Eventos Platform", "no-reply@eventos-tech.com"),
    ]

def build_emails():
    base = datetime(2026, 5, 16, tzinfo=timezone.utc)
    all_e = []
    for day_off in range(4):
        day = base + timedelta(days=day_off)
        if day_off % 2 == 0:
            batch = eset1()[:3] + eset2()[:3] + eset3()[:2] + eset4()[:2]
        else:
            batch = eset1()[3:] + eset2()[3:] + eset3()[2:] + eset4()[2:]
        for h, e in enumerate(batch):
            all_e.append((day + timedelta(hours=8+h), e))
    return all_e

async def process_one(orch, received_at, email, idx, total):
    db = async_session_factory()
    try:
        ctx = await orch.process_raw_email(
            subject=email.subject, body_plain=email.body,
            sender_name=email.sender_name, sender_email=email.sender_email,
            received_at=received_at, db=db)
        return {
            "idx": idx, "total": total,
            "day": received_at.strftime("%m-%d %H:%M"),
            "subj": email.subject[:55],
            "cat": ctx.final_category or "?",
            "conf": ctx.final_confidence or 0,
            "method": ctx.resolution_method or "?",
            "error": ctx.error,
            "votes": ", ".join(f"{v.agent_name}={v.category}({v.confidence:.0%})" for v in (ctx.votes or [])),
            "routing": ", ".join(ctx.routing.departments) if ctx.routing and ctx.routing.departments else "",
            "ms": ctx.processing_time_ms,
        }
    finally:
        await db.close()

async def process_batch(batch, total):
    orch = Orchestrator()
    return await asyncio.gather(*[process_one(orch, r, e, i, total) for i, r, e in batch])

async def main():
    print("="*60+"\n  SIMULACION 40 EMAILS (16-19 May 2026)\n"+"="*60)
    all_emails = build_emails()
    print(f"Total: {len(all_emails)} emails\n")

    # Limpiar BD previa
    db = async_session_factory()
    for t in ["classification_history", "email_contacts", "opportunities", "emails", "contacts", "accounts"]:
        await db.execute(__import__('sqlalchemy').text(f"DELETE FROM {t}"))
    await db.commit()
    await db.close()
    print("BD limpiada\n")

    batches = []
    for i in range(0, len(all_emails), 2):
        batches.append([(j+1, r, e) for j, (r, e) in enumerate(all_emails[i:i+2], i)])

    stats = {"total": len(all_emails), "ok": 0, "err": 0, "cats": {}, "res": {}, "ms": 0}
    start = time.time()

    for bn, batch in enumerate(batches, 1):
        bs = time.time()
        print(f"-- Lote {bn}/{len(batches)} ({len(batch)} emails) --")
        results = await process_batch(batch, len(all_emails))
        for r in results:
            if r["error"]:
                print(f"  [{r['idx']:02d}/{r['total']}] ERROR: {r['subj'][:50]} | {r['error'][:70]}")
                stats["err"] += 1
            else:
                stats["ok"] += 1
                stats["cats"][r["cat"]] = stats["cats"].get(r["cat"], 0) + 1
                stats["res"][r["method"]] = stats["res"].get(r["method"], 0) + 1
                stats["ms"] += r["ms"]
                rte = f" -> {r['routing']}" if r["routing"] else ""
                print(f"  [{r['idx']:02d}/{r['total']}] {r['day']} | {r['cat']}({r['conf']:.0%}) via {r['method']}{rte}")
                print(f"         {r['subj']} | {r['votes']}")
        print(f"  Lote en {time.time()-bs:.0f}s\n")

    elapsed = time.time() - start
    print("="*60+"\n  RESULTADOS\n"+"="*60)
    print(f"Procesados: {stats['ok']}/{stats['total']} | Errores: {stats['err']}")
    print(f"Tiempo: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    if stats["ok"]: print(f"Media: {stats['ms']/stats['ok']:.0f}ms/email")
    print("\nCategorias:")
    for c, n in sorted(stats["cats"].items()):
        print(f"  {c}: {n} ({n/stats['total']*100:.0f}%)")
    print("\nResolucion:")
    for m, n in sorted(stats["res"].items()):
        print(f"  {m}: {n}")

    # Verificar BD final
    from src.db.models import Email, Contact, ClassificationHistory
    db = async_session_factory()
    for lbl, mdl in [("Emails", Email), ("Contacts", Contact), ("ClassHist", ClassificationHistory)]:
        r = await db.execute(sel(func.count()).select_from(mdl))
        print(f"  BD {lbl}: {r.scalar()}")
    cr = await db.execute(sel(Email.category, func.count()).group_by(Email.category))
    for row in cr:
        print(f"    '{row[0]}': {row[1]}")
    await db.close()
    print("\nHECHO.")

if __name__ == "__main__":
    asyncio.run(main())
