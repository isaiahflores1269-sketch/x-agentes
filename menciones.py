"""Agente de menciones: lee menciones nuevas en X, Gemini redacta una respuesta
y la deja como Issue en GitHub para que Isaias la apruebe (etiqueta 'aprobar')."""
import json, os, re, sys, urllib.request
from requests_oauthlib import OAuth1Session
import agente

GH = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}"
GH_H = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json", "Content-Type": "application/json"}


def gh(method, path, data=None):
    req = urllib.request.Request(GH + path, method=method, headers=GH_H,
                                 data=json.dumps(data).encode() if data else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 422:  # ya existe (etiquetas)
            return None
        raise


def x():
    return OAuth1Session(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                         os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def gemini(prompt):
    agente.MODELO = agente.MODELO or agente.elegir_modelo()
    req = urllib.request.Request(
        f"{agente.API}/models/{agente.MODELO}:generateContent",
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').strip()


def ultimo_id():
    ids = []
    for est in ("open", "closed"):
        for i in gh("GET", f"/issues?labels=mencion&state={est}&per_page=100") or []:
            m = re.search(r"Mención (\d+)", i["title"])
            if m: ids.append(int(m.group(1)))
    return max(ids) if ids else None


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    gh("POST", "/labels", {"name": "mencion", "color": "1d9bf0"})
    gh("POST", "/labels", {"name": "aprobar", "color": "2ea043", "description": "Publica la respuesta en X"})
    s = x()
    yo = s.get("https://api.x.com/2/users/me").json()["data"]["id"]
    params = {"max_results": 10, "expansions": "author_id", "user.fields": "username"}
    desde = ultimo_id()
    if desde: params["since_id"] = str(desde)
    else: params["max_results"] = 5  # primera vez: solo las 5 últimas
    r = s.get(f"https://api.x.com/2/users/{yo}/mentions", params=params)
    print(r.status_code); r.raise_for_status()
    data = r.json()
    usuarios = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
    menciones = [m for m in data.get("data", []) if m["author_id"] != yo]
    print(f"{len(menciones)} menciones nuevas")
    for m in reversed(menciones):
        user = usuarios.get(m["author_id"], "?")
        try:
            borrador = gemini(
                "Eres @IAautonomosES (IA para Autónomos), cuenta de X que ayuda a autónomos y pymes de España "
                f"con inteligencia artificial. @{user} te ha escrito: \"{m['text']}\". Redacta UNA respuesta: "
                "español de España, cercana, útil y concreta, máximo 250 caracteres, sin enlaces, sin hashtags. "
                "Si es spam u ofensivo responde solo: IGNORAR. Devuelve SOLO el texto.")
        except Exception as e:
            borrador = f"(Gemini falló: {e}) Escribe tú la respuesta en un comentario."
        gh("POST", "/issues", {
            "title": f"Mención {m['id']} de @{user}",
            "labels": ["mencion"],
            "body": (f"**@{user} escribió:**\n> {m['text']}\n\nhttps://x.com/{user}/status/{m['id']}\n\n"
                     f"**Respuesta propuesta:**\n<!--RESPUESTA-->\n{borrador}\n<!--FIN-->\n\n---\n"
                     "✅ Para publicarla: añade la etiqueta **aprobar**.\n"
                     "✏️ Para cambiarla: escribe tu versión como comentario y luego añade **aprobar**.\n"
                     "❌ Para ignorarla: cierra el issue."),
        })
        print("Issue creado para", m["id"])
