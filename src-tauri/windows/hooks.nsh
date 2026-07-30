; MarkFlow 安装器 NSIS 钩子
; 在安装完成后询问用户是否安装 Pandoc 转换引擎

!macro NSIS_HOOK_POSTINSTALL
  ; 搜索 Pandoc MSI 安装包
  ; Tauri 2 将资源文件存放在 _up_ 目录下（保留原相对路径结构）
  StrCpy $R0 ""

  ; data/pandoc-*.msi（tauri.conf.json 显式映射的资源路径）
  FindFirst $0 $R1 "$INSTDIR\data\pandoc*.msi"
  ${If} $R1 != ""
    StrCpy $R0 "$INSTDIR\data\$R1"
  ${EndIf}
  FindClose $0

  ; _up_/data/pandoc-*.msi（Tauri 2 标准路径）
  ${If} $R0 == ""
    FindFirst $0 $R1 "$INSTDIR\_up_\data\pandoc*.msi"
    ${If} $R1 != ""
      StrCpy $R0 "$INSTDIR\_up_\data\$R1"
    ${EndIf}
    FindClose $0
  ${EndIf}

  ; 如果没找到，再试 resources/ 目录（旧版 Tauri 路径兼容）
  ${If} $R0 == ""
    FindFirst $0 $R1 "$INSTDIR\resources\pandoc*.msi"
    ${If} $R1 != ""
      StrCpy $R0 "$INSTDIR\resources\$R1"
    ${EndIf}
    FindClose $0
  ${EndIf}

  ${If} $R0 == ""
    FindFirst $0 $R1 "$INSTDIR\resources\data\pandoc*.msi"
    ${If} $R1 != ""
      StrCpy $R0 "$INSTDIR\resources\data\$R1"
    ${EndIf}
    FindClose $0
  ${EndIf}

  StrCmp $R0 "" no_msi

  ; 询问用户
  MessageBox MB_YESNO|MB_ICONQUESTION \
    "Pandoc 转换引擎未安装。$\r$\n$\r$\nPandoc 是文档格式转换核心引擎，支持将 Markdown 转换为 $\r$\nDOCX、PDF、HTML、LaTeX、EPUB 等多种格式。$\r$\n$\r$\n是否立即安装 Pandoc（将弹出标准的 MSI 安装向导）？" \
    IDYES install_pandoc \
    IDNO pandoc_done

install_pandoc:
  DetailPrint "正在启动 Pandoc 安装向导..."
  ExecWait 'msiexec /i "$R0"'
  Goto pandoc_done

no_msi:
  DetailPrint "未找到 Pandoc 安装包，用户可在启动应用后通过设置面板安装"

pandoc_done:
!macroend
