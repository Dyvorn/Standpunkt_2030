import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Nutze relative Pfade basierend auf dem Skript-Ort
base_dir = Path(__file__).parent
input_dir = base_dir / "compressed"
output_dir = base_dir / "fixed"
output_dir.mkdir(exist_ok=True)

def convert(video):
    output = output_dir / video.name
    cmd = [
        "ffmpeg", "-i", str(video),
        "-c:v", "libx264",         # Stabiler CPU-Encoder
        "-crf", "20",              # Gute Qualität
        "-preset", "medium",
        "-pix_fmt", "yuv420p",     # Wichtig für maximale Kompatibilität
        "-movflags", "faststart",  # Schiebt Metadaten an den Anfang
        "-profile:v", "high",      # Kompatibilitätsprofil
        "-level", "4.1",
        "-c:a", "aac",             # Audio-Codec
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