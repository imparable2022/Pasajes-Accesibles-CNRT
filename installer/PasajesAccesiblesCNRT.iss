#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BuildRoot
  #define BuildRoot "..\\dist\\Pasajes Accesibles CNRT"
#endif
#ifndef BrowserRoot
  #define BrowserRoot "..\\build\\ms-playwright"
#endif

[Setup]
AppId={{A24D652E-1A8E-4B5F-AB75-990EC3C00E21}
AppName=Pasajes Accesibles CNRT
AppVersion={#AppVersion}
AppVerName=Pasajes Accesibles CNRT {#AppVersion}
AppPublisher=Martín Ortiz
AppPublisherURL=https://github.com/
AppSupportURL=https://github.com/
DefaultDirName={localappdata}\Programs\Pasajes Accesibles CNRT
DefaultGroupName=Pasajes Accesibles CNRT
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=..\release
OutputBaseFilename=Pasajes_Accesibles_CNRT_Setup
UninstallDisplayIcon={app}\Pasajes Accesibles CNRT.exe
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BrowserRoot}\*"; DestDir: "{app}\ms-playwright"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Pasajes Accesibles CNRT"; Filename: "{app}\Pasajes Accesibles CNRT.exe"
Name: "{autodesktop}\Pasajes Accesibles CNRT"; Filename: "{app}\Pasajes Accesibles CNRT.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Run]
Filename: "{app}\Pasajes Accesibles CNRT.exe"; Description: "Abrir Pasajes Accesibles CNRT"; Flags: nowait postinstall skipifsilent
