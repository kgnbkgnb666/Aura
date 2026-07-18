; Aura - AI Voice Assistant Installer Script
Unicode true
!define PRODUCT_NAME "Aura"
!define PRODUCT_VERSION "0.1.0"
!define PRODUCT_PUBLISHER "Aura Team"
!define PRODUCT_WEB_SITE "https://github.com/kgnbkgnb666/Aura"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\Aura.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define INSTALL_DIR "$LOCALAPPDATA\Programs\${PRODUCT_NAME}"

SetCompressor /SOLID lzma
SetCompressorDictSize 64

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\Aura_Setup_${PRODUCT_VERSION}.exe"
InstallDir "${INSTALL_DIR}"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show

; Modern UI
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "src-tauri\icons\icon.ico"
!define MUI_UNICON "src-tauri\icons\icon.ico"

; Pages (must come before MUI_LANGUAGE)
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language (must come after pages)
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; Installer Section
Section "Install"
  SetOutPath "$INSTDIR"

  ; Main application
  File "src-tauri\target\release\aura.exe"
  File "src-tauri\target\release\aura-sidecar.exe"

  ; Modes directory
  SetOutPath "$INSTDIR\modes"
  File "modes\*.yaml"
  SetOutPath "$INSTDIR"

  ; Create Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Aura.lnk" "$INSTDIR\aura.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall Aura.lnk" "$INSTDIR\Uninstall.exe"

  ; Create Desktop shortcut
  CreateShortCut "$DESKTOP\Aura.lnk" "$INSTDIR\aura.exe"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Register Add/Remove Programs
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\aura.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "EstimatedSize" 0x00050000
SectionEnd

; Uninstaller Section
Section "Uninstall"
  Delete "$INSTDIR\modes\*.yaml"
  RMDir "$INSTDIR\modes"
  Delete "$INSTDIR\aura.exe"
  Delete "$INSTDIR\aura-sidecar.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Aura.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall Aura.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\Aura.lnk"

  DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"

  ; Prompt user to delete user data (config, history, API keys)
  MessageBox MB_YESNO|MB_ICONQUESTION "是否同时删除用户数据（配置、历史记录、API密钥）？$\n$\n数据位置: %APPDATA%\Aura\$\n$\n如果您计划重新安装，选择【否】可保留配置。" IDNO skip_userdata
    RMDir /r "$APPDATA\Aura"
    MessageBox MB_OK|MB_ICONINFORMATION "用户数据已删除。"
  skip_userdata:

  SetAutoClose true
SectionEnd
