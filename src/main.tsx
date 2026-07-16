import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { register, unregister } from "@tauri-apps/plugin-global-shortcut";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

async function installGlobalShortcut() {
  const shortcut = "CommandOrControl+Shift+Space";
  try {
    await unregister(shortcut).catch(() => undefined);
    await register(shortcut, async (event) => {
      if (event.state !== "Pressed") return;
      const win = getCurrentWindow();
      const visible = await win.isVisible();
      if (visible) {
        await win.hide();
      } else {
        await win.show();
        await win.setFocus();
      }
    });
  } catch {
    // The app still works without the global shortcut in browser preview or restricted environments.
  }
}

installGlobalShortcut();
