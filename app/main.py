import asyncio
import json
from pathlib import Path
import os
from typing import Dict, List
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import socket
import qrcode

app = FastAPI()

# --- PFADE ---
BASE_DIR = Path(__file__).parent.parent
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"
data_path = BASE_DIR / "data"

# Ordner sicherstellen
# FastAPI/Starlette requires these directories to exist on startup.
# This will create them if they are missing and raise a clear error if it fails.
os.makedirs(static_path, exist_ok=True)
os.makedirs(templates_path, exist_ok=True)
os.makedirs(data_path, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# --- GAME CLASS ---
class Game:
    """Encapsulates all game logic and state for better customization."""
    def __init__(self, scenarios_path: Path, themes_path: Path):
        self.scenarios = self._load_json(scenarios_path)
        self.themes = self._load_json(themes_path)
        if not self.scenarios or not self.themes:
            raise RuntimeError("Could not load game data. Check data/scenarios.json and data/themes.json.")
        
        self.available_themes = [{"id": k, "name": v["name"]} for k, v in self.themes.items()]
        self.state: Dict = {}
        self.board_clients: List[WebSocket] = []
        self.player_clients: List[WebSocket] = []
        
        first_theme_id = next(iter(self.themes), None)
        if first_theme_id:
            self.reset(first_theme_id)
        else:
            print("FEHLER: Keine Themes in themes.json gefunden. Spiel kann nicht gestartet werden.")
            self.state = {"phase": "error", "scenario_data": {"title": "Konfigurationsfehler", "board": {"title_text": "Keine Themes in themes.json gefunden."}}}

    def _load_json(self, path: Path) -> Dict:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"FEHLER: Konnte '{path.name}' unter '{path}' nicht finden.")
        return {}

    async def connect(self, websocket: WebSocket, client_type: str):
        """Adds a new client, updates player count, and sends current state."""
        await websocket.accept()
        if client_type == "board":
            self.board_clients.append(websocket)
        else:
            self.player_clients.append(websocket)
        
        self.state["player_count"] = len(self.player_clients)
        await websocket.send_json(self.state)
        # Broadcast the new player count to everyone (especially the board)
        await self.broadcast_state()

    async def disconnect(self, websocket: WebSocket):
        """Removes a client and updates player count."""
        if websocket in self.board_clients:
            self.board_clients.remove(websocket)
        elif websocket in self.player_clients:
            self.player_clients.remove(websocket)
            self.state["player_count"] = len(self.player_clients)
            await self.broadcast_state()

    async def broadcast_state(self):
        """Sends the current state to all connected clients."""
        for client in self.board_clients + self.player_clients:
            try:
                await client.send_json(self.state)
            except Exception:
                pass

    def reset(self, theme_id: str):
        """Resets the game to the initial state of a specific theme."""
        theme_data = self.themes.get(theme_id)
        if not theme_data:
            print(f"FEHLER: Theme '{theme_id}' nicht in themes.json gefunden.")
            return

        self.state = {
            "values": theme_data.get("initial_values", {}).copy(),
            "current_scenario_id": None,
            "theme": theme_id,
            "scenario_data": {},
            "votes": {},
            "phase": "loading",
            "available_themes": self.available_themes,
            "player_count": len(self.player_clients),
        }
        start_scenario_id = theme_data.get("start_scenario_id")
        if start_scenario_id:
            self.change_scenario(start_scenario_id)
        print(f"Spiel zurückgesetzt. Theme: '{theme_id}', Start-Szenario: '{start_scenario_id}'.")

    def change_scenario(self, scenario_id: str):
        """Changes the game to the specified scenario."""
        next_scenario_data = self.scenarios.get(scenario_id)
        if not next_scenario_data:
            print(f"FEHLER: Szenario '{scenario_id}' nicht in scenarios.json gefunden.")
            self.state["phase"] = "end"
            self.state["scenario_data"] = {"title": "Spielende", "board": {"title_text": f"Szenario '{scenario_id}' konnte nicht geladen werden."}}
            return

        self.state["current_scenario_id"] = scenario_id
        self.state["scenario_data"] = next_scenario_data
        
        vote_options = next_scenario_data.get("vote_options", [])
        self.state["votes"] = {opt["id"]: 0 for opt in vote_options}
        
        self.state["phase"] = "voting" if vote_options else "end"
            
        self.state.pop("winning_option_id", None)
        self.state.pop("next_scenario_id", None)

    def vote(self, option_id: str):
        """Registers a vote for a given option."""
        if self.state.get("phase") == "voting" and option_id in self.state.get("votes", {}):
            self.state["votes"][option_id] += 1

    def end_voting_and_show_results(self):
        """Determines the winner, applies effects, and moves to the 'result' phase."""
        votes = self.state.get("votes", {})
        if not votes: return

        winner_id = max(votes, key=votes.get)
        winning_option_data = next((opt for opt in self.state["scenario_data"].get("vote_options", []) if opt["id"] == winner_id), None)
        
        if not winning_option_data:
            print(f"FEHLER: Gewinner-Option '{winner_id}' nicht in Szenario-Daten gefunden.")
            return

        for key, value in winning_option_data.get("value_effects", {}).items():
            if key in self.state["values"]:
                current_val = self.state["values"][key]
                self.state["values"][key] = max(0, min(100, current_val + value))

        self.state["phase"] = "result"
        self.state["winning_option_id"] = winner_id
        self.state["next_scenario_id"] = winning_option_data.get("next_scenario_if_wins")

    def advance_to_next_phase(self):
        """Handles the logic for advancing the game from one phase to the next."""
        phase = self.state.get("phase")
        if phase == "voting":
            self.end_voting_and_show_results()
        elif phase == "result":
            next_id = self.state.get("next_scenario_id")
            if next_id:
                self.change_scenario(next_id)

# --- GLOBAL GAME INSTANCE ---
game = Game(
    scenarios_path=data_path / "scenarios.json",
    themes_path=data_path / "themes.json"
)

# --- ROUTEN ---
@app.get("/", response_class=HTMLResponse)
async def get_landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/board", response_class=HTMLResponse)
async def get_board(request: Request):
    return templates.TemplateResponse("board.html", {"request": request})

@app.get("/play", response_class=HTMLResponse)
async def get_mobile(request: Request):
    return templates.TemplateResponse("mobile.html", {"request": request})

# --- WEBSOCKET LOGIC ---
@app.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str):
    await game.connect(websocket, client_type)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            # Only players (or anyone) can vote, but logic handled in game.vote
            if message_type == "vote":
                option_id = data.get("value")
                game.vote(option_id)
                await game.broadcast_state()

            # ONLY BOARD (Teacher) controls:
            elif message_type == "reset_game" and client_type == "board":
                # Reset to a specific theme, or the first one available.
                theme_id = data.get("theme_id", next(iter(game.themes), "default"))
                game.reset(theme_id)
                await game.broadcast_state()

            elif message_type == "advance_game" and client_type == "board":
                game.advance_to_next_phase()
                await game.broadcast_state()
                
    except WebSocketDisconnect:
        await game.disconnect(websocket)

def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Servers im Netzwerk."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Muss nicht erreichbar sein, dient nur zum Ermitteln der lokalen IP
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # Fallback
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    # Generate QR Code for local network access
    HOST_IP = get_local_ip()
    PORT = 8000
    
    # Versuche, weitere IPs zu finden (falls die automatische Erkennung fehlschlägt)
    other_ips = []
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        other_ips = [ip for ip in all_ips if not ip.startswith("127.") and ip != HOST_IP]
    except Exception:
        pass

    play_url = f"http://{HOST_IP}:{PORT}/play"
    
    # QR-Code als Bild im Static-Ordner speichern
    qr_code_path = static_path / "qr_code.png"
    try:
        qrcode.make(play_url).save(str(qr_code_path))
    except Exception as e:
        print(f"⚠️  FEHLER beim Erstellen des QR-Codes: {e}")

    print("\n" + "="*60)
    print(f"🚀 STANDPUNKT 2030 SERVER LÄUFT")
    print("="*60)
    print(f"📍 1. BOARD (Lehrer/Beamer):")
    print(f"   👉 http://localhost:{PORT}/board")
    print(f"\n📱 2. SPIELER (Handy/Tablet):")
    print(f"   👉 {play_url}")
    
    if other_ips:
        print("\n   Falls die Verbindung fehlschlägt, probieren Sie diese IPs:")
        for ip in other_ips:
             print(f"   👉 http://{ip}:{PORT}/play")

    print("\n🔧 TROUBLESHOOTING:")
    print("   1. Geräte müssen im GLEICHEN WLAN sein.")
    print("   2. ⚠️  WINDOWS FIREWALL: Zugriff für 'Python' zulassen!")
    print("   3. In Gast-WLANs/Schul-WLANs sind Geräte oft isoliert.")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=PORT)