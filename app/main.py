import asyncio
import json
import os
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# --- PFADE ---
BASE_DIR = Path(__file__).resolve().parent.parent
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"
data_path = BASE_DIR / "data"

# Ordner sicherstellen
for p in [static_path, templates_path, data_path]:
    if not p.exists():
        os.makedirs(p)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# --- GAME STATE ---
# Hier laden wir die JSON Datei beim Start
def load_scenario(filename):
    path = data_path / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def initialize_game_state():
    """Erstellt den initialen Spielstatus."""
    return {
        "phase": "question",
        "scenario": load_scenario("wehrpflicht.json"),
        "votes": {"A": 0, "B": 0}
    }

# Aktueller Status des Spiels (Global)
current_game_state = initialize_game_state()

connected_clients = []

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
            # 2. Auf Nachrichten warten (Votes)
            data = await websocket.receive_json()
            
            if data.get("type") == "vote":
                option = data.get("value")
                # Vote zählen
                if option in current_game_state["votes"]:
                    current_game_state["votes"][option] += 1
                
                # Update an ALLE senden (damit Board Balken aktualisiert)
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

if __name__ == "__main__":
    # On startup, reset the game state
    # current_game_state is already initialized above
    uvicorn.run(app, host="0.0.0.0", port=8000)