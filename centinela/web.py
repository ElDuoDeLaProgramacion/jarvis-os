"""Centinela para las webs del dominio: lee el registro de accesos de Caddy y reconoce ataques por IP real.

Detrás de Cloudflare todas las visitas llegan desde IPs de Cloudflare; la IP real viene en la cabecera
Cf-Connecting-Ip. Por eso un atacante que entra por Cloudflare no se puede bloquear en nftables (se
bloquearía a Cloudflare entero): se bloquea en Cloudflare, por su API, si hay token. Sin token, avisa.

Funciones puras (se prueban en test_centinela.py) + un cliente mínimo de la API de Cloudflare.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

# Lo que delata un intento de inyección o de colarse, buscado en la URL ya decodificada y en el User-Agent.
ATAQUES = {
    "inyección SQL": re.compile(r"union(\s|/\*.*?\*/)+(all\s+)?select|'\s*(or|and)\s*'?\d+'?\s*=\s*'?\d|"
                                r"\bsleep\s*\(\s*\d|benchmark\s*\(|information_schema|\bwaitfor\s+delay|"
                                r"';?\s*(drop|insert|update|delete)\s|\bor\s+1\s*=\s*1\b|extractvalue\s*\(|"
                                r"load_file\s*\(|into\s+outfile", re.I),
    "XSS": re.compile(r"<\s*script|javascript\s*:|\bon(error|load|mouseover|focus)\s*=|<\s*(svg|img|iframe)[^>]*"
                      r"\bon\w+\s*=|document\.cookie|alert\s*\(", re.I),
    "recorrido de rutas": re.compile(r"\.\./|\.\.\\|/etc/(passwd|shadow|hosts)|/proc/self/|c:\\windows|boot\.ini", re.I),
    "ejecución de comandos": re.compile(r"[;|`]\s*(cat|wget|curl|nc|bash|sh|id|whoami|uname)\b|\$\(\s*\w+|"
                                        r"\$\{jndi:|\$\{\$\{|/bin/(ba)?sh\b|cmd\.exe|powershell", re.I),
    "inclusión de archivos": re.compile(r"(php|data|expect|file|zip|phar)://|=\s*https?://[^&]*\.(txt|php)\b", re.I),
}
# Rutas que solo pide quien está buscando huecos (un visitante normal nunca las toca).
SENSIBLES = re.compile(r"/\.(env|git|svn|hg|aws|ssh|htpasswd|DS_Store)\b|/wp-(login|admin|config)|xmlrpc\.php|"
                       r"phpmyadmin|/adminer|/\.well-known/security\.txt\.bak|/(backup|dump|db|database)\.(sql|zip|tar|gz)|"
                       r"/config\.(php|json|yml|yaml)\b|/server-status|/actuator|/vendor/phpunit|/cgi-bin/|/console\b|"
                       r"/HNAP1|/boaform|/shell\b|\.(bak|old|swp|sql)$", re.I)
# Las que ningún visitante de tus webs pide jamás: quien las pide está robando secretos o buscando un panel
# que no existe aquí. Bastan una sola vez para bloquear.
TRAMPAS = re.compile(r"/\.(env|git|svn|hg|aws|ssh|htpasswd|docker|kube)\b|\.env\.(bak|old|local|prod|production|dev|save)\b|"
                     r"/wp-(login|admin|config|content|includes)|xmlrpc\.php|phpmyadmin|/pma\b|/adminer|/vendor/phpunit|"
                     r"/HNAP1|/boaform|/cgi-bin/|/(backup|dump|db|database)\.(sql|zip|tar|gz)|/id_(rsa|ed25519)\b|"
                     r"/(credentials|secrets)\.(json|yml|yaml)", re.I)
ESCANERES = re.compile(r"sqlmap|nikto|nuclei|masscan|zgrab|gobuster|ffuf|wpscan|dirbuster|dirb/|feroxbuster|"
                       r"acunetix|nessus|openvas|netsparker|w3af|hydra|httpx|jaeles|whatweb", re.I)
GRAVES = {"ejecución de comandos", "recorrido de rutas", "busca secretos (.env, .git, wp-login...)"}   # uno solo de estos ya merece bloqueo


def linea(texto):
    """Una línea JSON del registro de Caddy -> dict con lo que importa (None si no es un acceso)."""
    try:
        d = json.loads(texto)
    except ValueError:
        return None
    req = d.get("request")
    if not isinstance(req, dict):
        return None
    cab = {k.lower(): (v[0] if isinstance(v, list) and v else v) for k, v in (req.get("headers") or {}).items()}
    return {
        "t": d.get("ts", 0), "remoto": req.get("remote_ip") or req.get("client_ip") or "",
        "cf_ip": cab.get("cf-connecting-ip", ""), "host": req.get("host", ""), "metodo": req.get("method", ""),
        "uri": req.get("uri", ""), "ua": cab.get("user-agent", ""), "estado": int(d.get("status") or 0),
        "bytes": int(d.get("size") or 0),
    }


def ip_real(acceso, es_cloudflare):
    """Si el acceso llegó desde Cloudflare, la IP real es Cf-Connecting-Ip; si no, la que se conectó."""
    if acceso["cf_ip"] and es_cloudflare(acceso["remoto"]):
        return acceso["cf_ip"], True
    return acceso["remoto"], False


def ataques_en(acceso):
    """Lista de tipos de ataque que se ven en la petición."""
    uri = acceso["uri"]
    for _ in range(2):                      # %252e%252e → %2e%2e → ..
        uri = urllib.parse.unquote_plus(uri)
    texto = f"{uri} {acceso['ua']}"
    out = [nombre for nombre, r in ATAQUES.items() if r.search(texto)]
    ruta = uri.split("?")[0]
    if TRAMPAS.search(ruta):
        out.append("busca secretos (.env, .git, wp-login...)")
    elif SENSIBLES.search(ruta):
        out.append("busca archivos sensibles")
    if ESCANERES.search(acceso["ua"]):
        out.append("escáner automático")
    return out


class Cloudflare:
    """Lo justo de la API: bloquear/soltar una IP en la zona y subir/bajar el nivel de seguridad."""

    def __init__(self, token, zona, abrir=urllib.request.urlopen):
        self.token, self.zona, self.abrir = token, zona, abrir

    def _pedir(self, metodo, ruta, cuerpo=None):
        req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/zones/{self.zona}{ruta}", method=metodo,
                                     data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with self.abrir(req, timeout=20) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read() or b"{}")
            except ValueError:
                return {"success": False, "errors": [{"message": f"HTTP {e.code}"}]}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"success": False, "errors": [{"message": str(e)}]}

    @staticmethod
    def error(r):
        return "; ".join(e.get("message", "?") for e in r.get("errors") or []) or "sin detalle"

    def bloquear(self, ip, nota):
        objetivo = "ip6" if ":" in ip else "ip"
        r = self._pedir("POST", "/firewall/access_rules/rules",
                        {"mode": "block", "configuration": {"target": objetivo, "value": ip}, "notes": nota})
        return (r.get("result") or {}).get("id") if r.get("success") else None, r

    def soltar(self, regla):
        return self._pedir("DELETE", f"/firewall/access_rules/rules/{regla}")

    def nivel(self):
        r = self._pedir("GET", "/settings/security_level")
        return (r.get("result") or {}).get("value") if r.get("success") else None

    def poner_nivel(self, valor):
        return self._pedir("PATCH", "/settings/security_level", {"value": valor})


# Nombres en español de los países de donde más llegan ataques; el resto se muestra con su código (p. ej. "KZ").
PAISES = {
    "US": "Estados Unidos", "CN": "China", "RU": "Rusia", "DE": "Alemania", "NL": "Países Bajos", "FR": "Francia",
    "GB": "Reino Unido", "IN": "India", "BR": "Brasil", "SG": "Singapur", "HK": "Hong Kong", "JP": "Japón",
    "KR": "Corea del Sur", "VN": "Vietnam", "ID": "Indonesia", "UA": "Ucrania", "IR": "Irán", "TR": "Turquía",
    "CA": "Canadá", "AU": "Australia", "IT": "Italia", "ES": "España", "PL": "Polonia", "RO": "Rumania",
    "BG": "Bulgaria", "SE": "Suecia", "FI": "Finlandia", "LT": "Lituania", "TW": "Taiwán", "TH": "Tailandia",
    "PK": "Pakistán", "BD": "Bangladés", "ZA": "Sudáfrica", "MX": "México", "CO": "Colombia", "AR": "Argentina",
    "CL": "Chile", "PE": "Perú", "VE": "Venezuela", "EC": "Ecuador", "PA": "Panamá", "SC": "Seychelles",
}


def origen(ip, token="", abrir=urllib.request.urlopen):
    """País, ciudad y empresa de una IP según ipinfo.io: "Estados Unidos (Ashburn), Google LLC (AS15169)".
    Es la ubicación del centro de datos o del proveedor, no la de la persona. None si no se pudo saber."""
    url = f"https://ipinfo.io/{urllib.parse.quote(ip)}/json" + (f"?token={urllib.parse.quote(token)}" if token else "")
    try:
        with abrir(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=4) as r:
            d = json.loads(r.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("bogon") or not d.get("country"):
        return None
    lugar = PAISES.get(d["country"], d["country"]) + (f" ({d['city']})" if d.get("city") else "")
    org = str(d.get("org") or "")
    m = re.match(r"(AS\d+)\s+(.*)", org)
    empresa = f"{m.group(2)} ({m.group(1)})" if m else org
    return f"{lugar}, {empresa}" if empresa else lugar


def tam(n):
    """Bytes en algo legible: 820 B, 3.4 KB, 12 MB."""
    if n < 1000:
        return f"{n} B"
    if n < 1e6:
        return f"{n / 1e3:.1f} KB"
    return f"{n / 1e6:.1f} MB" if n < 1e7 else f"{n / 1e6:.0f} MB"


def servida(estado, size):
    """¿La web entregó contenido a esa petición? 2xx con cuerpo = sí (posible fuga); 3xx, 4xx, 5xx o vacía = no."""
    return 200 <= estado < 300 and size > 0


def resultado(res):
    """Una línea para el aviso: ¿el ataque logró sacar información?  res = {"codigos": {"404": 3, "200": 1},
    "ok_bytes": 3400, "ok_ejemplo": "GET api.x/.env"} con solo las peticiones maliciosas de esa IP.
    Mira el código HTTP que Caddy devolvió a cada una: 200 con contenido = se sirvió; lo demás = no se llevó nada."""
    codigos = {int(k): v for k, v in (res.get("codigos") or {}).items()}
    total = sum(codigos.values())
    if not total:
        return ""
    lista = ", ".join(f"{k or 'sin respuesta'} ×{v}" for k, v in sorted(codigos.items(), key=lambda kv: (-kv[1], kv[0])))
    ok = res.get("ok", 0)
    pet = "petición maliciosa" if total == 1 else "peticiones maliciosas"
    if ok:
        ej = f"\nPasó: `{res['ok_ejemplo']}` → 200" if res.get("ok_ejemplo") else ""
        return (f"📤 *¿Se llevó datos? ⚠️ POSIBLE:* {ok} de {total} {pet} {'respondió' if ok == 1 else 'respondieron'} 200 "
                f"({tam(res.get('ok_bytes', 0))} entregados). Códigos: {lista}.{ej}\n"
                f"Revisa si lo que devolvió era el archivo de verdad o tu página normal (algunas webs responden 200 a todo).")
    nota = ""
    if any(200 <= k < 300 for k in codigos):
        nota += " Los 200 fueron páginas normales pedidas por su herramienta de ataque, sin nada sensible."
    if any(k >= 500 for k in codigos):
        nota += " La web dio error 5xx: el ataque no sacó datos, pero revisa que no la haya roto."
    sus = "su petición maliciosa" if total == 1 else f"sus {total} {pet}"
    return f"📤 *¿Se llevó datos? ✅ NO:* {sus} no consiguió nada sensible (códigos: {lista}).{nota}" if total == 1 else \
        f"📤 *¿Se llevó datos? ✅ NO:* ninguna de {sus} consiguió nada sensible (códigos: {lista}).{nota}"
