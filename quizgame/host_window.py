import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QCheckBox,
    QSizePolicy,
    QApplication,
    QLineEdit,
    QScrollArea,
    QFrame,
    QGridLayout,
    QMessageBox,
    QHBoxLayout,
    QProgressDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QUrl, QTimer
from PyQt6.QtGui import QFont, QPixmap, QDesktopServices, QPainter, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import qrcode
from io import BytesIO
from pyngrok import ngrok, conf, installer
import os

# Disable progress output in pyngrok to prevent stdout write issues in GUI mode
installer._print_progress_enabled = False
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
from updater import UpdateChecker, UpdateDownloader


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

    def __init__(self, engine, server_module, local_ip, current_version="1.0.1"):
        super().__init__()
        self.engine = engine
        self.server = server_module
        self.local_ip = local_ip
        self.current_version = current_version

        # UI-Bridge initialisieren und dem Server-Modul übergeben
        self.ui_bridge = UiBridge()
        self.server.ui_bridge = self.ui_bridge

        self.setWindowTitle(f"QuizGame - Lehrer Panel (v{self.current_version})")
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

        # Timer-Logik für Fragen
        self.question_timer = QTimer()
        self.question_timer.timeout.connect(self.update_countdown)
        self.remaining_time = 0

        # Initialisierung der einzelnen Screens
        self.init_setup_screen()
        self.init_lobby_screen()
        self.init_game_screen()
        self.init_resolution_screen()
        self.init_result_screen()
        
        # Auf Updates prüfen
        self.check_for_updates()

    def check_for_updates(self):
        """Startet den Update-Checker im Hintergrund."""
        # Das Repo ist laut git-URL Dyvorn/Standpunkt_2030
        self.checker = UpdateChecker(self.current_version, "Dyvorn", "Standpunkt_2030")
        self.checker.update_available.connect(self.on_update_available)
        self.checker.start()

    def on_update_available(self, version, download_url):
        """Wird aufgerufen, wenn ein Update gefunden wurde."""
        reply = QMessageBox.question(
            self,
            "Update verfügbar",
            f"Eine neue Version (v{version}) ist verfügbar. Möchtest du sie jetzt herunterladen und installieren?\n\nDas Spiel wird nach dem Download beendet.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.start_download(download_url)

    def start_download(self, download_url):
        """Startet den Download in einem separaten Thread und zeigt einen Ladebalken."""
        self.progress_dialog = QProgressDialog("Update wird heruntergeladen...", "Abbrechen", 0, 100, self)
        self.progress_dialog.setWindowTitle("Update")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)

        self.downloader = UpdateDownloader(download_url)
        self.downloader.progress.connect(self.progress_dialog.setValue)
        self.downloader.finished.connect(self.on_download_finished)
        self.downloader.error.connect(lambda e: QMessageBox.critical(self, "Download-Fehler", f"Fehler: {e}"))
        
        self.progress_dialog.canceled.connect(self.downloader.terminate)
        self.downloader.start()

    def on_download_finished(self, file_path):
        """Führt den heruntergeladenen Installer aus und beendet die aktuelle Anwendung."""
        try:
            os.startfile(file_path)
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte Installer nicht starten: {e}")

    def init_setup_screen(self):
        """Initialisiert den Screen für die Bereichsauswahl."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        top_layout = QHBoxLayout()
        
        # Logo
        self.logo_label = QLabel()
        logo_path = self.get_asset_path("logo.png")
        if logo_path and logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(
                150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            
            # Make the logo rounded
            size = min(pixmap.width(), pixmap.height())
            rounded = QPixmap(size, size)
            rounded.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, size, size, 25, 25)  # 25 is the corner radius
            painter.setClipPath(path)
            # Draw the pixmap centered
            x_offset = (size - pixmap.width()) // 2
            y_offset = (size - pixmap.height()) // 2
            painter.drawPixmap(x_offset, y_offset, pixmap)
            painter.end()
            
            self.logo_label.setPixmap(rounded)
        else:
            self.logo_label.setText("LOGO (Asset/logo.png)")
            self.logo_label.setStyleSheet("color: #6366f1; font-weight: bold; font-size: 18px;")
        top_layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignLeft)

        title = QLabel("Quiz-Themen auswählen")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        top_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Buy me a coffee QR
        self.bmc_label = QLabel()
        bmc_path = self.get_asset_path("bmc.png")
        if bmc_path and bmc_path.exists():
            pixmap = QPixmap(str(bmc_path)).scaled(
                100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.bmc_label.setPixmap(pixmap)
            self.bmc_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self.bmc_label.mousePressEvent = lambda event: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/refined"))
        else:
            self.bmc_label.setText("☕ Buy me a Coffee QR\n(Asset/bmc.png)")
            self.bmc_label.setStyleSheet("color: #f59e0b; font-size: 14px;")
            self.bmc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self.bmc_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top_layout)

        self.scroll = QScrollArea()
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)

        self.checkboxes = []
        # Suche nach JSON-Dateien im Verzeichnis des Skripts und in 'data'-Ordnern
        base_path = Path(__file__).parent
        search_dirs = [base_path, base_path / "data", Path("data")]

        processed_files = set()
        for d in search_dirs:
            if d.exists():
                for file in d.glob("*.json"):
                    resolved_path = file.resolve()
                    if resolved_path in processed_files:
                        continue
                    processed_files.add(resolved_path)
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        # Nur Dateien laden, die das Quiz-Format (bereich & fragen) haben
                        if (
                            isinstance(data, dict) and
                            "bereich" in data and
                            "fragen" in data
                        ):
                            cb = QCheckBox(
                                f"{data['bereich']} ({len(data['fragen'])} Fragen)"
                            )
                            cb.setProperty("data", data)
                            cb.setCursor(Qt.CursorShape.PointingHandCursor)
                            self.scroll_layout.addWidget(cb)
                            self.checkboxes.append(cb)
                    except Exception:
                        continue

        self.scroll.setWidget(self.scroll_content)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        # --- NGROK EINSTELLUNGEN ---
        self.ngrok_frame = QFrame()
        self.ngrok_frame.setStyleSheet(
            "background: #1e293b; border-radius: 12px; padding: 15px;"
        )
        ngrok_layout = QVBoxLayout(self.ngrok_frame)

        self.online_mode_cb = QCheckBox("Online Mode (Ngrok Tunnel)")
        self.online_mode_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.online_mode_cb.toggled.connect(self.toggle_ngrok_input)
        ngrok_layout.addWidget(self.online_mode_cb)

        self.ngrok_token_input = QLineEdit()
        self.ngrok_token_input.setPlaceholderText("Ngrok Auth Token eingeben...")
        self.ngrok_token_input.setStyleSheet(
            "padding: 10px; border-radius: 8px; background: #0f172a; border: 1px solid #334155; color: white;"
        )
        self.ngrok_token_input.setEnabled(False)

        self.token_file = (
            Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "ngrok_token.txt"
        )
        if self.token_file.exists():
            try:
                self.ngrok_token_input.setText(self.token_file.read_text().strip())
            except Exception:
                pass
        ngrok_layout.addWidget(self.ngrok_token_input)
        layout.addWidget(self.ngrok_frame)

        btn = QPushButton("Vorbereiten")
        btn.setMinimumHeight(70)
        btn.setStyleSheet("background-color: #10b981; font-size: 20px;")
        btn.clicked.connect(self.prepare_game)
        layout.addWidget(btn)

        version_label = QLabel(f"v{self.current_version}")
        version_label.setStyleSheet("color: #64748b; font-size: 13px; font-weight: bold;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(version_label)

        self.stack.addWidget(page)

    def toggle_ngrok_input(self, checked):
        self.ngrok_token_input.setEnabled(checked)

    def init_lobby_screen(self):
        """Initialisiert den Lobby-Screen mit QR-Code und Spielerliste."""
        self.lobby_page = QWidget()
        layout = QVBoxLayout(self.lobby_page)
        layout.setContentsMargins(40, 40, 40, 40)

        # QR Code Container für Schatten-Effekt
        qr_container = QFrame()
        qr_container.setStyleSheet(
            "background: white; border-radius: 20px; padding: 20px;"
        )
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
        self.start_btn.setEnabled(False)  # Deaktiviert, bis Spieler beitreten
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

        self.timer_display = QLabel("20")
        self.timer_display.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.timer_display.setStyleSheet(
            "color: #f59e0b; background: #1e293b; border-radius: 40px; padding: 10px; min-width: 80px;"
        )
        layout.addWidget(self.timer_display, alignment=Qt.AlignmentFlag.AlignCenter)

        self.q_text = QLabel("Fragentext")
        self.q_text.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.q_text.setWordWrap(True)
        self.q_text.setMinimumHeight(150)
        self.q_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.q_text)

        self.ans_grid = QGridLayout()
        self.ans_grid.setSpacing(20)
        self.ans_labels = []
        colors = [
            "#ef4444",
            "#3b82f6",
            "#f59e0b",
            "#10b981",
        ]  # Modernere Tailwind-Farben
        shapes = ["▲", "◆", "●", "■"]  # Dreieck, Raute, Kreis, Quadrat
        for i in range(4):
            lbl = QLabel()
            lbl.setStyleSheet(
                f"background-color: {colors[i]}; color: white; padding: 30px; border-radius: 15px; font-size: 24px; font-weight: bold;"
            )
            lbl.setText(f"{shapes[i]} Antwort")
            lbl.setWordWrap(True)
            lbl.setMinimumHeight(120)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ans_grid.addWidget(lbl, i // 2, i % 2)  # 2x2 Gitter
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
        self.video_widget.setMinimumHeight(450)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        layout.addWidget(self.video_widget)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.errorOccurred.connect(self.handle_video_error)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)

        self.play_btn = QPushButton("▶ Video abspielen")
        self.play_btn.setMinimumHeight(60)
        self.play_btn.setStyleSheet("background-color: #3b82f6; font-size: 18px;")
        self.play_btn.clicked.connect(self.toggle_playback)
        layout.addWidget(self.play_btn)

        self.res_info = QLabel("Korrekte Antwort: ...")
        self.res_info.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.res_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.res_info.setWordWrap(True)
        layout.addWidget(self.res_info)

        next_btn = QPushButton("Nächste Frage")
        next_btn.setMinimumHeight(50)
        next_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; font-size: 18px;"
        )
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
        new_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; font-size: 18px;"
        )
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

        # NGROK INIT
        if self.online_mode_cb.isChecked():
            token = self.ngrok_token_input.text().strip()
            if not token:
                QMessageBox.warning(
                    self,
                    "Fehler",
                    "Bitte gib ein Ngrok Auth Token ein oder deaktiviere den Online Mode.",
                )
                return
            try:
                try:
                    self.token_file.write_text(token)
                except Exception:
                    pass
                try:
                    ngrok.kill()
                except Exception:
                    pass
                conf.get_default().auth_token = token
                tunnel = ngrok.connect(5000, "http")
                self.public_url = tunnel.public_url
            except Exception as e:
                QMessageBox.warning(
                    self, "Ngrok Fehler", f"Konnte Ngrok nicht starten:\n{str(e)}"
                )
                return
        else:
            self.public_url = f"http://{self.local_ip}:5000"

        self.engine.load_questions(selected)
        self.engine.state = "LOBBY"

        # QR Generieren
        img = qrcode.make(self.public_url)
        buffer = BytesIO()
        img.save(buffer, "PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        self.qr_label.setPixmap(
            pixmap.scaled(
                400,
                400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        self.url_label.setText(self.public_url)
        self.stack.setCurrentIndex(1)  # Wechsel zum Lobby-Screen

    def update_lobby_list(self, players):
        """Aktualisiert die Liste der beigetretenen Spieler im Lobby-Screen."""
        names = [p["name"] for p in players]
        self.player_list_label.setText("Spieler: " + ", ".join(names))
        self.start_btn.setText(f"Spiel starten ({len(players)} Spieler)")
        self.start_btn.setEnabled(len(players) > 0)

    def start_game(self):
        """Startet das Spiel und sendet das 'game_start'-Event an alle Schüler über die Server-Funktion."""
        self.server.broadcast_game_start()
        self.trigger_next_question()

    def trigger_next_question(self):
        """Wechselt zur nächsten Frage oder zu den Endergebnissen."""
        # Schutz vor doppeltem Aufruf (z.B. Video-Ende + manueller Klick + Timer)
        if self.engine.state != "RESOLUTION" and self.engine.state != "LOBBY":
            return

        self.media_player.stop()  # Stoppt das Video, falls es noch läuft
        q = self.engine.next_question()
        if q:
            self.q_progress.setText(
                f"Frage {self.engine.current_question_index + 1} / {len(self.engine.questions)}"
            )
            self.q_text.setText(q["frage"])
            for i, ans in enumerate(q["antworten"]):
                self.ans_labels[i].setText(f"{['▲', '◆', '●', '■'][i]} {ans['text']}")
            self.ans_counter.setText("0 geantwortet")

            # Lesezeit starten (5 Sekunden)
            self.remaining_time = 5
            self.timer_display.setText(str(self.remaining_time))
            self.timer_display.setStyleSheet(
                "color: #6366f1; background: #1e293b; border-radius: 40px; padding: 10px; min-width: 80px;"
            )
            self.question_timer.start(1000)

            self.server.broadcast_question(q)
            self.stack.setCurrentIndex(2)  # Wechsel zum Game-Screen
        else:
            self.show_final_results()

    def update_countdown(self):
        self.remaining_time -= 1
        self.timer_display.setText(str(self.remaining_time))
        if self.remaining_time <= 0:
            if self.engine.is_reading_time:
                # Lesezeit vorbei -> Abstimmung starten
                self.engine.start_voting()
                self.remaining_time = 20
                self.timer_display.setText(str(self.remaining_time))
                self.timer_display.setStyleSheet(
                    "color: #f59e0b; background: #1e293b; border-radius: 40px; padding: 10px; min-width: 80px;"
                )
                self.server.broadcast_start_voting()
            else:
                self.question_timer.stop()
                self.show_resolution()

    def update_answer_count(self, count):
        """Aktualisiert die Anzeige der eingegangenen Antworten."""
        self.ans_counter.setText(f"{count} von {len(self.engine.players)} geantwortet")
        if count >= len(self.engine.players) and self.engine.state == "QUESTION":
            self.question_timer.stop()
            self.show_resolution()

    def show_resolution(self):
        """Zeigt die Auflösung der Frage, spielt das Video ab und markiert die korrekte Antwort."""
        self.question_timer.stop()
        self.engine.state = "RESOLUTION"
        q = self.engine.get_current_question()

        if not q:  # Falls keine Frage geladen ist
            QMessageBox.warning(
                self, "Fehler", "Keine aktuelle Frage zur Auflösung vorhanden."
            )
            return

        correct_answer_text = ""
        for i, ans in enumerate(q["antworten"]):
            if ans["korrekt"]:
                correct_answer_text = ans["text"]
                break

        self.res_info.setText(f"Korrekte Antwort: {correct_answer_text}")

        # Markiere die korrekte Antwort im Game-Screen (optional, da wir zum Resolution-Screen wechseln)
        # for i, label in enumerate(self.ans_labels):
        #     if i == correct_idx:
        #         label.setStyleSheet(label.styleSheet() + "border: 3px solid green;")
        #     else:
        #         label.setStyleSheet(label.styleSheet() + "border: 3px solid red;")

        self.server.broadcast_resolution()
        self.stack.setCurrentIndex(3)  # Wechsel zum Resolution-Screen

        # Video-Pfad ermitteln (berücksichtigt Entwicklung und Build)
        video_filename = q.get("video")

        # Vor dem Laden sicherstellen, dass das Widget im Layout verankert ist
        self.stack.setCurrentIndex(3)
        QApplication.processEvents()

        vid_path = self.get_video_path(video_filename)
        if vid_path and vid_path.exists():
            # Re-binding des VideoOutputs hilft oft, das Rendering-Fenster neu zu initialisieren
            self.media_player.setVideoOutput(self.video_widget)
            self.media_player.setSource(QUrl.fromLocalFile(str(vid_path.absolute())))
            # Lehrer muss explizit auf Play drücken
            self.play_btn.setText("▶ Video abspielen")
            self.play_btn.setEnabled(True)
            self.play_btn.setStyleSheet("background-color: #3b82f6; font-size: 18px;")
        else:
            self.res_info.setText(
                f"{self.res_info.text()}\n⚠️ Video '{video_filename}' nicht gefunden."
            )
            self.play_btn.setEnabled(False)
            self.play_btn.setStyleSheet("background-color: #334155; color: #94a3b8;")

    def get_video_path(self, filename):
        """Sucht nach dem Video in verschiedenen Verzeichnissen (Entwicklung & Build)."""
        if not filename:
            return None
        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

        candidates = [
            base_path / "videos" / "fixed" / filename,
            base_path / "videos" / "compressed" / filename,
            base_path / "videos" / filename,
            Path("videos") / "fixed" / filename,
            Path("videos") / filename,
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def get_asset_path(self, filename):
        """Sucht nach dem Asset im Asset-Ordner."""
        if not filename:
            return None
        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

        candidates = [
            base_path / "Asset" / filename,
            Path("Asset") / filename,
            Path("../Asset") / filename,
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def toggle_playback(self):
        """Wechselt zwischen Wiedergabe und Pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶ Video fortsetzen")
        elif self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()
            self.play_btn.setText("⏸ Video pausieren")
        else:
            self.media_player.play()
            self.play_btn.setText("⏸ Video pausieren")
            # Kleiner UI-Refresh um das Rendering zu forcieren
            self.video_widget.update()

    def handle_media_status(self, status):
        """Reagiert auf Statusänderungen des Videos (z.B. Ende erreicht)."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setText("↺ Video erneut abspielen")
            self.play_btn.setStyleSheet("background-color: #6366f1; font-size: 18px;")

    def handle_video_error(self, error, error_string):
        """Zeigt Fehlermeldungen des Media Players an."""
        self.res_info.setText(
            f"{self.res_info.text()}\n❌ Video-Fehler: {error_string}"
        )
        print(f"Media Error: {error_string} (Code: {error})")

    def show_final_results(self):
        """Zeigt die finale Rangliste an."""
        self.engine.state = "RESULTS"
        self.server.broadcast_results()
        leaderboard = self.engine.get_leaderboard()
        text = ""
        for p in leaderboard[:10]:  # Top 10 Spieler anzeigen
            text += f"{p['rank']}. {p['name']} - {p['points']} Pkt\n"
        self.rank_label.setText(text)
        self.stack.setCurrentIndex(4)  # Wechsel zum Result-Screen

    def reset_everything(self):
        """Setzt das Spiel komplett zurück und kehrt zum Setup-Screen zurück."""
        self.engine.reset()
        self.server.broadcast_game_reset()
        self.ui_bridge.update_players_signal.emit(list(self.engine.players.values()))
        if hasattr(self, "public_url") and "ngrok" in self.public_url:
            try:
                ngrok.kill()
            except Exception:
                pass
        self.stack.setCurrentIndex(0)  # Wechsel zum Setup-Screen

    def closeEvent(self, event):
        """Wird aufgerufen, wenn das Fenster geschlossen wird."""
        try:
            ngrok.kill()
        except Exception:
            pass
        event.accept()
