#!/usr/bin/env python3
"""
Lo mínimo de la API de Bitso (v3) que usa la billetera real de Orión: saldos y órdenes de mercado.

Claves en .env (las pone David a mano): BITSO_API_KEY y BITSO_API_SECRET. Deben ser de una cuenta o
subcuenta solo para Orión y tener permiso de operar, NUNCA de retirar: así, pase lo que pase, el dinero
no puede salir de la cuenta. Solo usa la biblioteca estándar.
"""

import hashlib
import hmac
import json
import math
import os
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("BITSO_BASE", "https://api.bitso.com")


def configurado():
    return bool(os.environ.get("BITSO_API_KEY") and os.environ.get("BITSO_API_SECRET"))


class Rechazo(RuntimeError):
    """Bitso contestó y dijo que no: la orden seguro no existe."""


def pedir(metodo, ruta, cuerpo=None):
    """Llamada firmada: firma = HMAC-SHA256(secreto, nonce + método + ruta + json)."""
    if not configurado():
        raise RuntimeError("faltan BITSO_API_KEY y BITSO_API_SECRET en .env")
    datos = json.dumps(cuerpo, separators=(",", ":")) if cuerpo is not None else ""
    nonce = str(time.time_ns() // 1000)
    firma = hmac.new(os.environ["BITSO_API_SECRET"].encode(), f"{nonce}{metodo}{ruta}{datos}".encode(),
                     hashlib.sha256).hexdigest()
    req = urllib.request.Request(BASE + ruta, data=datos.encode() if datos else None, method=metodo, headers={
        "Authorization": f"Bitso {os.environ['BITSO_API_KEY']}:{nonce}:{firma}",
        "Content-Type": "application/json", "User-Agent": "orion-billetera"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            respuesta = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("error", {})
        except ValueError:
            detalle = {}
        # Un 4xx es un no; un 5xx (o un tiempo agotado) no dice si la orden entró.
        error = Rechazo if e.code < 500 else RuntimeError
        raise error(f"Bitso respondió {e.code}: {detalle.get('message', '')}"[:300]) from None
    except (OSError, ValueError) as e:
        raise RuntimeError(f"no pude hablar con Bitso: {e}") from None
    if not respuesta.get("success"):
        raise Rechazo(f"Bitso rechazó la orden: {respuesta.get('error', {}).get('message', respuesta)}"[:300])
    return respuesta["payload"]


def _publico(ruta, que):
    """GET a la parte pública de Bitso (sin firma)."""
    req = urllib.request.Request(BASE + ruta, headers={"User-Agent": "orion-billetera"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["payload"]
    except (OSError, ValueError, KeyError) as e:
        raise RuntimeError(f"no pude leer {que} de Bitso: {e}") from None


def libros():
    """Los libros que Bitso tiene abiertos, p. ej. {"btc_cop", "eth_cop", "btc_mxn"}."""
    return {b["book"] for b in _publico("/v3/available_books/", "los libros")}


def ultimo(libro):
    """Último precio de un libro: en usd_cop, cuántos pesos vale un dólar."""
    try:
        return float(_publico(f"/v3/ticker/?book={libro}", f"el precio de {libro}")["last"])
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Bitso no dio el precio de {libro}: {e}") from None


def saldos():
    """{"cop": 500000.0, "btc": 0.0001, ...} con lo disponible (no lo reservado en órdenes)."""
    return {b["currency"].lower(): float(b["available"]) for b in pedir("GET", "/v3/balance/")["balances"]}


def _cifra(monto, decimales):
    """Redondea hacia abajo: nunca pide más de lo que hay en la cuenta."""
    return f"{math.floor(monto * 10 ** decimales) / 10 ** decimales:.{decimales}f}"


def _buscar(origen):
    """El oid de la orden con nuestro origin_id, o None si Bitso no la tiene."""
    ordenes = pedir("GET", f"/v3/orders/?origin_ids={origen}")
    return ordenes[0]["oid"] if ordenes else None


def _orden(libro, lado, campo, monto):
    # Cada orden lleva un id propio (origin_id): si Bitso tarda en contestar, se busca por ese id antes de
    # darla por fallida, porque pudo llenarse igual.
    origen = f"orion-{uuid.uuid4().hex[:24]}"
    cuerpo = {"book": libro, "side": lado, "type": "market", campo: _cifra(monto, 2 if campo == "minor" else 8),
              "origin_id": origen}
    try:
        oid = pedir("POST", "/v3/orders/", cuerpo)["oid"]
    except Rechazo:
        raise
    except RuntimeError as e:
        oid = None
        for _ in range(3):
            time.sleep(2)
            try:
                oid = _buscar(origen)
            except RuntimeError:
                continue
            if oid:
                break
        if not oid:
            raise RuntimeError(f"{e}; no encontré la orden {origen} en Bitso (revisa la cuenta)") from None
    # Una orden de mercado se llena casi al instante; se suman sus operaciones para saber cuánto fue de verdad.
    for _ in range(15):
        time.sleep(1)
        trades = pedir("GET", f"/v3/order_trades/{oid}/")
        if trades:
            break
    else:
        raise RuntimeError(f"la orden {oid} no se llenó todavía; revisa Bitso")
    mayor = sum(abs(float(t["major"])) for t in trades)
    menor = sum(abs(float(t["minor"])) for t in trades)
    comision = sum(abs(float(t.get("fees_amount") or 0)) for t in trades)
    moneda_comision = (trades[0].get("fees_currency") or "").lower()
    return {"oid": oid, "mayor": mayor, "menor": menor, "comision": comision, "moneda_comision": moneda_comision}


def comprar(libro, gastar):
    """Compra a mercado gastando `gastar` de la moneda base (COP en btc_cop)."""
    return _orden(libro, "buy", "minor", gastar)


def vender(libro, cantidad):
    """Vende a mercado `cantidad` de la cripto (BTC en btc_cop)."""
    return _orden(libro, "sell", "major", cantidad)
