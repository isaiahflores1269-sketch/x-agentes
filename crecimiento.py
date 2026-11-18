"""Agente de crecimiento: busca posts recientes de autónomos/pymes españoles, Gemini propone
una respuesta útil (sin autopromoción) y la deja como Issue para aprobar con la etiqueta 'aprobar'."""
import os, re, sys, time
from menciones import gh, x, gemini

# Vocabulario propio de España y personas hablando en primera persona (no partidos ni medios)
CONSULTA = ('("soy autónomo" OR "soy autónoma" OR "como autónomo" OR "mi cuota de autónomo" OR "tarifa plana" '
            'OR "modelo 303" OR "Verifactu" OR "mi gestoría" OR "mis clientes") '
            'lang:es -is:retweet -is:reply -is:quote -has:links -is:verified')
# Política y temas polémicos: nunca responder
POLITICA = re.compile(r"(\bpp\b|ppopular|psoe|\bvox\b|\bsumar\b|podemos|\biu\b|feij|abascal|gobierno|ministr|"
                      r"diputad|congreso|senado|elecciones|izquierda|derecha|facha|comunis|independentis|"
                      r"frenteampl|pedro s[aá]nchez|yolanda d[ií]az|#\w*29n)", re.I)
MAX_PROPUESTAS = 5


def ya_vistos():
    ids = set()
    for est in ("open", "closed"):
        for i in gh("GET", f"/issues?labels=crecimiento&state={est}&per_page=100") or []:
            m = re.search(r"Post (\d+)", i["title"])
            if m: ids.add(m.group(1))
    return ids


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    gh("POST", "/labels", {"name": "crecimiento", "color": "ffc93c"})
    gh("POST", "/labels", {"name": "aprobar", "color": "2ea043", "description": "Publica la respuesta en X"})
    s = x()
    r = s.get("https://api.x.com/2/tweets/search/recent", params={
        "query": CONSULTA, "max_results": 10, "expansions": "author_id",
        "tweet.fields": "public_metrics,created_at", "user.fields": "username,public_metrics"})
    print(r.status_code); r.raise_for_status()
    data = r.json()
    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
    vistos = ya_vistos()
    posts = [p for p in data.get("data", []) if p["id"] not in vistos
             and users.get(p["author_id"], {}).get("username", "").lower() != "iaautonomoses"
             and not POLITICA.search(p["text"]) and len(p["text"]) > 40]
    # prioriza los que tienen algo de interacción y autores con audiencia
    def puntos(p):
        m = p.get("public_metrics", {}); f = users.get(p["author_id"], {}).get("public_metrics", {}).get("followers_count", 0)
        return m.get("reply_count", 0) * 3 + m.get("like_count", 0) + min(f, 20000) / 1000
    posts.sort(key=puntos, reverse=True)
    print(f"{len(posts)} candidatos")
    for p in posts[:MAX_PROPUESTAS]:
        user = users.get(p["author_id"], {}).get("username", "?")
        borrador = None
        for _ in range(3):  # Gemini a veces da 503: reintenta
            try:
                borrador = gemini(
                    "Eres @IAautonomosES, cuenta de X que ayuda a autónomos y pymes de España con IA. "
                    f"@{user} ha publicado: \"{p['text']}\". Escribe UNA respuesta que aporte valor real "
                    "(un consejo concreto, una herramienta o un prompt corto) relacionado con lo que dice. "
                    "Español de España, cercana, máximo 240 caracteres, sin enlaces, sin hashtags, "
                    "sin vender nada ni mencionar tu cuenta. Si el post no parece de alguien de España, no tiene que ver con negocios, es "
                    "polémico (política, quejas personales) o es spam, responde solo: IGNORAR. Devuelve SOLO el texto.")
                break
            except Exception as e:
                print("Gemini falló:", e)
                time.sleep(20)
        if not borrador:
            print("Sin borrador, se salta", p["id"]); continue
        if borrador.upper().startswith("IGNORAR"):
            print("Ignorado", p["id"]); continue
        gh("POST", "/issues", {
            "title": f"Post {p['id']} de @{user}",
            "labels": ["crecimiento"],
            "body": (f"**@{user} publicó:**\n> {p['text']}\n\nhttps://x.com/{user}/status/{p['id']}\n\n"
                     f"**Respuesta propuesta:**\n<!--RESPUESTA-->\n{borrador}\n<!--FIN-->\n\n---\n"
                     "✅ Publicar: añade la etiqueta **aprobar**.\n"
                     "✏️ Cambiar: escribe tu versión como comentario y luego pon **aprobar**.\n"
                     "❌ Descartar: cierra el issue."),
        })
        print("Propuesta creada para", p["id"])
