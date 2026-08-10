from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import logging

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Wird von main.py gesetzt
engine = None
ui_bridge = None


@app.route("/")
def index():
    if engine.state == "SETUP" or engine.state == "LOBBY":
        return render_template("join.html")
    return "Spiel läuft bereits oder ist beendet."


@app.route("/lobby")
def lobby():
    return render_template("lobby.html")


@app.route("/game")
def game():
    return render_template("game.html")


@socketio.on("join_game")
def handle_join(data):
    """Handles a player joining the game and updates the UI lobby list."""
    name = data.get("name", "Anonym")
    print(f"Spieler beigetreten/reconnected: {name} (SID: {request.sid})")
    engine.add_player(request.sid, name)
    emit("player_joined", {"name": name, "count": len(engine.players)}, broadcast=True)
    if ui_bridge:
        ui_bridge.update_players_signal.emit(list(engine.players.values()))


@socketio.on("submit_answer")
def handle_answer(data):
    """Handles a player's answer submission and logs it."""
    idx = data.get("index")
    print(f"Antwort-Versuch von {request.sid}: Index {idx}")
    if engine.submit_answer(request.sid, idx):
        print(f"Antwort akzeptiert für {request.sid}")
        emit("answer_confirmed", {"status": "ok"})
        if ui_bridge:
            ui_bridge.answer_received_signal.emit(engine.answers_received)
    else:
        print(
            f"Antwort abgelehnt für {request.sid}. Grund: Falsche Phase oder SID nicht in engine.players (Bekannt: {request.sid in engine.players})"
        )


@socketio.on("request_current_state")
def handle_state_request():
    # Falls ein Spieler mitten im Spiel beitritt/neu lädt, bekommt er die aktuelle Frage
    q = engine.get_current_question()
    if q and engine.state == "QUESTION":
        broadcast_question(q, room=request.sid)  # Nur an den anfragenden Client senden
        if not engine.is_reading_time:
            emit("start_voting", to=request.sid)


@socketio.on("disconnect")
def handle_disconnect():
    # In einer robusten App würde man Spieler hier entfernen
    pass


def broadcast_question(question_data, room=None):
    """Broadcasts the current question text and answers to all or a specific room."""
    # Wir senden nur die Texte, nicht die Korrektheit
    clean_answers = [a["text"] for a in question_data["antworten"]]
    socketio.emit(
        "new_question",
        {
            "frage": question_data["frage"],
            "antworten": clean_answers,
            "index": engine.current_question_index + 1,
            "total": len(engine.questions),
        },
        to=room,
    )


def broadcast_resolution():
    q = engine.get_current_question()
    correct_idx = next(i for i, a in enumerate(q["antworten"]) if a["korrekt"])
    correct_text = q["antworten"][correct_idx]["text"]

    # Individuelles Feedback für jeden Spieler
    for sid, p in engine.players.items():
        socketio.emit(
            "resolution",
            {
                "correct_index": correct_idx,
                "correct_text": correct_text,
                "your_correct": p.get("last_correct", False),
                "points": p["points"],
            },
            to=sid,
        )


def broadcast_results():
    leaderboard = engine.get_leaderboard()
    socketio.emit("final_results", {"leaderboard": leaderboard})


def broadcast_game_start():
    socketio.emit("game_start")


def broadcast_start_voting():
    socketio.emit("start_voting")


def broadcast_game_reset():
    socketio.emit("game_reset")


def run_server(host, port):
    socketio.run(
        app,
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
