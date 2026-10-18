"""Páginas web que Orión publica en el servidor ("publícalo").

Cada sitio vive en <JARVIS_SITIOS>/<nombre>/ (por defecto /srv/orion-sitios) y Caddy lo sirve en
https://sitios.<dominio>/<nombre>/. Es otro origen distinto al de la API y la app: una página publicada
no puede leer la clave de Orión que guarda la app del celular.

Solo archivos estáticos (HTML, CSS, JS, imágenes, fuentes). Un proyecto con build (React, Vite...)
se publica ya construido (dist/ o build/).
"""
import io
import unicodedata
import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

NOMBRE = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")
MAX_ZIP = 40 * 1024 * 1024          # lo que llega por la red
MAX_TOTAL = 150 * 1024 * 1024       # descomprimido
MAX_ARCHIVOS = 3000
IGNORAR = {".git", "node_modules", ".venv", "__pycache__", ".env", ".DS_Store"}


class Error(ValueError):
    pass


def raiz():
    return Path(os.environ.get("JARVIS_SITIOS", "/srv/orion-sitios"))


def url(nombre):
    """La dirección pública del sitio: JARVIS_SITIOS_URL, o sitios.<host de JARVIS_SERVIDOR>."""
    base = os.environ.get("JARVIS_SITIOS_URL", "").strip().rstrip("/")
    if not base:
        host = urlparse(os.environ.get("JARVIS_SERVIDOR", "").strip()).hostname
        base = f"https://sitios.{host}" if host else ""
    return f"{base}/{nombre}/" if base else f"/{nombre}/"


def limpiar_nombre(texto):
    """'Página de Angelé' -> 'pagina-de-angele'."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:49].strip("-")
    if not NOMBRE.match(t):
        raise Error("nombre inválido: usa letras, números y guiones")
    return t


def empaquetar(carpeta):
    """Zip en memoria de la carpeta del sitio, sin .git, node_modules ni .env."""
    carpeta = Path(carpeta)
    if not (carpeta / "index.html").is_file():
        for sub in ("dist", "build", "out", "public"):
            if (carpeta / sub / "index.html").is_file():
                carpeta = carpeta / sub
                break
        else:
            raise Error(f"no hay index.html en {carpeta} (ni en dist/, build/, out/ o public/)")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(carpeta.rglob("*")):
            rel = f.relative_to(carpeta)
            if any(p in IGNORAR for p in rel.parts) or f.is_symlink() or not f.is_file():
                continue
            z.write(f, rel.as_posix())
    datos = buffer.getvalue()
    if len(datos) > MAX_ZIP:
        raise Error(f"el sitio pesa {len(datos) // 1048576} MB comprimido; el tope es {MAX_ZIP // 1048576} MB")
    return datos


def instalar(datos, nombre):
    """Descomprime el zip en <raíz>/<nombre>, reemplazando la versión anterior de una vez."""
    if not NOMBRE.match(nombre or ""):
        raise Error("nombre inválido")
    if len(datos) > MAX_ZIP:
        raise Error("demasiado grande")
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
        miembros = [m for m in z.infolist() if not m.is_dir()]
    except zipfile.BadZipFile:
        raise Error("no es un zip")
    if not miembros or len(miembros) > MAX_ARCHIVOS:
        raise Error("zip vacío o con demasiados archivos")
    if sum(m.file_size for m in miembros) > MAX_TOTAL:
        raise Error("demasiado grande descomprimido")
    nombres = [m.filename.replace("\\", "/") for m in miembros]
    for n in nombres:
        partes = n.split("/")
        if n.startswith("/") or ".." in partes or ":" in partes[0] or any(p in IGNORAR for p in partes):
            raise Error(f"ruta no permitida en el zip: {n}")
    # Si todo viene dentro de una sola carpeta, esa carpeta es el sitio.
    prefijo = ""
    primeras = {n.split("/")[0] for n in nombres}
    if len(primeras) == 1 and all("/" in n for n in nombres):
        prefijo = primeras.pop() + "/"
    if prefijo + "index.html" not in nombres:
        raise Error("falta index.html")

    base = raiz()
    base.mkdir(parents=True, exist_ok=True)
    nuevo = base / f".{nombre}.{time.time_ns()}"
    try:
        for m, n in zip(miembros, nombres):
            destino = nuevo / n[len(prefijo):]
            if nuevo.resolve() not in destino.resolve().parents:
                raise Error(f"ruta no permitida en el zip: {n}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as origen, open(destino, "wb") as salida:
                shutil.copyfileobj(origen, salida)
            destino.chmod(0o644)
        for d in [nuevo, *[p for p in nuevo.rglob("*") if p.is_dir()]]:
            d.chmod(0o755)
        final = base / nombre
        viejo = base / f".{nombre}.viejo.{time.time_ns()}"
        if final.exists():
            final.rename(viejo)
        nuevo.rename(final)
        shutil.rmtree(viejo, ignore_errors=True)
    finally:
        shutil.rmtree(nuevo, ignore_errors=True)
    return len(miembros)


def quitar(nombre):
    if not NOMBRE.match(nombre or ""):
        raise Error("nombre inválido")
    carpeta = raiz() / nombre
    if not carpeta.is_dir():
        return False
    shutil.rmtree(carpeta)
    return True


def lista():
    base = raiz()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and NOMBRE.match(p.name))
