; LazyTool Inno Setup Installer Script
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define MyAppName "LazyTool"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Musaib Bin Bashir"
#define MyAppExeName "lazytool.exe"

[Setup]
AppId={{B7F3A2E1-4D5C-6E7F-8A9B-0C1D2E3F4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=LazyTool-Setup
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[UninstallDelete]
; Remove all files inside the user data directory
Type: files; Name: "{%USERPROFILE}\.lazytool\*"
Type: dirifempty; Name: "{%USERPROFILE}\.lazytool"
; Remove any leftover files in the install directory
Type: files; Name: "{app}\*"
Type: dirifempty; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  AppDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Remove user data directory
    DataDir := ExpandConstant('{%USERPROFILE}\.lazytool');
    if DirExists(DataDir) then
      DelTree(DataDir, True, True, True);

    // Remove install directory if still present
    AppDir := ExpandConstant('{app}');
    if DirExists(AppDir) then
      DelTree(AppDir, True, True, True);
  end;
end;
