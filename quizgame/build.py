import PyInstaller.__main__
import shutil
import os

def build():
    PyInstaller.__main__.run([
        'main.py',
        '--onedir',
        '--windowed',
        '--name=QuizGame',
        '--add-data=templates;templates',
        '--add-data=data;data',
        '--add-data=videos;videos',
    ])
    print("\n" + "="*30)
    print("Build fertig! Öffne installer.iss in Inno Setup.")

if __name__ == "__main__": build()