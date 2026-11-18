"""Publica en X la respuesta aprobada de un Issue (se lanza al poner la etiqueta 'aprobar')."""
import json, os, re, sys, urllib.request
from requests_oauthlib import OAuth1Session
from menciones import gh, x

if __name__ == "__main__":
    n = os.environ["ISSUE_NUMBER"]
    issue = gh("GET", f"/issues/{n}")
    tid = re.search(r"(?:Mención|Post) (\d+)", issue["title"]).group(1)
    owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    comentarios = [c["body"].strip() for c in gh("GET", f"/issues/{n}/comments") or []
                   if c["user"]["login"] == owner]
    if comentarios:
        texto = comentarios[-1]
    else:
        texto = re.search(r"<!--RESPUESTA-->\n(.*?)\n<!--FIN-->", issue["body"], re.S).group(1).strip()
    if not texto or texto.upper().startswith("IGNORAR") or texto.startswith("(Gemini falló"):
        gh("POST", f"/issues/{n}/comments", {"body": "No hay respuesta válida que publicar."})
        sys.exit(0)
    if len(texto) > 280 or re.search(r"https?://|www\.", texto, re.I):
        gh("POST", f"/issues/{n}/comments", {"body": "⚠️ La respuesta pasa de 280 caracteres o lleva enlace. Corrígela en un comentario y vuelve a poner 'aprobar'."})
        gh("DELETE", f"/issues/{n}/labels/aprobar")
        sys.exit(1)
    r = x().post("https://api.x.com/2/tweets", json={"text": texto, "reply": {"in_reply_to_tweet_id": tid}})
    print(r.status_code, r.text)
    if r.status_code == 403:  # X puede bloquear respuestas por API a quien no te ha mencionado
        gh("POST", f"/issues/{n}/comments", {"body": "⚠️ X no permite publicar esta respuesta por API. "
           f"Ábrelo y pégala a mano:\n\nhttps://x.com/i/status/{tid}\n\n```\n{texto}\n```"})
        sys.exit(0)
    r.raise_for_status()
    nuevo = r.json()["data"]["id"]
    gh("POST", f"/issues/{n}/comments", {"body": f"✅ Publicada: https://x.com/i/status/{nuevo}"})
    gh("PATCH", f"/issues/{n}", {"state": "closed"})
