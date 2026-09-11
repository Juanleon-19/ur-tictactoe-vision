; Compile after scripts/build_release.ps1 has produced the complete onedir.
#define AppVersion "1.0.0"
#define ProductDir "..\dist\RobotTriqui"

[Setup]
AppId={{D8409D22-AAC5-44D9-8CF9-4E128D0F2928}
AppName=Robot Triqui
AppVersion={#AppVersion}
AppPublisher=Juan Esteban León Saiz
DefaultDirName={localappdata}\Programs\Robot Triqui
DefaultGroupName=Robot Triqui
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
WizardStyle=modern
OutputDir=output
OutputBaseFilename=RobotTriqui_Setup
SetupIconFile=..\build\assets\RobotTriqui.ico
UninstallDisplayIcon={app}\RobotTriqui.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
VersionInfoDescription=Robot Triqui
VersionInfoCompany=Juan Esteban León Saiz

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; Flags: unchecked

[Files]
Source: "{#ProductDir}\*"; DestDir: "{app}"; Excludes: "config\app.yaml,config\vision.yaml"; Flags: ignoreversion recursesubdirs createallsubdirs
; Preserve an operator's existing configuration when updating an installation.
Source: "{#ProductDir}\config\app.yaml"; DestDir: "{app}\config"; Flags: onlyifdoesntexist
Source: "{#ProductDir}\config\vision.yaml"; DestDir: "{app}\config"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\Robot Triqui"; Filename: "{app}\RobotTriqui.exe"; WorkingDir: "{app}"; IconFilename: "{app}\RobotTriqui.exe"
Name: "{autodesktop}\Robot Triqui"; Filename: "{app}\RobotTriqui.exe"; WorkingDir: "{app}"; IconFilename: "{app}\RobotTriqui.exe"; Tasks: desktopicon

; No [Run] or [UninstallRun]: installation/removal never starts the robot app.
