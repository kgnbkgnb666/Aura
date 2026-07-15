#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};

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

fn sidecar_is_compatible(port: u16) -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(180)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response.contains("\"app\": \"Aura\"") && response.contains("\"api_version\": 3")
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

    Command::new(program)
        .args(prefix_args)
        .args(["-m", "aura.sidecar", "--host", "127.0.0.1", "--port"])
        .arg(port_arg)
        .current_dir(root)
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
}

fn spawn_sidecar(port: u16) -> Result<Child, String> {
    if let Ok(program) = std::env::var("AURA_PYTHON") {
        if !program.trim().is_empty() {
            if let Ok(child) = spawn_with(&program, &[], port) {
                return Ok(child);
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
    for port in SIDECAR_PORTS {
        if sidecar_is_compatible(port) {
            return Ok(SidecarInfo {
                port,
                base_url: format!("http://127.0.0.1:{port}"),
            });
        }
    }

    let mut child_slot = state.child.lock().map_err(|_| "Sidecar lock poisoned".to_string())?;
    if let Some(child) = child_slot.as_mut() {
        if child.try_wait().map_err(|error| error.to_string())?.is_none() {
            for port in SIDECAR_PORTS {
                if sidecar_is_compatible(port) {
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![ensure_sidecar])
        .run(tauri::generate_context!())
        .expect("error while running Aura");
}
