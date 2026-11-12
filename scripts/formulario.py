#!/usr/bin/env python3
"""Formularios propios de Orión (habilidad `formularios`). Corre en el servidor, donde vive la API.

  python3 scripts/formulario.py crear <pagina.html | carpeta> --titulo "Encuesta del taller" [--sin-avisos] [--dias 7]
  python3 scripts/formulario.py lista
  python3 scripts/formulario.py respuestas <id> [--json]
  python3 scripts/formulario.py cerrar <id>  |  abrir <id>  |  avisos <id> si|no

"crear" imprime el enlace para compartir. Cada respuesta llega a David por WhatsApp (salvo --sin-avisos)
y queda en cola/formularios/<id>/respuestas.jsonl.
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "servidor"))
import formularios  # noqa: E402


def cargar_env():
    f = RAIZ / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def resumen(fid):
    meta = formularios._meta(fid)
    if not meta:
        raise formularios.Error("no existe ese formulario")
    rs = formularios.respuestas(fid)
    print(f"{meta['titulo']} ({formularios.url(fid)}): {len(rs)} respuesta(s), "
          f"{'abierto' if formularios.abierto(meta) else 'cerrado'}.")
    if not rs:
        return
    # Conteo por campo cuando los valores se repiten (opciones); el texto libre se lista.
    campos = {}
    for r in rs:
        for k, v in r["respuesta"].items():
            campos.setdefault(k, []).extend(v if isinstance(v, list) else [v])
    for k, valores in campos.items():
        conteo = Counter(v for v in valores if v.strip())
        if not conteo:
            continue
        print(f"\n## {k}")
        if conteo and len(conteo) <= max(8, len(valores) // 2):
            for v, n in conteo.most_common():
                print(f"- {v}: {n}")
        else:
            for v in valores[-30:]:
                if v.strip():
                    print(f"- {' '.join(v.split())[:300]}")


def main():
    cargar_env()
    p = argparse.ArgumentParser(description="Formularios propios de Orión")
    sub = p.add_subparsers(dest="orden", required=True)
    c = sub.add_parser("crear")
    c.add_argument("origen")
    c.add_argument("--titulo", required=True)
    c.add_argument("--sin-avisos", action="store_true")
    c.add_argument("--dias", type=float)
    sub.add_parser("lista")
    r = sub.add_parser("respuestas")
    r.add_argument("id")
    r.add_argument("--json", action="store_true")
    for nombre in ("cerrar", "abrir"):
        sub.add_parser(nombre).add_argument("id")
    a = sub.add_parser("avisos")
    a.add_argument("id")
    a.add_argument("valor", choices=["si", "no"])
    args = p.parse_args()
    try:
        if args.orden == "crear":
            fid, enlace = formularios.crear(args.origen, args.titulo, not args.sin_avisos, args.dias)
            print(f"Formulario creado (id {fid}): {enlace}")
            if enlace.startswith("/"):
                print("Ojo: no sé el dominio del servidor. Pon JARVIS_FORMULARIOS_URL=https://<dominio de la API> en .env.")
        elif args.orden == "lista":
            filas = formularios.lista()
            if not filas:
                print("No hay formularios.")
            for f in filas:
                print(f"{f['id']}  {f['titulo']}  {f['respuestas']} resp.  {'abierto' if f['abierto'] else 'cerrado'}  {f['url']}")
        elif args.orden == "respuestas":
            if args.json:
                print(json.dumps(formularios.respuestas(args.id), ensure_ascii=False, indent=1))
            else:
                resumen(args.id)
        elif args.orden in ("cerrar", "abrir"):
            formularios.cambiar(args.id, cerrado=args.orden == "cerrar", **({"cierra": None} if args.orden == "abrir" else {}))
            print("Cerrado: ya no recibe respuestas." if args.orden == "cerrar" else "Abierto otra vez.")
        elif args.orden == "avisos":
            formularios.cambiar(args.id, avisar=args.valor == "si")
            print("Te aviso por WhatsApp de cada respuesta." if args.valor == "si" else "Ya no te aviso de cada respuesta.")
    except formularios.Error as e:
        sys.exit(f"No pude: {e}")


if __name__ == "__main__":
    main()
