import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    exclude: [".tmp/**", "build/**", "dist/**", "node_modules/**", "src-tauri/**"],
  },
});
