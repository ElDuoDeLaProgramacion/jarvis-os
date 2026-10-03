#!/usr/bin/env python3
"""
Transcribe las notas de voz de WhatsApp en local con faster-whisper (el audio no sale del equipo).

El puente (puente.mjs) lo deja corriendo y le pasa una ruta por línea en stdin; por cada una
responde una línea JSON en stdout: {"ruta": ..., "texto": ...} o {"ruta": ..., "error": ...}.

Modelo: WHATSAPP_MODELO_AUDIO en .env (por defecto "small"; "base" es más rápido, "medium" más fino).
"""
import json
import os
import sys
import wave

import numpy as np
from faster_whisper import WhisperModel

def audio(ruta):
    """El WAV de la app de Android (16 kHz, mono) se lee directo; lo demás (notas .ogg) lo decodifica PyAV."""
    if ruta.endswith(".wav"):
        with wave.open(ruta) as w:
            if w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2:
                return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return ruta


modelo = WhisperModel(os.environ.get("WHATSAPP_MODELO_AUDIO") or "small", device="cpu", compute_type="int8")
print(json.dumps({"listo": True}), flush=True)

for linea in sys.stdin:
    ruta = linea.strip()
    if not ruta:
        continue
    try:
        segmentos, _ = modelo.transcribe(audio(ruta), language="es", vad_filter=True)
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        print(json.dumps({"ruta": ruta, "texto": texto}, ensure_ascii=False), flush=True)
    except Exception as e:  # un audio raro no tumba el transcriptor
        print(json.dumps({"ruta": ruta, "error": repr(e)}), flush=True)
