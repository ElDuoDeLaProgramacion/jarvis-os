#!/usr/bin/env python3
"""
Prueba el detector de "Jarvis" de la app con voces sintéticas (espeak-ng), igual que lo usa la app:
el modelo pequeño de Vosk en español con la gramática de app/src/main/res/raw/gramatica.json ("jarvis"
más palabras señuelo, para que lo demás no se fuerce a "jarvis"). Solo cuenta el resultado final de cada frase
y la confianza de la palabra "jarvis" tiene que llegar al UMBRAL de EscuchaService.kt.
Lo corre el workflow antes de armar el APK.

    python3 android/probar_oido.py <carpeta-del-modelo>

Falla si se le escapa más de una frase con "Jarvis" o si lo oye en más de una que no lo dice.
"""
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)

FRASES = ["Jarvis", "Jarvis, qué tengo hoy", "Jarvis, pasa la canción", "Jarvis, apaga la música",
          "Jarvis, cuántos correos tengo", "Oye Jarvis, pon algo de Queen"]
VOCES = ["es-419", "es", "es-419 -s 140", "es-419 -s 200 -p 30", "es-419+m3", "es-419+f2"]
CON = [(v, f) for v in VOCES for f in FRASES]
SIN = [("es-419", "Buenos días, cómo estás"), ("es-419", "Mañana tengo una reunión con Ana"),
       ("es-419", "Pásame la sal por favor"), ("es-419", "Hoy hace mucho calor en Bogotá"),
       ("es-419", "Voy a revisar el correo después"), ("es-419", "Vamos a la casa de Javier"),
       ("es-419", "Hay muchos carros en la vía"), ("es-419", "Ya vi esa película"),
       ("es-419", "Garbanzos con arroz"), ("es", "Las variables del sistema"),
       ("es-419+m3", "Harvey es mi amigo"), ("es-419+f2", "La jarra está en el jardín"),
       ("es", "Qué hora es"), ("es-419", "Ponme un vaso de agua")]
SIN += [("es-419", "Anoche vimos un partido muy bueno en la televisión"),
        ("es-419", "Harvard es una universidad de Estados Unidos"), ("es-419+m3", "Marvin llegó tarde"),
        ("es", "Los jardines del parque están bonitos"), ("es-419", "Javier vino a la casa ayer"),
        ("es-419+f2", "Carlos y Marcos fueron al mercado"), ("es-419", "Ya revisé la lista de tareas"),
        ("es", "Hay que pagar el servicio de internet"), ("es-419 -s 200", "Dale play a la canción de nuevo")]
CARPETA = Path(__file__).parent / "app/src/main"
GRAMATICA = (CARPETA / "res/raw/gramatica.json").read_text(encoding="utf-8")
UMBRAL = float(re.search(r"UMBRAL = ([0-9.]+)f", (CARPETA / "java/co/jarvis/os/EscuchaService.kt").read_text())[1])


def audio(voz, texto, carpeta):
    crudo, listo = carpeta / "crudo.wav", carpeta / "listo.wav"
    voz, _, extra = voz.partition(" ")
    subprocess.run(["espeak-ng", "-v", voz, *extra.split(), "-w", str(crudo), texto], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(crudo), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(listo)], check=True)
    return listo


def confianza(modelo, ruta):
    """La mayor confianza con que oyó "jarvis" en los resultados finales (0 si no lo oyó), como la app."""
    r = KaldiRecognizer(modelo, 16000, GRAMATICA)
    r.SetWords(True)
    finales = []
    with wave.open(str(ruta)) as w:
        # Un poco de silencio antes y después, como en la vida real.
        datos = b"\0" * 16000 + w.readframes(w.getnframes()) + b"\0" * 32000
    for i in range(0, len(datos), 3200):
        if r.AcceptWaveform(datos[i:i + 3200]):
            finales.append(json.loads(r.Result()))
    finales.append(json.loads(r.FinalResult()))
    return max((p["conf"] for f in finales for p in f.get("result", []) if p["word"] == "jarvis"), default=0)


def main():
    modelo = Model(sys.argv[1])
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d)
        con = [(confianza(modelo, audio(v, t, carpeta)), v, t) for v, t in CON]
        sin = [(confianza(modelo, audio(v, t, carpeta)), v, t) for v, t in SIN]
    for c, v, t in con:
        print(f"  {'oye   ' if c >= UMBRAL else 'NO oye'}  {c:.2f}  [{v}] {t}")
    for c, v, t in sin:
        print(f"  {'FALSO ' if c >= UMBRAL else 'bien  '}  {c:.2f}  [{v}] {t}")
    for u in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99):
        print(f"  umbral {u}: oye {sum(c >= u for c, *_ in con)}/{len(con)}, falsos {sum(c >= u for c, *_ in sin)}/{len(sin)}")
    aciertos, falsos = sum(c >= UMBRAL for c, *_ in con), sum(c >= UMBRAL for c, *_ in sin)
    print(f"Con el umbral {UMBRAL}: oyó Jarvis en {aciertos}/{len(con)} y se confundió en {falsos}/{len(sin)}.")
    if aciertos < len(con) - 2 or falsos > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
