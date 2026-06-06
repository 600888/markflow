use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::AppHandle;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

static BACKEND_PROCESS: Mutex<Option<Child>> = Mutex::new(None);
static BACKEND_PORT: Mutex<u16> = Mutex::new(62581);

/// 启动 Python 后端 Sidecar
pub async fn start_backend(app: &AppHandle) {
    let port = get_available_port(62581);
    *BACKEND_PORT.lock().unwrap() = port;

    let sidecar = app
        .shell()
        .sidecar("pandoc-service")
        .expect("找不到 sidecar 二进制");

    let (mut rx, child) = sidecar
        .args(["--port", &port.to_string()])
        .spawn()
        .expect("启动后端失败");

    *BACKEND_PROCESS.lock().unwrap() = Some(child);

    // 等待后端就绪
    while let Some(event) = rx.recv().await {
        if let tauri_plugin_shell::process::CommandEvent::Stdout(line) = event {
            let output = String::from_utf8_lossy(&line);
            if output.contains("Uvicorn running on") {
                break;
            }
        }
    }
}

/// 关闭后端进程
pub async fn stop_backend() {
    if let Ok(mut guard) = BACKEND_PROCESS.lock() {
        if let Some(ref mut child) = *guard {
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
    }
}

/// 向前端返回后端 URL
#[tauri::command]
pub fn get_backend_url() -> String {
    let port = BACKEND_PORT.lock().unwrap();
    format!("http://127.0.0.1:{}", port)
}

fn get_available_port(start: u16) -> u16 {
    let mut port = start;
    loop {
        if std::net::TcpListener::bind(format!("127.0.0.1:{}", port)).is_ok() {
            return port;
        }
        port += 1;
    }
}
