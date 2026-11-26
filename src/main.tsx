import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { InlinePreview, RecordingBar } from "./FloatingApp";
import "./i18n";
import "./styles.css";

const view = new URLSearchParams(window.location.search).get("view");
const Root = view === "overlay" ? RecordingBar : view==="inline" ? InlinePreview : App;
document.documentElement.dataset.view = view || "main";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
