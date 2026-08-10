use tauri::Manager;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

mod backend;

fn output_directory() -> Result<std::path::PathBuf, String> {
    Ok(backend::data_directory()?.join("artifacts"))
}

#[tauri::command]
fn open_output_directory() -> Result<(), String> {
    let directory = output_directory()?;
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;

    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = std::process::Command::new("explorer.exe");
        command.arg(&directory);
        command
    };
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = std::process::Command::new("open");
        command.arg(&directory);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = std::process::Command::new("xdg-open");
        command.arg(&directory);
        command
    };

    command.spawn().map_err(|error| error.to_string())?;
    Ok(())
}

#[tauri::command]
fn list_system_fonts() -> Result<Vec<String>, String> {
    #[cfg(target_os = "windows")]
    {
        let script = r#"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$paths = @(
  'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',
  'Registry::HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
)
$faces = foreach ($path in $paths) {
  if (Test-Path $path) { (Get-Item $path).GetValueNames() }
}
$faces |
  ForEach-Object {
    $_ -replace '\s+\((TrueType|OpenType)\)$', '' `
       -replace '\s+(Regular|Roman|Bold Italic|Bold Oblique|SemiBold Italic|SemiBold|Semibold|DemiBold|Medium Italic|Medium|Light Italic|Light|ExtraLight|Thin|Bold|Italic|Oblique)$', ''
  } |
  Where-Object { $_ -and $_.Trim() } |
  ForEach-Object { $_.Trim() } |
  Sort-Object -Unique
"#;
        // 必须使用 CREATE_NO_WINDOW，否则 GUI 程序 spawn console 子进程时会弹出黑框
        let mut command = std::process::Command::new("powershell.exe");
        command.args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]);
        #[cfg(target_os = "windows")]
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        let output = command
            .output()
            .map_err(|error| error.to_string())?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        return Ok(String::from_utf8_lossy(&output.stdout)
            .lines()
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .map(str::to_owned)
            .collect());
    }

    #[cfg(not(target_os = "windows"))]
    Ok(Vec::new())
}

#[tauri::command]
async fn open_temp_file(file_name: String, bytes: Vec<u8>) -> Result<(), String> {
    let safe_name = std::path::Path::new(&file_name)
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("document");
    let preview_id = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_millis();
    let directory = std::env::temp_dir()
        .join("markflow")
        .join("history-preview")
        .join(preview_id.to_string());
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    let path = directory.join(safe_name);
    std::fs::write(&path, bytes).map_err(|error| error.to_string())?;

    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = std::process::Command::new("explorer.exe");
        command.arg(&path);
        command
    };
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = std::process::Command::new("open");
        command.arg(&path);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = std::process::Command::new("xdg-open");
        command.arg(&path);
        command
    };

    command.spawn().map_err(|error| error.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // 同步启动后端进程（立即注册 handle，防止关闭窗口时遗漏清理）
            let backend_url = backend::spawn_backend(&handle);

            // 异步等待后端就绪
            tauri::async_runtime::spawn(async move {
                backend::wait_backend_ready(&backend_url).await;
            });

            // 窗口关闭时：轻量清理，不阻塞 GUI 线程
            // 完整的端口清扫延迟到 ExitRequested 中执行
            if let Some(win) = app.get_webview_window("main") {
                win.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { .. } = event {
                        eprintln!("[MarkFlow] window close requested, fast cleanup");
                        backend::cleanup_managed_process();
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend::get_backend_url,
            backend::is_backend_ready,
            open_output_directory,
            open_temp_file,
            list_system_fonts,
        ])
        .build(tauri::generate_context!())
        .expect("启动 MarkFlow 失败");

    // 应用退出时确保后端进程被终止
    // Tauri v2 中 ExitRequested 默认会退出应用（不调用 prevent_default 即可）
    // ExitRequested 在窗口关闭后触发，Exit 在进程退出前触发
    app.run(|_app_handle, event| {
        match event {
            tauri::RunEvent::ExitRequested { .. } => {
                eprintln!("[MarkFlow] ExitRequested, stopping backend");
                backend::stop_backend();
                // 不调用 prevent_default()，让应用正常退出
            }
            tauri::RunEvent::Exit => {
                eprintln!("[MarkFlow] Exit, final cleanup");
                backend::stop_backend();
            }
            _ => {}
        }
    });
}
