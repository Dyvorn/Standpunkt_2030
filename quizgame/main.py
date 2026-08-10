import sys
import os

# Fix for PyInstaller GUI mode (--noconsole) where sys.stdout and sys.stderr are None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import socket
import threading
from PyQt6.QtWidgets import QApplication
from game_engine import GameEngine
import server
from host_window import HostWindow

CURRENT_VERSION = "1.0.1"

def get_local_ip():
    """Ermittelt die IP-Adresse im lokalen Netzwerk."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Diese Adresse muss nicht existieren, es löst nur das Interface-Routing aus
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def main():
    """Main entry point: initializes engine, starts Flask server thread, and runs PyQt6 app."""
    # 1. Engine initialisieren
    engine = GameEngine()
    server.engine = engine

    # 2. IP bestimmen
    local_ip = get_local_ip()

    # 3. Flask Server in Hintergrund-Thread starten
    # Wir nutzen daemon=True, damit der Thread endet, wenn die GUI schließt
    server_thread = threading.Thread(
        target=server.run_server, args=("0.0.0.0", 5000), daemon=True
    )
    server_thread.start()

    # 4. PyQt6 GUI starten
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = HostWindow(engine, server, local_ip, current_version=CURRENT_VERSION)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
