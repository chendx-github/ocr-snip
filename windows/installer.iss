; ==========================================================================
;  ocrsnip 安装包脚本（Inno Setup 6）
;  先用 windows\build.bat 生成 windows\dist\ocrsnip\，再编译本文件。
; ==========================================================================

#define AppName "ocrsnip"
#define AppVersion "0.3.0"
#define AppPublisher "chendx"
#define AppExe "ocrsnip.exe"

[Setup]
AppId={{8E4F2C71-9A3B-4D6E-9C1F-OCRSNIP00001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename={#AppName}-{#AppVersion}-setup
OutputDir=Output
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog commandline
; 首次启动要解压 PySide6/onnxruntime 的 dll，给足时间
SetupIconFile=ocrsnip.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
; Inno Setup 6 官方只带 Default.isl；简体中文 .isl 属于非官方翻译包，
; 装了才有中文向导。这里始终保证 English 可用，自定义文案本身是中文。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "autostart"; Description: "开机登录后自动启动（推荐）"; GroupDescription: "附加任务:"

[Files]
; onedir 产物整目录拷入
Source: "dist\ocrsnip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; 自启动：写当前用户的 Run 键，不需要管理员权限
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "ocrsnip"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}（托盘常驻，热键 Ctrl+Alt+Q）"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 配置与日志保留（用户可能还想留着），仅清理程序留下的运行期文件
Type: filesandordirs; Name: "{localappdata}\ocrsnip\run"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // 卸载时兜底清掉 Run 键（万一安装时选了 autostart 后又改了）
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ocrsnip');
  end;
end;
