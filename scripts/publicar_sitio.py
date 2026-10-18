#!/usr/bin/env python3
"""Publica una página web en el servidor de Orión y dice su dirección. Solo cuando David dice "publícalo".

  python3 scripts/publicar_sitio.py <carpeta> --nombre angele      -> https://sitios.<dominio>/angele/
  python3 scripts/publicar_sitio.py --quitar angele
  python3 scripts/publicar_sitio.py --lista

En el servidor escribe directo en JARVIS_SITIOS; en el PC lo manda a la API del servidor
(JARVIS_SERVIDOR + JARVIS_API_TOKEN). Volver a publicar con el mismo nombre reemplaza la versión anterior.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "servidor"))
import sitios  # noqa: E402


def cargar_env():
    f = RAIZ / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def en_el_servidor():
    """Aquí está la carpeta de sitios y se puede escribir: estamos en el servidor."""
    base = sitios.raiz()
    return base.is_dir() and os.access(base, os.W_OK)


def al_servidor(ruta, nombre, datos=b""):
    base = os.environ.get("JARVIS_SERVIDOR", "").strip().rstrip("/")
    token = os.environ.get("JARVIS_API_TOKEN", "").strip()
    if not base or not token:
        raise SystemExit("No sé dónde está el servidor: falta JARVIS_SERVIDOR o JARVIS_API_TOKEN en .env.")
    pedido = urllib.request.Request(f"{base}{ruta}?nombre={urllib.parse.quote(nombre)}", data=datos, method="POST",
                                    headers={"Authorization": f"Bearer {token}",
                                             "Content-Type": "application/zip"})
    try:
        with urllib.request.urlopen(pedido, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read()).get("error", "")
        except ValueError:
            detalle = ""
        raise SystemExit(f"El servidor no lo aceptó ({e.code}): {detalle}")
    except OSError as e:
        raise SystemExit(f"No llego al servidor ({base}): {e}")


def main():
    cargar_env()
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("carpeta", nargs="?")
    a.add_argument("--nombre", help="nombre corto del sitio (por defecto, el de la carpeta)")
    a.add_argument("--quitar", metavar="NOMBRE", help="despublica ese sitio")
    a.add_argument("--lista", action="store_true", help="sitios publicados (en el servidor)")
    args = a.parse_args()
    if os.environ.get("JARVIS_AUTOMATICO") == "1":
        raise SystemExit("Publicar solo cuando David lo pide; desde la cola no.")
    try:
        if args.lista:
            for n in sitios.lista():
                print(f"{n}  {sitios.url(n)}")
            return 0
        if args.quitar:
            nombre = sitios.limpiar_nombre(args.quitar)
            ok = sitios.quitar(nombre) if en_el_servidor() else al_servidor("/api/sitios/quitar", nombre)["ok"]
            print(f"Quitado: {nombre}" if ok else f"No había un sitio llamado {nombre}.")
            return 0
        if not args.carpeta:
            a.error("falta la carpeta del sitio")
        carpeta = Path(args.carpeta).expanduser().resolve()
        nombre = sitios.limpiar_nombre(args.nombre or carpeta.name)
        datos = sitios.empaquetar(carpeta)
        if en_el_servidor():
            n = sitios.instalar(datos, nombre)
            enlace = sitios.url(nombre)
        else:
            r = al_servidor("/api/sitios/publicar", nombre, datos)
            n, enlace = r["archivos"], r["url"]
    except sitios.Error as e:
        raise SystemExit(f"No se pudo publicar: {e}")
    print(f"Publicado ({n} archivos): {enlace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
