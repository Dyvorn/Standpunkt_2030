import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import socket
import qrcode

app = FastAPI()

# --- PFADE ---
BASE_DIR = Path(__file__).resolve().parent.parent
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"
data_path = BASE_DIR / "data"

# Ordner sicherstellen
for p in [static_path, templates_path, data_path]:
    p.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# --- GAME STATE ---
# Lädt alle Szenarien aus der zentralen JSON-Datei
def load_all_scenarios(filename="scenarios.json"):
    path = Path(__file__).resolve().parent / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"FEHLER: Konnte '{filename}' nicht finden.")
    return {}

ALL_SCENARIOS = load_all_scenarios()

def _create_initial_state():
    """Helper to create the base state dictionary."""
    initial_values = {
        "sicherheit": 50, "freiheit": 65, "budget": 60,
        "tierwohl": 40, "lebenshaltungskosten": 55, "bauernzufriedenheit": 60
    }
    return {
        "values": initial_values,
        "current_scenario_id": None,
        "theme": None,
        "scenario_data": {},
        "votes": {},
        "phase": "loading", # Startphase
    }

# Aktueller Status des Spiels (Global)
current_game_state = _create_initial_state()

connected_clients = []

def change_scenario(scenario_id: str):
    """Wechselt das Spiel zum angegebenen Szenario und setzt den Status zurück."""
    global current_game_state
    
    next_scenario_data = ALL_SCENARIOS.get(scenario_id)
    if not next_scenario_data:
        print(f"FEHLER: Szenario '{scenario_id}' nicht in scenarios.json gefunden.")
        # Gracefully end the game if scenario is not found
        current_game_state["phase"] = "end"
        current_game_state["scenario_data"] = {"title": "Spielende", "board": {"title_text": f"Szenario '{scenario_id}' konnte nicht geladen werden."}}
        return

    current_game_state["current_scenario_id"] = scenario_id
    current_game_state["scenario_data"] = next_scenario_data
    current_game_state["theme"] = next_scenario_data.get("theme")
    
    vote_options = next_scenario_data.get("vote_options", [])
    current_game_state["votes"] = {opt["id"]: 0 for opt in vote_options}
    
    current_game_state["phase"] = "voting" if vote_options else "end"
        
    current_game_state.pop("winning_option_id", None)
    current_game_state.pop("next_scenario_id", None)

def end_voting_and_show_results():
    """Ermittelt den Gewinner, wendet Effekte an und wechselt in die 'result' Phase."""
    global current_game_state

    votes = current_game_state.get("votes", {})
    if not votes: return

    # Gewinner ermitteln (höchste Stimmenzahl, bei Gleichstand gewinnt die erste Option)
    winner_id = max(votes, key=votes.get)

    winning_option_data = next((opt for opt in current_game_state["scenario_data"].get("vote_options", []) if opt["id"] == winner_id), None)
    
    if not winning_option_data:
        print(f"FEHLER: Gewinner-Option '{winner_id}' nicht in Szenario-Daten gefunden.")
        return

    # Effekte anwenden
    for key, value in winning_option_data.get("value_effects", {}).items():
        if key in current_game_state["values"]:
            current_game_state["values"][key] += value

    # Status für die 'result'-Phase aktualisieren
    current_game_state["phase"] = "result"
    current_game_state["winning_option_id"] = winner_id
    current_game_state["next_scenario_id"] = winning_option_data.get("next_scenario_if_wins")

def reset_game(start_scenario_id: str = "W1"):
    """Setzt das Spiel auf den Anfangszustand zurück."""
    global current_game_state
    current_game_state = _create_initial_state()
    change_scenario(start_scenario_id)
    print(f"Spiel zurückgesetzt auf Szenario {start_scenario_id}.")

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
    await websocket.accept()
    connected_clients.append(websocket)
    
    # 1. SOFORT den aktuellen Stand an den Neuen senden!
    # Damit das Handy weiß, was es anzeigen soll.
    await websocket.send_json(current_game_state)
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "vote" and current_game_state.get("phase") == "voting":
                option_id = data.get("value")
                if option_id in current_game_state.get("votes", {}):
                    current_game_state["votes"][option_id] += 1
                    await broadcast_state()

            elif message_type == "reset_game":
                start_id = data.get("start_scenario_id", "W1") # Default to Wehrpflicht
                reset_game(start_id)
                await broadcast_state()

            elif message_type == "advance_game":
                phase = current_game_state.get("phase")
                if phase == "voting":
                    end_voting_and_show_results()
                    await broadcast_state()
                elif phase == "result":
                    next_id = current_game_state.get("next_scenario_id")
                    if next_id:
                        change_scenario(next_id)
                        await broadcast_state()
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

async def broadcast_state():
    """Sendet den aktuellen Status an alle verbundenen Geräte"""
    for client in connected_clients:
        try:
            await client.send_json(current_game_state)
        except:
            pass # Ignorieren, falls einer gerade disconnectet

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
    # On startup, reset the game state
    reset_game() # Startet standardmäßig mit "W1"

    # Generate QR Code for local network access
    HOST_IP = get_local_ip()
    PORT = 8000
    play_url = f"http://{HOST_IP}:{PORT}/play"
    
    # QR-Code als Bild im Static-Ordner speichern
    qr_code_path = static_path / "qr_code.png"
    try:
        qrcode.make(play_url).save(str(qr_code_path))
        print("="*50)
        print("Spiel-Server wird gestartet. So können Spieler beitreten:")
        print(f"1. Alle Geräte mit demselben WLAN/Hotspot verbinden.")
        print(f"   (Es wird KEINE Internetverbindung benötigt)")
        print(f"2. Auf dem 'Board' (Beamer) die Seite http://{HOST_IP}:{PORT}/board öffnen.")
        print(f"3. Spieler scannen den QR-Code oder geben die URL ein:")
        print(f"   {play_url}")
        print("="*50)
    except Exception as e:
        print(f"FEHLER beim Erstellen des QR-Codes: {e}")
        print("Stellen Sie sicher, dass 'qrcode' und 'Pillow' installiert sind: pip install qrcode[pil]")

    uvicorn.run(app, host="0.0.0.0", port=PORT)