; Inno Setup script for AI Document Assistant
; Builds a Windows installer (Setup.exe) that:
;   - Installs AI_Document_Assistant.exe into Program Files
;   - Creates Start Menu + optional Desktop shortcuts
;   - Automatically registers an uninstaller in "Add or Remove Programs"
;     (Inno Setup generates unins000.exe next to the installed app)
;
; Requires: Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Requires that dist\AI_Document_Assistant.exe already exists
; (built beforehand via PyInstaller, see .github/workflows/build-windows.yml)
;
; Build locally:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\windows\setup.iss

#define MyAppName "AI Document Assistant"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "AI Document Assistant"
#define MyAppExeName "AI_Document_Assistant.exe"

[Setup]
AppId={{B6C1B7B0-6E6A-4B7C-9C1B-AAAA11112222}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist_installer
OutputBaseFilename=AI_Document_Assistant_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Show an uninstall entry with icon/name in Add or Remove Programs
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\AI_Document_Assistant"
