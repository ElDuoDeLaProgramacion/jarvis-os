"""
Programa del HUD de JARVIS para Windows.

Abre el HUD en su propia ventana de escritorio (sin navegador). Arranca el
servidor en WSL sin consola y lo apaga al cerrar la ventana.

    hud\\abrir-hud.bat                      ->  ventana normal, maximizada
    hud\\abrir-hud.bat --pantalla-completa   ->  pantalla completa (Esc no sale; Alt+F4 cierra)
    hud\\abrir-hud.bat --distro Kali-Linux   ->  otra distribución de WSL
"""

import argparse
import subprocess
import sys
import time
import urllib.request

import webview

PUERTO = 7777
URL = f"http://localhost:{PUERTO}"
FONDO = "#07080a"  # el mismo --fondo de index.html, para que no haya destello blanco


def responde():
    try:
        with urllib.request.urlopen(f"{URL}/api/estado", timeout=2):
            return True
    except OSError:
        return False


def arrancar_servidor(distro):
    """Lanza hud.sh en WSL sin ventana. Le dejamos la entrada abierta: al cerrarla, el servidor sale."""
    return subprocess.Popen(
        ["wsl.exe", "-d", distro, "--cd", "/mnt/p/jarvis-os", "--exec",
         "./scripts/hud.sh", "--con-programa"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def esperar(ventana, servidor, segundos=90):
    """Al encender el PC, WSL puede tardar: espera a que el HUD responda y lo carga."""
    limite = time.time() + segundos
    while time.time() < limite:
        if responde():
            ventana.load_url(URL)
            return
        if servidor and servidor.poll() is not None:
            break
        time.sleep(1)
    ventana.load_html(PANTALLA.format(
        texto="No pude arrancar el HUD en WSL.<br>"
              "Revisa que la distribución se llame bien (--distro) y que el repo esté en P:\\jarvis-os."))


PANTALLA = (
    f"<body style='margin:0;height:100vh;display:grid;place-items:center;background:{FONDO};"
    "color:#9fb3c8;font:14px Consolas,monospace;text-align:center'><div>{texto}</div></body>"
)


class Api:
    """Funciones que la página del HUD puede llamar (window.pywebview.api...)."""

    _ventana = None  # con guion bajo: pywebview no lo expone a la página

    def traer_al_frente(self):
        """La voz pidió la ventana de análisis: mostrar el HUD encima de todo un momento."""
        v = self._ventana
        if v is None:
            return
        try:
            v.restore()
            v.show()
            v.on_top = True
            time.sleep(0.5)
            v.on_top = False
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="HUD de JARVIS")
    p.add_argument("--distro", default="Ubuntu")
    p.add_argument("--pantalla-completa", action="store_true")
    args = p.parse_args()

    # Si ya hay un servidor (abierto a mano, por ejemplo), lo usamos y no lo apagamos.
    servidor = None if responde() else arrancar_servidor(args.distro)

    api = Api()
    ventana = webview.create_window(
        "JARVIS",
        js_api=api,
        html=PANTALLA.format(texto="JARVIS arrancando..."),
        width=1600, height=900, min_size=(1100, 700),
        background_color=FONDO,
        fullscreen=args.pantalla_completa,
    )
    api._ventana = ventana
    if not args.pantalla_completa:
        ventana.events.shown += lambda: ventana.maximize()

    webview.start(esperar, (ventana, servidor))

    if servidor:
        try:
            servidor.stdin.close()
            servidor.wait(timeout=5)
        except Exception:
            servidor.kill()
    sys.exit(0)


if __name__ == "__main__":
    main()
