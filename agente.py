"""Agentes de @IAautonomosES: elige tema -> redacta (Gemini gratis) -> verifica -> publica en X."""
import datetime, json, os, re, sys, urllib.request
from requests_oauthlib import OAuth1Session

TEMAS = [
    "Un truco concreto para que un autónomo ahorre 1 hora a la semana usando ChatGPT, Gemini o Claude",
    "Una herramienta de IA gratuita útil para pymes españolas y para qué usarla exactamente",
    "Un prompt listo para copiar que ayude a un autónomo a redactar presupuestos o facturas",
    "Un error común de autónomos con la IA y cómo evitarlo",
    "Cómo automatizar la respuesta a clientes por WhatsApp o email con IA, explicado en simple",
    "Una idea rápida de IA para conseguir más clientes en redes sociales siendo autónomo",
    "Pregunta abierta a autónomos sobre cómo usan la IA en su negocio",
]
MODELO = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def redactar(tema):
    prompt = (
        "Eres el community manager de la cuenta de X @IAautonomosES (IA para Autónomos), "
        "dirigida a autónomos y pymes de España. Escribe UN solo post para X sobre: " + tema +
        ". Reglas: español de España, tono cercano y práctico, máximo 260 caracteres, sin enlaces, "
        "máximo 1 hashtag, máximo 1 emoji, sin promesas exageradas. Devuelve SOLO el texto del post."
    )
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').strip()


def verificar(t):
    problemas = []
    if not t: problemas.append("vacío")
    if len(t) > 280: problemas.append("más de 280 caracteres")
    if re.search(r"https?://|www\.", t, re.I): problemas.append("contiene enlace")
    if t.count("#") > 2: problemas.append("demasiados hashtags")
    return problemas


def publicar(t):
    x = OAuth1Session(
        os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"],
    )
    r = x.post("https://api.x.com/2/tweets", json={"text": t})
    print(r.status_code, r.text)
    r.raise_for_status()


if __name__ == "__main__":
    tema = TEMAS[datetime.date.today().weekday()]
    for intento in range(3):  # el verificador puede pedir hasta 3 borradores
        texto = redactar(tema)
        problemas = verificar(texto)
        print(f"Borrador {intento+1}: {texto}\nProblemas: {problemas or 'ninguno'}")
        if not problemas:
            break
    else:
        sys.exit("Ningún borrador pasó la verificación; hoy no se publica.")
    if os.environ.get("SOLO_PRUEBA") == "1":
        print("Modo prueba: no se publica.")
    else:
        publicar(texto)
