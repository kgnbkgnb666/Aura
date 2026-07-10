import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { register } from "@tauri-apps/plugin-global-shortcut";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

async function installGlobalShortcut() {
  try {
    await register("CommandOrControl+Shift+Space", async () => {
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
