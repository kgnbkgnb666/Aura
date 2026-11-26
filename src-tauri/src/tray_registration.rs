use std::path::Path;
use windows_sys::Win32::{
    Foundation::RECT,
    UI::{
        Shell::{
            Shell_NotifyIconGetRect, Shell_NotifyIconW, NIM_DELETE, NOTIFYICONDATAW,
            NOTIFYICONIDENTIFIER,
        },
        WindowsAndMessaging::IsWindow,
    },
};

// Explorer can retain a dead registration when the dev runner terminates the old process.
pub fn remember(path: &Path, hwnd: usize) {
    unsafe {
        if let Ok(bytes) = std::fs::read(path) {
            if let Ok((old, id)) = serde_json::from_slice::<(usize, u32)>(&bytes) {
                if IsWindow(old as _) == 0 {
                    let mut icon: NOTIFYICONDATAW = std::mem::zeroed();
                    icon.cbSize = std::mem::size_of_val(&icon) as u32;
                    icon.hWnd = old as _;
                    icon.uID = id;
                    Shell_NotifyIconW(NIM_DELETE, &icon);
                }
            }
        }
        let mut ident: NOTIFYICONIDENTIFIER = std::mem::zeroed();
        ident.cbSize = std::mem::size_of_val(&ident) as u32;
        ident.hWnd = hwnd as _;
        let mut rect: RECT = std::mem::zeroed();
        for id in 0..16 {
            ident.uID = id;
            if Shell_NotifyIconGetRect(&ident, &mut rect) >= 0 {
                if let Some(dir) = path.parent() {
                    let _ = std::fs::create_dir_all(dir);
                }
                let _ = std::fs::write(path, serde_json::to_vec(&(hwnd, id)).unwrap());
                break;
            }
        }
    }
}
