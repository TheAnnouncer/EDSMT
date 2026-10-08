; The EDSMT installer. This is the download link on radioraxxla.com/EDSMT.
;
; People click a link and expect Setup. They get one: a normal wizard, a
; Start Menu entry, a desktop shortcut, and a proper line in Add/Remove
; Programs. No admin prompt, because it installs for the current user.
;
; It packages the FOLDER build (dist\EDSMT\), not the portable single file,
; so it starts instantly rather than unpacking itself on every launch.
;
; Compile with:  iscc build\installer.iss

#define AppName    "EDSMT"
#define AppLong    "EDSMT - Surface Mining Survey"
#define AppVersion "1.10034"
#define ExeName    "EDSMT.exe"

[Setup]
; Keep this GUID forever. Change it and Windows treats the next build as a
; separate product and leaves the old one installed alongside.
AppId={{B4E7A1C9-3D62-4F08-9A15-7C2E5B8D4610}
AppName={#AppLong}
AppVersion={#AppVersion}
AppVerName={#AppLong} {#AppVersion}
AppPublisher=Radio Raxxla
AppCopyright=Copyright (C) 2026 Radio Raxxla. GPL-3.0-only
AppPublisherURL=https://www.radioraxxla.com/EDSMT
VersionInfoVersion=1.10034.0.0

; Per-user by default: no admin prompt, which is one fewer thing to explain
; and one fewer reason for somebody to give up on the download.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Every Radio Raxxla tool lives under C:\EDTools\RadioRaxxla\<tool>, and in
; one Start menu folder, Radio Raxxla (1.10034, #167). Windows lets an
; ordinary user make a folder at the top of the system drive, so this needs
; no admin prompt either.
DefaultDirName={sd}\EDTools\RadioRaxxla\EDSMT
DefaultGroupName=Radio Raxxla
DisableProgramGroupPage=yes
; Not the previous folder or group: an EDSMT installed before 1.10034 is
; MOVED here - the new copy goes in, then [Code] below takes out only the
; files the old Setup put in the old folder, and its old Start menu entries.
UsePreviousAppDir=no
UsePreviousGroup=no
; UPGRADES. Same AppId, so Windows replaces the installed copy rather
; than putting a second one beside it. CloseApplications lets the Restart Manager
; shut EDSMT first: PyInstaller folder builds hold their DLLs open, and
; installing over a running copy is how you get a half-updated one.
CloseApplications=yes
RestartApplications=no
SetupMutex=EDSMTSetupMutex
; The app holds this mutex while it runs (INSTANCE_NAME in edsmt.py). With
; it named here, Setup sees a running copy before it touches anything and
; asks for it to be closed - so the app closes itself, saving on the way out,
; instead of being shut from outside part way through writing its settings.
; That is how an update once lost a commander's entire settings file.
AppMutex=RadioRaxxla.EDSMT.Running
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=..\upload
OutputBaseFilename=EDSMT-Setup
SetupIconFile=..\radioraxxla.ico
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppLong}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Clear the previous build's runtime before laying down the new one.
; ignoreversion overwrites what it recognises, but a file that existed in
; the old version and not the new one would simply stay - and a stale .pyd
; or .dll left in _internal gets loaded in preference to nothing at all,
; which produces a crash that makes no sense against the current source.
; %LOCALAPPDATA%\RadioRaxxla\EDSMT is not touched: finds are not ours to
; delete.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\JOURNAL-NOTES.md"

[Files]
; recursesubdirs matters: the folder build puts customtkinter's themes and
; the Tcl/Tk runtime in _internal\, and the app will not start without them.
Source: "..\dist\EDSMT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
; README and the licence only. Developer notes and build documents are
; source-zip material; nothing on a commander's PC describes how this was
; built or where anything runs.
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\EDSMT"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall EDSMT"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EDSMT"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch EDSMT"; Flags: nowait postinstall skipifsilent
; An update from inside the app runs this Setup with /SILENT once EDSMT has
; closed itself. There is no Finish page to tick then, so EDSMT is opened
; again here - the commander pressed INSTALL UPDATE and gets EDSMT back.
; runasoriginaluser: without it an entry that is not "postinstall" runs with
; Setup's own rights, so an all-users install would reopen EDSMT elevated -
; and an elevated window cannot be clicked through to, or dragged onto, by
; a game running as the normal user.
Filename: "{app}\{#ExeName}"; Flags: nowait skipifnotsilent runasoriginaluser

; Finds live in %LOCALAPPDATA%\RadioRaxxla\EDSMT and are deliberately left
; alone on uninstall. Nobody should lose a mapped system because they
; reinstalled.

[Code]
// 1.10034 (#167): an EDSMT installed before this, in its old folder, is
// moved to C:\EDTools\RadioRaxxla\EDSMT. The new copy is installed first;
// only then are the files the OLD Setup put in the old folder removed, one
// by name - never the folder's other contents, never the finds and settings
// in %LOCALAPPDATA%\RadioRaxxla\EDSMT - and the old folder itself only if
// that left it empty. The old Start menu entries go the same way.
var
  OldDir: String;

function PreviousInstallDir(): String;
var
  Key, Dir: String;
begin
  Result := '';
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B4E7A1C9-3D62-4F08-9A15-7C2E5B8D4610}_is1';
  if RegQueryStringValue(HKCU, Key, 'Inno Setup: App Path', Dir) then
    Result := Dir
  else if IsWin64 and RegQueryStringValue(HKLM64, Key, 'Inno Setup: App Path', Dir) then
    Result := Dir
  else if RegQueryStringValue(HKLM32, Key, 'Inno Setup: App Path', Dir) then
    Result := Dir;
end;

function InitializeSetup(): Boolean;
begin
  OldDir := PreviousInstallDir();
  Result := True;
end;

procedure RemoveOldShortcuts(Folder: String);
begin
  DeleteFile(AddBackslash(Folder) + 'EDSMT.lnk');
  DeleteFile(AddBackslash(Folder) + 'Uninstall EDSMT.lnk');
  RemoveDir(Folder);
end;

procedure RemoveOldCopy(Dir: String);
var
  Base: String;
begin
  Base := AddBackslash(Dir);
  DeleteFile(Base + '{#ExeName}');
  DelTree(Base + '_internal', True, True, True);
  DeleteFile(Base + 'README.md');
  DeleteFile(Base + 'LICENSE');
  DeleteFile(Base + 'JOURNAL-NOTES.md');
  DeleteFile(Base + 'unins000.exe');
  DeleteFile(Base + 'unins000.dat');
  // Only if nothing else is in it.
  RemoveDir(Dir);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (OldDir <> '') and
     (CompareText(RemoveBackslashUnlessRoot(OldDir),
                  RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0) then
  begin
    RemoveOldCopy(OldDir);
    RemoveOldShortcuts(ExpandConstant('{userprograms}\EDSMT'));
    if IsAdminInstallMode then
      RemoveOldShortcuts(ExpandConstant('{commonprograms}\EDSMT'));
  end;
end;

