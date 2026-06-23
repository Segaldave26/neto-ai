from fastapi import FastAPI, Request
from anthropic import Anthropic
from twilio.rest import Client
from dotenv import load_dotenv
import os
import json
import httpx

load_dotenv()

app = FastAPI()
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

SECRET_CUENTA_B = os.getenv("SECRET_KEY_CUENTA_B", "CLAVEB")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS_SUPABASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

SYSTEM_PROMPT_A = """Sos el CFO virtual de esta empresa argentina, integrado en WhatsApp por Neto AI.
Hablás como un CFO senior porteño: directo, sin vueltas, con criterio financiero real.
Usás el lenguaje que usa cualquier empresario argentino en el día a día.

CONTEXTO ECONÓMICO QUE MANEJÁS:
- Sabés que la autoridad fiscal ya no se llama AFIP sino ARCA (Agencia de Recaudación y Control Aduanero)
- Conocés el dólar blue, dólar MEP, dólar CCL, dólar oficial, dólar tarjeta
- Entendés el cepo cambiario y sus implicancias en el flujo de caja
- Manejás conceptos como retenciones, percepciones, IIBB (Ingresos Brutos), IVA, Ganancias, Bienes Personales
- Sabés lo que es una cuenta corriente bancaria, un descubierto, un cheque diferido, un echeq
- Conocés los plazos fijos, LECAPs, LETEs, FCI Money Market, FCI T+1, ON dollar-linked, CEDEARs, cauciones
- Entendés inflación, UVA, CER, devaluación, brecha cambiaria
- Sabés lo que es el aguinaldo (SAC), las cargas sociales, los aportes, el SIPA, la ART
- Manejás términos como quincena, cierre de mes, balance, mayor, libro diario
- Conocés los vencimientos típicos: IVA (día 20 aprox según CUIT), Ganancias, IIBB, sueldos
- Entendés lo que es un proveedor que cobra en negro, una factura B, una factura A, un ticket
- Sabés lo que significa tener plata en la calle (cuentas a cobrar), stock parado, mercadería en consignación
- Conocés el mercado inmobiliario argentino en dólares y los ladrillos como reserva de valor

CÓMO HABLÁS:
- Directo y concreto, como un CFO que tiene 20 años de experiencia en PyMEs argentinas
- Usás términos del día a día: "la plata", "el efectivo", "la caja", "el flujo", "los números"
- Cuando hay riesgo lo decís claramente: "ojo con esto", "cuidado que acá...", "esto te puede complicar"
- Cuando hay oportunidad la marcás: "acá podés ganar", "esto te conviene", "aprovechá que..."
- Usás comparaciones en dólares MEP cuando es relevante para que el empresario entienda el valor real
- Si algo no tiene sentido financiero lo decís sin rodeos
- Respondés de forma concisa por WhatsApp — máximo 3-4 párrafos, sin texto innecesario
- Usás emojis con criterio para hacer más legible el mensaje (📊 💰 ⚠️ ✅)

LÍMITES IMPORTANTES:
- Solo tenés acceso a Cuenta A (contabilidad formal)
- Si te preguntan por datos internos o Cuenta B, decís: "No tengo acceso a esa información con el modo actual."
- No inventás números — si no tenés el dato, lo decís y pedís que te lo pasen
- Cuando das recomendaciones de inversión siempre aclarás que es orientación financiera, no asesoramiento regulado"""

PREGUNTAS_ONBOARDING = [
    ("nombre_cuenta_b", "👋 Bienvenido al modo *Cuenta B*. Para poder hablar en tu idioma, te hago unas preguntas rápidas.\n\n*¿Cómo llamás vos a tu contabilidad interna?* (ejemplos: 'la B', 'los internos', 'la paralela', 'la caja negra')"),
    ("nombre_ingresos_informales", "💰 ¿Cómo llamás a los ingresos que no van por factura? (ejemplos: 'lo que entra en mano', 'el negro', 'la plata de afuera')"),
    ("nombre_pagos_informales", "📤 ¿Cómo llamás a los pagos que hacés sin factura? (ejemplos: 'lo que pago en negro', 'los gastos internos', 'los viáticos')"),
    ("nombre_caja", "🏦 ¿Cómo llamás al efectivo físico que tenés? (ejemplos: 'la caja', 'el sobre', 'el cajón', 'el efectivo')"),
    ("vocabulario_extra", "📝 ¿Hay algún otro término especial que uses en tu negocio que quieras que yo conozca? (si no hay, respondé 'no')")
]

onboarding_estado = {}

def build_system_prompt_b(cliente):
    nombre_b = cliente.get("nombre_cuenta_b", "Cuenta B")
    ingresos = cliente.get("nombre_ingresos_informales", "ingresos informales")
    pagos = cliente.get("nombre_pagos_informales", "pagos en negro")
    caja = cliente.get("nombre_caja", "caja")
    extra = cliente.get("vocabulario_extra", "")

    return f"""Sos el CFO virtual de esta empresa argentina, integrado en WhatsApp por Neto AI.
Hablás como un CFO senior porteño: directo, sin vueltas, con criterio financiero real.

VOCABULARIO PERSONALIZADO DE ESTE CLIENTE:
- A la contabilidad interna la llaman: "{nombre_b}"
- A los ingresos informales los llaman: "{ingresos}"
- A los pagos informales los llaman: "{pagos}"
- Al efectivo físico lo llaman: "{caja}"
{f'- Términos adicionales del negocio: {extra}' if extra and extra.lower() != 'no' else ''}

SIEMPRE usás el vocabulario del cliente, nunca los términos genéricos.

CONTEXTO ECONÓMICO QUE MANEJÁS:
- Sabés que la autoridad fiscal ya no se llama AFIP sino ARCA (Agencia de Recaudación y Control Aduanero)
- Conocés el dólar blue, dólar MEP, dólar CCL, dólar oficial, dólar tarjeta
- Entendés el cepo cambiario y sus implicancias en el flujo de caja
- Manejás conceptos como retenciones, percepciones, IIBB, IVA, Ganancias, Bienes Personales
- Sabés lo que es un cheque diferido, un echeq, una cuenta corriente, un descubierto
- Conocés LECAPs, FCI Money Market, FCI T+1, ON dollar-linked, CEDEARs, cauciones, plazos fijos UVA
- Entendés inflación, UVA, CER, devaluación, brecha cambiaria
- Sabés lo que es el aguinaldo (SAC), cargas sociales, SIPA, ART
- Entendés plata en la calle, stock parado, mercadería en consignación

ACCESO COMPLETO — MODO {nombre_b.upper()}:
Tenés acceso completo a ambas contabilidades.
Cuando analizás mostrás tres niveles si es relevante:
📋 Cuenta A (formal): ...
📦 {nombre_b}: ...
📊 Consolidado real: ...

CÓMO HABLÁS:
- Directo y concreto, 20 años de experiencia en PyMEs argentinas
- "la plata", "el efectivo", "el flujo", "los números"
- Riesgos: "ojo con esto", "cuidado que acá...", "esto te puede complicar"
- Oportunidades: "acá podés ganar", "esto te conviene", "aprovechá que..."
- Máximo 3-4 párrafos por WhatsApp, emojis con criterio (📊 💰 ⚠️ ✅)
- No inventás números — si no tenés el dato, lo pedís
- Recomendaciones de inversión siempre con aclaración: orientación financiera, no asesoramiento regulado"""

async def get_cliente(numero):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/clientes?numero=eq.{numero}",
            headers=HEADERS_SUPABASE
        )
        data = r.json()
        return data[0] if data else None

async def crear_cliente(numero):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/clientes",
            headers=HEADERS_SUPABASE,
            json={"numero": numero, "historial": []}
        )
        return r.json()[0] if r.status_code == 201 else None

async def actualizar_cliente(numero, datos):
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/clientes?numero=eq.{numero}",
            headers=HEADERS_SUPABASE,
            json=datos
        )

MENSAJE_BIENVENIDA = """👋 ¡Hola! Soy tu CFO virtual de *Neto AI*.

Estoy acá para ayudarte con las finanzas de tu empresa: flujo de caja, inversiones, vencimientos, rentabilidad, lo que necesites.

¿En qué te puedo dar una mano hoy?"""

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    mensaje = form.get("Body", "").strip()
    numero = form.get("From", "")

    cliente = await get_cliente(numero)

    if not cliente:
        cliente = await crear_cliente(numero)
        enviar_whatsapp(numero, MENSAJE_BIENVENIDA)
        return {"status": "ok"}

    # Onboarding Cuenta B en progreso
    if numero in onboarding_estado:
        estado = onboarding_estado[numero]
        campo = PREGUNTAS_ONBOARDING[estado["paso"]][0]
        await actualizar_cliente(numero, {campo: mensaje})

        estado["paso"] += 1

        if estado["paso"] < len(PREGUNTAS_ONBOARDING):
            siguiente_pregunta = PREGUNTAS_ONBOARDING[estado["paso"]][1]
            enviar_whatsapp(numero, siguiente_pregunta)
        else:
            del onboarding_estado[numero]
            await actualizar_cliente(numero, {"onboarding_completo": True, "cuenta_b_activa": True})
            cliente_actualizado = await get_cliente(numero)
            enviar_whatsapp(numero, f"✅ *¡Perfecto!* Ya conozco tu idioma. Ahora tenés acceso completo a tu *{cliente_actualizado.get('nombre_cuenta_b', 'Cuenta B')}*. ¿En qué te ayudo?")
        return {"status": "ok"}

    # Activar Cuenta B
    if mensaje.upper() == SECRET_CUENTA_B.upper():
        if cliente.get("onboarding_completo"):
            await actualizar_cliente(numero, {"cuenta_b_activa": True})
            nombre_b = cliente.get("nombre_cuenta_b", "Cuenta B")
            enviar_whatsapp(numero, f"✅ *{nombre_b} desbloqueada.* Tenés acceso completo. ¿En qué te ayudo?")
        else:
            onboarding_estado[numero] = {"paso": 0}
            enviar_whatsapp(numero, PREGUNTAS_ONBOARDING[0][1])
        return {"status": "ok"}

    # Bloquear Cuenta B
    if mensaje.upper() == "BLOQUEAR B":
        await actualizar_cliente(numero, {"cuenta_b_activa": False})
        enviar_whatsapp(numero, "🔒 Cuenta B bloqueada. Quedás en modo Cuenta A (formal) solamente.")
        return {"status": "ok"}

    historial = cliente.get("historial") or []
    historial.append({"role": "user", "content": mensaje})
    if len(historial) > 10:
        historial = historial[-10:]

    if cliente.get("cuenta_b_activa") and cliente.get("onboarding_completo"):
        system = build_system_prompt_b(cliente)
    else:
        system = SYSTEM_PROMPT_A

    try:
        response = anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system,
            messages=historial
        )
        respuesta = response.content[0].text
    except Exception:
        respuesta = "⚠️ Tuve un problema técnico. Intentá de nuevo en un momento."

    historial.append({"role": "assistant", "content": respuesta})
    await actualizar_cliente(numero, {"historial": historial})

    enviar_whatsapp(numero, respuesta)
    return {"status": "ok"}

def enviar_whatsapp(numero: str, mensaje: str):
    twilio.messages.create(
        body=mensaje,
        from_=os.getenv("TWILIO_WHATSAPP_FROM"),
        to=numero
    )

@app.get("/")
def root():
    return {"status": "Neto AI backend corriendo"}
