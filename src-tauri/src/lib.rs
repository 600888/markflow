use tauri::Manager;

mod backend;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // 后台启动 Python 后端
            tauri::async_runtime::spawn(async move {
                backend::start_backend(&handle).await;
            });

            // 窗口关闭时立即杀死后端（在 RunEvent 之前处理）
            if let Some(win) = app.get_webview_window("main") {
                win.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { .. } = event {
                        eprintln!("[MarkFlow] window close requested, killing backend");
                        backend::stop_backend();
                        // 不调用 close()，让默认关闭行为继续
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend::get_backend_url,
            backend::is_backend_ready,
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
