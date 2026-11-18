"""Publica en Threads (API oficial de Meta, gratis). Si no hay THREADS_TOKEN, no hace nada."""
import json, os, time, urllib.parse, urllib.request

API = "https://graph.threads.net/v1.0"


def _post(ruta, params):
    params["access_token"] = os.environ["THREADS_TOKEN"]
    req = urllib.request.Request(f"{API}/{ruta}", data=urllib.parse.urlencode(params).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def publicar(texto, responder_a=None):
    """Devuelve el id del post en Threads, o None si no está configurado o falla (nunca rompe X)."""
    if not os.environ.get("THREADS_TOKEN"):
        return None
    try:
        p = {"media_type": "TEXT", "text": texto}
        if responder_a:
            p["reply_to_id"] = responder_a
        cont = _post("me/threads", p)["id"]
        time.sleep(5)  # Meta recomienda esperar antes de publicar el contenedor
        pid = _post("me/threads_publish", {"creation_id": cont})["id"]
        print("Threads OK", pid)
        return pid
    except Exception as e:
        print("Threads falló:", e)
        return None


def renovar_token():
    """Alarga 60 días el token de larga duración (se llama a diario)."""
    if not os.environ.get("THREADS_TOKEN"):
        return
    try:
        url = (f"https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token"
               f"&access_token={os.environ['THREADS_TOKEN']}")
        with urllib.request.urlopen(url, timeout=60) as r:
            print("Token de Threads renovado, caduca en", json.load(r).get("expires_in"), "s")
    except Exception as e:
        print("No se pudo renovar el token de Threads:", e)
