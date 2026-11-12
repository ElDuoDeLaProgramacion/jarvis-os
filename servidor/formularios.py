"""Formularios propios de Orión: páginas que diseña Orión, con su enlace, y las respuestas de vuelta a David.

Cada formulario vive en cola/formularios/<id>/:
  sitio/            la página (index.html y lo que use); es lo único que se sirve
  meta.json         título, cuándo se creó, si avisa a David y si está cerrado
  respuestas.jsonl  una línea JSON por respuesta (nunca se sirve)

La API (servidor/api.py) lo sirve en https://<dominio de la API>/f/<id>/ y recibe las respuestas con un POST a esa
misma dirección: sin clave, porque lo llena cualquiera que tenga el enlace. Por eso la página va con
"Content-Security-Policy: sandbox" (sin allow-same-origin): corre como un origen aparte y no puede leer la clave de
la app del celular, que vive en ese mismo dominio. Cada respuesta nueva deja un aviso en cola/whatsapp/avisos/
y el puente de WhatsApp se lo manda a David.
"""
import json
import os
import re
import secrets
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
ID = re.compile(r"^[a-z0-9]{10}$")
MAX_CUERPO = 64 * 1024          # una respuesta de formulario es texto: 64 KB sobra
MAX_CAMPOS = 60
MAX_VALOR = 4000
MAX_SITIO = 15 * 1024 * 1024
MAX_RESPUESTAS = 5000
POR_IP, VENTANA = 20, 600       # respuestas por IP cada 10 min: que nadie llene el disco ni el WhatsApp de David
IGNORAR = {".git", "node_modules", ".env", ".DS_Store", "__pycache__"}
CSP = ("sandbox allow-forms allow-scripts allow-popups allow-modals allow-downloads; "
       "default-src * data: blob: 'unsafe-inline' 'unsafe-eval'; form-action 'self' *")


class Error(ValueError):
    pass


def raiz():
    return Path(os.environ.get("JARVIS_FORMULARIOS", RAIZ / "cola" / "formularios"))


def avisos():
    return Path(os.environ.get("JARVIS_AVISOS_WHATSAPP", RAIZ / "cola" / "whatsapp" / "avisos"))


def url(fid):
    """La dirección pública: JARVIS_FORMULARIOS_URL, o el dominio de la API (de JARVIS_SITIOS_URL o JARVIS_SERVIDOR)."""
    base = os.environ.get("JARVIS_FORMULARIOS_URL", "").strip().rstrip("/")
    if not base:
        sitios = urlparse(os.environ.get("JARVIS_SITIOS_URL", "").strip())
        if sitios.hostname and sitios.hostname.startswith("sitios."):
            base = f"{sitios.scheme or 'https'}://{sitios.hostname[7:]}"
        else:
            base = os.environ.get("JARVIS_SERVIDOR", "").strip().rstrip("/")
    return f"{base}/f/{fid}/" if base else f"/f/{fid}/"


def _meta(fid):
    try:
        return json.loads((raiz() / fid / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _guardar_meta(fid, meta):
    destino = raiz() / fid / "meta.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(destino)


def crear(origen, titulo, avisar=True, dias=None):
    """Copia la página (un .html o una carpeta con index.html) y devuelve (id, url)."""
    origen = Path(origen)
    if origen.is_file():
        if origen.suffix.lower() not in (".html", ".htm"):
            raise Error("el formulario tiene que ser un .html o una carpeta con index.html")
        archivos = [(origen, Path("index.html"))]
    elif (origen / "index.html").is_file():
        archivos = [(f, f.relative_to(origen)) for f in sorted(origen.rglob("*"))
                    if f.is_file() and not f.is_symlink() and not any(p in IGNORAR for p in f.relative_to(origen).parts)]
    else:
        raise Error(f"no encuentro {origen} (ni un .html ni una carpeta con index.html)")
    if sum(f.stat().st_size for f, _ in archivos) > MAX_SITIO:
        raise Error("el formulario pesa más de 15 MB")
    titulo = " ".join(str(titulo or "Formulario").split())[:120]
    fid = "".join(secrets.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(10))
    carpeta = raiz() / fid
    (carpeta / "sitio").mkdir(parents=True)
    for f, rel in archivos:
        destino = carpeta / "sitio" / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, destino)
    meta = {"titulo": titulo, "creado": datetime.now().isoformat(timespec="seconds"), "avisar": bool(avisar),
            "cerrado": False, "cierra": (time.time() + dias * 86400) if dias else None}
    _guardar_meta(fid, meta)
    return fid, url(fid)


def lista():
    base = raiz()
    if not base.is_dir():
        return []
    salida = []
    for d in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = ID.match(d.name) and _meta(d.name)
        if meta:
            salida.append({"id": d.name, "url": url(d.name), "respuestas": len(respuestas(d.name)),
                           "abierto": abierto(meta), **meta})
    return salida


def abierto(meta):
    return bool(meta) and not meta.get("cerrado") and not (meta.get("cierra") and time.time() > meta["cierra"])


def cambiar(fid, **cambios):
    meta = _meta(fid) if ID.match(fid or "") else None
    if not meta:
        raise Error("no existe ese formulario")
    meta.update(cambios)
    _guardar_meta(fid, meta)
    return meta


def respuestas(fid):
    if not ID.match(fid or ""):
        return []
    try:
        lineas = (raiz() / fid / "respuestas.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    salida = []
    for linea in lineas:
        try:
            salida.append(json.loads(linea))
        except ValueError:
            pass
    return salida


def archivo(fid, ruta):
    """El archivo de la página a servir, o None. Nunca sale de sitio/ (meta.json y respuestas quedan fuera)."""
    if not ID.match(fid or "") or not _meta(fid):
        return None
    base = (raiz() / fid / "sitio").resolve()
    destino = (base / (ruta or "index.html")).resolve()
    if destino.is_dir():
        destino = destino / "index.html"
    if base != destino and base not in destino.parents:
        return None
    return destino if destino.is_file() else None


def leer_cuerpo(tipo, cuerpo):
    """Las respuestas como {campo: valor o lista de valores}, desde JSON o desde un <form> normal."""
    tipo = (tipo or "").split(";")[0].strip().lower()
    texto = cuerpo.decode("utf-8", "replace")
    if tipo == "application/json":
        try:
            datos = json.loads(texto or "{}")
        except ValueError:
            raise Error("json inválido")
        if not isinstance(datos, dict):
            raise Error("se espera un objeto JSON")
    elif tipo in ("application/x-www-form-urlencoded", "text/plain", ""):
        datos = {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(texto, keep_blank_values=True).items()}
    else:
        raise Error("tipo de contenido no soportado (usa un <form> normal o JSON)")
    limpio = {}
    for k, v in list(datos.items())[:MAX_CAMPOS]:
        k = " ".join(str(k).split())[:80]
        if not k or k.startswith("_"):      # _gotcha, _redirect...: campos internos de la página
            continue
        if isinstance(v, list):
            v = [str(x)[:MAX_VALOR] for x in v[:50]]
        elif isinstance(v, (dict,)):
            v = json.dumps(v, ensure_ascii=False)[:MAX_VALOR]
        else:
            v = str(v if v is not None else "")[:MAX_VALOR]
        limpio[k] = v
    return limpio


class Limite:
    def __init__(self):
        self.veces, self.cerrojo = {}, threading.Lock()

    def permitido(self, ip):
        ahora = time.time()
        with self.cerrojo:
            recientes = [t for t in self.veces.get(ip, []) if ahora - t < VENTANA]
            if len(recientes) >= POR_IP:
                self.veces[ip] = recientes
                return False
            self.veces[ip] = recientes + [ahora]
            if len(self.veces) > 10000:
                self.veces = {k: v for k, v in self.veces.items() if v and ahora - v[-1] < VENTANA}
            return True


LIMITE = Limite()
_escritura = threading.Lock()


def responder(fid, datos):
    """Guarda una respuesta y deja el aviso para WhatsApp. Devuelve el número de respuesta."""
    meta = _meta(fid) if ID.match(fid or "") else None
    if not meta:
        raise Error("no existe ese formulario")
    if not abierto(meta):
        raise Error("este formulario ya está cerrado")
    if not any((v if isinstance(v, str) else "".join(v)).strip() for v in datos.values()):
        raise Error("la respuesta está vacía")
    with _escritura:
        previas = len(respuestas(fid))
        if previas >= MAX_RESPUESTAS:
            raise Error("este formulario ya no recibe más respuestas")
        registro = {"fecha": datetime.now().isoformat(timespec="seconds"), "respuesta": datos}
        with open(raiz() / fid / "respuestas.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    n = previas + 1
    if meta.get("avisar", True):
        avisar(fid, meta, datos, n)
    return n


def resumen_respuesta(datos, largo=900):
    lineas = []
    for k, v in datos.items():
        valor = ", ".join(v) if isinstance(v, list) else v
        if not valor.strip():
            continue
        lineas.append(f"- {k}: {' '.join(valor.split())[:300]}")
    texto = "\n".join(lineas)
    return texto if len(texto) <= largo else texto[:largo] + "\n…"


def avisar(fid, meta, datos, n):
    carpeta = avisos()
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        texto = (f"Llegó la respuesta {n} a tu formulario «{meta.get('titulo', 'Formulario')}»:\n"
                 f"{resumen_respuesta(datos)}\n\nPídeme \"resume las respuestas del formulario\" cuando quieras.")
        (carpeta / f"{time.time_ns()}-formulario-{fid}.txt").write_text(texto, encoding="utf-8")
    except OSError:
        pass


GRACIAS = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title><style>
:root{{color-scheme:light dark}}body{{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;
background:radial-gradient(circle at 30% 20%,#7c3aed33,transparent 60%),radial-gradient(circle at 80% 80%,#06b6d433,transparent 60%),#0b1020;color:#e8ecff}}
main{{max-width:28rem;padding:2.5rem 2rem;text-align:center;border-radius:1.5rem;background:#ffffff0d;border:1px solid #ffffff1f;backdrop-filter:blur(8px)}}
.m{{font-size:3rem;line-height:1}}h1{{font-size:1.5rem;margin:.8rem 0 .4rem}}p{{opacity:.8;margin:0}}
</style></head><body><main><div class="m">{marca}</div><h1>{titulo}</h1><p>{texto}</p></main></body></html>"""


def pagina(titulo, texto, ok=True):
    from html import escape
    return GRACIAS.format(titulo=escape(titulo), texto=escape(texto), marca="✓" if ok else "×").encode()
