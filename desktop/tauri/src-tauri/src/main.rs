#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, WebviewWindow};

#[derive(Default)]
struct ServerState {
    child: Arc<Mutex<Option<Child>>>,
}

fn port_open(host: &str, port: u16) -> bool {
    TcpStream::connect((host, port)).is_ok()
}

fn repo_root_from_manifest() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or(manifest)
}

fn spawn_server(app: &AppHandle, state: Arc<Mutex<Option<Child>>>) -> Result<(), String> {
    if port_open("127.0.0.1", 22267) {
        return Ok(());
    }

    let mut command;
    let working_dir;

    if cfg!(debug_assertions) {
        let root = repo_root_from_manifest();
        let python = root.join(".venv").join("bin").join("python");
        let python_fallback = PathBuf::from("python3");

        working_dir = root.clone();
        command = if python.exists() {
            let mut cmd = Command::new(python);
            cmd.arg("server.py");
            cmd
        } else {
            let mut cmd = Command::new(python_fallback);
            cmd.arg("server.py");
            cmd
        };
        command.current_dir(root);
    } else {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|e| format!("Failed to resolve app resources: {e}"))?;
        let exe = resource_dir.join("oas_server").join("OAS");
        if !exe.exists() {
            return Err(format!("Bundled server not found: {}", exe.display()));
        }

        working_dir = resource_dir.clone();
        command = Command::new(exe);
        command.current_dir(resource_dir);
    }

    let child = command
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| {
            format!(
                "Failed to start OAS server from {}: {e}",
                working_dir.display()
            )
        })?;

    let mut guard = state
        .lock()
        .map_err(|_| "Server state lock poisoned".to_string())?;
    *guard = Some(child);
    Ok(())
}

fn wait_for_server(window: WebviewWindow) {
    thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(60);
        while Instant::now() < deadline {
            if port_open("127.0.0.1", 22267) {
                let _ = window.eval("window.location.replace('http://127.0.0.1:22267/webui/')");
                return;
            }
            thread::sleep(Duration::from_millis(500));
        }
    });
}

fn main() {
    tauri::Builder::default()
        .manage(ServerState::default())
        .setup(|app| {
            let state = app.state::<ServerState>().child.clone();
            spawn_server(&app.handle(), state)?;
            let window = app
                .get_webview_window("main")
                .ok_or_else(|| "Main window not found".to_string())?;
            wait_for_server(window);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let child_state = window.state::<ServerState>().child.clone();
                let mut guard = match child_state.lock() {
                    Ok(guard) => guard,
                    Err(_) => return,
                };
                if let Some(child) = guard.as_mut() {
                    let _ = child.kill();
                }
                *guard = None;
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
