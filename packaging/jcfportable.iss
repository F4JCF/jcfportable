; Installateur Windows de JCF Portable (Inno Setup 6)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1F2A57-6E1B-4C8E-9F4E-4A4F4A43F001}
AppName=JCF Portable
AppVersion={#AppVersion}
AppPublisher=F4JCF
AppPublisherURL=https://github.com/F4JCF/jcfportable
DefaultDirName={autopf}\JCF Portable
DefaultGroupName=JCF Portable
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=JCFPortable-{#AppVersion}-windows-installation
SetupIconFile=jcfportable.ico
UninstallDisplayIcon={app}\jcfportable.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JCF Portable"; Filename: "{app}\jcfportable.exe"
Name: "{autodesktop}\JCF Portable"; Filename: "{app}\jcfportable.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\jcfportable.exe"; Description: "Lancer JCF Portable"; Flags: nowait postinstall skipifsilent
