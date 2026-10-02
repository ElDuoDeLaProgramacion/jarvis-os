"""
Lee los números de los canales de David y los imprime en JSON.

Los canales salen de la tabla "## Canales" de boveda/wiki/perfil.md.
- GitHub:    API pública, sin clave (seguidores, repos y estrellas).
- YouTube:   YouTube Data API v3; necesita YOUTUBE_API_KEY en .env (gratis, ver README).
- TikTok:    página pública del perfil (puede fallar si TikTok la bloquea).
- Instagram: endpoint público de la web (puede fallar si Instagram lo bloquea).

Uso:  python3 scripts/canales.py
Solo biblioteca estándar.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def cargar_env():
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip().strip('"'))


def canales_del_perfil():
    texto = (RAIZ / "boveda" / "wiki" / "perfil.md").read_text(encoding="utf-8")
    seccion = texto.split("## Canales", 1)[-1].split("\n## ", 1)[0]
    canales = []
    for fila in seccion.splitlines():
        celdas = [c.strip() for c in fila.strip().strip("|").split("|")]
        if len(celdas) >= 2 and celdas[0] and celdas[0] not in ("Plataforma",) and not set(celdas[0]) <= {"-"}:
            canales.append({"plataforma": celdas[0], "usuario": celdas[1]})
    return canales


def pedir(url, cabeceras=None):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR, **(cabeceras or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def github(usuario):
    datos = json.loads(pedir(f"https://api.github.com/users/{usuario}"))
    estrellas, pagina = 0, 1
    while True:
        repos = json.loads(pedir(f"https://api.github.com/users/{usuario}/repos?per_page=100&page={pagina}"))
        estrellas += sum(r.get("stargazers_count", 0) for r in repos)
        if len(repos) < 100:
            break
        pagina += 1
    return {"seguidores": datos["followers"], "repos_publicos": datos["public_repos"], "estrellas": estrellas}


def youtube(usuario):
    clave = os.environ.get("YOUTUBE_API_KEY")
    if not clave:
        raise RuntimeError("falta YOUTUBE_API_KEY en .env")
    handle = usuario if usuario.startswith("@") else "@" + usuario
    url = ("https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet"
           f"&forHandle={urllib.parse.quote(handle)}&key={clave}")
    items = json.loads(pedir(url)).get("items", [])
    if not items:
        raise RuntimeError(f"no se encontró el canal {handle}")
    e = items[0]["statistics"]
    return {
        "canal": items[0]["snippet"]["title"],
        "suscriptores": int(e.get("subscriberCount", 0)),
        "vistas": int(e.get("viewCount", 0)),
        "videos": int(e.get("videoCount", 0)),
    }


def tiktok(usuario):
    html = pedir(f"https://www.tiktok.com/@{usuario.lstrip('@')}")
    resultado = {}
    for campo, nombre in (("followerCount", "seguidores"), ("heartCount", "me_gusta"), ("videoCount", "videos")):
        m = re.search(rf'"{campo}":(\d+)', html)
        if m:
            resultado[nombre] = int(m.group(1))
    if not resultado:
        raise RuntimeError("TikTok no devolvió los datos (página bloqueada o cambió)")
    return resultado


def instagram(usuario):
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={usuario.lstrip('@')}"
    datos = json.loads(pedir(url, {"x-ig-app-id": "936619743392459"}))
    u = datos["data"]["user"]
    return {"seguidores": u["edge_followed_by"]["count"], "publicaciones": u["edge_owner_to_timeline_media"]["count"]}


LECTORES = {"github": github, "youtube": youtube, "tiktok": tiktok, "instagram": instagram}


def main():
    cargar_env()
    salida = []
    for c in canales_del_perfil():
        lector = LECTORES.get(c["plataforma"].lower())
        fila = dict(c)
        if not lector:
            fila["error"] = "plataforma sin lector"
        else:
            try:
                fila.update(lector(c["usuario"]))
            except Exception as e:  # cada canal falla por su cuenta sin tumbar a los demás
                fila["error"] = str(e)[:200]
        salida.append(fila)
    json.dump(salida, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
