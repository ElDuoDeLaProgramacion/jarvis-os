"""
Gestos de la mano para JARVIS, con la lógica de Hands-Free Navigator (voz/manos/).

Solo los gestos básicos (índice y medio son los dedos de trabajo):

  Índice + medio arriba y JUNTOS        -> mover el cursor
     bajar ambos y subirlos            -> clic izquierdo (dos veces: doble clic)
     bajar solo el medio y subirlo     -> clic derecho
  Índice + medio SEPARADOS (V)
     bajar el dedo derecho / izquierdo -> Tab: siguiente / anterior aplicación (Alt+Tab)
  Palma abierta deslizada              -> pestaña anterior / siguiente
  Cuernos (índice + meñique) 1 s       -> activar / pausar los gestos

Arranca en pausa para no mover el ratón al encender el PC: haz los cuernos para activar.
Scroll, arrastrar, zoom y grabar pantalla de Hands-Free Navigator quedan fuera.
"""

import threading
import time

from manos.config import Config
from manos.gestures import Gesture, GestureDetector

BASICOS = {
    Gesture.CLICK, Gesture.DOUBLE_CLICK, Gesture.RIGHT_CLICK,
    Gesture.SWIPE_LEFT, Gesture.SWIPE_RIGHT,
    Gesture.APP_NEXT, Gesture.APP_PREV,
}


def configuracion(camara=0):
    cfg = Config()
    cfg.camera_index = camara
    cfg.two_hand_mode = False   # sin zoom con dos manos
    cfg.drag_enabled = False    # sin arrastrar
    cfg.start_paused = True
    return cfg


class Filtro:
    """Detección -> qué ejecutar. Separado de la cámara para poder probarlo."""

    def __init__(self, cfg, al_cambiar_pausa=None):
        self.cfg = cfg
        self.pausado = cfg.start_paused
        self.al_cambiar_pausa = al_cambiar_pausa or (lambda pausado: None)

    def procesar(self, det, cursor, acciones):
        if det.gesture is Gesture.TOGGLE_PAUSE:
            self.pausado = not self.pausado
            self.al_cambiar_pausa(self.pausado)
            return None
        if self.pausado:
            acciones.release_all()
            return None
        if det.gesture in BASICOS:
            acciones.run(det.gesture)
        acciones.update_cursor(cursor)
        return det.gesture if det.gesture in BASICOS else None


class Ojos(threading.Thread):
    """Lee la cámara en segundo plano y maneja ratón y teclado con los gestos básicos."""

    def __init__(self, camara=0, ver=False, al_cambiar_pausa=None):
        super().__init__(daemon=True)
        self.cfg = configuracion(camara)
        self.ver = ver
        self.filtro = Filtro(self.cfg, al_cambiar_pausa)

    def run(self):
        import cv2
        import mediapipe as mp
        from manos.actions import ActionExecutor

        cfg = self.cfg
        cap = cv2.VideoCapture(cfg.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_height)
        if not cap.isOpened():
            print("Gestos: no pude abrir la cámara. Sigo solo con voz.", flush=True)
            return
        manos = mp.solutions.hands.Hands(max_num_hands=1,
                                         min_detection_confidence=cfg.detection_confidence,
                                         min_tracking_confidence=cfg.tracking_confidence)
        detector, acciones = GestureDetector(cfg), ActionExecutor(cfg)
        ultima, visto = None, -1e9
        print("Gestos: cámara lista, en pausa. Haz los cuernos (índice y meñique) 1 s para activarlos.",
              flush=True)
        try:
            while True:
                ok, cuadro = cap.read()
                if not ok:
                    time.sleep(0.5)
                    continue
                if cfg.mirror:
                    cuadro = cv2.flip(cuadro, 1)
                resultado = manos.process(cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB))
                ahora = time.monotonic()
                mano = resultado.multi_hand_landmarks[0].landmark if resultado.multi_hand_landmarks else None
                # Como Hands-Free Navigator: un parpadeo de 1-2 cuadros no reinicia el gesto.
                if mano is not None:
                    ultima, visto = mano, ahora
                elif ahora - visto < cfg.hand_mode_debounce_s:
                    mano = ultima
                det = detector.update(mano, ahora)
                hecho = self.filtro.procesar(det, detector.cursor, acciones)
                if self.ver:
                    texto = f"{det.pose}  {'PAUSA' if self.filtro.pausado else (hecho.name if hecho else '')}"
                    cv2.putText(cuadro, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
                    cv2.imshow("JARVIS gestos", cuadro)
                    cv2.waitKey(1)
                else:
                    time.sleep(0.02)
        finally:
            acciones.close()  # nunca dejar Alt ni el botón del ratón pulsados
            cap.release()
