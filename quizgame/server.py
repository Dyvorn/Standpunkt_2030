from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import logging

# Logging deaktivieren für sauberere Konsole
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Wird von main.py gesetzt
engine = None
ui_bridge = None 

@app.route('/')
def index():
    if engine.state == "SETUP" or engine.state == "LOBBY":
        return render_template('join.html')
    return "Spiel läuft bereits oder ist beendet."

@app.route('/lobby')
def lobby():
    return render_template('lobby.html')

@app.route('/game')
def game():
    return render_template('game.html')

@socketio.on('join_game')
def handle_join(data):
    name = data.get('name', 'Anonym')
    engine.add_player(request.sid, name)
    emit('player_joined', {'name': name, 'count': len(engine.players)}, broadcast=True)
    if ui_bridge:
        ui_bridge.update_players_signal.emit(list(engine.players.values()))

@socketio.on('submit_answer')
def handle_answer(data):
    idx = data.get('index')
    if engine.submit_answer(request.sid, idx):
        emit('answer_confirmed', {'status': 'ok'})
        if ui_bridge:
            ui_bridge.answer_received_signal.emit(engine.answers_received)

@socketio.on('disconnect')
def handle_disconnect():
    # In einer robusten App würde man Spieler hier entfernen
    pass

def broadcast_question(question_data):
    # Wir senden nur die Texte, nicht die Korrektheit
    clean_answers = [a["text"] for a in question_data["antworten"]]
    socketio.emit('new_question', {
        'frage': question_data['frage'],
        'antworten': clean_answers,
        'index': engine.current_question_index + 1,
        'total': len(engine.questions)
    })

def broadcast_resolution():
    q = engine.get_current_question()
    correct_idx = next(i for i, a in enumerate(q["antworten"]) if a["korrekt"])
    
    # Individuelles Feedback für jeden Spieler
    for sid, p in engine.players.items():
        socketio.emit('resolution', {
            'correct_index': correct_idx,
            'your_correct': p.get("last_correct", False),
            'points': p['points']
        }, room=sid)

def broadcast_results():
    leaderboard = engine.get_leaderboard()
    socketio.emit('final_results', {'leaderboard': leaderboard})

def broadcast_game_start():
    socketio.emit('game_start')

def run_server(host, port):
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)