#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Mutex, OnceLock},
    time::Duration,
};
use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, PhysicalPosition, WebviewUrl, WebviewWindowBuilder, WindowEvent,
};

mod shortcuts;
#[cfg(windows)]
mod tray_registration;

const SIDECAR_PORTS: [u16; 4] = [8765, 8766, 8767, 8768];

#[cfg(target_os = "windows")]
mod input_target;

#[cfg(target_os = "windows")]
mod desktop_input {
    use super::*;

    use windows_sys::Win32::{
        Foundation::{LPARAM, LRESULT, WPARAM},
        UI::{

            WindowsAndMessaging::{CallNextHookEx, GetMessageW, SetWindowsHookExW, KBDLLHOOKSTRUCT, MSG, WH_KEYBOARD_LL, WH_MOUSE_LL, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP},
        },
    };

    static APP: OnceLock<tauri::AppHandle> = OnceLock::new();
    unsafe extern "system" fn keyboard_hook(code: i32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
        if code < 0 { return CallNextHookEx(std::ptr::null_mut(), code, wparam, lparam); }
        let event = &*(lparam as *const KBDLLHOOKSTRUCT);
        let down = wparam == WM_KEYDOWN as usize || wparam == WM_SYSKEYDOWN as usize;
        let up = wparam == WM_KEYUP as usize || wparam == WM_SYSKEYUP as usize;
        if down || up {
            let (swallow, action) = shortcuts::handle(event.vkCode, down);
            if let (Some(app), Some(action)) = (APP.get(), action) { let _ = app.emit(action, ()); }
            if swallow { return 1; }
        }
        CallNextHookEx(std::ptr::null_mut(), code, wparam, lparam)
    }

    unsafe extern "system" fn mouse_hook(code: i32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
        if code < 0 { return CallNextHookEx(std::ptr::null_mut(), code, wparam, lparam); }
        let (key, down) = match wparam as u32 {
            WM_LBUTTONDOWN => (0x1001, true), WM_LBUTTONUP => (0x1001, false),
            WM_RBUTTONDOWN => (0x1002, true), WM_RBUTTONUP => (0x1002, false),
            WM_MBUTTONDOWN => (0x1003, true), WM_MBUTTONUP => (0x1003, false),
            _ => return CallNextHookEx(std::ptr::null_mut(), code, wparam, lparam),
        };
        let (swallow, action) = shortcuts::handle(key, down);
        if let (Some(app), Some(action)) = (APP.get(), action) { let _ = app.emit(action, ()); }
        if swallow { return 1; }
        CallNextHookEx(std::ptr::null_mut(), code, wparam, lparam)
    }

    pub fn install(app: tauri::AppHandle) {
        let _ = APP.set(app);
        std::thread::spawn(|| unsafe {
            let hook = SetWindowsHookExW(WH_KEYBOARD_LL, Some(keyboard_hook), std::ptr::null_mut(), 0);
            if hook.is_null() { return; }
            let mouse_hook = SetWindowsHookExW(WH_MOUSE_LL, Some(mouse_hook), std::ptr::null_mut(), 0);
            if mouse_hook.is_null() { return; }
            let mut message: MSG = std::mem::zeroed();
            while GetMessageW(&mut message, std::ptr::null_mut(), 0, 0) > 0 {}
        });
    }

    pub use super::input_target::insert_text;

}

#[cfg(not(target_os = "windows"))]
mod desktop_input {
    pub fn install(_app: tauri::AppHandle) {}
    pub fn insert_text(_text: String) -> Result<bool, String> {
        Ok(false)
    }
}

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

const SIDECAR_API_VERSION: u32 = 9;

fn sidecar_is_compatible(port: u16, token: &str) -> bool {
    sidecar_health(port, token)
        .map(|health| health.app == "Aura" && health.api_version == SIDECAR_API_VERSION)
        .unwrap_or(false)
}

fn sidecar_belongs_to_current_process(port: u16, token: &str) -> bool {
    sidecar_health(port, token)
        .map(|health| {
            health.app == "Aura"
                && health.api_version == SIDECAR_API_VERSION
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

fn center_main_window(window: &tauri::WebviewWindow) -> Result<(), String> {
    let monitor = window
        .current_monitor()
        .map_err(|e| e.to_string())?
        .or(window.primary_monitor().map_err(|e| e.to_string())?);
    let Some(monitor) = monitor else {
        return Ok(());
    };
    let area = monitor.work_area();
    let size = window.outer_size().map_err(|e| e.to_string())?;
    let x = area.position.x + (area.size.width as i32 - size.width as i32) / 2;
    let y = area.position.y + (area.size.height as i32 - size.height as i32) / 2;
    window
        .set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())
}

fn show_main_window(app: &tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_minimized().map_err(|e| e.to_string())? {
            window.unminimize().map_err(|e| e.to_string())?;
        }
        center_main_window(&window)?;
        window.show().map_err(|e| e.to_string())?;
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

#[tauri::command]
fn show_main(app: tauri::AppHandle, tab: String) -> Result<(), String> {
    show_main_window(&app)?;
    app.emit("aura://open-settings", tab).map_err(|error| error.to_string())
}

#[tauri::command]
async fn set_bar_visible(app: tauri::AppHandle, visible: bool, editing: Option<bool>, wide: Option<bool>, translating: Option<bool>) -> Result<Option<String>, String> {
    let bar = app.get_webview_window("recording-bar").ok_or("听写浮窗未就绪")?;
    let bar_width:f64 = if wide.unwrap_or(false) || translating.unwrap_or(false) { 264.0 } else { 124.0 };
    #[cfg(target_os = "windows")]
    let position = |point: Option<(i32, i32)>| -> Result<(), String> {
        if let Some((x, y)) = point {
            if let Some(monitor) = bar.monitor_from_point(x as f64, y as f64).map_err(|e| e.to_string())? {
                let area = monitor.work_area();
                let scale = monitor.scale_factor();
                let width = (bar_width * scale).round() as i32;
                let inset = ((if translating.unwrap_or(false){100.0}else{64.0}) * scale).round() as i32;
                bar.set_position(PhysicalPosition::new(
                    area.position.x + (area.size.width as i32 - width) / 2,
                    area.position.y + area.size.height as i32 - inset,
                )).map_err(|e| e.to_string())?;
            }
        }
        Ok(())
    };
    #[cfg(target_os = "windows")]
    let initial_point = input_target::initial_bar_point();
    if visible {
        bar.set_size(tauri::LogicalSize::new(bar_width, if translating.unwrap_or(false){76.0}else{40.0})).map_err(|e|e.to_string())?;
        #[cfg(target_os = "windows")]
        position(initial_point)?;
    }
    #[cfg(target_os = "windows")]
    unsafe {
        use windows_sys::Win32::UI::WindowsAndMessaging::{ShowWindow, SW_HIDE, SW_SHOWNOACTIVATE};
        ShowWindow(bar.hwnd().map_err(|e| e.to_string())?.0, if visible { SW_SHOWNOACTIVATE } else { SW_HIDE });
        let (point, selected) = if visible { input_target::remember(editing.unwrap_or(false)) } else { (None, None) };
        if visible && point != initial_point {
            position(point)?;
        }
        Ok(selected)
    }
    #[cfg(not(target_os = "windows"))]
    (if visible { bar.show() } else { bar.hide() }).map(|_| None).map_err(|e| e.to_string())
}

#[tauri::command]
async fn inline_preview(app: tauri::AppHandle, text: String) -> Result<bool,String> {
    let window = app.get_webview_window("inline-preview").ok_or("预览窗口不可用")?;
    #[cfg(windows)]
    if !text.is_empty() {
        if let Some((x,y))=input_target::preview_anchor() {
            if let Some(monitor)=window.monitor_from_point(x as f64,y as f64).map_err(|e|e.to_string())? {
                let area=monitor.work_area();
                let scale=monitor.scale_factor();
                let width=(text.chars().count() as f64*14.0+18.0).clamp(45.0,280.0);
                window.set_size(tauri::LogicalSize::new(width,26.0)).map_err(|e|e.to_string())?;
                let right=area.position.x + area.size.width as i32;
                let bottom=area.position.y + area.size.height as i32;
                window.set_position(PhysicalPosition::new(x.min(right-(width*scale) as i32).max(area.position.x),
                    y.min(bottom-(26.0*scale) as i32).max(area.position.y))).map_err(|e|e.to_string())?;
                window.emit("aura://draft",text).map_err(|e|e.to_string())?;
                unsafe {windows_sys::Win32::UI::WindowsAndMessaging::ShowWindow(window.hwnd().map_err(|e|e.to_string())?.0, 4);}
                return Ok(true);
            }
        }
    }
    #[cfg(windows)]
    unsafe {windows_sys::Win32::UI::WindowsAndMessaging::ShowWindow(window.hwnd().map_err(|e|e.to_string())?.0,0);}
    Ok(false)
}

#[tauri::command]
async fn insert_text(text: String) -> Result<bool, String> {
    desktop_input::insert_text(text)
}

#[tauri::command]
fn set_shortcut_capture(active: bool) {
    shortcuts::set_capture(active);
}

#[tauri::command]
async fn undo_edit() -> Result<bool, String> {
    #[cfg(target_os = "windows")]
    return input_target::undo_edit();
    #[cfg(not(target_os = "windows"))]
    Ok(false)
}

#[tauri::command]
async fn export_rewrite_skills(app: tauri::AppHandle, skills: Vec<serde_json::Value>) -> Result<(), String> {
    use tauri_plugin_dialog::DialogExt;
    let Some(file) = app.dialog().file().add_filter("Aura Skills", &["json"])
        .set_file_name("aura-rewrite-skills.json").blocking_save_file() else {return Ok(());};
    let path=file.into_path().map_err(|e|e.to_string())?;
    let content=serde_json::to_vec_pretty(&serde_json::json!({"version":1,"skills":skills})).map_err(|e|e.to_string())?;
    std::fs::write(path,content).map_err(|e|e.to_string())
}

#[tauri::command]
fn copy_text(text: String) -> Result<(), String> {
    arboard::Clipboard::new().and_then(|mut c| c.set_text(text)).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_tray_language(app: tauri::AppHandle, language: String) -> Result<(), String> {
    let tray = app
        .tray_by_id("main")
        .ok_or_else(|| "Aura tray is unavailable".to_string())?;
    let (settings_label, quit_label) = match language.as_str() {
        "zh-TW" => ("設定", "結束 Aura"),
        "en" => ("Settings", "Quit Aura"),
        "ja" => ("設定", "Aura を終了"),
        _ => ("设置", "退出 Aura"),
    };
    let settings_item = MenuItemBuilder::with_id("settings", settings_label)
        .build(&app)
        .map_err(|error| error.to_string())?;
    let quit_item = MenuItemBuilder::with_id("quit", quit_label)
        .build(&app)
        .map_err(|error| error.to_string())?;
    let menu = MenuBuilder::new(&app)
        .item(&settings_item)
        .separator()
        .item(&quit_item)
        .build()
        .map_err(|error| error.to_string())?;
    tray.set_menu(Some(menu)).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| { let _ = show_main_window(app); }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![
            shortcuts::configure_shortcuts,
            ensure_sidecar,
            toggle_window,
            hide_window,
            set_tray_language,
            show_main,
            set_bar_visible,
            inline_preview,
            undo_edit,
            export_rewrite_skills,
            copy_text,
            insert_text
            ,set_shortcut_capture
        ])
        .setup(|app| {
            desktop_input::install(app.handle().clone());

            let overlay = WebviewWindowBuilder::new(app, "recording-bar", WebviewUrl::App("index.html?view=overlay".into()))
                .title("Aura 听写")
                .visible(false)
                .inner_size(124.0, 40.0)
                .resizable(false)
                .decorations(false)
                .transparent(true)
                .always_on_top(true)
                .skip_taskbar(true)
                .shadow(false)
                .focusable(false)
                .focused(false)
                .build()?;
            overlay.set_ignore_cursor_events(false)?;
            if let Some(monitor) = overlay.current_monitor()? {
                let size = monitor.size();
                let origin = monitor.position();
                let width = overlay.outer_size()?.width as i32;
                let inset = (96.0 * monitor.scale_factor()) as i32;
                overlay.set_position(PhysicalPosition::new(origin.x + (size.width as i32 - width) / 2, origin.y + size.height as i32 - inset))?;
            }

            let caption = WebviewWindowBuilder::new(app, "inline-preview", WebviewUrl::App("index.html?view=inline".into()))
                .title("Aura 字幕").inner_size(200.0,26.0).visible(false).resizable(false).decorations(false)
                .transparent(true).always_on_top(true).skip_taskbar(true).shadow(false).focusable(false).focused(false).build()?;
            caption.set_ignore_cursor_events(true)?;

            let icon = Image::from_bytes(include_bytes!("../icons/icon.ico"))
                .expect("Failed to load tray icon");

            let settings_item = MenuItemBuilder::with_id("settings", "设置").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "退出 Aura").build(app)?;
            let menu = MenuBuilder::new(app)
                .item(&settings_item)
                .separator()
                .item(&quit_item)
                .build()?;

            let _tray = TrayIconBuilder::with_id("main")
                .icon(icon)
                .menu(&menu)
                .show_menu_on_left_click(false)
                .tooltip("Aura")
                .on_menu_event(|app, event| {
                    match event.id().as_ref() {
                        "settings" => {
                            let _ = show_main_window(app);
                            let _ = app.emit("aura://open-settings", "general");
                        }
                        "quit" => {
                            // app.exit(0) skips Drop, so explicitly stop only this app's owned child.
                            if let Some(state) = app.try_state::<SidecarState>() {
                                state.shutdown();
                            }

                            if let Some(icon) = app.tray_by_id("main") { let _ = icon.set_visible(false); }
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
                        let _ = show_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            #[cfg(windows)]
            if let (Ok(dir), Ok(handle)) = (app.path().app_local_data_dir(), _tray.with_inner_tray_icon(|i| i.window_handle() as usize)) {
                tray_registration::remember(&dir.join("tray-registration.json"), handle);
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
