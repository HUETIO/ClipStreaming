#define AppName "Clipstream"
#define AppVersion "1.0.0"

[Setup]
AppId={{B975C4F1-11F3-4AB0-8370-6A673E5AD55B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DASH.IO
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist\installer
OutputBaseFilename=Clipstream-Setup
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\Clipstream.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\portable\Clipstream.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Clipstream.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Clipstream.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Clipstream.exe"; Description: "Iniciar {#AppName}"; Flags: nowait postinstall skipifsilent
