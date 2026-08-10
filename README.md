# 🐾 Standpunkt 2030 – Das Tierschutz-Quiz!

Willkommen beim **Standpunkt 2030 Quiz**! 🎉  
Hier geht's um interaktiven Spielspaß rund um die Themen Tierschutz, Artenschutz und den richtigen Umgang mit Haustieren & Wildtieren. Egal ob in der Schule, in Jugendgruppen oder bei Events – einfach Beamer an, Handys raus und los geht's! 📱✨

---

## ❤️ Mega Dank & Shoutout!

Ein riesengroßes Dankeschön geht an den **Tierschutz Halle e.V.** für die fantastische Zusammenarbeit!  
Ohne eure Unterstützung, euer Fachwissen und die Erklärvideos die wir drehen durften wäre dieses Quiz nur halb so gut geworden. Danke, dass ihr euch jeden Tag für die Tiere einsetzt! 🐶🐱🦔

---

## 🎯 Worum geht's eigentlich?

Ganz kurz erklärt: Es ist wie Kahoot, nur vollgepackt mit wichtigen Tierschutz-Themen! 

Der Spielleiter (Lehrer, Gruppenleiter oder du 😉) startet die App auf dem Laptop/PC und wirft das Spiel an die Wand oder den Bildschirm. Alle Mitspieler scannen einfach mit ihrem Handy den QR-Code ein und sind sofort im Browser dabei – ohne irgendwelche App-Downloads oder nervige Registrierungen!

---

## 🚀 Wie läuft das Ganze ab?

### 1. 📱 Einfach einwählen
Scanne den QR-Code auf dem Bildschirm oder tippe die kurze Web-Adresse in deinen Browser ein. Such dir einen Künstlernamen aus und schon stehst du in der Lobby!

### 2. ❓ Fragen beantworten & Punkte abstauben
Sobald die Frage freigeschaltet wird, zählt jede Sekunde!
* **Schnelligkeit lohnt sich**: Wer richtig antwortet und schnell tippt, kassiert bis zu 1.000 Punkte! ⚡
* **Lesepause**: Damit alle faire Chancen haben, gibt es vor der Abstimmung immer eine kurze Vorlese- & Bedenkzeit.

### 3. 🎬 Auflösung mit Erklär-Videos
Nach jeder Frage löst der Spielleiter auf – inklusive eines kurzen, anschaulichen Videos zum Thema (z. B. richtige Fütterung von Katzen, Igel-Schutz im Garten oder Kaninchen-Haltung).

### 4. 🏆 Wer holt den Sieg?
Am Ende zeigt die **Top 10 Rangliste**, wer das meiste Wissen am Start hatte!

---

## 🌐 Zwei Wege zum Mitspielen

Die Host-App bietet zwei einfache Möglichkeiten, damit sich alle verbinden können:

* **Lokales WLAN (Klassenzimmer/Raum)**: Wenn alle im selben WLAN sind, läuft die Verbindung direkt und super schnell über die lokale IP.
* **Online-Modus (Ngrok)**: Mit nur einem Klick erstellt die App einen Online-Link. Perfekt, wenn das Schul-WLAN mal zickt oder Leute von unterwegs mitspielen!

---

## 💻 Installation & Start (für den Spielleiter)

### 📦 Fertige App installieren (Windows)
1. Lade dir einfach die neueste `Standpunkt2030_Setup.exe` hier bei den [GitHub Releases](https://github.com/Dyvorn/Standpunkt_2030/releases) runter.
2. Doppelklick auf die `.exe`, installieren und direkt starten!

> 💡 **Cooles Feature**: Die App prüft beim Start automatisch, ob es eine neue Version gibt. Du musst dich um Updates also gar nicht kümmern!

---

## 🛡️ Hinweis zu Windows-Warnungen ("Unbekannter Herausgeber")

Windows meckert beim Starten (`Der Computer wurde durch Windows geschützt`)? Keine Sorge! 🛑

* **Warum passiert das?**  
  Damit Windows eine App ohne Meckern starten lässt, benötigt man ein kommerzielles Code-Signing-Zertifikat (das mehrere hundert Euro pro Jahr kostet). Da dies ein kostenloses, gemeinnütziges Schul- & Bildungsprojekt ist, ist die Datei nicht signiert.
* **Kein Virus drin? 😇**  
  Das gesamte Projekt ist zu **100 % Open Source**. Der komplette Quellcode liegt genau hier auf GitHub offen – jeder kann jede Zeile Code einsehen!
* **So startest du es trotzdem**:
  1. Klicke im blauen Windows-Fenster auf **"Weitere Informationen"** (*More info*).
  2. Klicke unten auf **"Trotzdem ausführen"** (*Run anyway*).
  3. Schon geht's los! 🎉

---

## 🛠️ Für Tech-Interessierte & Entwickler

Falls du am Code schrauben willst oder wissen möchtest, wie die Zahnräder ineinandergreifen – hier ist der tiefere Blick unter die Haube:

### 🏗️ 1. Multi-Threaded Architektur (`PyQt6` + `Flask`)
* **Haupt-Thread (GUI)**: Das Lehrer-Fenster (`host_window.py`) läuft auf **PyQt6**. Es kümmert sich um die Benutzeroberfläche, das Rendern des QR-Codes (`qrcode` + `Pillow`) und spielt die 480p-Erklärvideos über `PyQt6.QtMultimedia` (`QMediaPlayer` & `QVideoWidget`) ab.
* **Hintergrund-Thread (Flask Server)**: Der Flask-Webserver (`server.py`) läuft in einem eigenen Daemon-Thread (`threading.Thread`). Dadurch bleibt die GUI immer 100 % flüssig und friert bei Netzwerk-Anfragen niemals ein.
* **Thread-Sichere Brücke (`UiBridge`)**: Da Flask und PyQt6 in verschiedenen Threads laufen, kommunizieren sie über PyQt-Signale (`pyqtSignal`), um Spielerlisten und eingehende Antworten thread-sicher in die GUI zu spiegeln.

---

### ⚡ 2. Echtzeit-WebSockets & Spiel-Engine
* **Event-Driven Kommunication**: Der Server nutzt **Flask-SocketIO**, um Nachrichten per WebSocket in Echtzeit an alle Handys zu senden (`join_game`, `new_question`, `start_voting`, `resolution`, `final_results`).
* **Game Engine (`game_engine.py`)**: Verwaltet den aktuellen Zustand (`SETUP`, `LOBBY`, `QUESTION`, `RESOLUTION`, `RESULTS`), verhindert Mehrfach-Antworten und regelt die Vorlese-Sperre (`is_reading_time`).
* **Dynamischer Punkte-Algorithmus**:
  $$\text{Punkte} = \max(500, 1000 - (\text{Verstrichene Sekunden} \times 25))$$
  Wer sofort richtig antwortet, erhält die vollen 1.000 Punkte. Je länger man braucht, desto weniger Punkte gibt es (bis zum Minimum von 500 Punkten).

---

### 🌐 3. Automatisches Netzwerk-Routing & Tunneling
* **Lokale IP-Ermittlung**: Die App baut beim Start eine kurze UDP-Verbindung auf, um das aktive Netzwerk-Interface abzufragen und die echte lokale IP (z. B. `192.168.x.x`) für das WLAN-Spiel herauszufinden.
* **Ngrok Reverse-Proxy (`pyngrok`)**: Bei Auswahl des Online-Modus wird automatisch ein verschlüsselter HTTPS-Tunnel (`ngrok.connect(5000)`) gestartet.
* **Prozess-Lifecycle**: Damit keine ngrok-Zombies im Hintergrund hängen bleiben, beendet die App beim Programmende oder beim Zurücksetzen des Spiels alte Tunnels sauber via `ngrok.kill()`.

---

### 🔄 4. Hintergrund-Updater (`updater.py`)
* Ein eigener `QThread` (`UpdateChecker`) prüft beim Start asynchron die GitHub REST-API (`/repos/Dyvorn/Standpunkt_2030/releases/latest`).
* Vergleicht die Semantic-Versioning-Versionsnummern (`v1.0.1` vs. Release-Tag).
* Liegt ein Update vor, lädt der `UpdateDownloader`-Thread die neue `Standpunkt2030_Setup.exe` mit Fortschrittsbalken (`QProgressDialog`) herunter, startet den Installer per `os.startfile` und beendet die alte App sauber.

---

### 📦 5. Build- & Deployment-Pipeline
* **`build.py`**: Paketiert das gesamte Projekt mit **PyInstaller** (`--windowed`, `--onedir`) inklusive aller Templates, JSON-Fragenkataloge und kompilierten MP4-Videos in den Ordner `dist/Standpunkt2030_Quiz`.
* **Inno Setup (`installer.iss`)**: Kompiliert das PyInstaller-Bundle zu einer einzigen Windows-Installationsdatei (`Standpunkt2030_Setup.exe`).

---

Made with ❤️ for Animals. Viel Spaß beim Quizen! 🐾
