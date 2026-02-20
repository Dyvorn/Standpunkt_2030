import json
import os
import secrets
import string
import socket
import sys
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn

app = FastAPI()

# --- PFADE ---
if getattr(sys, 'frozen', False):
    # Wenn das Programm als .exe läuft (PyInstaller)
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Wenn es normal als Skript läuft
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
# Statt eines globalen Zustands verwalten wir mehrere Spielräume
game_rooms = {}

def generate_room_code(length=5):
    """Generiert einen einzigartigen, leicht zu merkenden Raum-Code."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        if code not in game_rooms:
            return code

def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Computers im Netzwerk."""
    try:
        # Dummy-Verbindung aufbauen, um die eigene IP zu finden (sendet keine Daten)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def load_theme_file(filename):
    path = data_path / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# --- ROUTEN ---
@app.get("/", response_class=HTMLResponse)
async def get_landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "server_ip": get_local_ip()})

@app.post("/create")
async def create_room():
    """Erstellt einen neuen Spielraum und leitet den Host zur Admin-Seite."""
    room_code = generate_room_code()
    game_rooms[room_code] = {
        "active_theme_data": {},
        "state": {"scenario": None, "votes": {}, "stats": {}},
        "clients": []
    }
    return RedirectResponse(url=f"/admin/{room_code}", status_code=303)

@app.post("/join")
async def join_room(room_code: str = Form(...)):
    """Leitet einen Spieler in einen Raum weiter, wenn dieser existiert."""
    code = room_code.upper()
    if code in game_rooms:
        return RedirectResponse(url=f"/play/{code}", status_code=303)
    else:
        return RedirectResponse(url="/?error=notfound", status_code=303)

@app.get("/board/{room_code}", response_class=HTMLResponse)
async def get_board(request: Request, room_code: str):
    return templates.TemplateResponse("board.html", {"request": request, "room_code": room_code.upper()})

@app.get("/play/{room_code}", response_class=HTMLResponse)
async def get_mobile(request: Request, room_code: str):
    return templates.TemplateResponse("mobile.html", {"request": request, "room_code": room_code.upper()})

# --- ADMIN ROUTEN ---
@app.get("/admin/{room_code}", response_class=HTMLResponse)
async def get_admin(request: Request, room_code: str):
    if room_code.upper() in game_rooms:
        return templates.TemplateResponse("admin.html", {"request": request, "room_code": room_code.upper(), "server_ip": get_local_ip()})
    return HTMLResponse("Raum nicht gefunden", status_code=404)

@app.get("/admin/{room_code}/status")
async def get_admin_status(room_code: str):
    room = game_rooms.get(room_code.upper())
    if room:
        return JSONResponse(room["state"])
    return JSONResponse({"error": "Room not found"}, status_code=404)

@app.post("/admin/{room_code}/start")
async def start_game(room_code: str, theme: str = Form(...)):
    room_code = room_code.upper()
    room = game_rooms.get(room_code)
    if not room:
        return HTMLResponse("Raum nicht gefunden", status_code=404)

    data = load_theme_file(theme)
    if data:
        room["active_theme_data"] = data
        room["state"]["stats"] = data["meta"]["initial_stats"].copy()
        start_scene_id = data["meta"]["start_scene"]
        
        load_scene(room_code, start_scene_id)
        await broadcast_state(room_code)
        
    return RedirectResponse(url=f"/admin/{room_code}", status_code=303)

@app.post("/admin/{room_code}/next")
async def next_scene(room_code: str):
    room_code = room_code.upper()
    room = game_rooms.get(room_code)
    if not room:
        return HTMLResponse("Raum nicht gefunden", status_code=404)

    votes = room["state"]["votes"]
    if not votes:
        return RedirectResponse(url=f"/admin/{room_code}", status_code=303)
        
    winner_id = max(votes, key=votes.get) if votes else "A"
    
    current_scene = room["state"]["scenario"]
    selected_option = next((opt for opt in current_scene["options"] if opt["id"] == winner_id), None)
    
    if selected_option:
        effects = selected_option.get("effects", {})
        for key, val in effects.items():
            if key in room["state"]["stats"]:
                room["state"]["stats"][key] += val
        
        next_id = selected_option.get("next_scene")
        if next_id and next_id in room["active_theme_data"]["scenes"]:
            load_scene(room_code, next_id)
            await broadcast_state(room_code)
            
    return RedirectResponse(url=f"/admin/{room_code}", status_code=303)

def load_scene(room_code: str, scene_id: str):
    """Lädt eine Szene aus active_theme_data in den aktuellen State"""
    room = game_rooms[room_code]
    scene = room["active_theme_data"]["scenes"][scene_id]
    room["state"]["scenario"] = scene
    room["state"]["votes"] = {opt["id"]: 0 for opt in scene.get("options", [])}

# --- WEBSOCKET LOGIC ---
@app.websocket("/ws/{room_code}/{client_type}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, client_type: str):
    room_code = room_code.upper()
    room = game_rooms.get(room_code)
    if not room:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    room["clients"].append(websocket)
    await websocket.send_json(room["state"])
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "vote":
                option = data.get("value")
                if option in room["state"]["votes"]:
                    room["state"]["votes"][option] += 1
                
                await broadcast_state(room_code)
                
    except WebSocketDisconnect:
        if websocket in room["clients"]:
            room["clients"].remove(websocket)

async def broadcast_state(room_code: str):
    """Sendet den aktuellen Status an alle verbundenen Geräte in einem Raum."""
    room_code = room_code.upper()
    room = game_rooms.get(room_code)
    if not room:
        return

    # Erstelle eine Kopie der Client-Liste, um sie sicher zu durchlaufen
    for client in list(room["clients"]):
        try:
            await client.send_json(room["state"])
        except Exception:
            if client in room["clients"]:
                room["clients"].remove(client)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
