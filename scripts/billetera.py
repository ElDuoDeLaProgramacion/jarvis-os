#!/usr/bin/env python3
"""
La billetera de Orión: un experimento en el que todas las IAs disponibles deciden, solas, qué hacer con
una cartera de cripto durante unos días (14 por defecto). Por ahora es SIMULADA: precios reales de
CoinGecko, dinero de mentira. Nada toca una billetera ni un exchange de verdad.

    python3 scripts/billetera.py iniciar [--saldo 1000] [--dias 14]   empieza el experimento
    python3 scripts/billetera.py ronda      una ronda: precios, voto de todas las IAs, decisión (la corre el cron)
    python3 scripts/billetera.py estado     cómo va: valor, posiciones, ganancia y comparación con solo guardar BTC
    python3 scripts/billetera.py pausar     no decide nada más hasta reanudar
    python3 scripts/billetera.py reanudar
    python3 scripts/billetera.py terminar   cierra el experimento y deja el informe final

Todo queda en boveda/outputs/billetera/: estado.json, decisiones.jsonl (cada voto de cada IA con su razón)
y diario/AAAA-MM-DD.md (lo legible). Reglas fijas que ninguna IA puede saltarse: como mucho
BILLETERA_TOPE_OPERACION (25 %) por operación, BILLETERA_MAX_OPERACIONES (3) operaciones al día, comisión
simulada de BILLETERA_COMISION (0,5 %) y solo los activos de BILLETERA_ACTIVOS.
Solo usa la biblioteca estándar.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ia_externa  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = Path(os.environ.get("BILLETERA_CARPETA", RAIZ / "boveda" / "outputs" / "billetera"))
COINGECKO = "https://api.coingecko.com/api/v3/coins/markets"


def ajustes():
    activos = os.environ.get("BILLETERA_ACTIVOS", "bitcoin:BTC,ethereum:ETH,solana:SOL")
    return {
        "activos": dict(par.split(":")[::-1] for par in activos.split(",") if ":" in par),  # BTC -> bitcoin
        "tope": float(os.environ.get("BILLETERA_TOPE_OPERACION", "25")),
        "max_operaciones": int(os.environ.get("BILLETERA_MAX_OPERACIONES", "3")),
        "comision": float(os.environ.get("BILLETERA_COMISION", "0.5")) / 100,
        "ias": int(os.environ.get("JARVIS_IAS_MAX", "8")),
    }


def leer_estado():
    f = CARPETA / "estado.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def guardar_estado(estado):
    CARPETA.mkdir(parents=True, exist_ok=True)
    tmp = CARPETA / "estado.json.tmp"
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(CARPETA / "estado.json")


def pausada():
    return (CARPETA / "PAUSA").exists()


def diario(texto, cuando=None):
    cuando = cuando or time.localtime()
    carpeta = CARPETA / "diario"
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / time.strftime("%Y-%m-%d.md", cuando)
    if not f.exists():
        f.write_text(f"---\nfecha: {time.strftime('%Y-%m-%d', cuando)}\ntipo: billetera\ntags: [billetera]\n---\n"
                     f"# Billetera de Orión · {time.strftime('%Y-%m-%d', cuando)}\n\n", encoding="utf-8")
    with f.open("a", encoding="utf-8") as h:
        h.write(texto.rstrip() + "\n\n")


def precios(activos):
    """{BTC: {precio, cambio_24h, cambio_7d}} de CoinGecko (gratis, sin clave)."""
    url = (f"{COINGECKO}?vs_currency=usd&ids={','.join(activos.values())}"
           "&price_change_percentage=24h,7d")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "orion-billetera"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            datos = json.load(r)
    except (OSError, ValueError) as e:
        raise RuntimeError(f"no pude leer los precios de CoinGecko: {e}") from None
    por_id = {d["id"]: d for d in datos}
    salida = {}
    for simbolo, ident in activos.items():
        d = por_id.get(ident)
        if d and d.get("current_price"):
            salida[simbolo] = {"precio": float(d["current_price"]),
                               "cambio_24h": round(d.get("price_change_percentage_24h_in_currency") or 0, 2),
                               "cambio_7d": round(d.get("price_change_percentage_7d_in_currency") or 0, 2)}
    if not salida:
        raise RuntimeError("CoinGecko no devolvió precios")
    return salida


def valor(estado, p):
    return estado["efectivo"] + sum(c * p[s]["precio"] for s, c in estado["posiciones"].items() if s in p)


SISTEMA = ("Eres una de varias IAs que manejan juntas una cartera SIMULADA de criptomonedas de Orión, el asistente "
           "de David, durante un experimento de {dias} días. Cada pocas horas cada IA vota una sola acción y gana la "
           "mayoría. Reglas fijas: solo los activos {activos}; como mucho {tope:g} % por operación; comisión de "
           "{comision:g} %; no hay apalancamiento, préstamos ni ventas en corto. Piensa en riesgo y no solo en "
           "ganancia: mantener también es una decisión válida. Responde SOLO con un objeto JSON, sin texto alrededor: "
           '{{"accion": "comprar" | "vender" | "mantener", "activo": "BTC" (o null si mantienes), '
           '"porcentaje": 1-{tope:g} (al comprar, % del valor total de la cartera; al vender, % de esa posición), '
           '"confianza": 1-10, "razon": "una o dos frases en español"}}')


def pregunta_de(estado, p, aj):
    total = valor(estado, p)
    lineas = [f"Fecha: {time.strftime('%Y-%m-%d %H:%M')} (día {dia_del_experimento(estado)} de {estado['dias']}).",
              f"Valor total: {total:.2f} USD (empezó con {estado['saldo_inicial']:.2f}).",
              f"Efectivo: {estado['efectivo']:.2f} USD.", "Posiciones:"]
    for s, c in estado["posiciones"].items():
        if c > 0 and s in p:
            lineas.append(f"- {s}: {c:.8f} = {c * p[s]['precio']:.2f} USD")
    if not any(c > 0 for c in estado["posiciones"].values()):
        lineas.append("- (ninguna, todo en efectivo)")
    lineas.append("Mercado ahora:")
    for s, d in p.items():
        lineas.append(f"- {s}: {d['precio']:.2f} USD, 24 h {d['cambio_24h']:+.2f} %, 7 días {d['cambio_7d']:+.2f} %")
    hoy = operaciones_de_hoy(estado)
    lineas.append(f"Operaciones hoy: {hoy} de {aj['max_operaciones']} permitidas.")
    if estado["historial"]:
        lineas.append("Últimas decisiones del grupo:")
        for h in estado["historial"][-6:]:
            lineas.append(f"- {h['fecha']}: {h['resumen']}")
    return "\n".join(lineas)


def dia_del_experimento(estado):
    return int((time.time() - estado["inicio"]) // 86400) + 1


def operaciones_de_hoy(estado):
    hoy = time.strftime("%Y-%m-%d")
    return sum(1 for h in estado["historial"] if h["fecha"].startswith(hoy) and h.get("operacion"))


def leer_voto(texto, activos, tope):
    """El JSON del voto, validado. Lo que no se entienda cuenta como 'mantener' para no inventar órdenes."""
    m = re.search(r"\{.*\}", texto or "", re.S)
    try:
        v = json.loads(m.group(0)) if m else {}
    except ValueError:
        v = {}
    accion = str(v.get("accion", "")).lower().strip()
    activo = str(v.get("activo") or "").upper().strip()
    try:
        porcentaje = max(0.0, min(float(v.get("porcentaje") or 0), tope))
    except (TypeError, ValueError):
        porcentaje = 0.0
    razon = str(v.get("razon") or "").strip()[:400]
    if accion not in ("comprar", "vender") or activo not in activos or porcentaje <= 0:
        return {"accion": "mantener", "activo": None, "porcentaje": 0,
                "razon": razon or "(respuesta sin un voto válido)", "valido": accion == "mantener"}
    return {"accion": accion, "activo": activo, "porcentaje": porcentaje, "razon": razon, "valido": True,
            "confianza": v.get("confianza")}


def decidir(votos):
    """Gana la acción con más votos; en empate gana mantener. El monto es la mediana de quienes la votaron."""
    grupos = {}
    for v in votos:
        grupos.setdefault((v["accion"], v["activo"]), []).append(v)
    mantener = len(grupos.get(("mantener", None), []))
    mejor, lista = max(grupos.items(), key=lambda kv: (len(kv[1]), kv[0][0] == "mantener"))
    if mejor[0] == "mantener" or len(lista) <= mantener:
        return {"accion": "mantener", "activo": None, "porcentaje": 0, "votos": max(mantener, len(lista))}
    return {"accion": mejor[0], "activo": mejor[1], "votos": len(lista),
            "porcentaje": round(statistics.median(v["porcentaje"] for v in lista), 2)}


def aplicar(estado, decision, p, aj):
    """Ejecuta la decisión en la cartera simulada. Devuelve la operación hecha o None."""
    if decision["accion"] == "mantener":
        return None
    if operaciones_de_hoy(estado) >= aj["max_operaciones"]:
        decision["bloqueo"] = f"ya hubo {aj['max_operaciones']} operaciones hoy"
        return None
    s, precio = decision["activo"], p[decision["activo"]]["precio"]
    pct = min(decision["porcentaje"], aj["tope"]) / 100
    if decision["accion"] == "comprar":
        usd = min(valor(estado, p) * pct, estado["efectivo"])
        if usd < 1:
            decision["bloqueo"] = "no queda efectivo"
            return None
        cantidad = usd * (1 - aj["comision"]) / precio
        estado["efectivo"] -= usd
        estado["posiciones"][s] = estado["posiciones"].get(s, 0) + cantidad
    else:
        tengo = estado["posiciones"].get(s, 0)
        cantidad = tengo * pct
        if cantidad * precio < 1:
            decision["bloqueo"] = f"no hay {s} para vender"
            return None
        usd = cantidad * precio * (1 - aj["comision"])
        estado["posiciones"][s] = tengo - cantidad
        estado["efectivo"] += usd
    return {"accion": decision["accion"], "activo": s, "cantidad": cantidad, "precio": precio, "usd": round(usd, 2)}


def votar(estado, p, aj):
    """Todas las IAs disponibles votan en paralelo. Devuelve [(modelo, voto, texto o error)]."""
    miembros = ia_externa.armar_panel(ia_externa.RAZONA, max(1, aj["ias"]))
    if not miembros:
        raise RuntimeError(ia_externa.sin_ias())
    sistema = SISTEMA.format(dias=estado["dias"], activos=", ".join(aj["activos"]), tope=aj["tope"],
                             comision=aj["comision"] * 100)
    pregunta = pregunta_de(estado, p, aj)
    respuestas = ia_externa.correr([(m, sistema, pregunta, {}) for m in miembros])
    return [(r["modelo"], leer_voto(r.get("texto"), aj["activos"], aj["tope"]) if r.get("texto") else None,
             r.get("texto") or r.get("error", "")) for r in respuestas]


def ronda(_args):
    estado = leer_estado()
    if not estado or estado.get("terminado"):
        return 0          # no hay experimento en marcha: el cron no hace nada
    if pausada():
        print("La billetera está en pausa.")
        return 0
    aj = ajustes()
    if time.time() >= estado["fin"]:
        return terminar(None)
    try:
        p = precios(aj["activos"])
    except RuntimeError as e:
        diario(f"## {time.strftime('%H:%M')} · sin ronda\n{e}")
        print(e)
        return 1
    try:
        resultados = votar(estado, p, aj)
    except RuntimeError as e:
        diario(f"## {time.strftime('%H:%M')} · sin ronda\nNo hubo IAs para votar: {e}")
        print(e)
        return 1
    votos = [v for _, v, _ in resultados if v]
    if not votos:
        diario(f"## {time.strftime('%H:%M')} · sin ronda\nNinguna IA respondió: "
               + "; ".join(f"{m}: {t[:120]}" for m, _, t in resultados))
        return 1
    decision = decidir(votos)
    operacion = aplicar(estado, decision, p, aj)
    total = valor(estado, p)
    fecha = time.strftime("%Y-%m-%d %H:%M")
    if operacion:
        resumen = (f"{operacion['accion']} {operacion['activo']} por {operacion['usd']:.2f} USD "
                   f"({decision['votos']} de {len(votos)} votos)")
    else:
        resumen = f"mantener ({decision['votos']} de {len(votos)} votos)" + (
            f"; se quería {decision['accion']} {decision['activo']} pero {decision['bloqueo']}"
            if decision.get("bloqueo") else "")
    estado["historial"].append({"fecha": fecha, "resumen": resumen, "operacion": operacion, "valor": round(total, 2)})
    guardar_estado(estado)

    with (CARPETA / "decisiones.jsonl").open("a", encoding="utf-8") as h:
        h.write(json.dumps({"fecha": fecha, "precios": p, "decision": decision, "operacion": operacion,
                            "valor": round(total, 2),
                            "votos": [{"modelo": m, **(v or {"error": t[:300]})} for m, v, t in resultados]},
                           ensure_ascii=False) + "\n")
    lineas = [f"## {time.strftime('%H:%M')} · {resumen}",
              f"Valor: {total:.2f} USD ({cambio(total, estado['saldo_inicial'])}). Precios: "
              + ", ".join(f"{s} {d['precio']:.2f}" for s, d in p.items()) + ".", ""]
    for m, v, t in resultados:
        if v:
            que = "mantener" if v["accion"] == "mantener" else f"{v['accion']} {v['activo']} {v['porcentaje']:g} %"
            lineas.append(f"- **{m}**: {que}. {v['razon']}")
        else:
            lineas.append(f"- **{m}**: no respondió ({t[:120]})")
    diario("\n".join(lineas))
    print(resumen)
    return 0


def cambio(ahora, antes):
    return f"{(ahora / antes - 1) * 100:+.2f} %" if antes else "sin dato"


def texto_estado(estado, p):
    total = valor(estado, p)
    lineas = [f"Billetera de Orión (simulada), día {min(dia_del_experimento(estado), estado['dias'])} de "
              f"{estado['dias']}" + (" · TERMINADO" if estado.get("terminado") else " · EN PAUSA" if pausada() else ""),
              f"Valor: {total:.2f} USD, empezó con {estado['saldo_inicial']:.2f} ({cambio(total, estado['saldo_inicial'])}).",
              f"Efectivo: {estado['efectivo']:.2f} USD."]
    for s, c in estado["posiciones"].items():
        if c > 0 and s in p:
            lineas.append(f"{s}: {c:.8f} ({c * p[s]['precio']:.2f} USD)")
    base = estado.get("precios_inicio", {}).get("BTC")
    if base and "BTC" in p:
        lineas.append(f"Si solo hubiera guardado BTC: {cambio(p['BTC']['precio'], base)}.")
    hechas = [h for h in estado["historial"] if h.get("operacion")]
    lineas.append(f"Rondas: {len(estado['historial'])}, operaciones: {len(hechas)}.")
    if estado["historial"]:
        lineas.append(f"Última: {estado['historial'][-1]['fecha']}, {estado['historial'][-1]['resumen']}.")
    return "\n".join(lineas)


def iniciar(args):
    estado = leer_estado()
    if estado and not estado.get("terminado"):
        print("Ya hay un experimento en marcha. Usa 'terminar' antes de empezar otro.")
        return 1
    if args.modo != "simulado":
        print("El modo real no está construido: hace falta que David elija la red y la billetera y confirme "
              "el monto máximo. Hoy solo existe el modo simulado.")
        return 2
    aj = ajustes()
    p = precios(aj["activos"])
    ahora = time.time()
    estado = {"modo": "simulado", "inicio": ahora, "fin": ahora + args.dias * 86400, "dias": args.dias,
              "saldo_inicial": args.saldo, "efectivo": args.saldo, "posiciones": {s: 0 for s in aj["activos"]},
              "precios_inicio": {s: d["precio"] for s, d in p.items()}, "historial": []}
    if CARPETA.exists() and (CARPETA / "estado.json").exists():
        # El experimento anterior se guarda aparte para no mezclar diarios.
        viejo = CARPETA.with_name(f"billetera-{time.strftime('%Y-%m-%d-%H%M')}")
        CARPETA.rename(viejo)
    guardar_estado(estado)
    (CARPETA / "PAUSA").unlink(missing_ok=True)
    diario(f"## Empieza el experimento\nCartera simulada de {args.saldo:.2f} USD durante {args.dias} días. "
           f"Activos: {', '.join(aj['activos'])}. Tope {aj['tope']:g} % por operación, "
           f"{aj['max_operaciones']} operaciones al día, comisión {aj['comision'] * 100:g} %.")
    print(f"Listo: {args.saldo:.2f} USD simulados durante {args.dias} días. La primera ronda la hace el cron.")
    return 0


def estado_cmd(_args):
    estado = leer_estado()
    if not estado:
        print("No hay experimento de billetera. Se empieza con: python3 scripts/billetera.py iniciar")
        return 1
    try:
        p = precios(ajustes()["activos"])
    except RuntimeError as e:
        print(f"{e}. Último valor guardado: {estado['historial'][-1]['valor'] if estado['historial'] else estado['saldo_inicial']} USD")
        return 1
    print(texto_estado(estado, p))
    return 0


def pausar(_args):
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / "PAUSA").write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    diario(f"## {time.strftime('%H:%M')} · pausa\nDavid pausó la billetera.")
    print("Billetera en pausa: no decide nada hasta que digas reanudar.")
    return 0


def reanudar(_args):
    (CARPETA / "PAUSA").unlink(missing_ok=True)
    diario(f"## {time.strftime('%H:%M')} · reanuda\nDavid reanudó la billetera.")
    print("Billetera reanudada.")
    return 0


def terminar(_args):
    estado = leer_estado()
    if not estado or estado.get("terminado"):
        print("No hay experimento en marcha.")
        return 1
    try:
        p = precios(ajustes()["activos"])
        texto = texto_estado(estado, p)
        estado["valor_final"] = round(valor(estado, p), 2)
    except RuntimeError as e:
        texto = f"(sin precios al terminar: {e})"
    estado["terminado"] = time.time()
    guardar_estado(estado)
    informe = CARPETA / "informe-final.md"
    informe.write_text(f"---\nfecha: {time.strftime('%Y-%m-%d')}\ntipo: billetera\ntags: [billetera, informe]\n---\n"
                       f"# Informe final de la billetera de Orión\n\n{texto}\n\nEl detalle de cada voto está en "
                       f"decisiones.jsonl y en diario/.\n", encoding="utf-8")
    diario(f"## Termina el experimento\n{texto}")
    print(texto)
    return 0


def main():
    ia_externa.cargar_env()
    a = argparse.ArgumentParser(description="La billetera simulada de Orión")
    sub = a.add_subparsers(dest="orden", required=True)
    i = sub.add_parser("iniciar")
    i.add_argument("--saldo", type=float, default=float(os.environ.get("BILLETERA_SALDO", "1000")))
    i.add_argument("--dias", type=int, default=14)
    i.add_argument("--modo", default="simulado", choices=["simulado", "real"])
    for nombre in ("ronda", "estado", "pausar", "reanudar", "terminar"):
        sub.add_parser(nombre)
    args = a.parse_args()
    return {"iniciar": iniciar, "ronda": ronda, "estado": estado_cmd, "pausar": pausar,
            "reanudar": reanudar, "terminar": terminar}[args.orden](args)


if __name__ == "__main__":
    sys.exit(main())
