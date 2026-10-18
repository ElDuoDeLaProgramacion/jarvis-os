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
    python3 scripts/ia_externa.py panel --rol auditoria [--n 3] [--guardar carpeta] --archivo resumen.md "pregunta"
        un panel de varias IAs a la vez, elegidas por especialidad, en paralelo. --rol acepta cualquier
        tema (ROLES trae instrucciones afinadas para los comunes); --guardar deja panel-<rol>.json para
        la ventana de propuestas del HUD
    python3 scripts/ia_externa.py flujo --tipo programacion --etapa plan --guardar carpeta [--archivo resumen.md] "pedido"
        un equipo con TODAS las IAs disponibles, por etapas (plan, programar, auditar, QA...). Cada
        llamada hace una etapa y lee las anteriores de la carpeta; --etapa resumen deja un resumen por IA.
        Sin --etapa, lista las etapas del tipo.

Claves en .env (las pone David a mano): GEMINI_API_KEY y OPENROUTER_API_KEY.
Modelos opcionales: GEMINI_MODELO y OPENROUTER_MODELO (si no, Gemini usa el flash más nuevo
y OpenRouter un modelo gratis, de los que terminan en ":free"; así funciona sin saldo).
Solo usa la biblioteca estándar.
"""

import argparse
import concurrent.futures
import http.client
import json
import os
import sys
import time
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

# Por esta API cada IA solo devuelve texto: que no finja videos, imágenes ni escaneos que no hizo.
HONESTO = ("Aquí solo puedes responder con texto: no puedes crear ni adjuntar videos, imágenes, audio ni archivos, "
           "ni ejecutar código, navegar o escanear sistemas. Si te piden algo de eso, dilo claro en la primera línea "
           "y entrega lo más útil que sí puedes (guion, storyboard, prompts listos para la herramienta adecuada, "
           "código, pasos). Nunca finjas haberlo hecho ni inventes resultados.")
SISTEMA = ("Eres una IA consultada por JARVIS, el asistente de David, como segunda opinión. "
           "Responde en español, directo y con argumentos. Si no estás seguro de algo, dilo. " + HONESTO)


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


def servidor():
    """(dirección, clave) del JARVIS del servidor si este equipo es el PC conectado a él; si no, None."""
    base, token = os.environ.get("JARVIS_SERVIDOR", "").strip(), os.environ.get("JARVIS_API_TOKEN", "").strip()
    if not base or len(token) < 24:
        return None
    return base.rstrip("/").removesuffix("/app"), token


_remotas = None
_error_servidor = None   # por qué no se pudo preguntar al servidor, para decirlo bien


def sin_ias():
    """Por qué no hay IAs: en el PC casi siempre es que no llega al servidor, que es donde están las claves."""
    if _error_servidor:
        return (f"No hay IAs externas porque no llego al servidor ({servidor()[0]}): {_error_servidor}. "
                "Las claves están allí. Revisa JARVIS_SERVIDOR en el .env del PC y que el servidor esté encendido.")
    return "No hay ninguna IA externa conectada. David debe poner en .env al menos una clave:"


def configuradas():
    """Las IAs con clave aquí. En el PC sin claves propias, las del servidor: las claves viven solo allí."""
    global _remotas, _error_servidor
    locales = [n for n, p in PROVEEDORES.items() if os.environ.get(p["clave"])]
    if locales or not servidor():
        return locales
    if _remotas is None:
        try:
            _remotas = [n for n in pedir_al_servidor("GET", "/api/ia", timeout=15).get("proveedores", [])
                        if n in PROVEEDORES]
        except RuntimeError as e:
            print(f"(no pude preguntarle al servidor qué IAs tiene: {e})", file=sys.stderr)
            _remotas, _error_servidor = [], str(e)
    return _remotas


def pedir_al_servidor(metodo, ruta, cuerpo=None, timeout=150):
    base, token = servidor()
    req = urllib.request.Request(base + ruta, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 method=metodo, headers={"Authorization": f"Bearer {token}",
                                                         "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("error", "")
        except ValueError:
            detalle = ""
        error = RuntimeError(f"el servidor respondió {e.code}: {detalle}"[:400])
        error.codigo = e.code
        raise error from None
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RuntimeError(f"no pude conectar con el servidor ({e})") from None


def llamar(proveedor, ruta, cuerpo=None, timeout=120):
    p = PROVEEDORES[proveedor]
    if not os.environ.get(p["clave"]) and servidor():
        # El PC usa las claves del servidor a través de su API (servidor/api.py, /api/ia).
        return pedir_al_servidor("POST", "/api/ia", {"proveedor": proveedor, "ruta": ruta, "cuerpo": cuerpo},
                                 timeout + 30)
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
    except (OSError, http.client.HTTPException, ValueError) as e:   # se cortó, tardó demasiado o no es JSON
        raise RuntimeError(f"{proveedor} no respondió bien: {e!r}") from None


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


def preguntar(proveedor, pregunta, modelo=None, sistema=SISTEMA, lista=None):
    ultimo = None
    for m in ([modelo] if modelo else (lista or candidatos(proveedor))):
        try:
            datos = llamar(proveedor, "/chat/completions", {
                "model": m,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": pregunta}],
            })
        except RuntimeError as e:
            # 404: ya no existe; 429: sin cuota; 400/413: la pregunta no le cabe (modelos de contexto corto).
            if getattr(e, "codigo", None) in (400, 404, 413, 429):
                ultimo = e
                continue
            raise
        texto = (datos.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return datos.get("model") or m, texto.strip()
    raise RuntimeError(f"ningún modelo tiene cuota ahora (puede ser el límite diario gratis). Último error: {ultimo}")


# Panel: para cada especialidad, qué pedirle a cada IA y qué modelos suelen ser mejores en eso
# (palabras del nombre del modelo, de más a menos preferido). Los nombres cambian: lo que no
# coincide queda al final, pero sigue pudiendo entrar. Son solo los más comunes: cualquier otro
# tema sirve como --rol (por ejemplo "nutricion" o "musica") y usa el experto genérico.
CODIGO = ["coder", "devstral", "codestral", "qwen3", "deepseek", "gpt-oss", "kimi", "glm", "llama"]
RAZONA = ["r1", "deepseek", "qwen3", "kimi", "gpt-oss", "glm", "nemotron", "llama", "mistral"]
CREATIVO = ["gemini", "llama", "kimi", "mistral", "qwen", "deepseek", "gpt-oss", "glm"]
GENERAL = ["deepseek", "qwen3", "kimi", "llama", "gemini", "gpt-oss", "mistral", "glm"]
ROLES = {
    "auditoria": ("Eres auditor de ciberseguridad sénior. Revisa lo que te pasan y lista vulnerabilidades y "
                  "malas prácticas concretas, cada una con gravedad (Alta, Media, Baja), por qué importa y el arreglo "
                  "(con el código corregido si aplica). No inventes: si algo no se puede saber con lo que ves, dilo.",
                  RAZONA),
    "programacion": ("Eres ingeniero de software sénior. Evalúa la calidad del código y la arquitectura: errores, "
                     "deuda técnica, pruebas, mantenibilidad y rendimiento. Da una nota de 1 a 10 y las 5 mejoras "
                     "más valiosas en orden, cada una con el código propuesto.", CODIGO),
    "planeacion": ("Eres jefe de producto y planeación. Evalúa el proyecto como producto: objetivo, alcance, "
                   "prioridades, riesgos y qué falta. Propón los próximos 5 pasos en orden y qué dejarías de hacer. "
                   "Si ayuda, dibuja el plan como diagrama.", CREATIVO),
    "ideas": ("Eres un juez de ideas exigente. Puntúa de 1 a 10 problema real, diferencia, viabilidad, costo y "
              "potencial; luego los 3 riesgos más serios y cómo probar la idea barato en una semana.", RAZONA),
    "diseno": ("Eres diseñador de producto e interfaces. Critica la experiencia y la interfaz: claridad, jerarquía, "
               "accesibilidad y flujo. Da las 5 mejoras de más impacto y una maqueta de la pantalla propuesta "
               "en HTML.", CREATIVO),
    "marketing": ("Eres estratega de marketing. Propón público objetivo, propuesta de valor, mensajes, canales y "
                  "3 campañas concretas con textos de ejemplo y cómo medir cada una. Si encaja, entrega un lienzo "
                  "(canvas) o una landing en HTML.", CREATIVO),
    "negocio": ("Eres consultor de negocio. Analiza modelo de negocio, ingresos, costos, competencia y riesgos. "
                "Entrega un Business Model Canvas y los 3 movimientos con más retorno.", RAZONA),
    "contenido": ("Eres creador de contenido y guionista. Propón ideas de videos o publicaciones con gancho, guion "
                  "breve, título y formato por plataforma.", CREATIVO),
    "presentaciones": ("Eres experto en presentaciones. Entrega la presentación completa diapositiva por diapositiva: "
                       "título, puntos clave y notas del orador.", CREATIVO),
    "finanzas": ("Eres analista financiero. Revisa números, supuestos, flujo de caja y escenarios; señala riesgos y "
                 "da recomendaciones concretas con cifras. No es asesoría profesional: dilo si hace falta un experto.",
                 RAZONA),
    "datos": ("Eres científico de datos. Propón qué medir, cómo analizarlo, consultas o código (SQL o Python) y "
              "qué conclusiones se pueden sacar y cuáles no.", CODIGO),
    "devops": ("Eres ingeniero DevOps. Revisa despliegue, servidores, CI, copias de seguridad, monitoreo y costos. "
               "Da los cambios concretos con los archivos de configuración propuestos.", CODIGO),
    "producto": ("Eres jefe de producto. Define usuarios, problemas, funciones priorizadas (MoSCoW), métricas de "
                 "éxito y el flujo principal como diagrama.", CREATIVO),
    "investigacion": ("Eres investigador. Explica el estado del tema, lo que se sabe con certeza, lo dudoso, las "
                      "opciones comparadas y qué fuentes consultar.", RAZONA),
    "educacion": ("Eres profesor experto. Explica el tema con un plan de aprendizaje por pasos, ejemplos, "
                  "ejercicios y cómo comprobar que se entendió.", GENERAL),
    "legal": ("Eres asesor legal general. Señala riesgos legales, licencias, privacidad y términos a revisar. "
              "Aclara que no sustituye a un abogado y cuándo hace falta uno.", RAZONA),
    "redaccion": ("Eres editor y redactor. Mejora el texto: claridad, tono, estructura y errores; entrega la "
                  "versión reescrita completa.", CREATIVO),
    "arquitectura": ("Eres arquitecto de software. Propón la estructura: módulos, archivos, datos, dependencias e "
                     "interfaces entre partes, como diagrama, y las decisiones técnicas con su porqué.", CODIGO),
    "revision": ("Eres revisor de código exigente. Busca errores, casos borde, nombres confusos y duplicación en "
                 "el código propuesto; da cada problema con el arreglo en ```diff.", CODIGO),
    "qa": ("Eres ingeniero de QA. Escribe el plan de pruebas, los casos (normales, borde y de error) y las pruebas "
           "automáticas en código; señala qué fallaría con lo propuesto y cómo reproducirlo.", CODIGO),
    "video": ("Eres productor y guionista de video. Entrega guion con tiempos, storyboard escena por escena, "
              "textos en pantalla, música sugerida y prompts listos para herramientas de video (Veo, Sora, Runway, "
              "Kling...). Si no puedes generar el video tú, dilo en la primera línea.", CREATIVO),
    "edicion": ("Eres editor final. Toma lo producido, corrige, une y pule: entrega la versión final lista para "
                "publicar y el plan de edición (cortes, ritmo, subtítulos, formatos por plataforma).", CREATIVO),
    "critica": ("Eres el abogado del diablo. Busca lo que falla en lo propuesto: supuestos débiles, riesgos, "
                "lo que falta y lo que sobra; luego di qué cambiarías.", RAZONA),
}
# Para temas sin rol propio: el mismo encargo, con el tema como especialidad.
GENERICO = ("Eres experto sénior en {tema}. Analiza lo que te pasan desde tu especialidad: qué está bien, qué "
            "falla, riesgos y las 5 propuestas más valiosas en orden, concretas y con ejemplos.")
ALIAS = {"seguridad": "auditoria", "codigo": "programacion", "plan": "planeacion", "diseño": "diseno",
         "ux": "diseno", "ui": "diseno", "negocios": "negocio", "ventas": "marketing", "redes": "contenido",
         "videos": "contenido", "presentacion": "presentaciones", "diapositivas": "presentaciones",
         "dinero": "finanzas", "analisis": "datos", "servidores": "devops", "infraestructura": "devops",
         "aprender": "educacion", "textos": "redaccion", "pruebas": "qa", "testing": "qa",
         "arquitecto": "arquitectura", "edicion de video": "edicion", "editar": "edicion"}

# Cómo entregar lo que se puede ver: JARVIS lo muestra en la ventana de propuestas del HUD y de la app.
FORMATO = ("Formato de lo visual: el código o los cambios van en bloques ``` con el lenguaje (```diff para "
           "cambios a archivos existentes); pantallas, landings, lienzos o maquetas en un solo bloque ```html "
           "autocontenido (CSS y JS dentro, sin recursos externos); diagramas en ```mermaid; una presentación en "
           "un bloque ```slides con las diapositivas separadas por una línea ---. Solo usa estos bloques cuando "
           "aporten.")


def rol_de(nombre):
    """Devuelve (clave, instrucciones, preferidos). Acepta cualquier tema, no solo los de ROLES."""
    clave = " ".join((nombre or "").strip().lower().split())
    clave = ALIAS.get(clave, clave)
    if clave in ROLES:
        return clave, ROLES[clave][0], ROLES[clave][1]
    return clave or "general", GENERICO.format(tema=clave or "el tema"), GENERAL


def ranking(preferidos, ids):
    def nota(m):
        b = m.lower()
        return next((i for i, k in enumerate(preferidos) if k in b), len(preferidos))
    return sorted(ids, key=nota)


def armar_panel(preferidos, n):
    """Lista de (proveedor, [modelos a probar en orden]) con n miembros de familias distintas."""
    miembros = []
    if "gemini" in configuradas():
        try:
            miembros.append(("gemini", candidatos("gemini")))
        except RuntimeError:
            pass
    if "openrouter" in configuradas():
        fijo = os.environ.get("OPENROUTER_MODELO")
        todos = modelos("openrouter")
        # Con saldo (OPENROUTER_PANEL_DE_PAGO=1) entran todos; si no, solo los gratis.
        pool = todos if os.environ.get("OPENROUTER_PANEL_DE_PAGO") == "1" else [m for m in todos if m.endswith(":free")]
        pool = [m for m in pool if m != "openrouter/auto"]
        usadas = set()
        ordenados = ranking(preferidos, pool)
        for m in ordenados:
            familia = m.split("/")[0]
            if familia in usadas:
                continue
            usadas.add(familia)
            # Si este no tiene cuota, se prueba el siguiente de la misma especialidad que nadie usa.
            reserva = [x for x in ordenados if x.split("/")[0] not in usadas][:3]
            miembros.append(("openrouter", [m] + reserva))
            if len(miembros) >= n:
                break
        if fijo and not any(fijo in l for _, l in miembros):
            miembros.insert(0, ("openrouter", [fijo]))
    return miembros[:n]


def panel(nombre, pregunta, n, guardar=None, resumen=None):
    rol, instrucciones, preferidos = rol_de(nombre)
    miembros = armar_panel(preferidos, n)
    if not miembros:
        print("No pude armar el panel. " + sin_ias())
        return 1
    sistema = f"{instrucciones} Responde en español, directo y con argumentos. {FORMATO} {HONESTO}"
    respuestas = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(miembros)) as ex:
        futuros = [ex.submit(preguntar, prov, pregunta, None, sistema, lista) for prov, lista in miembros]
        for (prov, lista), f in zip(miembros, futuros):
            try:
                usado, texto = f.result()
                respuestas.append({"modelo": usado, "proveedor": prov, "texto": texto})
            except Exception as e:
                respuestas.append({"modelo": lista[0], "proveedor": prov, "error": str(e)})
    if guardar:
        # Para la ventana de propuestas (hud/propuestas.html): un JSON por rol en la carpeta del panel.
        carpeta = Path(guardar)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / ("panel-" + "".join(c if c.isalnum() else "-" for c in rol).strip("-") + ".json")
        destino.write_text(json.dumps({
            "fecha": time.strftime("%Y-%m-%d %H:%M"), "rol": rol, "pregunta": (resumen or pregunta)[:2000],
            "respuestas": respuestas}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"# Panel de {rol}: {len(miembros)} IAs\n")
    for r in respuestas:
        print(f"## {r['modelo']}\n{r.get('texto') or 'Error: ' + r.get('error', '')}\n")
    if guardar:
        print(f"(guardado en {destino})")
    return 1 if any("error" in r for r in respuestas) else 0


# ---------- Flujo: todas las IAs disponibles, por etapas ----------
# Cada etapa: (nombre, roles que se reparten las IAs, encargo). Todas las IAs del equipo trabajan en
# cada etapa; los roles se reparten entre ellas y cada etapa ve lo que dejaron las anteriores.
FLUJOS = {
    "auditoria": [
        ("escaneo", ["auditoria", "programacion", "devops"],
         "Analiza lo que te pasan (código, configuración y salida de las herramientas de escaneo de JARVIS) y "
         "lista cada hallazgo con gravedad, evidencia (archivo, línea o salida) y arreglo."),
        ("verificacion", ["auditoria", "critica"],
         "Revisa los hallazgos de la etapa anterior: confirma los que tienen evidencia, marca los falsos positivos "
         "y añade lo que se les pasó. Termina con la lista final ordenada por gravedad."),
    ],
    "programacion": [
        ("plan", ["planeacion", "arquitectura", "producto"],
         "Haz el plan del trabajo: alcance, arquitectura, archivos, pasos en orden y riesgos. Reparte el trabajo "
         "en partes numeradas que distintas personas puedan programar en paralelo."),
        ("programar", ["programacion"],
         "Programa siguiendo el plan de la etapa anterior. Eres el programador {parte} de {total}: encárgate sobre "
         "todo de la parte {parte} del plan (si hay menos partes, de la que más falte) y entrega el código completo."),
        ("auditar", ["auditoria", "revision"],
         "Audita el código de la etapa anterior: seguridad, errores y calidad, cada problema con su arreglo."),
        ("qa", ["qa"],
         "Prueba lo construido: plan de pruebas, casos y pruebas automáticas; di qué falla y cómo arreglarlo."),
    ],
    "marketing": [
        ("planificar", ["marketing", "negocio", "producto"],
         "Planifica: objetivo, público, mensaje, canales, calendario y cómo medir."),
        ("desarrollar", ["contenido", "redaccion"],
         "Desarrolla la idea del plan: piezas concretas, textos, guiones y ganchos listos para usar."),
        ("producir", ["video", "diseno"],
         "Produce lo visual de lo desarrollado: videos (guion, storyboard y prompts) y diseños (maquetas en HTML, "
         "piezas, paleta). Si algo no lo puedes generar tú, dilo y deja el prompt para la herramienta adecuada."),
        ("editar", ["edicion", "critica"],
         "Edita y pule todo lo anterior hasta la versión final; señala lo que no convence y cómo mejorarlo."),
    ],
    "diseno": [
        ("investigar", ["producto", "diseno"], "Define usuarios, objetivos, flujo y referencias del diseño."),
        ("disenar", ["diseno"], "Diseña las pantallas propuestas como maquetas HTML autocontenidas."),
        ("revisar", ["critica", "qa"], "Revisa las maquetas: usabilidad, accesibilidad, coherencia y errores."),
    ],
    "investigacion": [
        ("investigar", ["investigacion", "datos"],
         "Explica el tema con lo que te pasan (la búsqueda web de JARVIS va en el contexto): lo seguro, lo dudoso "
         "y las opciones comparadas."),
        ("contrastar", ["critica", "investigacion"],
         "Contrasta lo anterior: qué se contradice, qué falta y cuál es la conclusión mejor sustentada."),
    ],
    "ideas": [
        ("analizar", ["ideas", "negocio", "finanzas"], "Evalúa la idea desde tu especialidad, con nota de 1 a 10."),
        ("criticar", ["critica", "planeacion"],
         "Cuestiona las evaluaciones anteriores y propone cómo probar la idea barato en una semana."),
    ],
}
TIPO_ALIAS = {"seguridad": "auditoria", "codigo": "programacion", "proyecto": "programacion", "app": "programacion",
              "software": "programacion", "contenido": "marketing", "busqueda": "investigacion",
              "investigar": "investigacion", "aprender": "investigacion", "comparar": "investigacion",
              "tendencias": "marketing", "canales": "marketing", "evaluar": "ideas", "campana": "marketing", "redes": "marketing",
              "videos": "marketing", "diseño": "diseno", "ux": "diseno", "idea": "ideas", "negocio": "ideas"}


def etapas_a_medida(texto):
    """--etapas "investigar=investigacion,datos; proponer=nutricion; revisar=critica,qa" (y, si quieres,
    ": encargo" tras los roles). Así cualquier tema tiene su propio flujo, no solo los de FLUJOS."""
    trozos = [t.strip() for t in (texto or "").split(";") if t.strip()]
    etapas = []
    for i, trozo in enumerate(trozos):
        nombre, _, resto = trozo.partition("=")
        roles, _, encargo = resto.partition(":")
        roles = [r.strip() for r in roles.split(",") if r.strip()] or [nombre.strip()]
        if not encargo.strip():
            encargo = ("Analiza el pedido desde tu especialidad y propone." if i == 0 else
                       "Revisa todo lo anterior, corrige lo que falle y deja la versión final." if i == len(trozos) - 1
                       else "Construye sobre lo que hicieron las etapas anteriores y entrega tu parte.")
        etapas.append((nombre.strip().lower(), roles, encargo.strip()))
    return etapas


def etapas_de(tipo, a_medida=None):
    """Las etapas del tipo. Con a_medida (--etapas), las que diga. Cualquier otro tema: expertos de
    ese tema y luego una crítica."""
    if a_medida:
        return " ".join((tipo or "a medida").strip().lower().split()), a_medida
    clave = " ".join((tipo or "").strip().lower().split())
    clave = TIPO_ALIAS.get(clave, clave)
    if clave in FLUJOS:
        return clave, FLUJOS[clave]
    tema = clave or "general"
    return tema, [("analizar", [tema, "investigacion"], "Analiza el pedido desde tu especialidad y propone."),
                  ("criticar", ["critica"], "Cuestiona lo anterior y deja la mejor versión combinada.")]


def equipo_completo(carpeta):
    """Todas las IAs disponibles (familias distintas), fijas para todo el flujo en <carpeta>/equipo.ias."""
    archivo = carpeta / "equipo.ias"   # no es .json: la ventana de propuestas lee los .json como paneles
    if archivo.exists():
        try:
            return [tuple(m) for m in json.loads(archivo.read_text(encoding="utf-8"))["equipo"]]
        except (ValueError, KeyError, OSError):
            pass
    tope = int(os.environ.get("JARVIS_IAS_MAX", "8"))
    miembros = armar_panel(GENERAL, max(1, tope))
    if miembros:
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps({"equipo": miembros}, ensure_ascii=False, indent=1), encoding="utf-8")
    return miembros


def repartir(roles, miembros):
    """A cada IA, un rol. Cada rol recibe primero a la IA que mejor le va; luego se reparten las demás."""
    libres, asignado = list(range(len(miembros))), {}
    while libres:
        for rol in roles:
            if not libres:
                break
            _, _, preferidos = rol_de(rol)
            mejor = ranking(preferidos, [miembros[i][1][0] for i in libres])[0]
            i = next(i for i in libres if miembros[i][1][0] == mejor)
            asignado[i] = rol
            libres.remove(i)
    return [asignado[i] for i in range(len(miembros))]


def _nombre_json(texto):
    return "".join(c if c.isalnum() else "-" for c in texto).strip("-")


def anteriores(carpeta, nombres, tope=45000):
    """Lo que dejaron las etapas anteriores, para pasárselo a la siguiente."""
    partes = []
    for i, nombre in enumerate(nombres, 1):
        f = carpeta / f"panel-{i}-{_nombre_json(nombre)}.json"
        if not f.exists():
            continue
        for r in json.loads(f.read_text(encoding="utf-8")).get("respuestas", []):
            if r.get("texto"):
                partes.append(f"### Etapa {nombre} · {r.get('rol', '')} · {r['modelo']}\n{r['texto']}")
    texto = "\n\n".join(partes)
    return texto[-tope:] if len(texto) > tope else texto


def correr(tareas):
    """[(miembro, sistema, pregunta, extra)] en paralelo -> respuestas con su modelo o su error."""
    salida = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(tareas))) as ex:
        futuros = [ex.submit(preguntar, prov, preg, None, sist, lista) for (prov, lista), sist, preg, _ in tareas]
        for ((prov, lista), _, _, extra), f in zip(tareas, futuros):
            try:
                usado, texto = f.result()
                salida.append({"modelo": usado, "proveedor": prov, "texto": texto, **extra})
            except Exception as e:
                salida.append({"modelo": lista[0], "proveedor": prov, "error": str(e), **extra})
    return salida


def trabajo_del_flujo(carpeta, nombres):
    """[(etapa, respuesta)] de todas las etapas ya hechas, solo las que traen texto."""
    salida = []
    for i, nombre in enumerate(nombres, 1):
        f = carpeta / f"panel-{i}-{_nombre_json(nombre)}.json"
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")).get("respuestas", []):
                if r.get("texto") and "ia" in r:
                    salida.append((nombre, r))
    return salida


def escribir_hojas(carpeta, tipo, asunto, nombres, miembros, trabajo, respuestas):
    """Las hojas que pidió David: resumen general, una por IA y una por equipo. Todas empiezan con los
    nombres de todas las IAs usadas. La conclusión de Orión se añade al final del resumen general."""
    hojas = carpeta / "hojas"
    hojas.mkdir(parents=True, exist_ok=True)
    for viejo in hojas.glob("*.md"):
        if viejo.name != "00-resumen-general.md":
            viejo.unlink()
    usadas = [m[1][0] for m in miembros]
    # Los agentes de Claude que entraron en alguna etapa (panel-claude.json) también cuentan, y Orión dirige.
    agentes = []
    try:
        agentes = [r for r in json.loads((carpeta / "panel-claude.json").read_text(encoding="utf-8")).get("respuestas", [])
                   if r.get("texto")]
    except (OSError, ValueError):
        pass
    todas = usadas + [r.get("modelo", "agente de Claude") for r in agentes] + ["Orión (Claude, dirige)"]
    fecha = time.strftime("%Y-%m-%d %H:%M")
    cabecera = (f"**IAs usadas ({len(todas)}):** " + ", ".join(todas) +
                f"\n\n**Pedido:** {asunto.splitlines()[0][:300] if asunto else ''}\n**Tipo:** {tipo} · **Fecha:** {fecha}\n")
    # Frontmatter de la bóveda y, justo debajo del título, los nombres de todas las IAs.
    frente = (f"---\nfecha: {fecha[:10]}\ntipo: panel-hoja\ntags: [panel, {_nombre_json(tipo).lower()}]\n"
              f"modelos: {json.dumps(todas, ensure_ascii=False)}\n---\n")
    por_ia = {r["ia"]: r for r in respuestas if "ia" in r and "equipo" not in r}
    por_equipo = {r["equipo"]: r for r in respuestas if "equipo" in r}

    def texto_de(r, abajo=""):
        return (r or {}).get("texto") or f"(no respondió: {(r or {}).get('error', 'no tuvo trabajo')}){abajo}"

    def primera(t):
        return next((l.strip(" -*#") for l in t.splitlines() if l.strip(" -*#")), "")

    # Una hoja por IA
    lineas_ia = []
    for i, nombre in enumerate(usadas):
        papeles = [f"- **{etapa}:** {r.get('rol', '')}" for etapa, r in trabajo if r["ia"] == i]
        entregas = [f"### {etapa} · {r.get('rol', '')}\n\n{r['texto']}" for etapa, r in trabajo if r["ia"] == i]
        suyo = texto_de(por_ia.get(i), "; abajo está todo lo que entregó" if entregas else "")
        archivo = hojas / f"ia-{i + 1:02d}-{_nombre_json(nombre)[:60]}.md"
        archivo.write_text(f"{frente}# {nombre}\n\n{cabecera}\n## Su papel\n" + ("\n".join(papeles) or "- (no trabajó)") +
                           f"\n\n## Qué hizo (en sus palabras)\n{suyo}\n\n## Lo que entregó\n\n" +
                           ("\n\n".join(entregas) or "(nada)") + "\n", encoding="utf-8")
        lineas_ia.append(f"- **{nombre}** ({', '.join(sorted({r.get('rol', '') for _, r in trabajo if r['ia'] == i})) or 'sin trabajo'}): "
                         f"{primera(suyo)} → [[{archivo.stem}]]")

    for j, r in enumerate(agentes, len(usadas) + 1):
        nombre = r.get("modelo", "agente de Claude")
        papel = r.get("etapa") or r.get("rol") or "agente de Claude"
        archivo = hojas / f"ia-{j:02d}-{_nombre_json(nombre)[:60]}.md"
        archivo.write_text(f"{frente}# {nombre}\n\n{cabecera}\n## Su papel\n- {papel} (agente de Claude, mira los archivos de verdad)"
                           f"\n\n## Qué hizo\n{r['texto']}\n", encoding="utf-8")
        lineas_ia.append(f"- **{nombre}** ({papel}): {primera(r['texto'])} → [[{archivo.stem}]]")

    # Una hoja por equipo (etapa + rol con dos o más IAs)
    lineas_equipo = []
    grupos = {}
    for etapa, r in trabajo:
        grupos.setdefault((etapa, r.get("rol", "")), []).append(r["ia"])
    for (etapa, rol), ias in grupos.items():
        nombres_eq = [usadas[i] for i in ias]
        if len(ias) < 2:
            lineas_equipo.append(f"- **{etapa} · {rol}:** {nombres_eq[0]} (sola)")
            continue
        r = por_equipo.get(f"{etapa} · {rol}")
        archivo = hojas / f"equipo-{nombres.index(etapa) + 1}-{_nombre_json(etapa)}-{_nombre_json(rol)}.md"
        archivo.write_text(f"{frente}# Equipo «{rol}» · etapa {etapa}\n\n{cabecera}\n## Integrantes ({len(ias)})\n" +
                           "\n".join(f"- {n}" for n in nombres_eq) + f"\n\n## Qué hizo el equipo\n{texto_de(r)}\n",
                           encoding="utf-8")
        lineas_equipo.append(f"- **{etapa} · {rol}:** {', '.join(nombres_eq)} → [[{archivo.stem}]]")

    # Resumen general (la conclusión de Orión, si ya estaba, se conserva)
    general = hojas / "00-resumen-general.md"
    conclusion = ""
    if general.exists():
        previo = general.read_text(encoding="utf-8")
        if "## Conclusión de Orión" in previo:
            conclusion = previo[previo.index("## Conclusión de Orión"):]
    general.write_text(f"{frente}# Resumen general\n\n{cabecera}\n## Etapas\n" + " → ".join(nombres) +
                       f"\n\n## Equipos\n" + ("\n".join(lineas_equipo) or "- (ninguno)") +
                       f"\n\n## Cada IA\n" + "\n".join(lineas_ia) + "\n\n" +
                       (conclusion or "## Conclusión de Orión\n(la escribe Orión al cerrar)\n"), encoding="utf-8")
    return hojas


def flujo(tipo, etapa, pedido, carpeta, resumen, a_medida=None):
    # Las etapas a medida se guardan en la carpeta, así las demás llamadas no tienen que repetirlas.
    guardadas = Path(carpeta) / "etapas.ias" if carpeta else None
    if a_medida and guardadas:
        guardadas.parent.mkdir(parents=True, exist_ok=True)
        guardadas.write_text(a_medida, encoding="utf-8")
    elif guardadas and guardadas.exists():
        a_medida = guardadas.read_text(encoding="utf-8")
    tipo, etapas = etapas_de(tipo, etapas_a_medida(a_medida))
    nombres = [e[0] for e in etapas]
    if not etapa:
        print(f"Flujo de {tipo}: " + " -> ".join(nombres) + " -> resumen")
        return 0
    if not carpeta:
        print("Falta --guardar <carpeta del panel>.")
        return 2
    carpeta = Path(carpeta)
    miembros = equipo_completo(carpeta)
    if not miembros:
        print(sin_ias())
        return 1
    if etapa == "resumen":
        # Cada IA resume lo suyo de todas las etapas, y cada equipo (las IAs de una etapa con el mismo rol)
        # cuenta qué hizo junto. Luego quedan las hojas: resumen general, una por IA y una por equipo.
        trabajo = trabajo_del_flujo(carpeta, nombres)
        todo, equipos = {}, {}
        for nombre, r in trabajo:
            todo.setdefault(r["ia"], []).append(f"### {nombre} ({r.get('rol', '')})\n{r['texto']}")
            equipos.setdefault((nombre, r.get("rol", "")), []).append(r)
        asunto = (resumen or pedido)[:1500]
        tareas = []
        for i, m in enumerate(miembros):
            suyo = todo.get(i)
            if suyo:
                tareas.append((m, "Eres una de las IAs del equipo de JARVIS. Responde en español. " + HONESTO,
                               "Resume en 5 a 8 líneas tu trabajo en este pedido: qué hiciste, lo más importante que "
                               "encontraste o propusiste, qué recomiendas y qué no pudiste hacer.\n\nPedido: "
                               f"{asunto}\n\nLo tuyo:\n" + "\n\n".join(suyo)[-30000:], {"ia": i}))
        for (nombre, rol_equipo), rs in equipos.items():
            if len(rs) < 2:
                continue   # una IA sola en su rol no es equipo: su hoja ya lo cuenta
            juntos = "\n\n".join(f"### {miembros[r['ia']][1][0]}\n{r['texto']}" for r in rs)
            tareas.append((miembros[rs[0]["ia"]], "Hablas por un equipo de IAs de JARVIS. Responde en español. " + HONESTO,
                           f"Ustedes fueron el equipo «{rol_equipo}» en la etapa «{nombre}». Resume en 5 a 10 líneas "
                           "qué hizo el equipo junto, cómo se repartieron el trabajo, qué aportó cada una (por nombre) "
                           f"y qué quedó pendiente.\n\nPedido: {asunto}\n\nLo del equipo:\n" + juntos[-30000:],
                           {"equipo": f"{nombre} · {rol_equipo}", "etapa": nombre, "rol": rol_equipo}))
        respuestas = correr(tareas)
        nombre_json, rol = "panel-9-resumen-por-ia.json", "resumen por IA y por equipo"
        hojas = escribir_hojas(carpeta, tipo, asunto, nombres, miembros, trabajo, respuestas)
    else:
        if etapa not in nombres:
            print(f"La etapa {etapa} no existe en {tipo}: " + ", ".join(nombres + ["resumen"]))
            return 2
        n = nombres.index(etapa)
        _, roles, encargo = etapas[n]
        previo = anteriores(carpeta, nombres[:n])
        reparto = repartir(roles, miembros)
        tareas = []
        for i, (m, rol) in enumerate(zip(miembros, reparto)):
            clave, instrucciones, _ = rol_de(rol)
            mismos = [j for j, r in enumerate(reparto) if r == rol]
            texto = encargo.format(parte=mismos.index(i) + 1, total=len(mismos))
            sistema = (f"{instrucciones} Eres parte de un equipo de {len(miembros)} IAs que trabaja por etapas; "
                       f"esta es la etapa «{etapa}». Responde en español, directo. {FORMATO} {HONESTO}")
            pregunta = f"{pedido}\n\n## Tu encargo en esta etapa\n{texto}"
            if previo:
                pregunta += f"\n\n## Lo que hicieron las etapas anteriores\n{previo}"
            tareas.append((m, sistema, pregunta, {"rol": clave, "ia": i}))
        respuestas = correr(tareas)
        nombre_json, rol = f"panel-{n + 1}-{_nombre_json(etapa)}.json", f"{n + 1}. {etapa}"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre_json
    destino.write_text(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M"), "rol": rol, "tipo": tipo,
                                   "pregunta": (resumen or pedido)[:2000], "respuestas": respuestas},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"# {tipo} · {rol}: {len(respuestas)} IAs\n")
    for r in respuestas:
        print(f"## {r['modelo']}{' · ' + r['rol'] if r.get('rol') else ''}\n"
              f"{r.get('texto') or 'Error: ' + r.get('error', '')}\n")
    print(f"(guardado en {destino})")
    if etapa == "resumen":
        print(f"(hojas: {hojas}: 00-resumen-general.md, una por IA y una por equipo)")
    return 0 if any(r.get("texto") for r in respuestas) else 1


def main():
    cargar_env()
    a = argparse.ArgumentParser(description="IAs externas a Claude para JARVIS")
    a.add_argument("pregunta", nargs="*")
    a.add_argument("--ia", choices=list(PROVEEDORES))
    a.add_argument("--modelo", help="modelo concreto (en OpenRouter: proveedor/modelo)")
    a.add_argument("--todas", action="store_true", help="preguntar a todas las configuradas")
    a.add_argument("--archivo", help="añadir el texto de este archivo a la pregunta")
    a.add_argument("--rol", help="panel: cualquier tema; con instrucciones propias: " + ", ".join(ROLES))
    a.add_argument("--guardar", help="panel: carpeta donde guardar las respuestas para la ventana de propuestas")
    a.add_argument("--n", type=int, default=3, help="panel: cuántas IAs (máximo 6)")
    a.add_argument("--tipo", help="flujo: auditoria, programacion, marketing, diseno, ideas o cualquier tema")
    a.add_argument("--etapa", help="flujo: la etapa a correr (sin ella, lista las etapas) o 'resumen'")
    a.add_argument("--etapas", help='flujo a medida: "nombre=rol,rol[: encargo]; nombre=rol..." (se guarda en la carpeta)')
    a.add_argument("--sin-cerebro", action="store_true",
                   help="no añadir la memoria de JARVIS (scripts/cerebro.py) a la pregunta")
    args = a.parse_intermixed_args()

    if args.pregunta[:1] == ["flujo"] and not args.etapa:
        return flujo(args.tipo, None, "", None, None, args.etapas)
    listas = configuradas()
    if not listas:
        print(sin_ias())
        if not _error_servidor:
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

    es_panel = args.pregunta[:1] == ["panel"]
    es_flujo = args.pregunta[:1] == ["flujo"]
    if es_panel or es_flujo:
        args.pregunta = args.pregunta[1:]
    pregunta = " ".join(args.pregunta).strip()
    if not pregunta and not args.archivo:
        a.error("falta la pregunta")
    texto = ""
    if args.archivo:
        texto = Path(args.archivo).read_text(encoding="utf-8", errors="replace")[:60000]
    pedido = pregunta
    if args.archivo:
        pedido = f"{pedido}\n\n--- {Path(args.archivo).name} ---\n{texto}"
    if not args.sin_cerebro:
        # Todas las IAs ven la misma memoria que Claude (sin lo privado), en lo que quepa junto al archivo.
        import cerebro
        memoria = cerebro.armar(f"{pregunta} {Path(args.archivo).stem if args.archivo else ''}",
                                max(15000, 75000 - len(texto)))
        if memoria:
            pedido = f"{memoria}\n\n## Lo que te piden\n{pedido}"
    original, pregunta = pregunta, pedido

    if es_flujo:
        return flujo(args.tipo, args.etapa, pregunta, args.guardar, original, args.etapas)
    if es_panel:
        if not args.rol:
            a.error("falta --rol (un tema: auditoria, marketing, nutricion...)")
        return panel(args.rol, pregunta, max(1, min(args.n, 6)), args.guardar, original)

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
