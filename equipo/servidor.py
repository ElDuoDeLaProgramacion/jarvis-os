"""
Sala de Orión Equipo + panel del dueño (equipo/README.md).

- La sala (/) tiene dos pestañas: el chat grupal del equipo (lo ven todos) y el chat privado de
  cada persona con Orión (uno a uno). Cada persona entra con usuario y contraseña.
- El panel (/panel) es solo de David: ve alertas, aprueba o rechaza las pruebas activas que pide el
  equipo, quita a alguien y pausa todo. Entra con su clave y el código de 6 dígitos de su app.

Orión atiende un pedido a la vez y sabe quién habla. No tiene nada del Orión de David (correo,
agenda, WhatsApp, billetera): solo pasa los pedidos a equipo/orion-equipo.sh. Solo biblioteca estándar.

    python3 equipo/servidor.py                 ->  socket /run/orion-equipo/sala.sock (Caddy)
    python3 equipo/servidor.py --puerto 7790   ->  http://127.0.0.1:7790 (pruebas)
"""

import argparse
import hashlib
import html
import json
import os
import re
import socketserver
import subprocess
import threading
import time
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import seguridad

AQUI = Path(__file__).resolve().parent
FUENTES = ("PlusJakartaSans-latin.woff2", "PlusJakartaSans-latin-ext.woff2")
CASA = Path(os.environ.get("ORION_EQUIPO_CASA", os.environ.get("HOME", "/home/equipo")))
PERSONAS = Path(os.environ.get("ORION_EQUIPO_PERSONAS", CASA / "personas"))
ADMIN = CASA / "admin.json"
SESIONES = CASA / "sesiones.json"
SALA_JSON = Path(os.environ.get("ORION_EQUIPO_SALA", CASA / "sala" / "sala.json"))
# El chat privado de cada persona con Orión (uno a uno), aparte del grupal.
PRIVADO = Path(os.environ.get("ORION_EQUIPO_PRIVADO", CASA / "sala" / "privado"))
AUTOR = CASA / "autorizaciones"
ALERTAS = CASA / "alertas.jsonl"
INFORMES = CASA / "informes"
BLOQUEADOS = CASA / "bloqueados"
ESPACIO = Path(os.environ.get("ORION_EQUIPO_ESPACIO", CASA / "espacio"))
PAUSA = CASA / "PAUSA"

SEGUIR_MIN = 30
LIMITE_SEG = 15 * 60
MAX_MENSAJES = 300
MAX_TEXTO = 4000
HORAS_SESION = 12


# ---------- informe: limpiar el HTML que escribe el equipo ----------
# El informe es un documento que el estudiante edita (texto e imágenes) y David lee en su panel.
# Como es contenido escrito por otra persona, antes de guardarlo dejamos solo una lista blanca de
# etiquetas y quitamos scripts, estilos y cualquier atributo peligroso. Las imágenes solo pueden ser
# data:image incrustadas (nada de URLs externas), así el informe es autocontenido y no filtra nada.

_ETIQUETAS_OK = {"p", "br", "b", "strong", "i", "em", "u", "h3", "ul", "ol", "li", "a", "img", "div", "span"}
_ATRIBUTOS_OK = {"a": {"href"}, "img": {"src"}}
_IMG_OK = re.compile(r"^data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+$")
_SOLO_CIERRE = {"br", "img"}



# Selector de proyectos arriba del panel: el mismo que en el panel de Hallazgos Viales (allá usa
# la misma variable). Formato "Nombre|URL;Nombre|URL". Para sumar un proyecto, agrégalo en los dos.
PANELES_DEFECTO = "Hallazgos Viales|https://api.ubuntulabs.co/panel;Orión Equipo|https://api.ubuntulabs.co/equipo"
# El panel también responde en /equipo (mismo contenido que /panel) para vivir junto al de Hallazgos en
# un solo dominio: el Caddy de ese dominio manda /equipo* a esta sala (lo arma ./equipo/instalar.sh).
ALIAS_PANEL = "/equipo"
# Login único con Cloudflare Access: si pones aquí tu correo (el dueño), y el panel vive detrás de
# Cloudflare Access, entras sin la clave+código del panel (Cloudflare ya te identificó). Vacío = como
# siempre, con clave+código. OJO: solo actívalo si el origen SOLO se alcanza por Cloudflare (nube naranja
# + 443 restringido a las IP de Cloudflare, o un túnel); si no, el encabezado se podría falsificar.
ACCESS_EMAIL = os.environ.get("ORION_EQUIPO_ACCESS_EMAIL", "").strip().lower()


def paneles():
    propio = os.environ.get("PANELES", "").strip()
    lista = []
    for parte in (propio or PANELES_DEFECTO).split(";"):
        nombre, _, url = (x.strip() for x in parte.partition("|"))
        if nombre and url.startswith(("https://", "http://")):
            lista.append({"nombre": nombre, "url": url})
    viejo = os.environ.get("ORION_EQUIPO_HALLAZGOS_URL", "").strip()   # versión anterior
    if viejo and not propio:
        lista = [{**p, "url": viejo} if p["nombre"] == "Hallazgos Viales" else p for p in lista]
    return lista

class _LimpiadorHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []

    def _atributos(self, tag, attrs):
        permitidos = _ATRIBUTOS_OK.get(tag, set())
        salida = []
        for k, v in attrs:
            k = (k or "").lower()
            if k not in permitidos or not v:
                continue
            v = v.strip()
            if tag == "img" and k == "src":
                if not _IMG_OK.match(v):
                    return None  # imagen inválida: se descarta la etiqueta entera
                salida.append(("src", v))
            elif tag == "a" and k == "href" and v.lower().startswith(("http://", "https://")):
                salida.append(("href", v))
        return salida

    def _abrir(self, tag, attrs, cierre_propio=False):
        tag = tag.lower()
        if tag not in _ETIQUETAS_OK:
            return
        a = self._atributos(tag, attrs)
        if tag == "img" and not a:
            return
        att = "".join(' {}="{}"'.format(k, html.escape(v, quote=True)) for k, v in (a or []))
        if tag in _SOLO_CIERRE:
            self.partes.append("<{}{}>".format(tag, att))
        else:
            self.partes.append("<{}{}>".format(tag, att))

    def handle_starttag(self, tag, attrs):
        self._abrir(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._abrir(tag, attrs, cierre_propio=True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _ETIQUETAS_OK and tag not in _SOLO_CIERRE:
            self.partes.append("</{}>".format(tag))

    def handle_data(self, data):
        self.partes.append(html.escape(data))


def limpiar_informe(texto, maximo=8_000_000):
    p = _LimpiadorHTML()
    p.feed(str(texto)[:maximo])
    p.close()
    return "".join(p.partes)


# ---------- personas (usuario + contraseña) ----------

def leer_personas(archivo=None):
    """{nombre: hash_scrypt}. Se lee en cada acción: añadir o quitar no pide reiniciar."""
    personas = {}
    try:
        for linea in (archivo or PERSONAS).read_text(encoding="utf-8").splitlines():
            if linea.startswith("#") or "\t" not in linea:
                continue
            nombre, h = linea.split("\t", 1)
            if nombre and h:
                personas[nombre.strip()] = h.strip()
    except OSError:
        pass
    return personas


def persona_correcta(usuario, clave):
    h = leer_personas().get(str(usuario or "").strip())
    return bool(h) and seguridad.clave_correcta(str(clave or ""), h)


def leer_bloqueados():
    """Nombres a los que David bloqueó la entrada (reversible, no borra su cuenta)."""
    try:
        return {l.strip() for l in BLOQUEADOS.read_text(encoding="utf-8").splitlines() if l.strip()}
    except OSError:
        return set()


def bloquear_persona(nombre, activar):
    nombre = str(nombre or "").strip()
    actuales = leer_bloqueados()
    if activar:
        actuales.add(nombre)
    else:
        actuales.discard(nombre)
    BLOQUEADOS.write_text("".join(n + "\n" for n in sorted(actuales)), encoding="utf-8")
    try:
        BLOQUEADOS.chmod(0o600)
    except OSError:
        pass


# ---------- sesiones (cookie) ----------

class Sesiones:
    def __init__(self, archivo=SESIONES):
        self.archivo = archivo
        self.cerrojo = threading.Lock()
        self.datos = {}
        try:
            self.datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def _guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.archivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.datos), encoding="utf-8")
        tmp.replace(self.archivo)

    def crear(self, quien, rol):
        t = seguridad.token()
        with self.cerrojo:
            self.datos[seguridad.huella(t)] = {"quien": quien, "rol": rol, "expira": time.time() + HORAS_SESION * 3600}
            self._guardar()
        return t

    def quien(self, token, rol):
        if not token:
            return None
        with self.cerrojo:
            s = self.datos.get(seguridad.huella(token))
            if not s or s["rol"] != rol or s["expira"] < time.time():
                return None
            return s["quien"]

    def borrar(self, token):
        if not token:
            return
        with self.cerrojo:
            if self.datos.pop(seguridad.huella(token), None):
                self._guardar()

    def borrar_persona(self, nombre):
        with self.cerrojo:
            antes = len(self.datos)
            self.datos = {k: v for k, v in self.datos.items() if not (v["rol"] == "persona" and v["quien"] == nombre)}
            if len(self.datos) != antes:
                self._guardar()


# ---------- alertas y autorizaciones ----------

def alertas_recientes(n=100):
    filas = []
    try:
        for linea in ALERTAS.read_text(encoding="utf-8").splitlines()[-n:]:
            try:
                filas.append(json.loads(linea))
            except ValueError:
                pass
    except OSError:
        pass
    return list(reversed(filas))


def anotar_alerta(tipo, persona, texto):
    ALERTAS.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTAS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"hora": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "tipo": tipo,
                            "persona": persona, "texto": texto}, ensure_ascii=False) + "\n")


def pendientes():
    carpeta = AUTOR / "pendientes"
    filas = []
    try:
        for f in sorted(carpeta.glob("*.json")):
            try:
                filas.append(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                pass
    except OSError:
        pass
    return filas


def aprobar(id_, horas):
    f = AUTOR / "pendientes" / f"{id_}.json"
    if not f.exists():
        return False
    d = json.loads(f.read_text(encoding="utf-8"))
    (AUTOR / "aprobadas").mkdir(parents=True, exist_ok=True)
    (AUTOR / "aprobadas" / f"{d['clave']}.json").write_text(json.dumps(
        {"objetivo": d["objetivo"], "herramienta": d["herramienta"], "por": "David",
         "hasta": time.time() + max(1, min(72, horas)) * 3600,
         "creada": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
    f.unlink(missing_ok=True)
    anotar_alerta("autorizada", d["persona"], f"David autorizó '{d['herramienta']}' contra {d['objetivo']} por {horas} h.")
    return True


def denegar(id_, motivo=""):
    f = AUTOR / "pendientes" / f"{id_}.json"
    if not f.exists():
        return False
    d = json.loads(f.read_text(encoding="utf-8"))
    f.unlink(missing_ok=True)
    anotar_alerta("denegada", d["persona"], f"David NO autorizó '{d['herramienta']}' contra {d['objetivo']}. {motivo}".strip())
    return True


# ---------- Sala ----------

class Sala:
    def __init__(self, archivo=None, guion=None, limite_dia=40):
        self.archivo = archivo or SALA_JSON
        self.guion = guion or str(AQUI / "orion-equipo.sh")
        self.limite_dia = limite_dia
        self.cerrojo = threading.Lock()
        self.turno = threading.Lock()
        self.mensajes, self.sesion, self.ocupado, self.cuenta = [], None, 0, {}
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            self.mensajes, self.sesion = datos.get("mensajes", []), datos.get("sesion")
            self.cuenta = datos.get("cuenta", {})
        except (OSError, ValueError):
            pass

    def _guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.archivo.with_suffix(".tmp")
        tmp.write_text(json.dumps({"mensajes": self.mensajes, "sesion": self.sesion, "cuenta": self.cuenta},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.archivo)

    def anotar(self, de, texto, **extra):
        with self.cerrojo:
            n = (self.mensajes[-1]["n"] + 1) if self.mensajes else 1
            self.mensajes.append({"n": n, "de": de, "texto": texto,
                                  "hora": datetime.now().strftime("%d/%m %H:%M"), **extra})
            self.mensajes = self.mensajes[-MAX_MENSAJES:]
            self._guardar()
            return n

    def desde(self, n):
        with self.cerrojo:
            return [m for m in self.mensajes if m["n"] > n], self.ocupado > 0

    def gastar(self, nombre):
        hoy = datetime.now().strftime("%Y-%m-%d")
        with self.cerrojo:
            if self.cuenta.get("dia") != hoy:
                self.cuenta = {"dia": hoy}
            usados = self.cuenta.get(nombre, 0)
            if self.limite_dia and usados >= self.limite_dia:
                return False
            self.cuenta[nombre] = usados + 1
            return True

    def pedir(self, nombre, texto):
        with self.cerrojo:
            self.ocupado += 1
        n = self.anotar(nombre, texto)
        threading.Thread(target=self._atender, args=(nombre, texto, n), daemon=True).start()
        return n

    def _atender(self, nombre, texto, n):
        try:
            with self.turno:
                self.anotar("orion", self._orion(nombre, f"{nombre}: {texto}"), para=n)
        finally:
            with self.cerrojo:
                self.ocupado -= 1

    # Botón "Empezar" del panel: Orión saluda y reparte los roles del trabajo de hoy.
    ARRANQUE = ("David dio inicio a la sesión de hoy. Saluda al equipo con energía pero breve, y "
                "reparte los roles del trabajo de seguridad sobre los objetivos autorizados: di quién "
                "se encarga del reconocimiento, quién revisa cabeceras/TLS/puertos, quién prepara las "
                "pruebas activas (recuerda que esas requieren la autorización de David) y quién arma el "
                "informe. Si no conoces los nombres del equipo, pide que cada quien diga en qué quiere ir.")

    def arrancar(self):
        with self.cerrojo:
            self.ocupado += 1
        n = self.anotar("David", "¡Arrancamos! Vamos a empezar con el trabajo de hoy.")
        threading.Thread(target=self._arrancar_bg, args=(n,), daemon=True).start()
        return n

    def _arrancar_bg(self, n):
        try:
            with self.turno:
                self.anotar("orion", self._orion("David", self.ARRANQUE), para=n)
        finally:
            with self.cerrojo:
                self.ocupado -= 1

    def _orion(self, nombre, pedido):
        args = []
        s = self.sesion
        if s and s.get("hasta", 0) > time.time():
            args += ["--reanudar", s["id"]]
        entorno = {**os.environ, "ORION_EQUIPO_PERSONA": nombre}
        try:
            r = subprocess.run([self.guion, *args, "--", pedido], capture_output=True, text=True,
                               timeout=LIMITE_SEG, stdin=subprocess.DEVNULL, env=entorno)
        except subprocess.TimeoutExpired:
            return "Se me acabó el tiempo con eso. Pídemelo otra vez, más concreto."
        respuesta = r.stdout.strip()
        if r.returncode != 0 or not respuesta:
            ultima = (r.stderr.strip().splitlines() or ["sin detalle"])[-1]
            return f"No pude hacerlo ({ultima[:200]})."
        sesion = next((l[7:].strip() for l in r.stderr.splitlines() if l.startswith("SESION=")), None)
        with self.cerrojo:
            if sesion:
                self.sesion = {"id": sesion, "hasta": time.time() + SEGUIR_MIN * 60}
            self._guardar()
        return respuesta


# ---------- HTTP ----------

class Fallos:
    MAXIMO, VENTANA, CASTIGO = 5, 600, 900

    def __init__(self):
        self.intentos, self.hasta, self.cerrojo = {}, {}, threading.Lock()

    def bloqueada(self, ip):
        with self.cerrojo:
            return self.hasta.get(ip, 0) > time.time()

    def anotar(self, ip):
        ahora = time.time()
        with self.cerrojo:
            recientes = [t for t in self.intentos.get(ip, []) if ahora - t < self.VENTANA] + [ahora]
            self.intentos[ip] = recientes
            if len(recientes) >= self.MAXIMO:
                self.hasta[ip], self.intentos[ip] = ahora + self.CASTIGO, []
            if len(self.intentos) > 10000:
                self.intentos = {k: v for k, v in self.intentos.items() if v and ahora - v[-1] < self.VENTANA}
                self.hasta = {k: v for k, v in self.hasta.items() if v > ahora}


class Manejador(BaseHTTPRequestHandler):
    timeout = 60
    sala = None
    sesiones = None
    fallos = None
    privadas = {}                     # chat privado por persona, creado al vuelo
    priv_cerrojo = threading.Lock()

    def _sala_de(self, quien, privado):
        """La sala grupal, o la privada uno-a-uno de esta persona (con su propia sesión de Orión)."""
        if not privado:
            return self.sala
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", quien)[:40] + "-" + hashlib.sha1(quien.encode()).hexdigest()[:8]
        with Manejador.priv_cerrojo:
            s = Manejador.privadas.get(quien)
            if s is None:
                s = Sala(PRIVADO / f"{slug}.json", guion=self.sala.guion, limite_dia=0)
                Manejador.privadas[quien] = s
            return s

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data:; frame-ancestors 'none'")
        super().end_headers()

    def _json(self, datos, codigo=200, cookie=None):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _alias(self):
        """/equipo, /equipo/api/... y /equipo/fuentes/... son el panel con otro nombre (ver ALIAS_PANEL)."""
        self.prefijo = "/panel"
        u = urlparse(self.path)
        if u.path == ALIAS_PANEL or u.path.startswith(ALIAS_PANEL + "/"):
            self.prefijo = ALIAS_PANEL
            resto = u.path[len(ALIAS_PANEL):]
            nueva = resto if resto.startswith("/fuentes/") else "/panel" + resto
            self.path = nueva + ("?" + u.query if u.query else "")

    def _html(self, nombre):
        cuerpo = (AQUI / nombre).read_bytes()
        if nombre == "panel.html" and self.prefijo != "/panel":
            p = self.prefijo.encode()
            cuerpo = (cuerpo.replace(b'"/panel/api/', b'"' + p + b"/api/")
                      .replace(b"url(/fuentes/", b"url(" + p + b"/fuentes/")
                      .replace(b'href="/panel"', b'href="' + p + b'"'))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _fuente(self, nombre):
        # Plus Jakarta Sans servida desde aquí mismo (la CSP no deja cargar nada de fuera).
        if nombre not in FUENTES:
            return self._json({"error": "no existe"}, 404)
        cuerpo = (AQUI / "fuentes" / nombre).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "font/woff2")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _ip(self):
        return self.headers.get("X-Forwarded-For", "").split(",")[-1].strip() or (
            self.client_address[0] if isinstance(self.client_address, tuple) else "local")

    def _cookie(self, nombre):
        for parte in self.headers.get("Cookie", "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == nombre:
                return v
        return ""

    def _cuerpo(self, maximo=20000):
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if not 0 <= largo <= maximo:
                return None
            return json.loads(self.rfile.read(largo) or b"{}")
        except (ValueError, AttributeError):
            return None

    def _csrf(self):
        return self.headers.get("X-OE") == "1"

    def _set_cookie(self, nombre, valor, path, borrar=False):
        seguro = os.environ.get("ORION_EQUIPO_INSEGURO") != "1"
        base = f"{nombre}={valor}; Path={path}; HttpOnly; SameSite=Strict" + ("; Secure" if seguro else "")
        return base + ("; Max-Age=0" if borrar else f"; Max-Age={HORAS_SESION * 3600}")

    # ------------------------------------------------ GET
    def do_GET(self):
        self._alias()
        url = urlparse(self.path)
        ruta = url.path
        if ruta in ("/", "/index.html"):
            return self._html("sala.html")
        if ruta == "/panel":
            return self._html("panel.html")
        if ruta.startswith("/fuentes/"):
            return self._fuente(ruta[len("/fuentes/"):])
        if ruta.startswith("/panel/api/"):
            return self._panel_get(ruta, url)
        if ruta.startswith("/api/"):
            return self._sala_get(ruta, url)
        self._json({"error": "no existe"}, 404)

    def _quien_sala(self):
        """Quién está en la sala por su cookie; None si no entró o si David lo bloqueó."""
        quien = self.sesiones.quien(self._cookie("oe_sesion"), "persona")
        return quien if quien and quien not in leer_bloqueados() else None

    def _sala_get(self, ruta, url):
        if ruta == "/api/yo":
            quien = self._quien_sala()
            return self._json({"nombre": quien} if quien else {"error": "entra"}, 200 if quien else 401)
        quien = self._quien_sala()
        if not quien:
            return self._json({"error": "entra", "salir": True}, 401)
        if ruta == "/api/sala":
            q = parse_qs(url.query)
            try:
                n = int(q.get("desde", ["0"])[0])
            except ValueError:
                n = 0
            sala = self._sala_de(quien, q.get("privado", ["0"])[0] == "1")
            mensajes, ocupado = sala.desde(n)
            return self._json({"mensajes": mensajes, "ocupado": ocupado, "pausa": PAUSA.exists()})
        if ruta == "/api/informe":
            arch = INFORMES / self._nombre_informe(quien)
            try:
                return self._json({"html": limpiar_informe(arch.read_text(encoding="utf-8"))})
            except OSError:
                return self._json({"html": ""})
        self._json({"error": "no existe"}, 404)

    @staticmethod
    def _nombre_informe(quien):
        limpio = re.sub(r"[^a-z0-9_-]", "", quien.lower()) or "equipo"
        return f"{datetime.now().strftime('%Y-%m-%d')}-{limpio}.html"

    def _access_dueno(self):
        """¿Cloudflare Access ya identificó al dueño? (solo si configuraste ORION_EQUIPO_ACCESS_EMAIL)."""
        if not ACCESS_EMAIL:
            return False
        em = self.headers.get("Cf-Access-Authenticated-User-Email", "").strip().lower()
        return bool(em) and em == ACCESS_EMAIL

    def _panel_autorizado(self):
        return self._access_dueno() or bool(self.sesiones.quien(self._cookie("oe_panel"), "admin"))

    def _panel_get(self, ruta, url):
        if ruta == "/panel/api/sesion":
            return self._json({"configurado": ADMIN.exists(), "dentro": self._panel_autorizado()})
        if not self._panel_autorizado():
            return self._json({"error": "entra", "salir": True}, 401)
        if ruta == "/panel/api/estado":
            hoy = self.sala.cuenta if self.sala.cuenta.get("dia") == datetime.now().strftime("%Y-%m-%d") else {}
            return self._json({"pausa": PAUSA.exists(),
                               "personas": sorted(leer_personas().keys()),
                               "bloqueados": sorted(leer_bloqueados()),
                               "pendientes": len(pendientes()),
                               "pedidos_hoy": {k: v for k, v in hoy.items() if k != "dia"},
                               "paneles": paneles()})
        if ruta == "/panel/api/alertas":
            return self._json({"alertas": alertas_recientes()})
        if ruta == "/panel/api/autorizaciones":
            return self._json({"pendientes": pendientes()})
        if ruta == "/panel/api/informes":
            return self._json({"informes": self._informes_recientes()})
        self._json({"error": "no existe"}, 404)

    @staticmethod
    def _informes_recientes(n=40):
        """Informes de los estudiantes (CASA/informes) y los de Orión (su bóveda)."""
        archivos = []
        try:
            archivos += list(INFORMES.glob("*.md")) + list(INFORMES.glob("*.html"))
        except OSError:
            pass
        try:
            archivos += list((ESPACIO / "boveda" / "outputs" / "seguridad" / "sesiones").glob("*.md"))
        except OSError:
            pass
        filas = []
        for f in sorted(archivos, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:n]:
            try:
                contenido = f.read_text(encoding="utf-8")
            except OSError:
                continue
            if f.suffix == ".html":
                # Ya viene saneado desde que se guardó; lo limpiamos otra vez por si acaso.
                filas.append({"archivo": f.name, "html": limpiar_informe(contenido)})
            else:
                filas.append({"archivo": f.name, "texto": contenido[:4000]})
        return filas

    # ------------------------------------------------ POST
    def do_POST(self):
        self._alias()
        ruta = urlparse(self.path).path
        if ruta.startswith("/panel/api/"):
            return self._panel_post(ruta)
        if ruta.startswith("/api/"):
            return self._sala_post(ruta)
        self._json({"error": "no existe"}, 404)

    def _sala_post(self, ruta):
        if ruta == "/api/entrar":
            ip = self._ip()
            if self.fallos.bloqueada(ip):
                return self._json({"error": "demasiados intentos, espera unos minutos"}, 429)
            j = self._cuerpo() or {}
            if persona_correcta(j.get("usuario"), j.get("clave")):
                if str(j["usuario"]).strip() in leer_bloqueados():
                    return self._json({"error": "tu entrada está bloqueada; habla con David"}, 403)
                t = self.sesiones.crear(str(j["usuario"]).strip(), "persona")
                return self._json({"ok": True}, cookie=self._set_cookie("oe_sesion", t, "/"))
            self.fallos.anotar(ip)
            time.sleep(0.4)
            return self._json({"error": "usuario o contraseña incorrectos"}, 401)
        quien = self._quien_sala()
        if not quien:
            return self._json({"error": "entra", "salir": True}, 401)
        if not self._csrf():
            return self._json({"error": "pedido no válido"}, 403)
        if ruta == "/api/salir":
            self.sesiones.borrar(self._cookie("oe_sesion"))
            return self._json({"ok": True}, cookie=self._set_cookie("oe_sesion", "x", "/", borrar=True))
        if ruta == "/api/pedir":
            if PAUSA.exists():
                return self._json({"error": "David puso el equipo en pausa. Vuelve en un rato."}, 409)
            j = self._cuerpo() or {}
            texto = str(j.get("texto", "")).strip()
            if not texto:
                return self._json({"error": "vacío"}, 400)
            if len(texto) > MAX_TEXTO:
                return self._json({"error": f"máximo {MAX_TEXTO} caracteres"}, 413)
            # El tope diario es por persona y se comparte entre el grupal y el privado.
            if not self.sala.gastar(quien):
                return self._json({"error": "llegaste al tope de pedidos de hoy; mañana sigues"}, 429)
            sala = self._sala_de(quien, bool(j.get("privado")))
            return self._json({"ok": True, "n": sala.pedir(quien, texto)}, 202)
        if ruta == "/api/informe":
            j = self._cuerpo(maximo=8_000_000)
            if j is None:
                return self._json({"error": "el informe pesa demasiado; usa menos imágenes"}, 413)
            limpio = limpiar_informe(j.get("html", ""))
            plano = html.unescape(re.sub(r"<[^>]+>", "", limpio)).strip()
            if len(plano) < 20 and "<img" not in limpio:
                return self._json({"error": "el informe está muy corto"}, 400)
            INFORMES.mkdir(parents=True, exist_ok=True)
            (INFORMES / self._nombre_informe(quien)).write_text(limpio + "\n", encoding="utf-8")
            anotar_alerta("informe", quien, f"{quien} guardó su informe de seguridad de la sesión.")
            return self._json({"ok": True})
        self._json({"error": "no existe"}, 404)

    def _panel_post(self, ruta):
        if ruta == "/panel/api/entrar":
            ip = self._ip()
            if self.fallos.bloqueada(ip):
                return self._json({"error": "demasiados intentos, espera unos minutos"}, 429)
            if not ADMIN.exists():
                return self._json({"error": "El panel no está configurado. En el servidor: ./equipo/admin.sh"}, 400)
            admin = json.loads(ADMIN.read_text(encoding="utf-8"))
            j = self._cuerpo() or {}
            clave_ok = seguridad.clave_correcta(str(j.get("clave") or ""), admin.get("clave", ""))
            codigo_ok = (not admin.get("totp")) or seguridad.totp_correcto(admin["totp"], str(j.get("codigo") or ""))
            if clave_ok and codigo_ok:
                t = self.sesiones.crear("David", "admin")
                return self._json({"ok": True}, cookie=self._set_cookie("oe_panel", t, self.prefijo))
            self.fallos.anotar(ip)
            time.sleep(0.5)
            return self._json({"error": "la clave o el código no son correctos"}, 401)
        if not self._panel_autorizado():
            return self._json({"error": "entra", "salir": True}, 401)
        if not self._csrf():
            return self._json({"error": "pedido no válido"}, 403)
        if ruta == "/panel/api/salir":
            self.sesiones.borrar(self._cookie("oe_panel"))
            return self._json({"ok": True}, cookie=self._set_cookie("oe_panel", "x", self.prefijo, borrar=True))
        j = self._cuerpo() or {}
        if ruta == "/panel/api/autorizar":
            horas = j.get("horas", 8)
            try:
                horas = int(horas)
            except (TypeError, ValueError):
                horas = 8
            return self._json({"ok": aprobar(str(j.get("id") or ""), horas)})
        if ruta == "/panel/api/denegar":
            return self._json({"ok": denegar(str(j.get("id") or ""), str(j.get("motivo") or "")[:300])})
        if ruta == "/panel/api/pausa":
            if j.get("activar"):
                PAUSA.write_text(datetime.now().isoformat(), encoding="utf-8")
            else:
                PAUSA.unlink(missing_ok=True)
            return self._json({"ok": True, "pausa": PAUSA.exists()})
        if ruta == "/panel/api/quitar":
            nombre = str(j.get("nombre") or "").strip()
            quitado = self._quitar_persona(nombre)
            if quitado:
                self.sesiones.borrar_persona(nombre)
                anotar_alerta("quitada", nombre, f"David quitó a {nombre} del equipo.")
            return self._json({"ok": quitado})
        if ruta == "/panel/api/bloquear":
            nombre = str(j.get("nombre") or "").strip()
            activar = bool(j.get("activar", True))
            bloquear_persona(nombre, activar)
            if activar:
                self.sesiones.borrar_persona(nombre)   # lo saca al instante
                anotar_alerta("bloqueada", nombre, f"David bloqueó la entrada de {nombre}.")
            else:
                anotar_alerta("desbloqueada", nombre, f"David desbloqueó a {nombre}.")
            return self._json({"ok": True, "bloqueado": activar})
        if ruta == "/panel/api/avisar":
            nombre = str(j.get("nombre") or "").strip()
            texto = str(j.get("texto") or "").strip()[:500]
            if not nombre or not texto:
                return self._json({"error": "falta a quién o el mensaje"}, 400)
            self.sala.anotar("David", f"Aviso para {nombre}: {texto}")
            anotar_alerta("aviso", nombre, f"David avisó a {nombre}: {texto}")
            return self._json({"ok": True})
        if ruta == "/panel/api/empezar":
            if PAUSA.exists():
                return self._json({"error": "está en pausa; reanuda antes de empezar"}, 409)
            self.sala.arrancar()
            anotar_alerta("empezar", "", "David dio inicio a la sesión; Orión reparte roles.")
            return self._json({"ok": True})
        self._json({"error": "no existe"}, 404)

    @staticmethod
    def _quitar_persona(nombre):
        try:
            lineas = PERSONAS.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        nuevas = [l for l in lineas if not (l.split("\t", 1)[0].strip() == nombre and "\t" in l)]
        if len(nuevas) == len(lineas):
            return False
        PERSONAS.write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
        return True

    def log_message(self, formato, *args):
        pass


class ServidorUnix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    p = argparse.ArgumentParser(description="Sala y panel de Orión Equipo")
    p.add_argument("--puerto", type=int)
    p.add_argument("--socket", default=os.environ.get("ORION_EQUIPO_SOCKET", "/run/orion-equipo/sala.sock"))
    args = p.parse_args()
    Manejador.sala = Sala(limite_dia=int(os.environ.get("ORION_EQUIPO_LIMITE_DIA", "40") or 0))
    Manejador.sesiones = Sesiones()
    Manejador.fallos = Fallos()
    if args.puerto:
        servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
        print(f"Orión Equipo en http://127.0.0.1:{args.puerto}/  (panel en /panel)", flush=True)
    else:
        Path(args.socket).unlink(missing_ok=True)
        servidor = ServidorUnix(args.socket, Manejador)
        os.chmod(args.socket, 0o666)
        print(f"Orión Equipo en {args.socket}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
