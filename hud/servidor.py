"""
Servidor local del HUD de JARVIS.

Sirve hud/index.html y una pequeña API que lee la bóveda, la cola y el sistema.
Solo usa la biblioteca estándar de Python, así que no hay nada que instalar.

    python3 hud/servidor.py            ->  http://localhost:7777
"""

import argparse
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
BOVEDA = RAIZ / "boveda"
COLA = RAIZ / "cola"
HUD = RAIZ / "hud"
ENLACE = re.compile(r"\[\[([^\]|#]+)")

# Botones del panel de comandos: (etiqueta, pedido que se encola)
COMANDOS = [
    ("Resumen matutino", "resumen matutino"),
    ("Plan de hoy", "plan de hoy"),
    ("Revisa pendientes", "revisa mis pendientes y los correos que esperan respuesta"),
    ("Resumen correo", "resume mis correos de hoy"),
    ("Tendencias", "tendencias de mis temas esta semana"),
    ("Tendencias GH", "tendencias GH"),
    ("Canales", "¿cómo van mis canales?"),
    ("Suscripciones", "revisa mis suscripciones"),
    ("Plan de mañana", "plan de mañana"),
    ("Revisión semanal", "revisión semanal"),
    ("Limpieza bóveda", "limpieza de bóveda"),
    ("Cierra el día", "cierra el día"),
]


# ---------- Sistema ----------

_cpu_anterior = None


def uso_cpu():
    """Porcentaje de CPU desde la última llamada, leyendo /proc/stat."""
    global _cpu_anterior
    try:
        valores = list(map(int, Path("/proc/stat").read_text().split("\n")[0].split()[1:]))
    except OSError:
        return None
    inactivo, total = valores[3] + valores[4], sum(valores)
    anterior, _cpu_anterior = _cpu_anterior, (inactivo, total)
    if not anterior or total == anterior[1]:
        return None
    return round(100 * (1 - (inactivo - anterior[0]) / (total - anterior[1])), 1)


def uso_memoria():
    try:
        info = dict(l.split(":", 1) for l in Path("/proc/meminfo").read_text().splitlines())
        total = int(info["MemTotal"].split()[0])
        libre = int(info["MemAvailable"].split()[0])
        return round(100 * (1 - libre / total), 1)
    except (OSError, KeyError, ValueError):
        return None


def vitales():
    disco = shutil.disk_usage(RAIZ)
    return {
        "cpu": uso_cpu(),
        "memoria": uso_memoria(),
        "disco": round(100 * disco.used / disco.total, 1),
        "carga": round(os.getloadavg()[0], 2) if hasattr(os, "getloadavg") else None,
    }


# ---------- Bóveda ----------

def notas():
    return sorted(p for p in BOVEDA.rglob("*.md") if ".obsidian" not in p.parts)


def grafo():
    """Nodos = notas, aristas = enlaces [[...]] entre ellas."""
    archivos = notas()
    indice = {p.stem.lower(): i for i, p in enumerate(archivos)}
    nodos, aristas = [], set()
    for i, p in enumerate(archivos):
        carpeta = p.relative_to(BOVEDA).parts[0]
        nodos.append({"id": i, "nombre": p.stem, "grupo": carpeta})
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for destino in ENLACE.findall(texto):
            j = indice.get(destino.strip().lower())
            if j is not None and j != i:
                aristas.add((min(i, j), max(i, j)))
    return {"nodos": nodos, "aristas": sorted(aristas)}


def tareas_abiertas():
    archivo = BOVEDA / "wiki" / "tareas.md"
    if not archivo.exists():
        return []
    salida = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- \[ \] (.+)", linea)
        if m:
            texto = m.group(1)
            fecha = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", texto)
            salida.append({
                "texto": re.sub(r"📅\s*\S+|#\S+", "", texto).strip(),
                "fecha": fecha.group(1) if fecha else None,
            })
    return salida


def plan_de_hoy():
    archivo = BOVEDA / "outputs" / "planes" / f"{date.today().isoformat()}.md"
    if not archivo.exists():
        return {"existe": False, "prioridades": [], "agenda": []}
    texto = archivo.read_text(encoding="utf-8")
    prioridades = [
        {"texto": m.group(2).strip(), "hecha": m.group(1).lower() == "x"}
        for m in re.finditer(r"^\s*\d+\.\s*\[( |x|X)\]\s*(.+)$", texto, re.M)
    ]
    agenda = [
        {"hora": m.group(1), "texto": m.group(2).strip()}
        for m in re.finditer(r"^\s*-\s*(\d{1,2}:\d{2})\s+(.+)$", texto, re.M)
    ]
    return {"existe": True, "prioridades": prioridades, "agenda": agenda}


def informes(limite=8):
    salidas = BOVEDA / "outputs"
    archivos = sorted(salidas.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"ruta": str(p.relative_to(BOVEDA)), "nombre": p.stem, "tipo": p.parent.name}
        for p in archivos[:limite]
    ]


def leer_nota(ruta):
    destino = (BOVEDA / ruta).resolve()
    if BOVEDA.resolve() not in destino.parents or destino.suffix != ".md" or not destino.exists():
        return None
    return destino.read_text(encoding="utf-8", errors="replace")


# ---------- Cola ----------

def leer_intencion(p):
    texto = p.read_text(encoding="utf-8", errors="replace")
    pedido = re.search(r'^pedido: "(.*)"$', texto, re.M)
    origen = re.search(r"^origen: (.*)$", texto, re.M)
    resultado = texto.split("## Resultado", 1)
    return {
        "archivo": p.name,
        "pedido": pedido.group(1).replace('\\"', '"') if pedido else p.stem,
        "origen": origen.group(1) if origen else "",
        "respuesta": resultado[1].split("\n", 2)[-1].strip() if len(resultado) > 1 else "",
    }


def estado_cola():
    def listar(nombre):
        return sorted((COLA / nombre).glob("*.md"), reverse=True)

    pendientes, en_curso = listar("pendientes"), listar("en-curso")
    terminadas = sorted(listar("hechas") + listar("fallidas"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "pendientes": len(pendientes),
        "en_curso": [leer_intencion(p) for p in en_curso],
        "recientes": [dict(leer_intencion(p), estado=p.parent.name) for p in terminadas[:6]],
        "hechas": len(listar("hechas")),
        "fallidas": len(listar("fallidas")),
    }


def estado_audio():
    """Lo escribe el cliente de voz de Windows; si lleva mucho sin cambiar, la voz no está abierta."""
    archivo = COLA / "voz-estado.txt"
    try:
        if time.time() - archivo.stat().st_mtime > 6 * 3600:
            return "VOZ APAGADA"
        return archivo.read_text(encoding="utf-8").strip() or "EN ESPERA"
    except OSError:
        return "VOZ APAGADA"


def encolar(pedido):
    pedido = pedido.strip()[:500]
    if not pedido:
        return False
    entorno = dict(os.environ, JARVIS_ORIGEN="hud")
    subprocess.run([str(RAIZ / "scripts" / "encolar.sh"), pedido], cwd=RAIZ, env=entorno,
                   check=True, capture_output=True)
    # El corredor corre en segundo plano; si ya hay uno trabajando, ese recogerá esta intención.
    subprocess.Popen([str(RAIZ / "scripts" / "corredor.sh")], cwd=RAIZ,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return True


# ---------- Analizar fuentes (ventana tipo "agregar fuentes") ----------

ABRIR_ANALIZAR = COLA / "analizar-abrir"        # lo deja la voz al oír "Jarvis, analiza..."
PEDIDO_ANALIZAR = COLA / "analizar-pedido.json"  # lo recoge la voz para responder hablando
MAX_ANALIZAR = 300 * 1024 * 1024                 # 300 MB por análisis
MEDIOS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".mp4", ".mkv", ".mov", ".webm", ".avi"}


def pedir_abrir_analizar():
    """True una sola vez cuando la voz pidió abrir la ventana de análisis."""
    try:
        ABRIR_ANALIZAR.unlink()
        return True
    except FileNotFoundError:
        return False


def nombre_seguro(nombre):
    nombre = Path(str(nombre)).name
    nombre = re.sub(r"[^\w.\- ]+", "_", nombre, flags=re.UNICODE).strip(" .")
    return nombre[:120] or "archivo"


def guardar_fuentes(datos):
    """Guarda archivos, enlaces y texto en boveda/raw/analisis/<fecha-hora>/ y arma el pedido."""
    fuentes = datos.get("fuentes") or []
    if not fuentes:
        raise ValueError("Agrega al menos una fuente.")
    carpeta = BOVEDA / "raw" / "analisis" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)
    rel = carpeta.relative_to(RAIZ).as_posix()
    lineas, medios, usados = [], [], set()
    for f in fuentes:
        tipo = f.get("tipo")
        if tipo == "archivo":
            nombre = nombre_seguro(f.get("nombre"))
            base, ext = os.path.splitext(nombre)
            k = 1
            while nombre in usados:
                nombre, k = f"{base}-{k}{ext}", k + 1
            usados.add(nombre)
            (carpeta / nombre).write_bytes(base64.b64decode(f.get("datos") or ""))
            lineas.append(f"- Archivo: `{rel}/{nombre}`")
            if ext.lower() in MEDIOS:
                medios.append(f"{rel}/{nombre}")
        elif tipo == "enlace":
            url = str(f.get("url", "")).strip()
            if re.match(r"https?://", url):
                lineas.append(f"- Enlace: {url}")
        elif tipo == "texto":
            texto = str(f.get("texto", "")).strip()
            if texto:
                n = sum(1 for l in lineas if l.startswith("- Texto")) + 1
                (carpeta / f"texto-{n}.md").write_text(texto, encoding="utf-8")
                lineas.append(f"- Texto copiado: `{rel}/texto-{n}.md`")
    if not lineas:
        raise ValueError("No había ninguna fuente válida.")
    pregunta = str(datos.get("pregunta") or "").strip()
    (carpeta / "fuentes.md").write_text(
        f"---\nfecha: {date.today().isoformat()}\ntipo: fuentes\ntags: [analisis]\n---\n"
        f"# Fuentes para analizar\n\n" + "\n".join(lineas) +
        (f"\n\nPregunta de David: {pregunta}\n" if pregunta else "\n"),
        encoding="utf-8")
    pedido = f"analiza las fuentes de {rel}/fuentes.md"
    if pregunta:
        pedido += f". Lo que quiero saber: {pregunta[:300]}"
    return pedido, medios


def rutinas():
    archivo = RAIZ / "rutinas" / "rutinas.csv"
    if not archivo.exists():
        return []
    filas = archivo.read_text(encoding="utf-8").strip().splitlines()[1:]
    return [dict(zip(("hora", "nombre", "pedido"), f.strip().split(",", 2))) for f in filas]


# ---------- HTTP ----------

def estado_completo():
    cola = estado_cola()
    total_notas = len(notas())
    return {
        "hora": datetime.now().isoformat(timespec="seconds"),
        "vitales": vitales(),
        "boveda": {
            "notas": total_notas,
            "wiki": len(list((BOVEDA / "wiki").glob("*.md"))),
            "salidas": len(list((BOVEDA / "outputs").rglob("*.md"))),
        },
        "tareas": tareas_abiertas(),
        "plan": plan_de_hoy(),
        "informes": informes(),
        "cola": cola,
        "actividad": "EJECUTANDO" if cola["en_curso"] else ("EN COLA" if cola["pendientes"] else "EN ESPERA"),
        "audio": estado_audio(),
        "rutinas": rutinas(),
        "comandos": [{"etiqueta": e, "pedido": p} for e, p in COMANDOS],
    }


class Manejador(BaseHTTPRequestHandler):
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            cuerpo = (HUD / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        elif url.path == "/api/estado":
            self._json(estado_completo())
        elif url.path == "/api/analizar/abrir":
            self._json({"abrir": pedir_abrir_analizar()})
        elif url.path == "/api/grafo":
            self._json(grafo())
        elif url.path == "/api/nota":
            ruta = parse_qs(url.query).get("ruta", [""])[0]
            texto = leer_nota(ruta)
            self._json({"ruta": ruta, "texto": texto} if texto is not None else {"error": "no existe"},
                       200 if texto is not None else 404)
        else:
            self._json({"error": "no existe"}, 404)

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta == "/api/analizar":
            return self._analizar()
        if ruta != "/api/encolar":
            return self._json({"error": "no existe"}, 404)
        largo = int(self.headers.get("Content-Length", 0))
        try:
            pedido = json.loads(self.rfile.read(largo) or b"{}").get("pedido", "")
        except json.JSONDecodeError:
            return self._json({"error": "JSON inválido"}, 400)
        ok = encolar(pedido)
        self._json({"ok": ok}, 200 if ok else 400)

    def _analizar(self):
        largo = int(self.headers.get("Content-Length", 0))
        if largo > MAX_ANALIZAR * 4 // 3 + 65536:
            return self._json({"error": "Es demasiado grande: máximo 300 MB por análisis."}, 413)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
            pedido, medios = guardar_fuentes(datos)
        except (json.JSONDecodeError, ValueError, binascii.Error) as e:
            return self._json({"error": str(e) or "Petición inválida"}, 400)
        if datos.get("para_voz"):
            # La voz está esperando: transcribe audio y video y responde hablando.
            PEDIDO_ANALIZAR.write_text(json.dumps({"pedido": pedido, "medios": medios}, ensure_ascii=False),
                                       encoding="utf-8")
            return self._json({"ok": True, "voz": True})
        ok = encolar(pedido)
        self._json({"ok": ok, "voz": False}, 200 if ok else 400)

    def log_message(self, formato, *args):
        pass  # silencio: el HUD consulta cada pocos segundos


def esperar_cierre():
    """El programa de Windows deja la entrada abierta; cuando se cierra, el servidor sale."""
    sys.stdin.read()
    os._exit(0)


def main():
    p = argparse.ArgumentParser(description="HUD de JARVIS")
    p.add_argument("--puerto", type=int, default=7777)
    p.add_argument("--con-programa", action="store_true",
                   help="se apaga solo cuando se cierra el programa del HUD en Windows")
    args = p.parse_args()
    if args.con_programa:
        threading.Thread(target=esperar_cierre, daemon=True).start()
    uso_cpu()  # primera lectura para tener referencia
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"HUD de JARVIS en http://localhost:{args.puerto}  (Ctrl+C para salir)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
