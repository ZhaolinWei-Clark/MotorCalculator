; MotorCalculator per-user installer. Values are supplied by build_windows_release.ps1.
#ifndef AppVersion
  #error AppVersion must be supplied by the release pipeline
#endif
#ifndef AppId
  #error AppId must be supplied by the release pipeline
#endif
#ifndef AppPublisher
  #error AppPublisher must be supplied by the release pipeline
#endif

#define AppName "MotorCalculator"
#define AppDisplayName "电机设计计算器"
#define AppExeName "MotorCalculator.exe"

[Setup]
AppId={#AppId}
AppName={#AppDisplayName}
AppVerName={#AppDisplayName} {#AppVersion}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppDisplayName} 安装程序
VersionInfoProductName={#AppName}
DefaultDirName={localappdata}\Programs\MotorCalculator
DefaultGroupName={#AppDisplayName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=MotorCalculator-{#AppVersion}-win64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppDisplayName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
UsePreviousAppDir=yes
UsePreviousGroup=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: ".\third_party\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\MotorCalculator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\卸载 {#AppDisplayName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppDisplayName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppDisplayName}"; Flags: nowait postinstall skipifsilent

; User data under %LOCALAPPDATA%\MotorCalculator is deliberately not removed.
; User-created .motorproj files are never owned by the installer.
