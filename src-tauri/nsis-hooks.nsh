; Tauri invokes this macro before it starts copying files into $INSTDIR.
; Aura normally keeps its window alive in the tray, so an upgrade can otherwise
; fail while Windows still has aura.exe or aura-sidecar.exe open.
!macro NSIS_HOOK_PREINSTALL
  DetailPrint "正在关闭旧版 Aura…"
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM aura.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM aura-sidecar.exe'
  Sleep 800
!macroend
