#
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
from pathlib import Path
from typing import Dict, List

app = FastAPI()
app.mount("/static", StaticFiles(directory="."), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, room_id: str, data: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(data)

# Load DATA
DATA = json.loads(Path("data.json").read_text(encoding="utf-8"))
rooms = {}  # room_id -> state

class SimpleGame:
    def __init__(self, thema):
        self.thema = thema
        self.scene = "lobby"
        self.werte = DATA["themen"][thema]["werte"].copy()
        self.votes = {}
        self.total_votes = 0

    def vote(self, option):
        self.votes[option] = self.votes.get(option, 0) + 1
        self.total_votes += 1
        return self.votes

    def next_scene(self, option_id):
        scene = DATA["themen"][self.thema]["szenarien"][self.scene]
        option = next((o for o in scene["optionen"] if o["id"] == option_id), None)
        if option:
            if "delta" in option and option["delta"]:
                for w, d in option["delta"].items():
                    if w in self.werte:
                        self.werte[w] = max(0, min(100, self.werte[w] + d))
            self.scene = option["next"]
        return self.scene

manager = ConnectionManager()

def get_state(room_id: str):
    if room_id not in rooms:
        return None
    game = rooms[room_id]
    scene_data = DATA["themen"][game.thema]["szenarien"][game.scene]
    return {
        "scene": scene_data,
        "werte": game.werte,
        "votes": game.votes,
        "total_votes": game.total_votes
    }

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html") as f:
        return HTMLResponse(content=f.read())

@app.post("/room/{room_id}/start/{thema}")
async def start(room_id: str, thema: str):
    rooms[room_id] = SimpleGame(thema)
    initial_state = get_state(room_id)
    await manager.broadcast(room_id, initial_state)
    return {"status": "started", "thema": thema}

@app.get("/room/{room_id}/state")
async def state_endpoint(room_id: str):
    state_data = get_state(room_id)
    if not state_data:
        return {"error": "Room not found"}
    return state_data

@app.post("/room/{room_id}/vote/{option}")
async def vote_endpoint(room_id: str, option: str):
    if room_id not in rooms:
        return {"error": "Room not found"}
    game = rooms[room_id]
    game.vote(option)
    await manager.broadcast(room_id, get_state(room_id))
    return {"votes": game.votes, "total": game.total_votes}

@app.post("/room/{room_id}/next/{option_id}")
async def next_endpoint(room_id: str, option_id: str):
    if room_id not in rooms:
        return {"error": "Room not found"}
    game = rooms[room_id]
    new_scene = game.next_scene(option_id)
    await manager.broadcast(room_id, get_state(room_id))
    return {"next_scene": new_scene, "werte": game.werte}

@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            await websocket.receive_text() # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
