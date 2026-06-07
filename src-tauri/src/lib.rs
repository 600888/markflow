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

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend::get_backend_url,
            backend::is_backend_ready,
        ])
        .build(tauri::generate_context!())
        .expect("启动 MarkFlow 失败");

    // 应用退出时确保后端进程被终止
    app.run(|_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            backend::stop_backend();
        }
    });
}
