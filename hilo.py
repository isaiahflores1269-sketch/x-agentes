"""Agente de hilos: 2 veces por semana publica un hilo de 5 posts (los hilos son lo que más alcance
y seguidores da en X). Mismo control de calidad que los posts diarios."""
import datetime, json, os, re, sys, time, urllib.request
import agente

TEMAS_HILO = [
    "7 tareas de un autónomo que la IA hace en 5 minutos (con el prompt de cada una)",
    "Cómo responder a un cliente que no paga, paso a paso, usando IA",
    "Las 5 herramientas de IA gratis que todo autónomo español debería tener",
    "Cómo preparar Black Friday o una campaña de temporada en 1 hora con IA",
    "Guía para crear tus posts de toda la semana en 20 minutos con IA",
    "Errores que cometen los autónomos al usar ChatGPT y cómo evitarlos",
    "Cómo conseguir más reseñas en Google Maps con ayuda de la IA",
    "Plantilla con IA para hacer presupuestos que el cliente acepta antes",
    "Cómo entender cartas de Hacienda o la Seguridad Social con IA (sin sustituir a la gestoría)",
    "Cómo organizar la semana de un autónomo con IA para ganar 5 horas",
]


def pedir_hilo(tema):
    prompt = agente.contexto_fecha() + (
        "Eres el community manager de @IAautonomosES (IA para Autónomos), cuenta de X para autónomos y pymes de "
        f"España. Escribe un HILO de exactamente 5 posts sobre: {tema}. Post 1: gancho potente que prometa algo "
        "concreto y termine con '🧵👇'. Posts 2-4: un consejo práctico cada uno, numerados (2/, 3/, 4/), con "
        "ejemplo o prompt entre comillas. Post 5: resumen en una frase + invitación a seguir la cuenta y a descargar "
        "gratis 10 prompts desde el enlace de la bio (sin poner enlaces). Reglas: español de España, cercano, "
        "cada post MÁXIMO 230 caracteres, sin enlaces, máximo 1 hashtag en todo el hilo. "
        'Devuelve SOLO un JSON: ["post1","post2","post3","post4","post5"]')
    modelos = agente.MODELOS or agente.elegir_modelos()
    agente.MODELOS = modelos
    for intento in range(4):
        modelo = modelos[intento % len(modelos)]
        try:
            req = urllib.request.Request(
                f"{agente.API}/models/{modelo}:generateContent",
                data=json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                                 "generationConfig": {"responseMimeType": "application/json"}}).encode(),
                headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
            with urllib.request.urlopen(req, timeout=120) as r:
                texto = json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
            posts = [p.strip() for p in json.loads(texto)]
            for i, p in enumerate(posts):  # el corrector acorta los que se pasen
                if len(p) > 280:
                    posts[i] = agente.acortar(p)
            problemas = {i + 1: agente.verificar(p) for i, p in enumerate(posts) if agente.verificar(p)}
            print(f"Intento {intento+1}: {len(posts)} posts. Problemas: {problemas or 'ninguno'}")
            if len(posts) == 5 and not problemas:
                return posts
        except Exception as e:
            print(f"Intento {intento+1} falló: {e}")
            time.sleep(20)
    sys.exit("No se consiguió un hilo válido; hoy no se publica.")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    semana = datetime.date.today().isocalendar()[1]
    tema = TEMAS_HILO[(semana * 2 + datetime.date.today().weekday()) % len(TEMAS_HILO)]
    print("Tema:", tema)
    posts = pedir_hilo(tema)
    for i, p in enumerate(posts, 1):
        print(f"{i}: {p}")
    if os.environ.get("SOLO_PRUEBA") == "1":
        sys.exit(print("Modo prueba: no se publica."))
    from menciones import x
    s, anterior = x(), None
    for p in posts:
        cuerpo = {"text": p}
        if anterior:
            cuerpo["reply"] = {"in_reply_to_tweet_id": anterior}
        r = s.post("https://api.x.com/2/tweets", json=cuerpo)
        print(r.status_code, r.text)
        r.raise_for_status()
        anterior = r.json()["data"]["id"]
        time.sleep(3)
