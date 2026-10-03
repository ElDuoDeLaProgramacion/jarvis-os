#!/usr/bin/env python3
"""
Prueba el detector de "Jarvis" de la app con voces sintéticas (espeak-ng), igual que lo usa la app:
un reconocedor de Vosk con la gramática ["jarvis", "[unk]"]. Lo corre el workflow antes de armar el APK.

    python3 android/probar_oido.py <carpeta-del-modelo>

Falla si no oye "Jarvis" en ninguna frase que lo dice, o si lo oye en más de una que no lo dice.
"""
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model

CON = [("en-us", "Jarvis"), ("en-us", "Jarvis, what is on my calendar today"),
       ("es-419", "Jarvis"), ("es-419", "Jarvis, qué tengo hoy"), ("es-419", "Yarvis, pon música"),
       ("es", "Jarvis, pasa la canción")]
SIN = [("es-419", "Buenos días, cómo estás"), ("es-419", "Mañana tengo una reunión con Ana"),
       ("es-419", "Pásame la sal por favor"), ("es-419", "Hoy hace mucho calor en Bogotá"),
       ("es-419", "Voy a revisar el correo después")]


def audio(voz, texto, carpeta):
    crudo, listo = carpeta / "crudo.wav", carpeta / "listo.wav"
    subprocess.run(["espeak-ng", "-v", voz, "-w", str(crudo), texto], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(crudo), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(listo)], check=True)
    return listo


def oye_jarvis(modelo, ruta):
    r = KaldiRecognizer(modelo, 16000, json.dumps(["jarvis", "[unk]"]))
    oido = []
    with wave.open(str(ruta)) as w:
        # Un poco de silencio antes y después, como en la vida real.
        datos = b"\0" * 16000 + w.readframes(w.getnframes()) + b"\0" * 32000
    for i in range(0, len(datos), 3200):
        if r.AcceptWaveform(datos[i:i + 3200]):
            oido.append(json.loads(r.Result())["text"])
        else:
            oido.append(json.loads(r.PartialResult())["partial"])
    oido.append(json.loads(r.FinalResult())["text"])
    return any(re.search(r"\bjarvis\b", t) for t in oido)


def main():
    modelo = Model(sys.argv[1])
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d)
        aciertos = falsos = 0
        for v, t in CON:
            if oye_jarvis(modelo, audio(v, t, carpeta)):
                aciertos += 1
                print(f"  oye     [{v}] {t}")
            else:
                print(f"  NO oye  [{v}] {t}")
        for v, t in SIN:
            if oye_jarvis(modelo, audio(v, t, carpeta)):
                falsos += 1
                print(f"  FALSO   [{v}] {t}")
            else:
                print(f"  bien    [{v}] {t}")
    print(f"Oyó Jarvis en {aciertos}/{len(CON)} y se confundió en {falsos}/{len(SIN)}.")
    if aciertos == 0 or falsos > 1:
        sys.exit(1)


if __name__ == "__main__":
    main()
