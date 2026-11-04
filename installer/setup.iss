#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\verified\DeadlockRelay"
#endif

[Setup]
AppId={{D61C4DF8-C89B-4D13-89C4-9F5EC7C63963}
AppName=Deadlock Relay
AppVersion={#AppVersion}
AppPublisher=ноль
AppPublisherURL=https://www.youtube.com/@zero-r2x1
DefaultDirName={localappdata}\Programs\DeadlockRelay
DefaultGroupName=Deadlock Relay
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.14393
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\DeadlockRelay.exe
OutputDir=..\dist
OutputBaseFilename=DeadlockRelay-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=install-notes.txt
VersionInfoDescription=Deadlock Relay Setup

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Deadlock Relay"; Filename: "{app}\DeadlockRelay.exe"
Name: "{autodesktop}\Deadlock Relay"; Filename: "{app}\DeadlockRelay.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DeadlockRelay.exe"; Description: "Запустить Deadlock Relay"; Flags: nowait postinstall skipifsilent
