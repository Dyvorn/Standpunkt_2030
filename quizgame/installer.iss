[Setup]
AppId={{C6E2E1A4-8D5C-4F9E-9E7D-5A2C8B3D4E5F}}
AppName=Standpunkt 2030 Quiz
AppVersion=1.0
DefaultDirName={localappdata}\Standpunkt2030Quiz
DefaultGroupName=Standpunkt 2030 Quiz
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=Standpunkt2030_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourcePath}\dist\Standpunkt2030_Quiz\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Standpunkt 2030 Quiz"; Filename: "{app}\Standpunkt2030_Quiz.exe"
Name: "{autodesktop}\Standpunkt 2030 Quiz"; Filename: "{app}\Standpunkt2030_Quiz.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Standpunkt2030_Quiz.exe"; Description: "{cm:LaunchProgram,Standpunkt 2030 Quiz}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"