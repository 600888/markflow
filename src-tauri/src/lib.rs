use tauri::Manager;

mod backend;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                backend::start_backend(&handle).await;
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let handle = window.app_handle();
                tauri::async_runtime::spawn(async move {
                    backend::stop_backend().await;
                });
            }
        })
        .invoke_handler(tauri::generate_handler![backend::get_backend_url])
        .run(tauri::generate_context!())
        .expect("启动 MarkFlow 失败");
}
