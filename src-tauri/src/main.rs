#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, WindowEvent,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const SIDECAR_PORTS: [u16; 4] = [8765, 8766, 8767, 8768];

#[derive(Default)]
struct SidecarState {
    child: Mutex<Option<Child>>,
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            if let Some(mut process) = child.take() {
                let _ = process.kill();
            }
        }
    }
}

#[derive(Serialize)]
struct SidecarInfo {
    port: u16,
    base_url: String,
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
        return PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."));
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

fn sidecar_health(port: u16) -> Option<SidecarHealth> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(180)) else {
        return None;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request =
        format!("GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
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

fn sidecar_is_compatible(port: u16) -> bool {
    sidecar_health(port)
        .map(|health| health.app == "Aura" && health.api_version == 3)
        .unwrap_or(false)
}

fn sidecar_belongs_to_current_process(port: u16) -> bool {
    sidecar_health(port)
        .map(|health| {
            health.app == "Aura"
                && health.api_version == 3
                && health.parent_pid == Some(std::process::id())
        })
        .unwrap_or(false)
}

fn wait_for_sidecar(port: u16) -> bool {
    for _ in 0..50 {
        if sidecar_is_compatible(port) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

fn spawn_with(program: &str, prefix_args: &[&str], port: u16) -> std::io::Result<Child> {
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
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    }
}

fn spawn_bundled_sidecar(exe_path: &Path, port: u16) -> std::io::Result<Child> {
    let port_arg = port.to_string();
    let parent_pid_arg = std::process::id().to_string();
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        Command::new(exe_path)
            .args(["--host", "127.0.0.1", "--port"])
            .arg(port_arg)
            .args(["--parent-pid", &parent_pid_arg])
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
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    }
}

fn spawn_sidecar(port: u16) -> Result<Child, String> {
    // Priority 1: explicit AURA_PYTHON env var
    if let Ok(program) = std::env::var("AURA_PYTHON") {
        if !program.trim().is_empty() {
            if let Ok(child) = spawn_with(&program, &[], port) {
                return Ok(child);
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
                return spawn_bundled_sidecar(&bundled, port)
                    .map_err(|e| format!("Failed to launch bundled sidecar: {e}"));
            }
        }
    }

    if let Ok(prefix) = std::env::var("VIRTUAL_ENV") {
        let program = PathBuf::from(prefix).join("Scripts").join("python.exe");
        if program.exists() {
            let program = program.to_string_lossy().to_string();
            if let Ok(child) = spawn_with(&program, &[], port) {
                return Ok(child);
            }
        }
    }

    if let Ok(prefix) = std::env::var("CONDA_PREFIX") {
        let program = PathBuf::from(prefix).join("python.exe");
        if program.exists() {
            let program = program.to_string_lossy().to_string();
            if let Ok(child) = spawn_with(&program, &[], port) {
                return Ok(child);
            }
        }
    }

    spawn_with("python", &[], port).or_else(|_| spawn_with("py", &["-3"], port)).map_err(|error| {
        format!("Unable to start Aura Python sidecar. Install Python or package a sidecar binary: {error}")
    })
}

#[tauri::command]
fn ensure_sidecar(state: tauri::State<'_, SidecarState>) -> Result<SidecarInfo, String> {
    // Only reuse a sidecar owned by this Aura process. An orphan left by an
    // interrupted dev run must never be adopted by a later app instance.
    for port in SIDECAR_PORTS {
        if sidecar_belongs_to_current_process(port) {
            return Ok(SidecarInfo {
                port,
                base_url: format!("http://127.0.0.1:{port}"),
            });
        }
    }

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
            for port in SIDECAR_PORTS {
                if sidecar_belongs_to_current_process(port) {
                    return Ok(SidecarInfo {
                        port,
                        base_url: format!("http://127.0.0.1:{port}"),
                    });
                }
            }
        }
    }

    for port in SIDECAR_PORTS {
        if tcp_port_is_open(port) {
            continue;
        }
        *child_slot = Some(spawn_sidecar(port)?);
        if wait_for_sidecar(port) {
            return Ok(SidecarInfo {
                port,
                base_url: format!("http://127.0.0.1:{port}"),
            });
        }
    }

    Err("No compatible Aura sidecar port is available. Stop old sidecar processes on 8765-8768 and retry.".to_string())
}

fn toggle_main_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        let is_visible = window.is_visible().map_err(|e| e.to_string())?;
        let is_focused = window.is_focused().map_err(|e| e.to_string())?;
        let is_minimized = window.is_minimized().map_err(|e| e.to_string())?;
        if is_visible && is_focused && !is_minimized {
            window.hide().map_err(|e| e.to_string())
        } else {
            window.show().map_err(|e| e.to_string())?;
            if is_minimized {
                window.unminimize().map_err(|e| e.to_string())?;
            }
            window.set_focus().map_err(|e| e.to_string())
        }
    } else {
        Ok(())
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![
            ensure_sidecar,
            toggle_window,
            hide_window
        ])
        .setup(|app| {
            if let Err(error) =
                app.global_shortcut()
                    .on_shortcut("ctrl+shift+space", |app, _shortcut, event| {
                        if event.state == ShortcutState::Pressed {
                            let _ = toggle_main_window(app);
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

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .menu(&menu)
                .tooltip("Aura")
                .on_menu_event(|app, event| {
                    match event.id().as_ref() {
                        "toggle" => {
                            let _ = toggle_main_window(app);
                        }
                        "quit" => {
                            // Kill sidecar before exit — app.exit(0) skips Drop, so we must clean up manually
                            if let Some(state) = app.try_state::<SidecarState>() {
                                if let Ok(mut child) = state.child.lock() {
                                    if let Some(ref mut process) = *child {
                                        let _ = process.kill();
                                        let _ = process.wait();
                                    }
                                    *child = None;
                                }
                            }

                            // Force kill all sidecar processes by name to prevent leaks
                            #[cfg(target_os = "windows")]
                            {
                                use std::process::Command;
                                let _ = Command::new("taskkill")
                                    .args(["/F", "/IM", "aura-sidecar.exe"])
                                    .output();
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
                        if let Ok(mut child) = app.child.lock() {
                            if let Some(ref mut process) = *child {
                                let _ = process.kill();
                                let _ = process.wait();
                            }
                            *child = None;
                        }
                    }
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Aura");
}
