#!/usr/bin/env python3
"""
IAs externas a Claude para JARVIS (habilidad "segunda-opinion"): Gemini de Google y, con una sola
clave, los modelos de OpenRouter (GPT, Gemini, Llama, DeepSeek, Mistral, Grok...).

    python3 scripts/ia_externa.py "pregunta"                     la primera IA configurada
    python3 scripts/ia_externa.py --ia gemini "pregunta"         una en concreto (gemini u openrouter)
    python3 scripts/ia_externa.py --modelo openai/gpt-5 "..."    un modelo de OpenRouter por su nombre
    python3 scripts/ia_externa.py --todas "pregunta"             todas las configuradas, una tras otra
    python3 scripts/ia_externa.py --archivo nota.md "pregunta"   añade el texto de un archivo a la pregunta
    python3 scripts/ia_externa.py modelos [gemini|openrouter|gratis]  modelos disponibles (gratis = los :free de OpenRouter)

Claves en .env (las pone David a mano): GEMINI_API_KEY y OPENROUTER_API_KEY.
Modelos opcionales: GEMINI_MODELO y OPENROUTER_MODELO (si no, Gemini usa el flash más nuevo
y OpenRouter un modelo gratis, de los que terminan en ":free"; así funciona sin saldo).
Solo usa la biblioteca estándar.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PROVEEDORES = {
    "gemini": {
        "clave": "GEMINI_API_KEY",
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "modelo": "GEMINI_MODELO",
        "alta": "https://aistudio.google.com/apikey",
    },
    "openrouter": {
        "clave": "OPENROUTER_API_KEY",
        "base": "https://openrouter.ai/api/v1",
        "modelo": "OPENROUTER_MODELO",
        "alta": "https://openrouter.ai/settings/keys",
    },
}

SISTEMA = ("Eres una IA consultada por JARVIS, el asistente de David, como segunda opinión. "
           "Responde en español, directo y con argumentos. Si no estás seguro de algo, dilo.")


def cargar_env():
    """Lee .env sin pisar lo que ya venga en el entorno (jarvis.sh ya lo exporta)."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        os.environ.setdefault(nombre.strip(), valor.strip().strip('"').strip("'"))


def configuradas():
    return [n for n, p in PROVEEDORES.items() if os.environ.get(p["clave"])]


def llamar(proveedor, ruta, cuerpo=None, timeout=120):
    p = PROVEEDORES[proveedor]
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(
        p["base"] + ruta, data=datos, method="POST" if datos else "GET",
        headers={"Authorization": f"Bearer {os.environ[p['clave']]}", "Content-Type": "application/json",
                 # OpenRouter muestra estos dos en su panel de uso; no llevan nada personal.
                 "HTTP-Referer": "https://github.com/ElDuoDeLaProgramacion/jarvis-os", "X-Title": "JARVIS"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        error = RuntimeError(f"{proveedor} respondió {e.code}: {detalle}")
        error.codigo = e.code
        raise error from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"No pude conectar con {proveedor}: {e.reason}") from None


def modelos(proveedor):
    datos = llamar(proveedor, "/models", timeout=30)
    ids = [m.get("id", "") for m in datos.get("data", [])]
    return sorted(i.removeprefix("models/") for i in ids if i)


def candidatos(proveedor):
    """Modelos a probar en orden. Si uno no tiene cuota gratis (429) o ya no existe (404), se pasa al siguiente."""
    elegido = os.environ.get(PROVEEDORES[proveedor]["modelo"])
    if elegido:
        return [elegido]
    if proveedor == "openrouter":
        # Sin saldo: los modelos gratis (":free"). Con saldo, David puede fijar OPENROUTER_MODELO=openrouter/auto.
        gratis = [m for m in modelos("openrouter") if m.endswith(":free")]
        orden = [m for familia in ("deepseek", "qwen", "llama", "gemini", "mistral", "gpt")
                 for m in gratis if familia in m]
        lista = list(dict.fromkeys(orden + gratis))
        if not lista:
            raise RuntimeError("OpenRouter no ofrece modelos gratis ahora; pon OPENROUTER_MODELO en .env")
        return lista[:6]
    # Gemini cambia de versión a menudo y no todos sus modelos tienen capa gratis: primero los "flash"
    # más nuevos, luego los "flash-lite".
    todos = [m for m in modelos("gemini") if "gemini" in m and "flash" in m
             and not any(x in m for x in ("image", "tts", "audio", "live", "embedding", "exp", "preview", "thinking"))]
    flash = sorted((m for m in todos if "lite" not in m), reverse=True)
    lite = sorted((m for m in todos if "lite" in m), reverse=True)
    if not todos:
        raise RuntimeError("No encontré un modelo Gemini flash; pon GEMINI_MODELO en .env "
                           "(mira la lista con: python3 scripts/ia_externa.py modelos gemini)")
    return (flash + lite)[:6]


def preguntar(proveedor, pregunta, modelo=None):
    ultimo = None
    for m in ([modelo] if modelo else candidatos(proveedor)):
        try:
            datos = llamar(proveedor, "/chat/completions", {
                "model": m,
                "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pregunta}],
            })
        except RuntimeError as e:
            if getattr(e, "codigo", None) in (404, 429):
                ultimo = e
                continue
            raise
        texto = (datos.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return datos.get("model") or m, texto.strip()
    raise RuntimeError(f"ningún modelo tiene cuota ahora (puede ser el límite diario gratis). Último error: {ultimo}")


def main():
    cargar_env()
    a = argparse.ArgumentParser(description="IAs externas a Claude para JARVIS")
    a.add_argument("pregunta", nargs="*")
    a.add_argument("--ia", choices=list(PROVEEDORES))
    a.add_argument("--modelo", help="modelo concreto (en OpenRouter: proveedor/modelo)")
    a.add_argument("--todas", action="store_true", help="preguntar a todas las configuradas")
    a.add_argument("--archivo", help="añadir el texto de este archivo a la pregunta")
    args = a.parse_args()

    listas = configuradas()
    if not listas:
        print("No hay ninguna IA externa conectada. David debe poner en .env al menos una clave:")
        for n, p in PROVEEDORES.items():
            print(f"  {p['clave']}=...   (se crea en {p['alta']})")
        return 2

    if args.pregunta[:1] == ["modelos"]:
        if args.pregunta[1:2] == ["gratis"] and "openrouter" in listas:
            print("\n".join(m for m in modelos("openrouter") if m.endswith(":free")))
            return 0
        for n in (args.pregunta[1:2] or listas):
            if n not in listas:
                print(f"{n}: sin clave en .env")
                continue
            print(f"## {n}")
            print("\n".join(modelos(n)))
        return 0

    pregunta = " ".join(args.pregunta).strip()
    if args.archivo:
        texto = Path(args.archivo).read_text(encoding="utf-8", errors="replace")[:60000]
        pregunta = f"{pregunta}\n\n--- {Path(args.archivo).name} ---\n{texto}"
    if not pregunta:
        a.error("falta la pregunta")

    if args.todas:
        elegidas = listas
    elif args.ia:
        elegidas = [args.ia]
    elif args.modelo and "openrouter" in listas:
        elegidas = ["openrouter"]
    else:
        elegidas = listas[:1]

    fallo = 0
    for n in elegidas:
        if n not in listas:
            print(f"## {n}\nSin clave: falta {PROVEEDORES[n]['clave']} en .env ({PROVEEDORES[n]['alta']}).\n")
            fallo = 1
            continue
        try:
            usado, texto = preguntar(n, pregunta, args.modelo if n == "openrouter" or args.ia else None)
            print(f"## {n} · {usado}\n{texto}\n")
        except RuntimeError as e:
            print(f"## {n}\nError: {e}\n")
            fallo = 1
    return fallo


if __name__ == "__main__":
    sys.exit(main())
