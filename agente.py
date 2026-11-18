"""Agentes de @IAautonomosES: elige tema -> redacta (Gemini gratis) -> verifica -> publica en X."""
import datetime, json, os, re, sys, time, urllib.request
from requests_oauthlib import OAuth1Session

TEMAS = [
    "Ahorrar 1 hora a la semana usando ChatGPT, Gemini o Claude en tareas de oficina",
    "Una herramienta de IA gratuita útil para pymes españolas y para qué usarla exactamente",
    "Redactar presupuestos o facturas más rápido con IA",
    "Un error común de autónomos con la IA y cómo evitarlo",
    "Responder a clientes por WhatsApp o email con ayuda de la IA",
    "Conseguir más clientes en redes sociales con IA siendo autónomo",
    "Reclamar un impago con buen tono usando IA",
    "Mejorar la ficha de Google Maps y conseguir reseñas con IA",
    "Entender cartas de Hacienda o la Seguridad Social con IA (sin sustituir a la gestoría)",
    "Organizar la semana y las tareas con IA",
    "Crear posts e imágenes para redes en minutos con IA gratis",
    "Preparar una oferta o promoción para meses flojos con IA",
    "Resumir documentos largos (contratos, convocatorias, BOE) con IA",
    "Calcular precios por hora y márgenes con ayuda de la IA",
    "Automatizar tareas repetitivas del negocio con herramientas gratuitas",
]
FORMATOS = [
    "un truco práctico y concreto que se pueda aplicar hoy",
    "un prompt listo para copiar entre comillas, con [corchetes] para que el lector lo personalice",
    "un error o mito frecuente sobre el tema, y termina con una pregunta a la audiencia para generar respuestas",
]
API = "https://generativelanguage.googleapis.com/v1beta"


def elegir_modelos():
    """Devuelve [Flash-Lite mas reciente, Flash mas reciente]: Lite es rapido; Flash queda de reserva."""
    if os.environ.get("GEMINI_MODEL"):
        return [os.environ["GEMINI_MODEL"]]
    req = urllib.request.Request(f"{API}/models?pageSize=200",
                                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        modelos = json.load(r).get("models", [])
    nombres = [m["name"].split("/")[-1] for m in modelos
               if "generateContent" in m.get("supportedGenerationMethods", [])]
    def mejor(lista):
        estables = [n for n in lista if "preview" not in n] or lista
        return sorted(estables, key=lambda n: [int(x) for x in re.findall(r"\d+", n)][:2], reverse=True)[0] if estables else None
    excluir = r"image|tts|audio|live|thinking|exp"
    lite = mejor([n for n in nombres if "flash-lite" in n and not re.search(excluir, n)])
    flash = mejor([n for n in nombres if "flash" in n and "lite" not in n and not re.search(excluir, n)])
    elegidos = [m for m in (lite, flash) if m]
    if not elegidos:
        sys.exit(f"No encuentro modelo Flash. Disponibles: {nombres}")
    print("Modelos Gemini:", elegidos)
    return elegidos


def elegir_modelo():  # compatibilidad con menciones.py
    return elegir_modelos()[-1]


MODELOS = None
INTENTO = 0


def turno():
    """0 = mañana, 1 = mediodía, 2 = tarde (según la hora UTC de ejecución)."""
    h = datetime.datetime.utcnow().hour
    return 0 if h < 11 else (1 if h < 17 else 2)


def redactar(tema):
    global MODELOS, INTENTO
    MODELOS = MODELOS or elegir_modelos()
    MODELO = MODELOS[min(INTENTO, len(MODELOS) - 1)] if INTENTO < 2 else MODELOS[0]
    INTENTO += 1
    franja = turno()
    prompt = (
        "Eres el community manager de la cuenta de X @IAautonomosES (IA para Autónomos), "
        "dirigida a autónomos y pymes de España. Escribe UN solo post para X sobre: " + tema +
        ". Formato: " + FORMATOS[franja] + ". Empieza con una primera frase que enganche (un problema real "
        "del autónomo). Reglas: español de España, tono cercano y práctico, máximo 260 caracteres, sin enlaces, "
        "máximo 1 hashtag, máximo 1 emoji, sin promesas exageradas. Devuelve SOLO el texto del post."
    )
    dia = datetime.date.today().toordinal()
    if franja == 2:  # el post de la tarde lleva llamada a la acción (sin enlace: los enlaces cuestan más en la API)
        if dia % 3 == 0:
            prompt += (" Termina mencionando de forma natural que en la bio está el Kit IA para Autónomos con 100 prompts "
                       "por 9 euros. No pongas ningún enlace.")
        else:
            prompt += (" Termina con una frase natural invitando a descargar gratis 10 prompts de IA para autónomos "
                       "desde el enlace de la bio. No pongas ningún enlace.")
    req = urllib.request.Request(
        f"{API}/models/{MODELO}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
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
    sys.stdout.reconfigure(line_buffering=True)
    tema = TEMAS[(datetime.date.today().toordinal() * 3 + turno()) % len(TEMAS)]
    for intento in range(4):  # el verificador puede pedir hasta 3 borradores
        try:
            texto = redactar(tema)
        except Exception as e:  # Gemini lento o caido: reintenta
            print(f"Intento {intento+1}: fallo al redactar ({e}); reintento")
            time.sleep(20)
            continue
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
