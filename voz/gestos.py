"""
Ojos de JARVIS: lee gestos de la mano con la cámara y los convierte en órdenes.

Solo reconoce gestos: no mueve el ratón ni toca el teclado. La clasificación de
dedos (extendido con histéresis y pulgar arriba/abajo) viene de Hands-Free
Navigator (hands_free/gestures.py), simplificada para posturas que se mantienen.

Cada gesto hay que mantenerlo GESTO_MANTENER segundos para que cuente, y no se
repite hasta que la mano cambie de postura. Qué hace cada gesto se define en
voz/gestos.csv.
"""

import csv
import math
import threading
import time
from pathlib import Path

WRIST, THUMB_MCP, THUMB_TIP = 0, 2, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20
DEDOS = ((INDEX_MCP, INDEX_PIP, INDEX_TIP), (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
         (RING_MCP, RING_PIP, RING_TIP), (PINKY_MCP, PINKY_PIP, PINKY_TIP))

# Umbrales de Hands-Free Navigator (config.py)
EXT_ON, EXT_OFF = 1.10, 1.00
REACH_ON, REACH_OFF = 0.55, 0.45
PULGAR_INCLINADO = 0.5
JUNTOS, SEPARADOS = 0.30, 0.45

GESTO_MANTENER = 1.0   # segundos sosteniendo la postura
GESTO_PAUSA = 2.0      # segundos mínimos entre dos órdenes

NOMBRES = {
    "palma": "palma abierta",
    "pulgar_arriba": "pulgar arriba",
    "pulgar_abajo": "pulgar abajo",
    "indice": "solo el índice",
    "v": "V (índice y medio separados)",
    "tres": "tres dedos",
    "cuernos": "cuernos (índice y meñique)",
}


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


class ClasificadorPostura:
    """Landmarks de MediaPipe -> nombre de postura (o None). Sin efectos, se puede probar."""

    def __init__(self):
        self._ext = [False] * 4
        self._separados = False

    def postura(self, lm):
        tam = max(_dist(lm[WRIST], lm[MIDDLE_MCP]), 1e-6)
        for k, (mcp, pip, tip) in enumerate(DEDOS):
            ratio = _dist(lm[tip], lm[WRIST]) / max(_dist(lm[pip], lm[WRIST]), 1e-6)
            alcance = _dist(lm[tip], lm[mcp]) / tam
            if self._ext[k]:
                self._ext[k] = not (ratio < EXT_OFF or alcance < REACH_OFF)
            else:
                self._ext[k] = ratio > EXT_ON and alcance > REACH_ON
        i, m, r, p = self._ext
        pulgar_dy = (lm[THUMB_TIP].y - lm[THUMB_MCP].y) / tam  # negativo = arriba

        if not (i or m or r or p):
            if pulgar_dy < -PULGAR_INCLINADO:
                return "pulgar_arriba"
            if pulgar_dy > PULGAR_INCLINADO:
                return "pulgar_abajo"
            return None  # puño: reposo
        if i and m and r and p:
            return "palma"
        if i and p and not m and not r:
            return "cuernos"
        if i and m and r and not p:
            return "tres"
        if i and m and not r and not p:
            separacion = _dist(lm[INDEX_TIP], lm[MIDDLE_TIP]) / tam
            if self._separados:
                self._separados = separacion > JUNTOS
            else:
                self._separados = separacion > SEPARADOS
            return "v" if self._separados else None
        if i and not m and not r and not p:
            return "indice"
        return None


class Mantenido:
    """Dispara una postura cuando se sostiene GESTO_MANTENER s; no repite hasta cambiar."""

    def __init__(self, mantener=GESTO_MANTENER, pausa=GESTO_PAUSA):
        self.mantener, self.pausa = mantener, pausa
        self._actual, self._desde, self._disparada = None, 0.0, False
        self._ultimo = -1e9

    def actualizar(self, postura, ahora):
        if postura != self._actual:
            self._actual, self._desde, self._disparada = postura, ahora, False
            return None
        if (postura and not self._disparada and ahora - self._desde >= self.mantener
                and ahora - self._ultimo >= self.pausa):
            self._disparada, self._ultimo = True, ahora
            return postura
        return None


def leer_acciones(ruta):
    """gestos.csv -> {postura: acción}. Acción: escuchar, callar, pausar o un pedido para JARVIS."""
    acciones = {}
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            gesto, accion = (fila.get("gesto") or "").strip(), (fila.get("accion") or "").strip()
            if gesto and accion and not gesto.startswith("#"):
                acciones[gesto] = accion
    return acciones


class Ojos(threading.Thread):
    """Lee la cámara en segundo plano y llama a al_gesto(postura) cuando se cumple un gesto."""

    def __init__(self, al_gesto, camara=0, ver=False):
        super().__init__(daemon=True)
        self.al_gesto, self.camara, self.ver = al_gesto, camara, ver
        self.pausado = False

    def run(self):
        import cv2
        import mediapipe as mp

        cap = cv2.VideoCapture(self.camara, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(self.camara)
        if not cap.isOpened():
            print("Gestos: no pude abrir la cámara. Sigo solo con voz.")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        manos = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.7,
                                         min_tracking_confidence=0.6)
        clasificador, mantenido = ClasificadorPostura(), Mantenido()
        print("Gestos: cámara lista.")
        while True:
            ok, cuadro = cap.read()
            if not ok:
                time.sleep(0.5)
                continue
            cuadro = cv2.flip(cuadro, 1)
            resultado = manos.process(cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB))
            postura = None
            if resultado.multi_hand_landmarks:
                postura = clasificador.postura(resultado.multi_hand_landmarks[0].landmark)
            gesto = mantenido.actualizar(postura, time.monotonic())
            if gesto == "cuernos":
                self.pausado = not self.pausado
                print("Gestos:", "en pausa" if self.pausado else "activos")
                self.al_gesto("cuernos")
            elif gesto and not self.pausado:
                self.al_gesto(gesto)
            if self.ver:
                texto = NOMBRES.get(postura, "-") + ("  (pausa)" if self.pausado else "")
                cv2.putText(cuadro, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 200), 2)
                cv2.imshow("JARVIS gestos", cuadro)
                cv2.waitKey(1)
            time.sleep(1 / 20)  # ~15-20 fps es suficiente para posturas


RUTA_ACCIONES = Path(__file__).resolve().parent / "gestos.csv"
