"""Instagram: convierte el post del mediodía en una imagen con la marca y la publica.
Uso:  python instagram.py render   -> crea imagenes/AAAA-MM-DD.png desde ig_pendiente.json
      python instagram.py publish  -> publica esa imagen (debe estar ya en GitHub, repo público)"""
import datetime, html, json, os, sys, time, urllib.error, urllib.parse, urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "isaiahflores1269-sketch/x-agentes")
HOY = datetime.date.today().isoformat()
IMG = f"imagenes/{HOY}.png"
TOKEN = os.environ.get("INSTAGRAM_TOKEN", "")
# Token de usuario del sistema (empieza por EAA, no caduca) -> Graph de Facebook; si no, Graph de Instagram
SISTEMA = TOKEN.startswith("EAA")
API = "https://graph.facebook.com/v21.0" if SISTEMA else "https://graph.instagram.com/v21.0"
BUSINESS = "1720912682930055"


def cuenta():
    if not SISTEMA:
        return "me"
    return os.environ.get("IG_USER_ID", "17841480914390825")  # @iaautonomoses

PLANTILLA = """<html><head><link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap' rel='stylesheet'>
<style>body{{margin:0;width:1080px;height:1350px;background:#0f1b33;font-family:Inter;color:#fff;position:relative;overflow:hidden}}
.g{{position:absolute;inset:0;background-image:radial-gradient(#ffffff12 2px,transparent 2px);background-size:36px 36px}}
.b{{position:absolute;width:520px;height:520px;border-radius:50%;background:#2f6fed;opacity:.35;right:-160px;top:-160px}}
.tag{{position:absolute;left:90px;top:110px;background:#ffc93c;color:#0f1b33;font-weight:800;font-size:30px;padding:12px 28px;border-radius:40px}}
.t{{position:absolute;left:90px;right:90px;top:240px;bottom:240px;display:flex;align-items:center;font-size:{fs}px;line-height:1.35;font-weight:600;white-space:pre-wrap}}
.f{{position:absolute;left:90px;right:90px;bottom:90px;display:flex;justify-content:space-between;font-size:30px;color:#c9d3e6}}
.f b{{color:#ffc93c}}</style></head><body><div class='g'></div><div class='b'></div>
<div class='tag'>TRUCO DE IA DEL DÍA</div><div class='t'>{texto}</div>
<div class='f'><span>@iaautonomoses</span><span><b>10 prompts gratis</b> · enlace en la bio</span></div></body></html>"""


def render():
    if not os.path.exists("ig_pendiente.json"):
        sys.exit(print("Nada que publicar en Instagram hoy."))
    texto = json.load(open("ig_pendiente.json"))["texto"]
    limpio = "\n".join(l for l in texto.split("\n") if not l.strip().startswith("#")).strip()
    fs = 54 if len(limpio) < 160 else 46 if len(limpio) < 230 else 40
    from playwright.sync_api import sync_playwright
    os.makedirs("imagenes", exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = b.new_page(viewport={"width": 1080, "height": 1350})
        p.set_content(PLANTILLA.format(texto=html.escape(limpio), fs=fs), wait_until="networkidle")
        p.wait_for_timeout(500)
        p.screenshot(path=IMG)
        b.close()
    print("Imagen creada:", IMG)


def _post(ruta, params):
    params["access_token"] = TOKEN
    req = urllib.request.Request(f"{API}/{ruta}", data=urllib.parse.urlencode(params).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:400]}")


def publish():
    if not (os.environ.get("INSTAGRAM_TOKEN") and os.path.exists("ig_pendiente.json") and os.path.exists(IMG)):
        sys.exit(print("Instagram no configurado o sin imagen; se omite."))
    texto = json.load(open("ig_pendiente.json"))["texto"]
    caption = (texto + "\n\n🎁 10 prompts de IA gratis para tu negocio: enlace en la bio.\n"
               "#autonomos #pymes #inteligenciaartificial #emprendedores #chatgpt #productividad")
    url = f"https://raw.githubusercontent.com/{REPO}/main/{IMG}"
    time.sleep(20)  # que GitHub sirva ya la imagen recién subida
    yo = cuenta()
    cont = _post(f"{yo}/media", {"image_url": url, "caption": caption})["id"]
    for _ in range(10):  # esperar a que Instagram procese la imagen
        time.sleep(6)
        try:
            pid = _post(f"{yo}/media_publish", {"creation_id": cont})["id"]
            print("Instagram OK", pid)
            break
        except Exception as e:
            print("Esperando a Instagram...", e)
    else:
        sys.exit("Instagram no pudo publicar.")
    if SISTEMA:
        return  # el token de sistema no caduca
    try:  # alarga 60 días el token
        urllib.request.urlopen("https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token"
                               f"&access_token={os.environ['INSTAGRAM_TOKEN']}", timeout=60)
    except Exception as e:
        print("No se pudo renovar el token de Instagram:", e)


if __name__ == "__main__":
    {"render": render, "publish": publish}[sys.argv[1]]()
