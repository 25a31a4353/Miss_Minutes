; packaging/installer/MissMinutes_setup.iss
; Inno Setup Script for Miss Minutes Desktop AI Assistant
; Target: Windows 10/11 (64-bit)

#define MyAppName "Miss Minutes"
#define MyAppVersion "2.5.0"
#define MyAppPublisher "Miss Minutes & Jarvis Team"
#define MyAppExeName "MissMinutes.exe"
#define MyAppIcon "..\MissMinutes.ico"

[Setup]
AppId={{C78921B5-3F42-4D3B-98A1-7E8E4233F901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\MissMinutes
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist\installer
OutputBaseFilename=MissMinutes_Setup
SetupIconFile={#MyAppIcon}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\MissMinutes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\packaging\MissMinutes.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\packaging\MissMinutes.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
