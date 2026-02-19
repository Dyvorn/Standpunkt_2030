from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# App initialisieren
app = FastAPI()

# Ordner verknüpfen
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Speicher für verbundene Geräte (Einfache Liste für den Anfang)
connected_clients = []

# --- ROUTEN (Die Seiten) ---

@app.get("/", response_class=HTMLResponse)
async def get_landing(request: Request):
    """Startseite: Hier wählen wir später, ob wir Board oder Handy sind"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/board", response_class=HTMLResponse)
async def get_board(request: Request):
    """Die Beamer-Ansicht"""
    return templates.TemplateResponse("board.html", {"request": request})

@app.get("/play", response_class=HTMLResponse)
async def get_mobile(request: Request):
    """Die Handy-Ansicht für Schüler"""
    return templates.TemplateResponse("mobile.html", {"request": request})

# --- WEBSOCKETS (Die Echtzeit-Verbindung) ---

@app.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Warte auf Nachricht (z.B. Vote vom Handy)
            data = await websocket.receive_text()
            print(f"Nachricht von {client_type}: {data}")
            
            # Sende Nachricht an ALLE zurück (Broadcast)
            for client in connected_clients:
                await client.send_text(f"Update: {data}")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print(f"{client_type} hat die Verbindung getrennt")

# Server Starten (Nur wenn direkt ausgeführt)
if __name__ == "__main__":
    # Wir übergeben 'app' direkt als Objekt, nicht als String.
    # Das funktioniert immer, egal wie du die Datei startest.
    uvicorn.run(app, host="0.0.0.0", port=8000)