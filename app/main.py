import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# --- Game State Management ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# In-memory storage for the game state. For a real-world app, this would be a database.
game_state: Dict[str, Any] = {}

# Load scenario data from JSON
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"
with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
    scenarios_data = json.load(f)

def initialize_game_state(theme: str = "wehrpflicht"):
    """Resets the game state to its initial values for a given theme."""
    global game_state

    initial_values = {
        "wehrpflicht": {"sicherheit": 50, "freiheit": 65, "budget": 60},
        "tierschutz": {"tierwohl": 40, "lebenshaltungskosten": 55, "bauernzufriedenheit": 60}
    }

    first_scenario = {
        "wehrpflicht": "W1",
        "tierschutz": "T1"
    }

    current_scenario_id = first_scenario.get(theme, "W1")

    game_state = {
        "session_id": f"session-{uuid.uuid4().hex[:8]}",
        "theme": theme,
        "current_scenario_id": current_scenario_id,
        "current_phase": "reading",  # reading, voting, results
        "values": initial_values.get(theme, {}),
        "votes": {},
        "clients": {},
        "scenario_history": [current_scenario_id],
    }
    # Initialize votes for the first scenario
    game_state["votes"][current_scenario_id] = {
        option["id"]: 0 for option in scenarios_data[current_scenario_id].get("vote_options", [])
    }
    game_state["votes"][current_scenario_id]["total_voted"] = 0


initialize_game_state() # Initialize on startup

# --- WebSocket Endpoint ---

@app.websocket("/ws/{client_id}/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, client_type: str):
    await manager.connect(websocket, client_id)
    print(f"Client connected: {client_id} ({client_type})")

    # Add client to game state
    game_state["clients"][client_id] = {"type": client_type, "connected": True}

    # Send initial state to the newly connected client
    await websocket.send_json({"event": "state_update", "payload": game_state})
    await manager.broadcast({"event": "client_update", "payload": game_state["clients"]})

    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            payload = data.get("payload")

            # --- Admin Events ---
            if event == "admin:start_session":
                print("Admin started a new session.")
                theme = payload.get("theme", "wehrpflicht")
                initialize_game_state(theme=theme)
                await manager.broadcast({"event": "state_update", "payload": game_state})

            if event == "admin:change_phase":
                new_phase = payload.get("phase")
                if new_phase in ["reading", "voting", "results"]:
                    game_state["current_phase"] = new_phase
                    print(f"Phase changed to {new_phase}")
                    await manager.broadcast({"event": "phase_change", "payload": {"phase": new_phase}})

            if event == "admin:next_scenario":
                print("Admin triggered next scenario.")
                current_scenario_id = game_state["current_scenario_id"]
                votes = game_state["votes"][current_scenario_id]

                if not votes or votes.get("total_voted", 0) == 0:
                    votes = {opt["id"]: 1 for opt in scenarios_data[current_scenario_id]["vote_options"]}
                
                # Determine winner
                winner = max(votes, key=lambda k: votes[k] if k != "total_voted" else -1)

                # Find next scenario ID
                current_scenario_options = scenarios_data[current_scenario_id]["vote_options"]
                next_scenario_id = None
                for option in current_scenario_options:
                    if option["id"] == winner:
                        next_scenario_id = option["next_scenario_if_wins"]
                        # Apply value effects
                        for value, effect in option["value_effects"].items():
                            if value in game_state["values"]:
                                game_state["values"][value] += effect
                        break
                
                if next_scenario_id and next_scenario_id in scenarios_data:
                    game_state["current_scenario_id"] = next_scenario_id
                    game_state["current_phase"] = "reading"
                    game_state["scenario_history"].append(next_scenario_id)
                    
                    # Initialize votes for the new scenario
                    if scenarios_data[next_scenario_id].get("vote_options"):
                        game_state["votes"][next_scenario_id] = { 
                            option["id"]: 0 for option in scenarios_data[next_scenario_id]["vote_options"]
                        }
                        game_state["votes"][next_scenario_id]["total_voted"] = 0

                    await manager.broadcast({"event": "scenario_change", "payload": {
                        "new_scenario_id": next_scenario_id,
                        "values": game_state["values"]
                    }})
                    await manager.broadcast({"event": "state_update", "payload": game_state})
                else:
                    print(f"End of path or invalid next_scenario_id: {next_scenario_id}")


            # --- Handy Events ---
            if event == "handy:vote":
                scenario_id = payload.get("scenario_id")
                choice = payload.get("choice")
                
                # Simple check to prevent double voting
                if game_state["clients"][client_id].get(f"voted_{scenario_id}"):
                    continue

                if scenario_id == game_state["current_scenario_id"] and game_state["current_phase"] == "voting":
                    if choice in game_state["votes"][scenario_id]:
                        game_state["votes"][scenario_id][choice] += 1
                        game_state["votes"][scenario_id]["total_voted"] += 1
                        game_state["clients"][client_id][f"voted_{scenario_id}"] = choice
                        
                        print(f"Vote received: {client_id} voted for {choice} in {scenario_id}")
                        
                        # Broadcast vote update
                        await manager.broadcast({
                            "event": "vote_update",
                            "payload": {
                                "scenario_id": scenario_id,
                                "votes": game_state["votes"][scenario_id]
                            }
                        })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        game_state["clients"][client_id]["connected"] = False
        print(f"Client disconnected: {client_id}")
        await manager.broadcast({"event": "client_update", "payload": game_state["clients"]})


# --- API Endpoints ---

@app.get("/api/scenarios")
async def get_scenarios():
    """Endpoint to get all scenario definitions."""
    return scenarios_data

@app.get("/api/state")
async def get_state():
    """Endpoint to get the current game state."""
    return game_state

# --- Static File Serving ---

# Create a dummy root file for the server path
@app.get("/")
async def read_root():
    return {"message": "Standpunkt 2030 Server is running. Connect clients to /admin, /board, or /handy."}


# Mount the frontend directories
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/admin", StaticFiles(directory=frontend_path / "admin", html=True), name="admin")
app.mount("/board", StaticFiles(directory=frontend_path / "board", html=True), name="board")
app.mount("/handy", StaticFiles(directory=frontend_path / "handy", html=True), name="handy")


if __name__ == "__main__":
    import uvicorn
    # On startup, reset the game state
    initialize_game_state()
    uvicorn.run(app, host="0.0.0.0", port=8000)