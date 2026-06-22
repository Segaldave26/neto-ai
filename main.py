from fastapi import FastAPI, Request
from anthropic import Anthropic
from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

SECRET_CUENTA_B = os.getenv("SECRET_KEY_CUENTA_B", "CLAVEB")

SYSTEM_PROMPT_A = """Eres CFO AI de Neto AI para empresas argentinas. 
Solo tenés acceso a Cuenta A (formal). 
Si preguntan por datos internos o Cuenta B, respondé: 'No tengo acceso a esa información.'
Analizás en pesos y dólares MEP. Conocés inflación argentina, AFIP, LECAPs, FCI, cheques diferidos."""

SYSTEM_PROMPT_AB = """Eres CFO AI de Neto AI para empresas argentinas.
Tenés acceso completo a Cuenta A (formal) y Cuenta B (gestión interna).
Siempre mostrás análisis en tres niveles: Cuenta A / Cuenta B / Consolidado.
Analizás en pesos y dólares MEP. Conocés inflación, AFIP, LECAPs, FCI, cheques diferidos."""

conversaciones = {}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    mensaje = form.get("Body", "").strip()
    numero = form.get("From", "")

    if numero not in conversaciones:
        conversaciones[numero] = {"historial": [], "cuenta_b": False}

    sesion = conversaciones[numero]

    # Verificar clave Cuenta B
    if mensaje.upper() == SECRET_CUENTA_B.upper():
        sesion["cuenta_b"] = True
        respuesta = "✅ Cuenta B desbloqueada. Ahora tenés acceso completo: Cuenta A + Cuenta B + Consolidado."
        enviar_whatsapp(numero, respuesta)
        return {"status": "ok"}

    # Bloquear Cuenta B
    if mensaje.upper() == "BLOQUEAR B":
        sesion["cuenta_b"] = False
        respuesta = "🔒 Cuenta B bloqueada."
        enviar_whatsapp(numero, respuesta)
        return {"status": "ok"}

    system = SYSTEM_PROMPT_AB if sesion["cuenta_b"] else SYSTEM_PROMPT_A
    sesion["historial"].append({"role": "user", "content": mensaje})

    # Limitar historial a 10 mensajes
    if len(sesion["historial"]) > 10:
        sesion["historial"] = sesion["historial"][-10:]

    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=sesion["historial"]
    )

    respuesta = response.content[0].text
    sesion["historial"].append({"role": "assistant", "content": respuesta})

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