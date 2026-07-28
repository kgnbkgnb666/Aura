#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, WindowEvent,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const SIDECAR_PORTS: [u16; 4] = [8765, 8766, 8767, 8768];

#[derive(Default)]
struct SidecarState {
    child: Mutex<Option<Child>>,
    connection: Mutex<Option<SidecarInfo>>,
}

impl SidecarState {
    fn shutdown(&self) {
        if let Ok(mut child) = self.child.lock() {
            if let Some(mut process) = child.take() {
                let _ = process.kill();
                let _ = process.wait();
            }
        }
        if let Ok(mut connection) = self.connection.lock() {
            *connection = None;
        }
    }
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[derive(Clone, Serialize)]
struct SidecarInfo {
    port: u16,
    base_url: String,
    token: String,
}

#[derive(Deserialize)]
struct SidecarHealth {
    app: String,
    api_version: u32,
    parent_pid: Option<u32>,
}

fn project_root() -> PathBuf {
    #[cfg(debug_assertions)]
    {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."))
    }

    #[cfg(not(debug_assertions))]
    {
        std::env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(PathBuf::from))
            .unwrap_or_else(|| PathBuf::from("."))
    }
}

fn tcp_port_is_open(port: u16) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    TcpStream::connect_timeout(&addr, Duration::from_millis(120)).is_ok()
}

fn sidecar_health(port: u16, token: &str) -> Option<SidecarHealth> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(180)) else {
        return None;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Aura-Token: {token}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return None;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return None;
    }
    let body = response.split("\r\n\r\n").nth(1)?;
    serde_json::from_str(body).ok()
}

fn sidecar_is_compatible(port: u16, token: &str) -> bool {
    sidecar_health(port, token)
        .map(|health| health.app == "Aura" && health.api_version == 5)
        .unwrap_or(false)
}

fn sidecar_belongs_to_current_process(port: u16, token: &str) -> bool {
    sidecar_health(port, token)
        .map(|health| {
            health.app == "Aura"
                && health.api_version == 5
                && health.parent_pid == Some(std::process::id())
        })
        .unwrap_or(false)
}

fn wait_for_sidecar(port: u16, token: &str) -> bool {
    for _ in 0..50 {
        if sidecar_is_compatible(port, token) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

fn spawn_with(
    program: &str,
    prefix_args: &[&str],
    port: u16,
    token: &str,
) -> std::io::Result<Child> {
    let root = project_root();
    let port_arg = port.to_string();
    let parent_pid_arg = std::process::id().to_string();

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        Command::new(program)
            .args(prefix_args)
            .args(["-m", "aura.sidecar", "--host", "127.0.0.1", "--port"])
            .arg(port_arg)
            .args(["--parent-pid", &parent_pid_arg])
            .current_dir(root)
            .env("PYTHONUTF8", "1")
            .env("AURA_SIDECAR_TOKEN", token)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()
    }
    #[cfg(not(target_os = "windows"))]
    {
        Command::new(program)
            .args(prefix_args)
            .args(["-m", "aura.sidecar", "--host", "127.0.0.1", "--port"])
            .arg(port_arg)
            .args(["--parent-pid", &parent_pid_arg])
            .current_dir(root)
            .env("PYTHONUTF8", "1")
            .env("AURA_SIDECAR_TOKEN", token)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    }
}

#[cfg(not(debug_assertions))]
fn spawn_bundled_sidecar(
    exe_path: &std::path::Path,
    port: u16,
    token: &str,
) -> std::io::Result<Child> {
    let port_arg = port.to_string();
    let parent_pid_arg = std::process::id().to_string();
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        Command::new(exe_path)
            .args(["--host", "127.0.0.1", "--port"])
            .arg(port_arg)
            .args(["--parent-pid", &parent_pid_arg])
            .env("AURA_SIDECAR_TOKEN", token)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()
    }
    #[cfg(not(target_os = "windows"))]
    {
        Command::new(exe_path)
            .args(["--host", "127.0.0.1", "--port"])
            .arg(port_arg)
            .args(["--parent-pid", &parent_pid_arg])
            .env("AURA_SIDECAR_TOKEN", token)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    }
}

fn spawn_sidecar(port: u16, token: &str) -> Result<Child, String> {
    // Priority 1: explicit AURA_PYTHON env var
    if let Ok(program) = std::env::var("AURA_PYTHON") {
        if !program.trim().is_empty() {
            if let Ok(child) = spawn_with(&program, &[], port, token) {
                return Ok(child);
            }
        }
    }

    // Development default: prefer the dedicated "aura" environment over a
    // base Conda interpreter inherited from the terminal.
    #[cfg(all(target_os = "windows", debug_assertions))]
    {
        let mut candidates = Vec::new();
        if let Ok(profile) = std::env::var("USERPROFILE") {
            candidates.push(
                PathBuf::from(profile)
                    .join(".conda")
                    .join("envs")
                    .join("aura")
                    .join("python.exe"),
            );
        }
        if let Ok(prefix) = std::env::var("CONDA_PREFIX") {
            let prefix = PathBuf::from(prefix);
            if prefix.file_name().and_then(|name| name.to_str()) == Some("aura") {
                candidates.push(prefix.join("python.exe"));
            } else {
                candidates.push(prefix.join("envs").join("aura").join("python.exe"));
            }
        }
        candidates.push(
            project_root()
                .join(".venv")
                .join("Scripts")
                .join("python.exe"),
        );

        for program in candidates {
            if program.exists() {
                let program = program.to_string_lossy().to_string();
                if let Ok(child) = spawn_with(&program, &[], port, token) {
                    return Ok(child);
                }
            }
        }
    }

    // Priority 2 (release): bundled sidecar exe next to Aura.exe
    #[cfg(not(debug_assertions))]
    {
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(PathBuf::from));
        if let Some(dir) = exe_dir {
            let bundled = dir.join("aura-sidecar.exe");
            if bundled.exists() {
                return spawn_bundled_sidecar(&bundled, port, token)
                    .map_err(|e| format!("Failed to launch bundled sidecar: {e}"));
            }
        }
    }

    if let Ok(prefix) = std::env::var("VIRTUAL_ENV") {
        let program = PathBuf::from(prefix).join("Scripts").join("python.exe");
        if program.exists() {
            let program = program.to_string_lossy().to_string();
            if let Ok(child) = spawn_with(&program, &[], port, token) {
                return Ok(child);
            }
        }
    }

    if let Ok(prefix) = std::env::var("CONDA_PREFIX") {
        let program = PathBuf::from(prefix).join("python.exe");
        if program.exists() {
            let program = program.to_string_lossy().to_string();
            if let Ok(child) = spawn_with(&program, &[], port, token) {
                return Ok(child);
            }
        }
    }

    spawn_with("python", &[], port, token).or_else(|_| spawn_with("py", &["-3"], port, token)).map_err(|error| {
        format!("Unable to start Aura Python sidecar. Install Python or package a sidecar binary: {error}")
    })
}

#[tauri::command]
fn ensure_sidecar(state: tauri::State<'_, SidecarState>) -> Result<SidecarInfo, String> {
    let mut child_slot = state
        .child
        .lock()
        .map_err(|_| "Sidecar lock poisoned".to_string())?;
    if let Some(child) = child_slot.as_mut() {
        if child
            .try_wait()
            .map_err(|error| error.to_string())?
            .is_none()
        {
            let connection = state
                .connection
                .lock()
                .map_err(|_| "Sidecar connection lock poisoned".to_string())?;
            if let Some(info) = connection.as_ref() {
                if sidecar_belongs_to_current_process(info.port, &info.token) {
                    return Ok(info.clone());
                }
            }
        }
    }

    if let Some(mut process) = child_slot.take() {
        let _ = process.kill();
        let _ = process.wait();
    }
    *state
        .connection
        .lock()
        .map_err(|_| "Sidecar connection lock poisoned".to_string())? = None;

    for port in SIDECAR_PORTS {
        if tcp_port_is_open(port) {
            continue;
        }
        let mut token_bytes = [0_u8; 32];
        getrandom::fill(&mut token_bytes)
            .map_err(|error| format!("Unable to generate sidecar token: {error}"))?;
        let token: String = token_bytes
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect();
        *child_slot = Some(spawn_sidecar(port, &token)?);
        if wait_for_sidecar(port, &token) {
            let info = SidecarInfo {
                port,
                base_url: format!("http://127.0.0.1:{port}"),
                token,
            };
            *state
                .connection
                .lock()
                .map_err(|_| "Sidecar connection lock poisoned".to_string())? = Some(info.clone());
            return Ok(info);
        }
        if let Some(mut process) = child_slot.take() {
            let _ = process.kill();
            let _ = process.wait();
        }
    }

    Err("No compatible Aura sidecar port is available. Stop old sidecar processes on 8765-8768 and retry.".to_string())
}

fn should_hide_main_window(is_visible: bool, is_minimized: bool) -> bool {
    is_visible && !is_minimized
}

fn show_main_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        if window.is_minimized().map_err(|e| e.to_string())? {
            window.unminimize().map_err(|e| e.to_string())?;
        }
        window.set_focus().map_err(|e| e.to_string())?;
        window.emit("aura://shown", ()).map_err(|e| e.to_string())
    } else {
        Ok(())
    }
}

fn toggle_main_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        let is_visible = window.is_visible().map_err(|e| e.to_string())?;
        let is_minimized = window.is_minimized().map_err(|e| e.to_string())?;
        if should_hide_main_window(is_visible, is_minimized) {
            window.hide().map_err(|e| e.to_string())
        } else {
            show_main_window(app)
        }
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::{should_hide_main_window, SidecarInfo, SidecarState};

    #[test]
    fn tray_toggle_hides_a_visible_non_minimized_window() {
        assert!(should_hide_main_window(true, false));
        assert!(!should_hide_main_window(false, false));
        assert!(!should_hide_main_window(true, true));
    }

    #[test]
    fn sidecar_shutdown_is_idempotent_and_clears_connection() {
        let state = SidecarState::default();
        *state.connection.lock().unwrap() = Some(SidecarInfo {
            port: 8765,
            base_url: "http://127.0.0.1:8765".to_string(),
            token: "test-token".to_string(),
        });

        state.shutdown();
        state.shutdown();

        assert!(state.child.lock().unwrap().is_none());
        assert!(state.connection.lock().unwrap().is_none());
    }
}

fn hide_main_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.hide().map_err(|e| e.to_string())
    } else {
        Ok(())
    }
}

#[tauri::command]
fn toggle_window(app: tauri::AppHandle) -> Result<(), String> {
    toggle_main_window(&app)
}

#[tauri::command]
fn hide_window(app: tauri::AppHandle) -> Result<(), String> {
    hide_main_window(&app)
}

fn tray_labels(language: &str) -> (&'static str, &'static str) {
    match language {
        "zh-TW" => ("顯示 / 隱藏", "結束 Aura"),
        "en" => ("Show / Hide", "Quit Aura"),
        "ja" => ("表示 / 非表示", "Aura を終了"),
        _ => ("显示 / 隐藏", "退出 Aura"),
    }
}

#[tauri::command]
fn set_tray_language(app: tauri::AppHandle, language: String) -> Result<(), String> {
    let tray = app
        .tray_by_id("main")
        .ok_or_else(|| "Aura tray is unavailable".to_string())?;
    let (toggle_label, quit_label) = tray_labels(&language);
    let toggle_item = MenuItemBuilder::with_id("toggle", toggle_label)
        .build(&app)
        .map_err(|error| error.to_string())?;
    let quit_item = MenuItemBuilder::with_id("quit", quit_label)
        .build(&app)
        .map_err(|error| error.to_string())?;
    let menu = MenuBuilder::new(&app)
        .item(&toggle_item)
        .separator()
        .item(&quit_item)
        .build()
        .map_err(|error| error.to_string())?;
    tray.set_menu(Some(menu)).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![
            ensure_sidecar,
            toggle_window,
            hide_window,
            set_tray_language
        ])
        .setup(|app| {
            if let Err(error) =
                app.global_shortcut()
                    .on_shortcut("ctrl+shift+space", |app, _shortcut, event| {
                        if event.state == ShortcutState::Pressed {
                            let _ = show_main_window(app);
                        }
                    })
            {
                eprintln!("Failed to register Ctrl+Shift+Space: {error}");
            }

            let icon = Image::from_bytes(include_bytes!("../icons/icon.ico"))
                .expect("Failed to load tray icon");

            let toggle_item = MenuItemBuilder::with_id("toggle", "显示 / 隐藏").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "退出 Aura").build(app)?;
            let menu = MenuBuilder::new(app)
                .item(&toggle_item)
                .separator()
                .item(&quit_item)
                .build()?;

            let _tray = TrayIconBuilder::with_id("main")
                .icon(icon)
                .menu(&menu)
                .tooltip("Aura")
                .on_menu_event(|app, event| {
                    match event.id().as_ref() {
                        "toggle" => {
                            let _ = toggle_main_window(app);
                        }
                        "quit" => {
                            // app.exit(0) skips Drop, so explicitly stop only this app's owned child.
                            if let Some(state) = app.try_state::<SidecarState>() {
                                state.shutdown();
                            }

                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let _ = toggle_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            if let Some(window) = app.get_webview_window("main") {
                // Autostart stays hidden; an ordinary launch must explicitly own keyboard focus
                // so Space works immediately after the WebView installs its listener.
                if std::env::args().any(|arg| arg == "--minimized") {
                    let _ = window.hide();
                } else {
                    let _ = window.show().and_then(|_| window.set_focus());
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            match event {
                WindowEvent::CloseRequested { api, .. } => {
                    let _ = window.hide();
                    api.prevent_close();
                }
                WindowEvent::Destroyed => {
                    // Clean up sidecar when window is actually destroyed (app exit)
                    if let Some(app) = window.app_handle().try_state::<SidecarState>() {
                        app.shutdown();
                    }
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Aura");
}
