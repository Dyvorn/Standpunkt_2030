import PyInstaller.__main__
import shutil
import os
import sys
from pathlib import Path
import time

sys.stdout.reconfigure(encoding="utf-8")


def build():
    base_dir = Path(__file__).parent.resolve()
    os.chdir(base_dir)
    print(f"📁 Arbeitsverzeichnis: {base_dir}")
    print(f"  templates: {(base_dir / 'templates').exists()}")
    print(f"  data:      {(base_dir / 'data').exists()}")
    print(f"  videos:    {(base_dir / 'videos').exists()}")

    # Alte Build-Ordner bereinigen
    print("\n🧹 Bereinige alte Build-Dateien und Ordner...")
    for folder in ["dist", "build"]:
        folder_path = base_dir / folder
        if folder_path.exists():
            shutil.rmtree(folder_path)
            print(f"🗑️ Ordner '{folder}' entfernt.")

    # Alte .spec-Datei entfernen
    spec_file = base_dir / "Standpunkt2030_Quiz.spec"
    if spec_file.exists():
        spec_file.unlink()
        print("🗑️ Alte .spec-Datei entfernt.")

    # Validierung der benötigten Dateien und Ordner
    print("\n🔍 Überprüfe benötigte Dateien und Ordner...")
    for item in ["main.py", "templates", "data", "videos/fixed", "Asset"]:
        if not (base_dir / item).exists():
            print(f"❌ FEHLER: '{item}' wurde nicht gefunden in: {base_dir}")
            return

    PyInstaller.__main__.run(
        [
            "main.py",  # Nur der Dateiname, da wir os.chdir genutzt haben
            "--onedir",
            "--windowed",
            "--name=Standpunkt2030_Quiz",
            "--distpath=dist",  # ZWINGT PyInstaller, dist HIER zu erstellen
            "--workpath=build",  # ZWINGT PyInstaller, build HIER zu erstellen
            "--specpath=.",  # ZWINGT PyInstaller, .spec HIER zu erstellen
            "--add-data=templates;templates",
            "--add-data=data;data",
            "--add-data=videos/fixed;videos/fixed",
            "--add-data=Asset;Asset",
            "--icon=Asset/logo.ico",
            "--exclude-module=cryptography",
            "--hidden-import=engineio.async_drivers.threading",
            "--noconfirm",
            "--clean",
        ]
    )

    # Kurze Pause für Windows
    time.sleep(1)

    # Überprüfen, ob der dist-Ordner nach dem PyInstaller-Lauf erfolgreich erstellt wurde
    final_dist_path = base_dir / "dist" / "Standpunkt2030_Quiz"
    if not (final_dist_path / "Standpunkt2030_Quiz.exe").exists():
        print(f"❌ FEHLER: EXE nicht gefunden in '{final_dist_path}'.")
        return

    print("\n" + "=" * 30)
    print("✅ PyInstaller Build fertig! Öffne jetzt 'installer.iss' in Inno Setup.")


if __name__ == "__main__":
    build()
