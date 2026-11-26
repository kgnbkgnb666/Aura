use serde::Deserialize;
use std::collections::HashSet;
use std::sync::{atomic::{AtomicBool, Ordering}, Mutex, OnceLock};

#[derive(Deserialize)]
pub struct Shortcuts {
    dictate: String,
    translate: String,
}

#[derive(Clone)]
struct Binding {
    keys: Vec<u32>,
    event: &'static str,
}

fn key_code(key: &str) -> Option<u32> {
    match key {
        "RightAlt" => Some(0xa5),
        "RightShift" => Some(0xa1),
        "RightCtrl" => Some(0xa3),
        "Space" => Some(0x20),
        "MouseLeft" => Some(0x1001),
        "MouseRight" => Some(0x1002),
        "MouseMiddle" => Some(0x1003),
        s => s
            .strip_prefix('F')?
            .parse::<u32>()
            .ok()
            .filter(|n| (1..=12).contains(n))
            .map(|n| 0x6f + n),
    }
}

static CAPTURING: AtomicBool = AtomicBool::new(false);

pub fn set_capture(active: bool) {
    CAPTURING.store(active, Ordering::Relaxed);
}

struct Keyboard {
    bindings: Vec<Binding>,
    down: HashSet<u32>,
    used: HashSet<u32>,
    swallowed: HashSet<u32>,
    synthetic_ctrl: bool,
}

impl Keyboard {
    fn handle(&mut self, key: u32, pressed: bool) -> (bool, Option<&'static str>) {
        // Windows reports Right Alt (AltGr) as Ctrl-down, RightAlt-down.
        // Remove that synthetic Ctrl before matching the configured tap.
        if key == 0xa5 && pressed && self.down.contains(&0xa2) {
            self.down.remove(&0xa2);
            self.used.remove(&0xa2);
            self.synthetic_ctrl = true;
        }
        if key == 0xa2 && !pressed && self.synthetic_ctrl {
            self.synthetic_ctrl = false;
            return (true, None);
        }
        if !pressed {
            let swallow = self.swallowed.remove(&key);
            let single = self.down.remove(&key) && !self.used.remove(&key);
            return (
                swallow,
                self.bindings
                    .iter()
                    .find(|b| single && b.keys == [key])
                    .map(|b| b.event),
            );
        }
        if !self.down.insert(key) {
            return (self.swallowed.contains(&key), None);
        }
        let chord = self
            .bindings
            .iter()
            .find(|b| b.keys.len() == 2 && b.keys[1] == key && self.down.contains(&b.keys[0]));
        if let Some(binding) = chord {
            self.used.extend(&binding.keys);
            self.swallowed.insert(key);
            return (true, Some(binding.event));
        }
        if self.down.len() > 1 {
            self.used.extend(&self.down);
        }
        let single = self.bindings.iter().any(|b| b.keys == [key]);
        if single {
            self.swallowed.insert(key);
        }
        (single, None)
    }
}

fn keyboard() -> &'static Mutex<Keyboard> {
    static KEYS: OnceLock<Mutex<Keyboard>> = OnceLock::new();
    KEYS.get_or_init(|| {
        Mutex::new(Keyboard {
            bindings: vec![
                Binding {
                    keys: vec![0xa5],
                    event: "aura://record-toggle",
                },
                Binding {
                    keys: vec![0xa5, 0xa1],
                    event: "aura://record-translate",
                },
            ],
            down: HashSet::new(),
            used: HashSet::new(),
            swallowed: HashSet::new(),
            synthetic_ctrl: false,
        })
    })
}

pub fn handle(key: u32, pressed: bool) -> (bool, Option<&'static str>) {
    if CAPTURING.load(Ordering::Relaxed) {
        return (false, None);
    }
    keyboard().lock().unwrap().handle(key, pressed)
}

#[tauri::command]
pub fn configure_shortcuts(shortcuts: Shortcuts) -> Result<(), String> {
    let mut bindings = Vec::new();
    for (value, event) in [
        (shortcuts.dictate, "aura://record-toggle"),
        (shortcuts.translate, "aura://record-translate"),
    ] {
        let keys = value
            .split('+')
            .map(key_code)
            .collect::<Option<Vec<_>>>()
            .ok_or("快捷键无效")?;
        if keys.len() > 2 || bindings.iter().any(|b: &Binding| b.keys == keys) {
            return Err("快捷键冲突".into());
        }
        bindings.push(Binding { keys, event });
    }
    keyboard().lock().unwrap().bindings = bindings;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn single_tap_and_combo_do_not_double_fire() {
        let mut k = Keyboard {
            bindings: vec![
                Binding {
                    keys: vec![165],
                    event: "start",
                },
                Binding {
                    keys: vec![165, 161],
                    event: "translate",
                },
            ],
            down: HashSet::new(),
            used: HashSet::new(),
            swallowed: HashSet::new(),
            synthetic_ctrl: false,
        };
        for _ in 0..2 {
            assert_eq!(k.handle(165, true), (true, None));
            assert_eq!(k.handle(165, false), (true, Some("start")));
        }
        k.handle(165, true);
        assert_eq!(k.handle(161, true).1, Some("translate"));
        assert_eq!(k.handle(161, true).1, None);
        assert_eq!(k.handle(165, false).1, None);
        assert_eq!(k.handle(161, false), (true, None));
    }

    #[test]
    fn right_alt_altgr_prefix_still_fires_on_release() {
        let mut k = Keyboard {
            bindings: vec![Binding {
                keys: vec![0xa5],
                event: "start",
            }],
            down: HashSet::new(),
            used: HashSet::new(),
            swallowed: HashSet::new(),
            synthetic_ctrl: false,
        };
        // The low-level Windows hook sends this synthetic Ctrl prefix for AltGr.
        assert_eq!(k.handle(0xa2, true), (false, None));
        assert_eq!(k.handle(0xa5, true), (true, None));
        assert_eq!(k.handle(0xa2, false), (true, None));
        assert_eq!(k.handle(0xa5, false), (true, Some("start")));
    }
}
