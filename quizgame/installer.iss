[Setup]
AppName=QuizGame
AppVersion=1.0
DefaultDirName={pf}\QuizGame
DefaultGroupName=QuizGame
OutputDir=installer_output
OutputBaseFilename=QuizGame_Setup
Compression=lzma
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Hier wird das Ergebnis von PyInstaller erwartet
Source: "dist\QuizGame\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QuizGame"; Filename: "{app}\QuizGame.exe"
Name: "{commondesktop}\QuizGame"; Filename: "{app}\QuizGame.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QuizGame.exe"; Description: "{cm:LaunchProgram,QuizGame}"; Flags: nowait postinstall skipifsilent

[Code]
// Optional: Prüfung auf Admin-Rechte oder Python (nicht nötig bei onedir)
```

