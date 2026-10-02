"""
JARVIS por voz y gestos (Windows).

Di "Jarvis" seguido de lo que quieras ("Jarvis, plan de hoy"), o solo "Jarvis"
y espera el "¿Sí?". Con la cámara, la mano maneja el ratón (voz/gestos.py).
1. Escucha el micrófono todo el tiempo y corta cada frase por los silencios.
2. Transcribe en local con faster-whisper (el audio no sale de la máquina) y
   solo atiende las frases que empiezan por "Jarvis".
3. Pasa el pedido a scripts/jarvis.sh dentro de WSL (Claude Code + habilidades).
4. Siempre contesta en voz alta con un TTS local (voces de Windows o Piper).

Uso:  python jarvis_voz.py            (ver opciones con --help)
"""

import argparse
import json
import queue
import re
import subprocess
import sys
import threading
import time
import unicodedata
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

FRECUENCIA = 16000  # Whisper trabaja a 16 kHz mono
BLOQUE_S = 0.03     # trozos de 30 ms para medir la voz

RAIZ = Path(__file__).resolve().parent.parent
COLA = RAIZ / "cola"
LOG = RAIZ / "logs" / "voz.log"

# Cómo suele transcribir Whisper "Jarvis" en español
PALABRA = re.compile(r"\b(?:(?:hey|oye|ok|ey)\s+)?(?:jarvis|jarvi|yarvis|yarbis|jarbis|charvis|harvis|jervis|yervis)\b[\s,.:;!?¿¡]*")


def log(*partes):
    texto = " ".join(str(p) for p in partes)
    print(texto, flush=True)
    try:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


def estado_audio(estado):
    """Deja el estado del audio donde el HUD lo lee (ESCUCHANDO, PENSANDO, HABLANDO, EN ESPERA)."""
    try:
        (COLA / "voz-estado.txt").write_text(estado, encoding="utf-8")
    except OSError:
        pass


def registrar(pedido, respuesta, origen="voz"):
    """Guarda la conversación en cola/hechas para que aparezca en la actividad del HUD."""
    try:
        destino = COLA / "hechas" / f"{datetime.now():%Y%m%d-%H%M%S}-{origen}.md"
        pedido_seguro = pedido.replace('"', '\\"')
        destino.write_text(
            f'---\npedido: "{pedido_seguro}"\norigen: {origen}\ncreado: {datetime.now().isoformat(timespec="seconds")}\n---\n'
            f"\n## Resultado (hecha, {origen})\n\n{respuesta}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def opciones():
    p = argparse.ArgumentParser(description="JARVIS por voz y gestos")
    p.add_argument("--tecla", default=None,
                   help="usar una tecla para hablar (mantener pulsada) en vez de decir 'Jarvis', p. ej. f9")
    p.add_argument("--modelo", default="small",
                   help="modelo de Whisper: tiny, base, small, medium, large-v3")
    p.add_argument("--dispositivo", default="cpu", help="cpu o cuda")
    p.add_argument("--distro", default="Ubuntu", help="distribución de WSL donde vive JARVIS")
    p.add_argument("--repo", default="/mnt/p/jarvis-os", help="ruta del repo dentro de WSL")
    p.add_argument("--piper", default=None,
                   help="ruta a un modelo .onnx de Piper; si no se da, usa las voces de Windows")
    p.add_argument("--sin-gestos", action="store_true", help="no usar la cámara")
    p.add_argument("--camara", type=int, default=0, help="número de cámara para los gestos")
    p.add_argument("--ver-camara", action="store_true", help="mostrar la cámara con el gesto detectado")
    p.add_argument("--sensibilidad", type=float, default=3.0,
                   help="cuánto más fuerte que el ruido de fondo debe ser la voz (más bajo = más sensible)")
    p.add_argument("--solo-texto", action="store_true",
                   help="escribir en vez de hablar (para probar sin micrófono)")
    return p.parse_args()


def normalizar(texto):
    """Minúsculas y sin tildes, letra por letra (misma longitud que el original)."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto.lower())


def separar_pedido(texto):
    """'Jarvis, plan de hoy' -> (True, 'plan de hoy'). Sin palabra de activación -> (False, '')."""
    plano = normalizar(texto)
    m = PALABRA.search(plano)
    if not m or m.start() > 12:  # la palabra debe ir al principio de la frase
        return False, ""
    return True, texto[m.end():].strip(" ,.;:!?¿¡")


# ---------- Cerebro: JARVIS en WSL ----------

def preguntar_a_jarvis(texto, distro, repo, reanudar=None):
    """Devuelve (respuesta, id de conversación). Con reanudar, sigue esa conversación."""
    cmd = ["wsl.exe", "-d", distro, "--cd", repo, "--exec", "./scripts/jarvis.sh", "--sesion"]
    if reanudar:
        cmd += ["--reanudar", reanudar]
    cmd += ["--", texto]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        log("Error al llamar a WSL:", e)
        return "No pude hablar con Ubuntu. Revisa que WSL esté instalado.", None
    sesion = next((l[7:].strip() for l in r.stderr.splitlines() if l.startswith("SESION=")), None)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        log("Error de JARVIS:", "\n".join(detalle[-5:]))
        return "Hubo un error al ejecutar la petición. Lo dejé anotado en el registro de la voz.", None
    return r.stdout.strip(), sesion


def es_pregunta(respuesta):
    """JARVIS espera respuesta si termina preguntando ("¿Lo envío? Sí o no.")."""
    final = respuesta.strip()[-160:]
    return final.endswith("?") or bool(re.search(r"\?\s*(s[ií] o no|responde|dime)[^?]*$", normalizar(final)))


# ---------- Pantalla: "Jarvis, lee mi pantalla" ----------

PANTALLAS = COLA / "pantalla"


def pide_pantalla(pedido):
    return "pantalla" in normalizar(pedido)


def capturar_pantalla():
    """Guarda una captura de toda la pantalla en cola/pantalla/ y devuelve su ruta relativa al repo."""
    import mss
    import mss.tools
    PANTALLAS.mkdir(parents=True, exist_ok=True)
    destino = PANTALLAS / f"{datetime.now():%Y%m%d-%H%M%S}.png"
    with mss.mss() as sct:
        imagen = sct.grab(sct.monitors[0])  # 0 = todas las pantallas juntas
        mss.tools.to_png(imagen.rgb, imagen.size, output=str(destino))
    for vieja in sorted(PANTALLAS.glob("*.png"))[:-10]:  # solo guardamos las 10 últimas
        vieja.unlink(missing_ok=True)
    return destino.relative_to(RAIZ).as_posix()


# ---------- Analizar: "Jarvis, analiza este archivo" ----------

ABRIR_ANALIZAR = COLA / "analizar-abrir"
PEDIDO_ANALIZAR = COLA / "analizar-pedido.json"
MEDIOS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".mp4", ".mkv", ".mov", ".webm", ".avi"}


def pide_analizar(pedido):
    plano = normalizar(pedido)
    return bool(re.match(r"\s*(analiza|analizar|analisis|resume este|resumeme este|revisa este)", plano)) \
        and "pantalla" not in plano and "http" not in plano


def hud_responde():
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:7777/api/estado", timeout=2):
            return True
    except OSError:
        return False


def limpiar_para_voz(texto):
    """Quita Markdown y enlaces para que el TTS no lea símbolos."""
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"[*_`#>|]", "", texto)
    texto = re.sub(r"^\s*[-•]\s+", "", texto, flags=re.M)
    return re.sub(r"\s+", " ", texto).strip()


# ---------- Boca: TTS local ----------

class Voz:
    """Habla con Piper si se da un modelo; si no, con las voces de Windows (SAPI) directamente.

    Antes usábamos pyttsx3, que en Windows a veces se queda mudo después de la primera
    frase. SAPI se crea en cada frase, en el hilo que habla, y se puede interrumpir.
    """

    def __init__(self, modelo_piper=None):
        self.piper = None
        self.callar = threading.Event()
        if modelo_piper:
            from piper import PiperVoice  # opcional: pip install piper-tts
            self.piper = PiperVoice.load(modelo_piper)

    def decir(self, texto):
        texto = limpiar_para_voz(texto)
        if not texto:
            return
        self.callar.clear()
        try:
            if self.piper:
                self._piper(texto)
            else:
                self._sapi(texto)
        except Exception as e:  # la voz nunca debe tumbar el programa
            log("No pude hablar con SAPI/Piper:", repr(e))
            try:
                self._powershell(texto)
            except Exception as e2:
                log("Tampoco con PowerShell:", repr(e2))

    def _piper(self, texto):
        audio = np.concatenate([
            np.frombuffer(trozo.audio_int16_bytes, dtype=np.int16)
            for trozo in self.piper.synthesize(texto)
        ])
        sd.play(audio, self.piper.config.sample_rate)
        while sd.get_stream().active:
            if self.callar.is_set():
                sd.stop()
                return
            time.sleep(0.05)

    def _sapi(self, texto):
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        try:
            sapi = comtypes.client.CreateObject("SAPI.SpVoice")
            voces = sapi.GetVoices()
            for k in range(voces.Count):
                desc = voces.Item(k).GetDescription().lower()
                if "spanish" in desc or "español" in desc:
                    sapi.Voice = voces.Item(k)
                    break
            sapi.Rate = 1
            sapi.Speak(texto, 1)  # 1 = asíncrono, para poder callarlo
            while not sapi.WaitUntilDone(100):
                if self.callar.is_set():
                    sapi.Speak("", 3)  # 3 = asíncrono + purgar lo que está diciendo
                    return
        finally:
            comtypes.CoUninitialize()

    def _powershell(self, texto):
        """Último recurso: la voz de Windows desde PowerShell."""
        seguro = texto.replace("'", "''")
        orden = ("Add-Type -AssemblyName System.Speech; "
                 f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{seguro}')")
        subprocess.run(["powershell", "-NoProfile", "-Command", orden],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# ---------- JARVIS: une oídos, ojos y boca ----------

class Jarvis:
    def __init__(self, args):
        self.args = args
        self.voz = Voz(args.piper)
        self.turno = threading.Lock()          # una orden a la vez
        self.ocupado = threading.Event()       # mientras piensa o habla, el micro no escucha
        self.esperando_hasta = 0.0             # tras "Jarvis" a secas: la frase siguiente es la orden
        self.seguimiento = None                # (id de conversación, hasta cuándo) si JARVIS preguntó algo
        self.modelo = None                     # Whisper, para transcribir audio y video al analizar

    def hablar(self, texto):
        self.ocupado.set()
        estado_audio("HABLANDO")
        self.voz.decir(texto)
        estado_audio("EN ESPERA")
        self.ocupado.clear()

    def escuchar_orden(self):
        """Activa la escucha sin palabra: lo siguiente que digas es la orden."""
        self.hablar("¿Sí?")
        self.esperando_hasta = time.monotonic() + 8
        estado_audio("ESCUCHANDO")

    def atender(self, pedido, origen="voz", reanudar=None):
        if origen == "voz" and not reanudar and pide_analizar(pedido):
            self.abrir_analizar()
            return
        with self.turno:
            self.ocupado.set()
            log(f"\nTú ({origen}): {pedido}")
            estado_audio("PENSANDO")
            self.voz.decir("Enseguida.")
            texto = pedido
            if pide_pantalla(pedido):
                try:
                    ruta = capturar_pantalla()
                    texto += (f" (Captura de mi pantalla de ahora mismo: {ruta}. Ábrela con Read, "
                              "mira qué estoy haciendo y dime en pocas frases qué hacer.)")
                except Exception as e:
                    log("No pude capturar la pantalla:", repr(e))
            respuesta, sesion = preguntar_a_jarvis(texto, self.args.distro, self.args.repo, reanudar)
            if not respuesta:
                respuesta = "Listo, ya está hecho. Los detalles quedaron en la bóveda."
            log(f"JARVIS: {respuesta}\n")
            registrar(pedido, respuesta, origen)
            # Si JARVIS pregunta algo, la respuesta no necesita "Jarvis" durante 20 segundos.
            self.seguimiento = (sesion, time.monotonic() + 20) if sesion and es_pregunta(respuesta) else None
            estado_audio("HABLANDO")
            self.voz.decir(respuesta)
            if self.seguimiento:
                self.seguimiento = (self.seguimiento[0], time.monotonic() + 20)  # cuenta desde que calla
            estado_audio("ESCUCHANDO" if self.seguimiento else "EN ESPERA")
            self.ocupado.clear()

    def abrir_analizar(self):
        """Abre la ventana de análisis del HUD y espera lo que David agregue allí."""
        PEDIDO_ANALIZAR.unlink(missing_ok=True)
        ABRIR_ANALIZAR.write_text(datetime.now().isoformat(), encoding="utf-8")
        if not hud_responde():
            abrir = RAIZ / "hud" / "abrir-hud.bat"
            subprocess.Popen(["cmd", "/c", str(abrir), "--distro", self.args.distro],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.hablar("Te abrí la ventana de análisis. Agrega lo que quieras y pulsa Analizar.")
        threading.Thread(target=self._esperar_analisis, daemon=True).start()

    def _esperar_analisis(self, minutos=15):
        limite = time.monotonic() + minutos * 60
        while time.monotonic() < limite:
            if PEDIDO_ANALIZAR.exists():
                try:
                    datos = json.loads(PEDIDO_ANALIZAR.read_text(encoding="utf-8"))
                finally:
                    PEDIDO_ANALIZAR.unlink(missing_ok=True)
                pedido = datos["pedido"]
                transcripciones = self._transcribir_medios(datos.get("medios", []))
                if transcripciones:
                    pedido += " Transcripciones del audio y video (hechas en local): " + ", ".join(transcripciones) + "."
                self.atender(pedido, "analisis")
                return
            time.sleep(1)
        ABRIR_ANALIZAR.unlink(missing_ok=True)

    def _transcribir_medios(self, medios):
        """Audio y video se transcriben aquí, con el mismo Whisper de la voz."""
        hechas = []
        if not medios or self.modelo is None:
            return hechas
        self.hablar("Transcribo el audio primero.")
        for rel in medios:
            origen = RAIZ / rel
            if origen.suffix.lower() not in MEDIOS or not origen.exists():
                continue
            try:
                segmentos, _ = self.modelo.transcribe(str(origen), vad_filter=True)
                texto = "\n".join(s.text.strip() for s in segmentos)
                destino = origen.with_name(origen.name + ".txt")
                destino.write_text(texto, encoding="utf-8")
                hechas.append(destino.relative_to(RAIZ).as_posix())
            except Exception as e:
                log("No pude transcribir", rel, repr(e))
        return hechas

    def frase(self, texto):
        """Decide qué hacer con una frase transcrita."""
        if not texto:
            return
        if self.seguimiento and time.monotonic() < self.seguimiento[1]:
            # JARVIS acaba de preguntar algo ("¿Lo envío?"): la respuesta va sin "Jarvis".
            sesion, self.seguimiento = self.seguimiento[0], None
            activada, pedido = separar_pedido(texto)
            self.atender(pedido if activada and pedido else texto, reanudar=sesion)
            return
        self.seguimiento = None
        if time.monotonic() < self.esperando_hasta:
            self.esperando_hasta = 0.0
            activada, pedido = separar_pedido(texto)
            self.atender(pedido if activada and pedido else texto)
            return
        activada, pedido = separar_pedido(texto)
        if not activada:
            return  # conversación que no es para JARVIS
        if pedido:
            self.atender(pedido)
        else:
            self.escuchar_orden()


# ---------- Oídos: escuchar y transcribir ----------

def transcribir(modelo, audio):
    if len(audio) < FRECUENCIA * 0.4:  # menos de 0,4 s: un golpe o un ruido
        return ""
    segmentos, _ = modelo.transcribe(audio, language="es", vad_filter=True,
                                     initial_prompt="Jarvis, plan de hoy.")
    return " ".join(s.text.strip() for s in segmentos).strip()


def escuchar_siempre(jarvis, modelo, sensibilidad):
    """Micrófono abierto: corta frases por silencio y se las pasa a Jarvis.frase."""
    bloques = queue.Queue()
    tam = int(FRECUENCIA * BLOQUE_S)

    def callback(datos, frames, tiempo, estado):
        bloques.put(datos[:, 0].copy())

    previo = deque(maxlen=int(0.4 / BLOQUE_S))  # 0,4 s antes de que empiece la voz
    frase, en_voz, voz_seguida, silencio, con_voz = [], False, 0, 0, 0
    piso = 0.01  # ruido de fondo, se ajusta solo

    with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="float32",
                        blocksize=tam, callback=callback):
        estado_audio("EN ESPERA")
        log('Listo. Di "Jarvis" y lo que necesitas. Ctrl+C para salir.')
        while True:
            bloque = bloques.get()
            if jarvis.ocupado.is_set():
                # Mientras piensa o habla no escuchamos (si no, se oiría a sí mismo).
                frase, en_voz, voz_seguida, silencio = [], False, 0, 0
                previo.clear()
                continue
            nivel = float(np.sqrt(np.mean(bloque ** 2)))
            umbral = max(piso * sensibilidad, 0.006)
            if not en_voz:
                previo.append(bloque)
                if nivel > umbral:
                    voz_seguida += 1
                else:
                    voz_seguida = 0
                    piso = 0.97 * piso + 0.03 * nivel
                if voz_seguida >= 3:
                    en_voz, frase, silencio, con_voz = True, list(previo), 0, voz_seguida
                continue
            frase.append(bloque)
            silencio = silencio + 1 if nivel < umbral * 0.7 else 0
            con_voz += nivel > umbral
            if silencio * BLOQUE_S >= 0.8 or len(frase) * BLOQUE_S >= 15:
                audio = np.concatenate(frase)
                corta = con_voz * BLOQUE_S < 0.3  # un golpe o una tos: ni se transcribe
                frase, en_voz, voz_seguida, silencio, con_voz = [], False, 0, 0, 0
                previo.clear()
                if corta:
                    continue
                texto = transcribir(modelo, audio)
                if texto:
                    print(f"(oído) {texto}", flush=True)
                jarvis.frase(texto)
                # Lo que se grabó mientras JARVIS pensaba o hablaba no cuenta.
                while not bloques.empty():
                    bloques.get_nowait()


def escuchar_con_tecla(jarvis, modelo, tecla):
    """Modo antiguo: mantener una tecla pulsada para hablar."""
    import keyboard

    def grabar():
        bloques = queue.Queue()
        with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="float32",
                            callback=lambda d, f, t, s: bloques.put(d.copy())):
            while keyboard.is_pressed(tecla):
                time.sleep(0.02)
        partes = [bloques.get() for _ in range(bloques.qsize())]
        return np.concatenate(partes).flatten() if partes else np.zeros(0, dtype=np.float32)

    estado_audio("EN ESPERA")
    log(f"Listo. Mantén pulsada {tecla.upper()} para hablar. Ctrl+C para salir.")
    while True:
        keyboard.wait(tecla)
        if jarvis.turno.locked():
            continue
        estado_audio("ESCUCHANDO")
        texto = transcribir(modelo, grabar())
        if texto:
            jarvis.atender(texto)
        else:
            jarvis.hablar("No te entendí.")


def arrancar_gestos(jarvis, args):
    """Ratón y teclado con la mano (gestos básicos de Hands-Free Navigator)."""
    try:
        import cv2, mediapipe, pyautogui  # noqa: F401  (solo comprobar que están)
        import gestos
    except ImportError:
        log("Gestos: no están instalados (mira voz/README.md). Sigo solo con voz.")
        return

    def al_cambiar_pausa(pausado):
        log("Gestos:", "en pausa" if pausado else "activos")
        if not jarvis.ocupado.is_set():
            jarvis.hablar("Gestos en pausa." if pausado else "Gestos activos.")

    gestos.Ojos(args.camara, args.ver_camara, al_cambiar_pausa).start()


def main():
    args = opciones()
    jarvis = Jarvis(args)

    if args.solo_texto:
        print("Modo texto. Escribe tu petición (Ctrl+C para salir).")
        while True:
            texto = input("> ").strip()
            if texto:
                seguir = jarvis.seguimiento[0] if jarvis.seguimiento else None
                jarvis.atender(texto, "texto", reanudar=seguir)

    from faster_whisper import WhisperModel
    log(f"Cargando el modelo de voz '{args.modelo}' (la primera vez se descarga)...")
    modelo = WhisperModel(args.modelo, device=args.dispositivo,
                          compute_type="int8" if args.dispositivo == "cpu" else "float16")
    jarvis.modelo = modelo
    if not args.sin_gestos:
        arrancar_gestos(jarvis, args)
    jarvis.hablar("JARVIS en línea.")

    if args.tecla:
        escuchar_con_tecla(jarvis, modelo, args.tecla)
    else:
        escuchar_siempre(jarvis, modelo, args.sensibilidad)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        main()
    except KeyboardInterrupt:
        print("\nHasta luego.")
