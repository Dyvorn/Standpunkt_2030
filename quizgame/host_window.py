import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QStackedWidget, QCheckBox, 
                             QScrollArea, QFrame, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QUrl, QTimer
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import qrcode
from io import BytesIO

class UiBridge(QObject):
    """
    Brücke zwischen dem Flask-Server-Thread und dem PyQt6-GUI-Thread.
    Signale werden verwendet, um Thread-sichere Updates an der GUI zu ermöglichen.
    """
    update_players_signal = pyqtSignal(list)
    answer_received_signal = pyqtSignal(int)

class HostWindow(QMainWindow):
    """
    Hauptfenster der Lehrer-App, implementiert mit PyQt6.
    Verwaltet die verschiedenen Spielphasen (Setup, Lobby, Spiel, Auflösung, Ergebnisse).
    """
    def __init__(self, engine, server_module, local_ip):
        super().__init__()
        self.engine = engine
        self.server = server_module
        self.local_ip = local_ip
        
        # UI-Bridge initialisieren und dem Server-Modul übergeben
        self.ui_bridge = UiBridge()
        self.server.ui_bridge = self.ui_bridge
        
        self.setWindowTitle("QuizGame - Lehrer Panel")
        self.setMinimumSize(1100, 800)
        
        # Globales Stylesheet für ein modernes Dark-Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0f172a; }
            QWidget { color: #f8fafc; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
            QLabel { color: #f8fafc; }
            QPushButton {
                background-color: #6366f1;
                color: white;
                border-radius: 12px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover { background-color: #4f46e5; }
            QPushButton:pressed { background-color: #4338ca; }
            QPushButton:disabled { background-color: #334155; color: #94a3b8; }
            QScrollArea { border: none; background-color: transparent; }
            QCheckBox { font-size: 16px; spacing: 10px; padding: 10px; border-radius: 8px; background: #1e293b; }
            QCheckBox:hover { background: #334155; }
        """)
        
        # QStackedWidget für die Verwaltung der verschiedenen Screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Signale der UI-Bridge mit den GUI-Update-Slots verbinden
        self.ui_bridge.update_players_signal.connect(self.update_lobby_list)
        self.ui_bridge.answer_received_signal.connect(self.update_answer_count)

        # Initialisierung der einzelnen Screens
        self.init_setup_screen()
        self.init_lobby_screen()
        self.init_game_screen()
        self.init_resolution_screen()
        self.init_result_screen()

    def init_setup_screen(self):
        """Initialisiert den Screen für die Bereichsauswahl."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        
        title = QLabel("Quiz-Themen auswählen")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        
        self.checkboxes = []
        data_dir = Path("data")
        if data_dir.exists():
            for file in data_dir.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cb = QCheckBox(f"{data['bereich']} ({len(data['fragen'])} Fragen)")
                        cb.setProperty("data", data) # Speichert die JSON-Daten direkt im Checkbox-Objekt
                        cb.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.scroll_layout.addWidget(cb)
                        self.checkboxes.append(cb)
                except Exception as e:
                    QMessageBox.warning(self, "Fehler beim Laden", f"Konnte Datei {file.name} nicht laden: {e}")
        
        self.scroll.setWidget(self.scroll_content)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        btn = QPushButton("Vorbereiten")
        btn.setMinimumHeight(70)
        btn.setStyleSheet("background-color: #10b981; font-size: 20px;")
        btn.clicked.connect(self.prepare_game)
        layout.addWidget(btn)
        
        self.stack.addWidget(page)

    def init_lobby_screen(self):
        """Initialisiert den Lobby-Screen mit QR-Code und Spielerliste."""
        self.lobby_page = QWidget()
        layout = QVBoxLayout(self.lobby_page)
        layout.setContentsMargins(40, 40, 40, 40)

        # QR Code Container für Schatten-Effekt
        qr_container = QFrame()
        qr_container.setStyleSheet("background: white; border-radius: 20px; padding: 20px;")
        qr_layout = QVBoxLayout(qr_container)
        self.qr_label = QLabel()
        qr_layout.addWidget(self.qr_label)
        layout.addWidget(qr_container, alignment=Qt.AlignmentFlag.AlignCenter)

        self.url_label = QLabel(f"http://{self.local_ip}:5000")
        self.url_label.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        self.url_label.setStyleSheet("color: #818cf8; margin-top: 20px;")
        layout.addWidget(self.url_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.player_list_label = QLabel("Warte auf Teilnehmer...")
        self.player_list_label.setFont(QFont("Segoe UI", 16))
        self.player_list_label.setStyleSheet("color: #94a3b8; margin: 30px;")
        self.player_list_label.setWordWrap(True)
        layout.addWidget(self.player_list_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.start_btn = QPushButton("Spiel starten (0 Spieler)")
        self.start_btn.setEnabled(False) # Deaktiviert, bis Spieler beitreten
        self.start_btn.setMinimumHeight(70)
        self.start_btn.setStyleSheet("background-color: #6366f1; font-size: 20px;")
        self.start_btn.clicked.connect(self.start_game)
        layout.addWidget(self.start_btn)

        self.stack.addWidget(self.lobby_page)

    def init_game_screen(self):
        """Initialisiert den Screen zur Anzeige der aktuellen Frage und Antworten."""
        self.game_page = QWidget()
        layout = QVBoxLayout(self.game_page)
        layout.setContentsMargins(40, 20, 40, 40)

        self.q_progress = QLabel("FRAGE 1 VON X")
        self.q_progress.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.q_progress.setStyleSheet("color: #6366f1; letter-spacing: 2px;")
        layout.addWidget(self.q_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self.q_text = QLabel("Fragentext")
        self.q_text.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.q_text.setWordWrap(True)
        self.q_text.setMinimumHeight(150)
        self.q_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.q_text)

        self.ans_grid = QGridLayout()
        self.ans_grid.setSpacing(20)
        self.ans_labels = []
        colors = ["#ef4444", "#3b82f6", "#f59e0b", "#10b981"] # Modernere Tailwind-Farben
        shapes = ["▲", "◆", "●", "■"] # Dreieck, Raute, Kreis, Quadrat
        for i in range(4):
            lbl = QLabel()
            lbl.setStyleSheet(f"background-color: {colors[i]}; color: white; padding: 30px; border-radius: 15px; font-size: 24px; font-weight: bold;")
            lbl.setText(f"{shapes[i]} Antwort")
            lbl.setWordWrap(True)
            lbl.setMinimumHeight(120)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ans_grid.addWidget(lbl, i // 2, i % 2) # 2x2 Gitter
            self.ans_labels.append(lbl)
        layout.addLayout(self.ans_grid)

        self.ans_counter = QLabel("0 geantwortet")
        self.ans_counter.setFont(QFont("Segoe UI", 18))
        self.ans_counter.setStyleSheet("color: #94a3b8; margin: 20px;")
        layout.addWidget(self.ans_counter, alignment=Qt.AlignmentFlag.AlignCenter)

        resolve_btn = QPushButton("Auflösung")
        resolve_btn.setMinimumHeight(60)
        resolve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        resolve_btn.clicked.connect(self.show_resolution)
        layout.addWidget(resolve_btn)

        self.stack.addWidget(self.game_page)

    def init_resolution_screen(self):
        """Initialisiert den Screen zur Video-Wiedergabe und Anzeige der korrekten Antwort."""
        self.res_page = QWidget()
        layout = QVBoxLayout(self.res_page)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(400)
        layout.addWidget(self.video_widget)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)

        self.res_info = QLabel("Korrekte Antwort: ...")
        self.res_info.setFont(QFont("Arial", 18))
        self.res_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.res_info)

        next_btn = QPushButton("Nächste Frage")
        next_btn.setMinimumHeight(50)
        next_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 18px;")
        next_btn.clicked.connect(self.trigger_next_question)
        layout.addWidget(next_btn)

        self.stack.addWidget(self.res_page)

    def init_result_screen(self):
        """Initialisiert den Screen zur Anzeige der finalen Rangliste."""
        self.res_final_page = QWidget()
        layout = QVBoxLayout(self.res_final_page)
        
        title = QLabel("Rangliste")
        title.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.rank_label = QLabel()
        self.rank_label.setFont(QFont("Arial", 16))
        self.rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.rank_label)

        new_btn = QPushButton("Neues Spiel")
        new_btn.setMinimumHeight(50)
        new_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 18px;")
        new_btn.clicked.connect(self.reset_everything)
        layout.addWidget(new_btn)

        self.stack.addWidget(self.res_final_page)

    # --- LOGIK FUNKTIONEN ---

    def prepare_game(self):
        """Sammelt ausgewählte Fragen und wechselt zum Lobby-Screen."""
        selected = [cb.property("data") for cb in self.checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Fehler", "Bitte wähle mindestens einen Bereich.")
            return
        
        self.engine.load_questions(selected)
        self.engine.state = "LOBBY"
        
        # QR Generieren
        url = f"http://{self.local_ip}:5000"
        img = qrcode.make(url)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        self.qr_label.setPixmap(pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        self.stack.setCurrentIndex(1) # Wechsel zum Lobby-Screen

    def update_lobby_list(self, players):
        """Aktualisiert die Liste der beigetretenen Spieler im Lobby-Screen."""
        names = [p["name"] for p in players]
        self.player_list_label.setText("Spieler: " + ", ".join(names))
        self.start_btn.setText(f"Spiel starten ({len(players)} Spieler)")
        self.start_btn.setEnabled(len(players) > 0)

    def start_game(self):
        """Startet das Spiel und sendet das 'game_start'-Event an alle Schüler."""
        self.server.socketio.emit('game_start', broadcast=True) # broadcast=True ist wichtig für alle Clients
        self.trigger_next_question()

    def trigger_next_question(self):
        """Wechselt zur nächsten Frage oder zu den Endergebnissen."""
        self.media_player.stop() # Stoppt das Video, falls es noch läuft
        q = self.engine.next_question()
        if q:
            self.q_progress.setText(f"Frage {self.engine.current_question_index + 1} / {len(self.engine.questions)}")
            self.q_text.setText(q["frage"])
            for i, ans in enumerate(q["antworten"]):
                self.ans_labels[i].setText(f"{['▲','◆','●','■'][i]} {ans['text']}")
            self.ans_counter.setText("0 geantwortet")
            self.server.broadcast_question(q)
            self.stack.setCurrentIndex(2) # Wechsel zum Game-Screen
        else:
            self.show_final_results()

    def update_answer_count(self, count):
        """Aktualisiert die Anzeige der eingegangenen Antworten."""
        self.ans_counter.setText(f"{count} von {len(self.engine.players)} geantwortet")

    def show_resolution(self):
        """Zeigt die Auflösung der Frage, spielt das Video ab und markiert die korrekte Antwort."""
        self.engine.state = "RESOLUTION"
        q = self.engine.get_current_question()
        
        if not q: # Falls keine Frage geladen ist
            QMessageBox.warning(self, "Fehler", "Keine aktuelle Frage zur Auflösung vorhanden.")
            return

        correct_answer_text = ""
        correct_idx = -1
        for i, ans in enumerate(q["antworten"]):
            if ans["korrekt"]:
                correct_answer_text = ans["text"]
                correct_idx = i
                break
        
        self.res_info.setText(f"Korrekte Antwort: {correct_answer_text}")
        
        # Markiere die korrekte Antwort im Game-Screen (optional, da wir zum Resolution-Screen wechseln)
        # for i, label in enumerate(self.ans_labels):
        #     if i == correct_idx:
        #         label.setStyleSheet(label.styleSheet() + "border: 3px solid green;")
        #     else:
        #         label.setStyleSheet(label.styleSheet() + "border: 3px solid red;")

        self.server.broadcast_resolution()
        self.stack.setCurrentIndex(3) # Wechsel zum Resolution-Screen

        # Video laden und abspielen
        vid_path = Path("videos") / q["video"]
        if vid_path.exists():
            self.media_player.setSource(QUrl.fromLocalFile(str(vid_path.absolute())))
            self.media_player.play()
        else:
            self.res_info.setText(f"{self.res_info.text()}\n(Video '{q['video']}' nicht gefunden oder Pfad falsch)")
            # Wenn kein Video, direkt zur nächsten Frage nach kurzer Verzögerung
            QTimer.singleShot(3000, self.trigger_next_question)

    def handle_media_status(self, status):
        """Behandelt den Status des Media Players, um nach Videoende fortzufahren."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.trigger_next_question()

    def show_final_results(self):
        """Zeigt die finale Rangliste an."""
        self.engine.state = "RESULTS"
        self.server.broadcast_results()
        leaderboard = self.engine.get_leaderboard()
        text = ""
        for p in leaderboard[:10]: # Top 10 Spieler anzeigen
            text += f"{p['rank']}. {p['name']} - {p['points']} Pkt\n"
        self.rank_label.setText(text)
        self.stack.setCurrentIndex(4) # Wechsel zum Result-Screen

    def reset_everything(self):
        """Setzt das Spiel komplett zurück und kehrt zum Setup-Screen zurück."""
        self.engine.reset()
        self.stack.setCurrentIndex(0) # Wechsel zum Setup-Screen