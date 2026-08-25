use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use reqwest::Client;
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

/// 创建一个不会弹出控制台窗口的命令（Windows 上使用 CREATE_NO_WINDOW 标志）
fn new_detached_cmd(program: &str) -> Command {
    let mut cmd = Command::new(program);
    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    cmd
}

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
        let _ = new_detached_cmd("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    } else {
        // Unix: 使用进程组 ID 杀死整个进程树
        let _ = new_detached_cmd("kill")
            .args(["-TERM", &format!("-{}", pid)])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
}

static BACKEND_PROCESS: Mutex<Option<ProcessHandle>> = Mutex::new(None);
static BACKEND_PORT: Mutex<u16> = Mutex::new(62581);
static BACKEND_READY: Mutex<bool> = Mutex::new(false);

/// 返回持久化数据目录。
///
/// 开发环境使用项目根目录下的 data；打包环境使用可执行文件（安装目录）
/// 旁边的 data，确保历史数据库和“打开输出目录”指向同一位置。
pub fn data_directory() -> Result<std::path::PathBuf, String> {
    #[cfg(debug_assertions)]
    {
        let current_dir = std::env::current_dir().map_err(|error| error.to_string())?;
        let project_root = if current_dir.join("start_back_end.py").is_file() {
            current_dir
        } else if current_dir
            .parent()
            .is_some_and(|parent| parent.join("start_back_end.py").is_file())
        {
            current_dir
                .parent()
                .expect("parent checked above")
                .to_path_buf()
        } else {
            return Err("无法定位开发环境的数据目录".to_string());
        };
        Ok(project_root.join("data"))
    }

    #[cfg(not(debug_assertions))]
    {
        let executable = std::env::current_exe().map_err(|error| error.to_string())?;
        let install_directory = executable
            .parent()
            .ok_or_else(|| "无法定位 MarkFlow 安装目录".to_string())?;
        Ok(install_directory.join("data"))
    }
}

/// 同步启动后端进程并注册到静态变量，返回后端 URL。
/// 必须在 `setup()` 中同步调用，确保窗口打开前 handle 已注册。
pub fn spawn_backend(app: &AppHandle) -> String {
    let port = get_available_port(62581);
    *BACKEND_PORT.lock().unwrap() = port;
    *BACKEND_READY.lock().unwrap() = false;

    let backend_url = format!("http://127.0.0.1:{}/api/v1/health", port);

    // 优先尝试 sidecar 模式（打包后），否则直接启动 Python 进程（开发模式）
    let process = try_spawn_sidecar(app, port)
        .map(ProcessHandle::Sidecar)
        .or_else(|| try_spawn_python_direct(port).map(ProcessHandle::Direct));

    if let Some(handle) = process {
        *BACKEND_PROCESS.lock().unwrap() = Some(handle);
        eprintln!("[MarkFlow] backend process spawned on port {}", port);
    } else {
        eprintln!("[MarkFlow] cannot start backend, check Python environment");
    }

    backend_url
}

/// 异步等待后端健康检查就绪
pub async fn wait_backend_ready(url: &str) {
    let ready = wait_for_backend(url, Duration::from_secs(30)).await;
    *BACKEND_READY.lock().unwrap() = ready;
    if ready {
        eprintln!("[MarkFlow] backend ready -> {}", url);
    } else {
        eprintln!("[MarkFlow] backend startup timeout");
    }
}

/// 尝试通过 Tauri sidecar 启动 Python 后端（打包后使用）
fn try_spawn_sidecar(app: &AppHandle, port: u16) -> Option<CommandChild> {
    let sidecar_cmd = app.shell().sidecar("markflow-service").ok()?;

    let mut cmd = sidecar_cmd.args(["--port", &port.to_string()]);

    let data_dir = data_directory()
        .ok()
        .filter(|dir| match std::fs::create_dir_all(dir) {
            Ok(()) => true,
            Err(error) => {
                eprintln!(
                    "[MarkFlow] cannot create app data directory {:?}: {}",
                    dir, error
                );
                false
            }
        });

    if let Some(ref dir) = data_dir {
        let dir_str = dir.to_string_lossy().to_string();
        eprintln!("[MarkFlow] MARKFLOW_DATA_DIR -> {:?}", dir);
        // 方式 1: 通过环境变量传递
        cmd = cmd.env("MARKFLOW_DATA_DIR", &dir_str);
        // 方式 2: 同时写入当前进程环境变量，确保子进程继承
        let _ = std::env::set_var("MARKFLOW_DATA_DIR", &dir_str);
        // 方式 3: 通过命令行参数传递（Python 端会读取 --data-dir）
        cmd = cmd.args(["--data-dir", &dir_str]);
    } else {
        eprintln!("[MarkFlow] WARN: cannot create app data directory");
        eprintln!("[MarkFlow]   data_directory: {:?}", data_directory());
    }

    let (_, child) = cmd.spawn().ok()?;
    Some(child)
}

/// 开发模式下直接 spawn Python 进程
fn try_spawn_python_direct(port: u16) -> Option<Child> {
    let current_dir = std::env::current_dir().ok()?;
    let project_root = if current_dir.join("start_back_end.py").is_file() {
        current_dir
    } else {
        current_dir.parent()?.to_path_buf()
    };
    let launcher = project_root.join("start_back_end.py");
    let launcher_arg = launcher.to_string_lossy().to_string();
    let port_arg = port.to_string();

    let python_cmds = if cfg!(target_os = "windows") {
        vec!["python", "python3", "py"]
    } else {
        vec!["python3", "python"]
    };

    for py in &python_cmds {
        if let Ok(child) = new_detached_cmd(py)
            .args([
                launcher_arg.as_str(),
                "--port",
                port_arg.as_str(),
            ])
            .current_dir(&project_root)
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

/// 轻量级清理：只杀死已管理的进程句柄，不做耗时的端口扫描。
/// 用于窗口 CloseRequested 事件，确保不阻塞 GUI 线程。
pub fn cleanup_managed_process() {
    let handle = {
        let mut guard = BACKEND_PROCESS.lock().unwrap();
        guard.take()
    };
    if let Some(h) = handle {
        eprintln!("[MarkFlow] killing managed process handle");
        let _ = h.kill();
    }
}

/// 关闭后端进程（同步版本）。
/// 包含完整的端口清扫逻辑，适合在 ExitRequested/Exit 等非 GUI 事件中调用。
pub fn stop_backend() {
    // 1. 先做轻量清理
    cleanup_managed_process();

    // 2. 额外通过端口清扫：防止 uvicorn --reload 模式的后台残留进程，
    //    也处理可能独立启动（如 dev terminal）的重复后端进程
    let port = *BACKEND_PORT.lock().unwrap();
    if port > 0 {
        kill_processes_on_port(port);
    }

    *BACKEND_READY.lock().unwrap() = false;
}

/// 强制杀死占用指定端口的全部进程（Windows 使用 netstat + taskkill）
fn kill_processes_on_port(port: u16) {
    if cfg!(target_os = "windows") {
        // 通过 netstat 找到占用端口的 PID
        let output = new_detached_cmd("netstat")
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
                            let _ = new_detached_cmd("taskkill")
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
        let _ = new_detached_cmd("fuser")
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
