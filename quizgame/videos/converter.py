import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

input_dir = Path(r"C:\VSC_Projects\Standpunkt 2030\Standpunkt_2030\quizgame\videos\compressed") # Jetzt der compressed-Ordner als Input
output_dir = input_dir.parent / "fixed" # WICHTIG: Anderer Ordner, um Datenverlust zu vermeiden!
output_dir.mkdir(exist_ok=True)

def convert(video):
    output = output_dir / video.name
    cmd = [
        "ffmpeg", "-i", str(video),
        "-c:v", "libx264",         # Stabiler CPU-Encoder
        "-crf", "23",              # Standard Qualität
        "-preset", "medium",
        "-pix_fmt", "yuv420p",     # Wichtig für maximale Kompatibilität
        "-movflags", "faststart",  # Schiebt Metadaten an den Anfang
        "-c:a", "aac",
        "-b:a", "128k",
        "-y", str(output)
    ]
    print(f"Verarbeite: {video.name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FEHLER bei {video.name}: {result.stderr}")
    else:
        print(f"Erfolgreich: {video.name}")

videos = list(input_dir.glob("*.mp4"))
with ThreadPoolExecutor(max_workers=3) as executor:
    executor.map(convert, videos)

print("Alle Videos fertig!")