"""Exploración temporal: compara configuraciones del detector con voces sintéticas."""
import json, re, subprocess, sys, tempfile, wave
from pathlib import Path
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)
CON = [("en-us", "Jarvis"), ("en-us", "Jarvis, what is on my calendar today"),
       ("es-419", "Jarvis"), ("es-419", "Jarvis, qué tengo hoy"), ("es-419", "Yarvis, pon música"),
       ("es", "Jarvis, pasa la canción"), ("es-419", "Oye Jarvis"), ("es", "Jarvis"),
       ("es-419", "Jarvis, apaga la música"), ("es-419", "Jarvis, cuántos correos tengo")]
SIN = [("es-419", "Buenos días, cómo estás"), ("es-419", "Mañana tengo una reunión con Ana"),
       ("es-419", "Pásame la sal por favor"), ("es-419", "Hoy hace mucho calor en Bogotá"),
       ("es-419", "Voy a revisar el correo después"), ("es-419", "Vamos a la casa de Javier"),
       ("es-419", "Hay muchos carros en la vía"), ("es-419", "Ya vi esa película"),
       ("es-419", "Garbanzos con arroz"), ("es", "Las variables del sistema"),
       ("en-us", "What a nice day"), ("es-419", "Harvey es mi amigo")]
DECOYS = ("the a is it yes no okay hello hi hey play stop music what when where why how who "
          "one two three four five six seven eight nine ten good day night time very much "
          "car bar far star service harvest harvey travis davis jar jars bus vis yard mark park").split()


def audio(voz, texto, d):
    c, l = d / "c.wav", d / "l.wav"
    subprocess.run(["espeak-ng", "-v", voz, "-w", str(c), texto], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(c), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(l)], check=True)
    with wave.open(str(l)) as w:
        return b"\0" * 16000 + w.readframes(w.getnframes()) + b"\0" * 32000


def textos(modelo, gram, datos):
    r = KaldiRecognizer(modelo, 16000, json.dumps(gram)) if gram else KaldiRecognizer(modelo, 16000)
    parciales, finales = [], []
    for i in range(0, len(datos), 3200):
        if r.AcceptWaveform(datos[i:i + 3200]):
            finales.append(json.loads(r.Result())["text"])
        else:
            parciales.append(json.loads(r.PartialResult())["partial"])
    finales.append(json.loads(r.FinalResult())["text"])
    return parciales, finales


def main():
    en, es = Model(sys.argv[1]), Model(sys.argv[2])
    configs = {
        "en-2": (en, ["jarvis", "[unk]"]),
        "en-decoys": (en, ["jarvis", *DECOYS, "[unk]"]),
        "en-libre": (en, None),
        "es-libre": (es, None),
    }
    patron = re.compile(r"\b(jarvis|yarvis|harvis|jarbis|yarbis|jervis)\b")
    with tempfile.TemporaryDirectory() as d:
        audios = [(True, v, t, audio(v, t, Path(d))) for v, t in CON] + \
                 [(False, v, t, audio(v, t, Path(d))) for v, t in SIN]
        for nombre, (m, g) in configs.items():
            print(f"=== {nombre}")
            for modo in ("parcial", "final"):
                bien = falsos = 0
                for con, v, t, a in audios:
                    p, f = textos(m, g, a)
                    oido = (p + f) if modo == "parcial" else f
                    oye = any(patron.search(x) for x in oido)
                    bien += oye and con
                    falsos += oye and not con
                    if modo == "final":
                        print(f"  {'+' if con else '-'} {'OYE' if oye else '   '} [{v}] {t!r} -> {' | '.join(x for x in f if x)!r}")
                print(f"  {modo}: aciertos {bien}/{len(CON)}, falsos {falsos}/{len(SIN)}")


main()
