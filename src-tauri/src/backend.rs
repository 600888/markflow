use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use reqwest::Client;
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

/// 统一的后端进程句柄（sidecar 或直接 spawn 的 Python）
enum ProcessHandle {
    Sidecar(CommandChild),
    Direct(Child),
}

impl ProcessHandle {
    /// 终止进程并等待结束（转移所有权以适配 CommandChild::kill(self)）
    fn kill(self) -> std::io::Result<()> {
        match self {
            ProcessHandle::Sidecar(c) => c.kill().map_err(|e| {
                std::io::Error::new(std::io::ErrorKind::Other, e)
            }),
            ProcessHandle::Direct(mut c) => {
                // 先 kill 进程树（uvicorn 可能产生子进程）
                kill_process_tree(c.id());
                let _ = c.kill();
                let _ = c.wait();
                Ok(())
            }
        }
    }
}

/// 跨平台杀死整个进程树
fn kill_process_tree(pid: u32) {
    if pid == 0 { return; }
    if cfg!(target_os = "windows") {
        let _ = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    } else {
        // Unix: 使用进程组 ID 杀死整个进程树
        let _ = Command::new("kill")
            .args(["-TERM", &format!("-{}", pid)])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
    }
}

static BACKEND_PROCESS: Mutex<Option<ProcessHandle>> = Mutex::new(None);
static BACKEND_PORT: Mutex<u16> = Mutex::new(62581);
static BACKEND_READY: Mutex<bool> = Mutex::new(false);

/// 启动 Python 后端
pub async fn start_backend(app: &AppHandle) {
    let port = get_available_port(62581);
    *BACKEND_PORT.lock().unwrap() = port;
    *BACKEND_READY.lock().unwrap() = false;

    let backend_url = format!("http://127.0.0.1:{}/api/v1/health", port);

    // 优先尝试 sidecar 模式（打包后），否则直接启动 Python 进程（开发模式）
    let process = try_spawn_sidecar(app, port)
        .map(ProcessHandle::Sidecar)
        .or_else(|| try_spawn_python_direct(port).map(ProcessHandle::Direct));

    match process {
        Some(handle) => {
            *BACKEND_PROCESS.lock().unwrap() = Some(handle);

            // 等待后端就绪（最长 30 秒）
            let ready = wait_for_backend(&backend_url, Duration::from_secs(30)).await;
            *BACKEND_READY.lock().unwrap() = ready;

            if ready {
                eprintln!("[MarkFlow] backend ready -> {}", backend_url);
            } else {
                eprintln!("[MarkFlow] backend startup timeout");
            }
        }
        None => {
            eprintln!("[MarkFlow] cannot start backend, check Python environment");
        }
    }
}

/// 尝试通过 Tauri sidecar 启动 Python 后端（打包后使用）
fn try_spawn_sidecar(app: &AppHandle, port: u16) -> Option<CommandChild> {
    let sidecar_cmd = app.shell().sidecar("pandoc-service").ok()?;
    let (_, child) = sidecar_cmd
        .args(["--port", &port.to_string()])
        .spawn()
        .ok()?;
    Some(child)
}

/// 开发模式下直接 spawn Python 进程
fn try_spawn_python_direct(port: u16) -> Option<Child> {
    let backend_dir = std::env::current_dir().ok()?.parent()?.join("backend");

    let python_cmds = if cfg!(target_os = "windows") {
        vec!["python", "python3", "py"]
    } else {
        vec!["python3", "python"]
    };

    for py in &python_cmds {
        if let Ok(child) = Command::new(py)
            .args([
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                &port.to_string(),
                "--log-level",
                "info",
            ])
            .current_dir(&backend_dir)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
        {
            eprintln!("[MarkFlow] using '{}' to start backend (port {})", py, port);
            return Some(child);
        }
    }

    eprintln!("[MarkFlow] no Python executable found");
    None
}

/// 等待后端 HTTP 健康检查通过
async fn wait_for_backend(url: &str, max_duration: Duration) -> bool {
    let client = Client::new();
    let start = std::time::Instant::now();

    loop {
        if start.elapsed() > max_duration {
            return false;
        }

        match client.get(url).send().await {
            Ok(resp) if resp.status().is_success() => return true,
            _ => {
                tokio::time::sleep(Duration::from_millis(500)).await;
                continue;
            }
        }
    }
}

/// 关闭后端进程（同步版本，用于窗口关闭事件中安全执行）
pub fn stop_backend() {
    let handle = {
        let mut guard = BACKEND_PROCESS.lock().unwrap();
        guard.take()
    };

    if let Some(h) = handle {
        let _ = h.kill();
    }

    *BACKEND_READY.lock().unwrap() = false;
}

/// 向前端返回后端 URL
#[tauri::command]
pub fn get_backend_url() -> Result<String, String> {
    let port = BACKEND_PORT.lock().map_err(|e| e.to_string())?;
    Ok(format!("http://127.0.0.1:{}", port))
}

/// 检查后端是否已就绪
#[tauri::command]
pub fn is_backend_ready() -> Result<bool, String> {
    BACKEND_READY.lock().map(|g| *g).map_err(|e| e.to_string())
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
