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

/// 跨平台杀死整个进程树（同步等待完成）
fn kill_process_tree(pid: u32) {
    if pid == 0 { return; }
    if cfg!(target_os = "windows") {
        let _ = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status(); // 用 status() 替代 spawn()，等待 taskkill 执行完毕
    } else {
        // Unix: 使用进程组 ID 杀死整个进程树
        let _ = Command::new("kill")
            .args(["-TERM", &format!("-{}", pid)])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status(); // 用 status() 替代 spawn()，等待 kill 执行完毕
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
    // 1. 从静态变量中取出已管理的进程句柄并杀死
    let handle = {
        let mut guard = BACKEND_PROCESS.lock().unwrap();
        guard.take()
    };

    if let Some(h) = handle {
        let _ = h.kill();
    }

    // 2. 额外通过端口清扫：防止 uvicorn --reload 模式的后台残留进程，
    //    也处理可能独立启动（如 dev terminal）的重复后端进程
    let port = *BACKEND_PORT.lock().unwrap();
    if port > 0 {
        kill_processes_on_port(port);
        // 也清扫相邻端口的残留（如果 get_available_port 跳到了更高端口）
        for p in port + 1..port + 10 {
            if std::net::TcpListener::bind(format!("127.0.0.1:{}", p)).is_ok() {
                break; // 遇到空闲端口即停止
            }
            kill_processes_on_port(p);
        }
    }

    *BACKEND_READY.lock().unwrap() = false;
}

/// 强制杀死占用指定端口的全部进程（Windows 使用 netstat + taskkill）
fn kill_processes_on_port(port: u16) {
    if cfg!(target_os = "windows") {
        // 通过 netstat 找到占用端口的 PID
        let output = Command::new("netstat")
            .args(["-ano"])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output()
            .ok();
        if let Some(out) = output {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let port_str = format!(":{}", port);
            for line in stdout.lines() {
                if line.contains(&port_str) && line.contains("LISTENING") {
                    // 提取最后一列 PID
                    if let Some(pid_str) = line.split_whitespace().last() {
                        if let Ok(pid) = pid_str.parse::<u32>() {
                            eprintln!("[MarkFlow] killing process {} on port {}", pid, port);
                            let _ = Command::new("taskkill")
                                .args(["/F", "/PID", &pid.to_string()])
                                .stdout(Stdio::null())
                                .stderr(Stdio::null())
                                .status();
                        }
                    }
                }
            }
        }
    } else {
        // Unix: 使用 lsof 或 fuser 查找端口占用进程
        let _ = Command::new("fuser")
            .args(["-k", &format!("{}/tcp", port)])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
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
