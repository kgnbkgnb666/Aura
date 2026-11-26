use std::sync::Mutex;
use windows::{
    core::BOOL,
    Win32::{
        System::{
            Com::{
                CoCreateInstance, CoInitializeEx, CoUninitialize, CLSCTX_INPROC_SERVER,
                COINIT_MULTITHREADED,
            },
            Ole::{SafeArrayDestroy, SafeArrayGetElement, SafeArrayGetLBound, SafeArrayGetUBound},
        },
        UI::Accessibility::*,
    },
};
use windows_sys::Win32::{
    Foundation::POINT,
    Graphics::Gdi::ClientToScreen,
    UI::{
        Controls::EM_REPLACESEL,
        Input::KeyboardAndMouse::{
            SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
            KEYEVENTF_UNICODE,
        },
        WindowsAndMessaging::{
            GetClassNameW, GetCursorPos, GetForegroundWindow, GetGUIThreadInfo,
            GetWindowThreadProcessId, SendMessageTimeoutW, GUITHREADINFO, SMTO_ABORTIFHUNG,
        },
    },
};

type Point = (i32, i32);

#[derive(Clone, PartialEq)]
struct Target {
    window: usize,
    focus: usize,
    element: Option<Vec<i32>>,
    selected: Option<Selection>,
}

#[derive(Clone, PartialEq)]
struct Selection {
    text: String,
    start: i32,
}

struct Undo {
    target: Target,
    replacement: String,
}

static LAST_EDIT: Mutex<Option<Undo>> = Mutex::new(None);

unsafe fn start_offset(range: &IUIAutomationTextRange) -> Option<i32> {
    let probe = range.Clone().ok()?;
    let moved = probe
        .MoveEndpointByUnit(
            TextPatternRangeEndpoint_Start,
            TextUnit_Character,
            -1_000_001,
        )
        .ok()?;
    (moved > -1_000_001).then_some(-moved)
}

static TARGET: Mutex<Option<Target>> = Mutex::new(None);

pub fn initial_bar_point() -> Option<Point> {
    unsafe {
        let window = GetForegroundWindow();
        let mut info: GUITHREADINFO = std::mem::zeroed();
        info.cbSize = std::mem::size_of_val(&info) as u32;
        let mut point: POINT = std::mem::zeroed();
        if !window.is_null()
            && GetGUIThreadInfo(GetWindowThreadProcessId(window, std::ptr::null_mut()), &mut info) != 0
            && !info.hwndCaret.is_null()
        {
            point.x = info.rcCaret.left;
            point.y = info.rcCaret.bottom;
            if ClientToScreen(info.hwndCaret, &mut point) != 0 {
                return Some((point.x, point.y));
            }
        }
        (GetCursorPos(&mut point) != 0).then_some((point.x, point.y))
    }
}

struct ComApartment;
impl Drop for ComApartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}

// Keep the COM interface on the calling thread. Only the element identity crosses requests.
unsafe fn focused_editor(
    read_selection: bool,
) -> Option<(Option<Vec<i32>>, Option<Point>, Option<Selection>)> {
    CoInitializeEx(None, COINIT_MULTITHREADED).ok().ok()?;
    let _apartment = ComApartment;
    let automation: IUIAutomation =
        CoCreateInstance(&CUIAutomation, None, CLSCTX_INPROC_SERVER).ok()?;
    let element = automation.GetFocusedElement().ok()?;
    let value = element
        .GetCurrentPatternAs::<IUIAutomationValuePattern>(UIA_ValuePatternId)
        .ok();
    if value
        .as_ref()
        .and_then(|v| v.CurrentIsReadOnly().ok())
        .is_some_and(|v| v.as_bool())
    {
        return None;
    }
    let mut active = BOOL::default();
    let has_caret = element
        .GetCurrentPatternAs::<IUIAutomationTextPattern2>(UIA_TextPattern2Id)
        .and_then(|p| p.GetCaretRange(&mut active))
        .is_ok()
        && active.as_bool();
    if element.CurrentControlType().ok() != Some(UIA_EditControlTypeId)
        && !has_caret
        && element
            .GetCurrentPatternAs::<IUIAutomationTextEditPattern>(UIA_TextEditPatternId)
            .is_err()
    {
        return None;
    }
    let point = element
        .CurrentBoundingRectangle()
        .ok()
        .filter(|r| r.right > r.left && r.bottom > r.top)
        .map(|r| {
            (
                r.left + (r.right - r.left) / 2,
                r.top + (r.bottom - r.top) / 2,
            )
        });
    let id = element.GetRuntimeId().ok().and_then(|array| {
        if array.is_null() {
            return None;
        }
        let values = (|| {
            let first = SafeArrayGetLBound(array, 1).ok()?;
            let last = SafeArrayGetUBound(array, 1).ok()?;
            (first..=last)
                .map(|i| {
                    let mut value = 0i32;
                    SafeArrayGetElement(array, &i, (&mut value as *mut i32).cast()).ok()?;
                    Some(value)
                })
                .collect::<Option<Vec<_>>>()
        })();
        let _ = SafeArrayDestroy(array);
        values
    });
    let selected = if read_selection && !element.CurrentIsPassword().unwrap_or_default().as_bool() {
        (|| {
            let pattern = element
                .GetCurrentPatternAs::<IUIAutomationTextPattern>(UIA_TextPatternId)
                .ok()?;
            let ranges = pattern.GetSelection().ok()?;
            if ranges.Length().ok()? != 1 {
                return None;
            }
            let range = ranges.GetElement(0).ok()?;
            let text = range.GetText(32769).ok()?.to_string();
            (!text.trim().is_empty() && text.encode_utf16().count() <= 32768).then_some(Selection {
                text,
                start: start_offset(&range)?,
            })
        })()
    } else {
        None
    };
    Some((id, point, selected))
}

fn capture(read_selection: bool) -> (Option<Target>, Option<Point>) {
    unsafe {
        let mut pointer: POINT = std::mem::zeroed();
        let pointer = (GetCursorPos(&mut pointer) != 0).then_some((pointer.x, pointer.y));
        let window = GetForegroundWindow();
        if window.is_null() {
            return (None, pointer);
        }
        let mut info: GUITHREADINFO = std::mem::zeroed();
        info.cbSize = std::mem::size_of_val(&info) as u32;
        let tid = GetWindowThreadProcessId(window, std::ptr::null_mut());
        if GetGUIThreadInfo(tid, &mut info) == 0 {
            return (None, pointer);
        }
        let editor = focused_editor(read_selection);
        let mut caret = POINT {
            x: info.rcCaret.left,
            y: info.rcCaret.bottom,
        };
        let caret = (!info.hwndCaret.is_null() && ClientToScreen(info.hwndCaret, &mut caret) != 0)
            .then_some((caret.x, caret.y));
        if GetForegroundWindow() != window || (caret.is_none() && editor.is_none()) {
            return (None, pointer);
        }
        let (element, bounds, selected) = editor.unwrap_or_default();
        (
            Some(Target {
                window: window as usize,
                focus: info.hwndFocus as usize,
                element,
                selected,
            }),
            caret.or(bounds).or(pointer),
        )
    }
}

pub fn remember(editing: bool) -> (Option<Point>, Option<String>) {
    LAST_EDIT.lock().unwrap().take();
    let (target, point) = capture(editing);
    let selected = target
        .as_ref()
        .and_then(|t| t.selected.as_ref().map(|s| s.text.clone()));
    *TARGET.lock().unwrap() = target;
    (point, selected)
}

pub fn insert_text(text: String) -> Result<bool, String> {
    let Some(target) = TARGET.lock().unwrap().take() else {
        return Ok(false);
    };
    let current = capture(target.selected.is_some()).0;
    let same_target = current.as_ref() == Some(&target)
        || current.as_ref().is_some_and(|candidate| {
            candidate.window == target.window
                && candidate.focus == target.focus
                && candidate.selected.as_ref().map(|s| &s.text)
                    == target.selected.as_ref().map(|s| &s.text)
        });
    if !same_target {
        return Ok(false);
    }
    let inserted = write_text(&target, &text)?;
    if inserted && target.selected.is_some() {
        *LAST_EDIT.lock().unwrap() = Some(Undo {
            target,
            replacement: text,
        });
    }
    Ok(inserted)
}

pub fn undo_edit() -> Result<bool, String> {
    let Some(edit) = LAST_EDIT.lock().unwrap().take() else {
        return Ok(false);
    };
    let mut target = edit.target;
    let original = target.selected.take().unwrap();
    if capture(false).0.as_ref() != Some(&target) {
        return Ok(false);
    }
    unsafe {
        CoInitializeEx(None, COINIT_MULTITHREADED)
            .ok()
            .map_err(|e| e.to_string())?;
        let _apartment = ComApartment;
        let select_replacement = || -> Option<()> {
            let automation: IUIAutomation =
                CoCreateInstance(&CUIAutomation, None, CLSCTX_INPROC_SERVER).ok()?;
            let element = automation.GetFocusedElement().ok()?;
            let pattern = element
                .GetCurrentPatternAs::<IUIAutomationTextPattern>(UIA_TextPatternId)
                .ok()?;
            let ranges = pattern.GetSelection().ok()?;
            if ranges.Length().ok()? != 1 {
                return None;
            }
            let range = ranges.GetElement(0).ok()?;
            if !range.GetText(1).ok()?.is_empty() {
                return None;
            }
            let count = start_offset(&range)? - original.start;
            if count <= 0 {
                return None;
            }
            range
                .MoveEndpointByUnit(TextPatternRangeEndpoint_Start, TextUnit_Character, -count)
                .ok()?;
            if range.GetText(-1).ok()?.to_string() != edit.replacement {
                return None;
            }
            range.Select().ok()
        };
        if select_replacement().is_none() {
            return Ok(false);
        }
    }
    target.selected = Some(Selection {
        text: edit.replacement,
        start: original.start,
    });
    if capture(true).0.as_ref() != Some(&target) {
        return Ok(false);
    }
    write_text(&target, &original.text)
}

fn write_text(target: &Target, text: &str) -> Result<bool, String> {
    let hwnd = target.focus as *mut std::ffi::c_void;
    let mut class = [0u16; 256];
    let length = unsafe { GetClassNameW(hwnd, class.as_mut_ptr(), class.len() as i32) };
    let class = String::from_utf16_lossy(&class[..length as usize]).to_ascii_lowercase();
    if unsafe { GetForegroundWindow() as usize } != target.window {
        return Ok(false);
    }
    if class == "edit" || class.starts_with("richedit") || class.starts_with("windowsforms10.edit.")
    {
        let value: Vec<u16> = text
            .replace("\r\n", "\n")
            .replace('\n', "\r\n")
            .encode_utf16()
            .chain(std::iter::once(0))
            .collect();
        let ok = unsafe {
            SendMessageTimeoutW(
                hwnd,
                EM_REPLACESEL,
                1,
                value.as_ptr() as isize,
                SMTO_ABORTIFHUNG,
                1500,
                std::ptr::null_mut(),
            )
        };
        return Ok(ok != 0);
    }
    // A simulated Return can send a chat message. Offer explicit copy for control characters.
    if text.chars().any(char::is_control)
        || target
            .selected
            .as_ref()
            .is_some_and(|s| s.text.chars().any(char::is_control))
    {
        return Ok(false);
    }
    let inputs: Vec<INPUT> = text
        .encode_utf16()
        .flat_map(|unit| {
            [0, KEYEVENTF_KEYUP].map(|flags| INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: 0,
                        wScan: unit,
                        dwFlags: KEYEVENTF_UNICODE | flags,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            })
        })
        .collect();
    Ok(!inputs.is_empty()
        && unsafe {
            SendInput(
                inputs.len() as u32,
                inputs.as_ptr(),
                std::mem::size_of::<INPUT>() as i32,
            ) == inputs.len() as u32
        })
}
pub fn preview_anchor() -> Option<Point> {
    let expected = TARGET.lock().ok()?.clone()?;
    if capture(expected.selected.is_some()).0.as_ref() != Some(&expected) {
        return None;
    }
    unsafe {
        let tid = GetWindowThreadProcessId(expected.window as _, std::ptr::null_mut());
        let mut info: GUITHREADINFO = std::mem::zeroed();
        info.cbSize = std::mem::size_of_val(&info) as u32;
        if GetGUIThreadInfo(tid, &mut info) != 0 && !info.hwndCaret.is_null() {
            let mut p = POINT {
                x: info.rcCaret.left,
                y: info.rcCaret.top,
            };
            if ClientToScreen(info.hwndCaret, &mut p) != 0 {
                return Some((p.x, p.y));
            }
        }
        CoInitializeEx(None, COINIT_MULTITHREADED).ok().ok()?;
        let _apartment = ComApartment;
        let a: IUIAutomation = CoCreateInstance(&CUIAutomation, None, CLSCTX_INPROC_SERVER).ok()?;
        let e = a.GetFocusedElement().ok()?;
        if e.CurrentIsPassword().ok()?.as_bool() {
            return None;
        }
        let ranges = e
            .GetCurrentPatternAs::<IUIAutomationTextPattern>(UIA_TextPatternId)
            .ok()?
            .GetSelection()
            .ok()?;
        let range = ranges.GetElement(0).ok()?;
        if let Some(point) = range_point(&range, false) {
            return Some(point);
        }
        // Chromium can return an empty rectangle for a collapsed selection.
        let after = range.Clone().ok()?;
        if after
            .MoveEndpointByUnit(TextPatternRangeEndpoint_End, TextUnit_Character, 1)
            .ok()?
            > 0
        {
            if let Some(point) = range_point(&after, false) {
                return Some(point);
            }
        }
        if range
            .MoveEndpointByUnit(TextPatternRangeEndpoint_Start, TextUnit_Character, -1)
            .ok()?
            < 0
        {
            if let Some(point) = range_point(&range, true) {
                return Some(point);
            }
        }
        let rect = e.CurrentBoundingRectangle().ok()?;
        (rect.right > rect.left && rect.bottom > rect.top).then_some((rect.left + 4, rect.top + 3))
    }
}

unsafe fn range_point(range: &IUIAutomationTextRange, trailing: bool) -> Option<Point> {
    let array = range.GetBoundingRectangles().ok()?;
    if array.is_null() {
        return None;
    }
    let coords = (|| {
        let first = SafeArrayGetLBound(array, 1).ok()?;
        if SafeArrayGetUBound(array, 1).ok()? - first < 3 {
            return None;
        }
        let mut rect = [0.0f64; 4];
        for (n, v) in rect.iter_mut().enumerate() {
            SafeArrayGetElement(array, &(first + n as i32), (v as *mut f64).cast()).ok()?;
        }
        (rect[3] > 0.0).then_some((
            (rect[0] + if trailing { rect[2] } else { 0.0 }) as i32,
            rect[1] as i32,
        ))
    })();
    let _ = SafeArrayDestroy(array);
    coords
}
