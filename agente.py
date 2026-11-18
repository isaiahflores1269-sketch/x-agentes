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
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
ESTACIONES = {12: "invierno", 1: "invierno", 2: "invierno", 3: "primavera", 4: "primavera", 5: "primavera",
              6: "verano", 7: "verano", 8: "verano", 9: "otoño", 10: "otoño", 11: "otoño"}


CAMPANAS = {
    1: "cuesta de enero, rebajas, modelos trimestrales de Hacienda hasta el día 30",
    2: "San Valentín, planificación del trimestre",
    3: "fin del primer trimestre, primavera, Semana Santa cercana",
    4: "Semana Santa, modelos trimestrales de Hacienda hasta el día 20, campaña de la Renta",
    5: "campaña de la Renta, preparar el verano",
    6: "fin de la Renta, inicio del verano, cierre del semestre",
    7: "verano, modelos trimestrales hasta el día 20, vacaciones",
    8: "agosto y vacaciones, preparar la vuelta en septiembre",
    9: "vuelta al cole y a la actividad, fin del tercer trimestre",
    10: "modelos trimestrales hasta el día 20, Halloween, preparar Black Friday",
    11: "Black Friday, Cyber Monday, preparar Navidad y el cierre de año",
    12: "Navidad, cierre de año, planificar el año nuevo",
}


def contexto_fecha():
    """Frase con la fecha real, para que la IA no hable de otra época del año."""
    hoy = datetime.date.today()
    mes, est = MESES[hoy.month - 1], ESTACIONES[hoy.month]
    return (f"CONTEXTO: hoy es {hoy.day} de {mes} de {hoy.year} ({est} en España). Si mencionas una época del año, "
            f"festividades o campañas, que sean las de ahora o las próximas semanas ({CAMPANAS[hoy.month]}). "
            f"No hables de otra estación, mes o año. ")


def fuera_de_fecha(t):
    """Detecta menciones a estaciones o meses lejanos a la fecha actual."""
    hoy = datetime.date.today()
    est_actual = ESTACIONES[hoy.month]
    vecinas = {ESTACIONES[(hoy.month % 12) + 1], est_actual}
    malas = [e for e in ("verano", "primavera", "otoño", "invierno") if e not in vecinas and re.search(rf"\b{e}\b", t, re.I)]
    cerca = {MESES[(hoy.month - 1 + d) % 12] for d in (-1, 0, 1, 2)}
    malas += [m for m in MESES if m not in cerca and re.search(rf"\b{m}\b", t, re.I)]
    for y in re.findall(r"\b(20\d\d)\b", t):
        if int(y) not in (hoy.year, hoy.year + 1):
            malas.append(y)
    return malas


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
    prompt = contexto_fecha() + (
        "Eres el community manager de la cuenta de X @IAautonomosES (IA para Autónomos), "
        "dirigida a autónomos y pymes de España. Escribe UN solo post para X sobre: " + tema +
        ". Formato: " + FORMATOS[franja] + ". Empieza con una primera frase que enganche (un problema real "
        "del autónomo). Reglas: español de España, tono cercano y práctico, MÁXIMO 220 caracteres en total, sin enlaces, "
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


def acortar(texto):
    req = urllib.request.Request(
        f"{API}/models/{MODELOS[0]}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text":
            contexto_fecha() + "Acorta este post de X a menos de 240 caracteres manteniendo el gancho, la idea y la frase final "
            "(sin enlaces). Devuelve SOLO el texto: " + texto}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').strip()


def verificar(t):
    problemas = []
    if not t: problemas.append("vacío")
    if len(t) > 280: problemas.append("más de 280 caracteres")
    if re.search(r"https?://|www\.", t, re.I): problemas.append("contiene enlace")
    if t.count("#") > 2: problemas.append("demasiados hashtags")
    if fuera_de_fecha(t): problemas.append(f"habla de otra época del año: {fuera_de_fecha(t)}")
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
        if problemas == ["más de 280 caracteres"]:  # agente corrector: acorta en vez de tirar el borrador
            try:
                corto = acortar(texto)
                if not verificar(corto):
                    texto, problemas = corto, []
            except Exception as e:
                print("No se pudo acortar:", e)
        print(f"Borrador {intento+1}: {texto}\nProblemas: {problemas or 'ninguno'}")
        if not problemas:
            break
    else:
        sys.exit("Ningún borrador pasó la verificación; hoy no se publica.")
    if os.environ.get("SOLO_PRUEBA") == "1":
        print("Modo prueba: no se publica.")
    else:
        publicar(texto)
