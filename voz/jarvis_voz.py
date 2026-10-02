"""
JARVIS por voz (Windows).

Mantén pulsada la tecla (F9 por defecto), habla y suelta.
1. Graba el micrófono mientras la tecla está pulsada.
2. Transcribe en local con faster-whisper (el audio no sale de la máquina).
3. Pasa el texto a scripts/jarvis.sh dentro de WSL (Claude Code + habilidades).
4. Lee la respuesta en voz alta con un TTS local (voces de Windows o Piper).

Uso:  python jarvis_voz.py            (ver opciones con --help)
"""

import argparse
import queue
import re
import subprocess
import sys
import threading
import time

import keyboard
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

FRECUENCIA = 16000  # Whisper trabaja a 16 kHz mono


def opciones():
    p = argparse.ArgumentParser(description="JARVIS por voz")
    p.add_argument("--tecla", default="f9", help="tecla para hablar (mantener pulsada)")
    p.add_argument("--modelo", default="small",
                   help="modelo de Whisper: tiny, base, small, medium, large-v3")
    p.add_argument("--dispositivo", default="cpu", help="cpu o cuda")
    p.add_argument("--distro", default="Ubuntu", help="distribución de WSL donde vive JARVIS")
    p.add_argument("--repo", default="/mnt/p/jarvis-os", help="ruta del repo dentro de WSL")
    p.add_argument("--piper", default=None,
                   help="ruta a un modelo .onnx de Piper; si no se da, usa las voces de Windows")
    p.add_argument("--solo-texto", action="store_true",
                   help="escribir en vez de hablar (para probar sin micrófono)")
    return p.parse_args()


# ---------- Oídos: grabar y transcribir ----------

def grabar_mientras_pulsada(tecla):
    """Graba desde el micrófono mientras la tecla siga pulsada."""
    bloques = queue.Queue()

    def callback(datos, frames, tiempo, estado):
        bloques.put(datos.copy())

    with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="float32", callback=callback):
        while keyboard.is_pressed(tecla):
            time.sleep(0.02)

    partes = []
    while not bloques.empty():
        partes.append(bloques.get())
    if not partes:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(partes).flatten()


def transcribir(modelo, audio):
    if len(audio) < FRECUENCIA * 0.4:  # menos de 0,4 s: probablemente un toque accidental
        return ""
    segmentos, _ = modelo.transcribe(audio, language="es", vad_filter=True)
    return " ".join(s.text.strip() for s in segmentos).strip()


# ---------- Cerebro: JARVIS en WSL ----------

def preguntar_a_jarvis(texto, distro, repo):
    cmd = ["wsl.exe", "-d", distro, "--cd", repo, "--exec", "./scripts/jarvis.sh", texto]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        print("Error de JARVIS:", "\n".join(detalle[-5:]), file=sys.stderr)
        return "Hubo un error al ejecutar la petición. Revisa la terminal."
    return r.stdout.strip()


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
    def __init__(self, modelo_piper=None):
        self.piper = None
        if modelo_piper:
            from piper import PiperVoice  # opcional: pip install piper-tts
            self.piper = PiperVoice.load(modelo_piper)
        else:
            import pyttsx3
            self.motor = pyttsx3.init()
            for v in self.motor.getProperty("voices"):
                nombre = (v.name + " " + v.id).lower()
                if "spanish" in nombre or "español" in nombre or "es-" in nombre:
                    self.motor.setProperty("voice", v.id)
                    break
            self.motor.setProperty("rate", 185)

    def decir(self, texto):
        if not texto:
            return
        if self.piper:
            audio = np.concatenate([
                np.frombuffer(trozo.audio_int16_bytes, dtype=np.int16)
                for trozo in self.piper.synthesize(texto)
            ])
            sd.play(audio, self.piper.config.sample_rate)
            sd.wait()
        else:
            self.motor.say(texto)
            self.motor.runAndWait()


# ---------- Bucle principal ----------

def atender(texto, args, voz):
    print(f"\nTú: {texto}")
    print("JARVIS: pensando...", flush=True)
    respuesta = preguntar_a_jarvis(texto, args.distro, args.repo)
    print(f"JARVIS: {respuesta}\n")
    voz.decir(limpiar_para_voz(respuesta))


def main():
    args = opciones()
    voz = Voz(args.piper)

    if args.solo_texto:
        print("Modo texto. Escribe tu petición (Ctrl+C para salir).")
        while True:
            texto = input("> ").strip()
            if texto:
                atender(texto, args, voz)

    print(f"Cargando el modelo de voz '{args.modelo}' (la primera vez se descarga)...")
    modelo = WhisperModel(args.modelo, device=args.dispositivo,
                          compute_type="int8" if args.dispositivo == "cpu" else "float16")
    print(f"Listo. Mantén pulsada {args.tecla.upper()} para hablar. Ctrl+C para salir.")

    ocupado = threading.Lock()
    while True:
        keyboard.wait(args.tecla)
        if not ocupado.acquire(blocking=False):
            continue
        try:
            print("Escuchando...", flush=True)
            audio = grabar_mientras_pulsada(args.tecla)
            texto = transcribir(modelo, audio)
            if texto:
                atender(texto, args, voz)
            else:
                print("No te entendí.")
        finally:
            ocupado.release()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nHasta luego.")
