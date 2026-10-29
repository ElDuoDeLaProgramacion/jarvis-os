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
ESCANERES = re.compile(r"sqlmap|nikto|nuclei|masscan|zgrab|gobuster|ffuf|wpscan|dirbuster|dirb/|feroxbuster|"
                       r"acunetix|nessus|openvas|netsparker|w3af|hydra|httpx|jaeles|whatweb", re.I)
GRAVES = {"ejecución de comandos", "recorrido de rutas"}   # uno solo de estos ya merece bloqueo


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
    if SENSIBLES.search(uri.split("?")[0]):
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
