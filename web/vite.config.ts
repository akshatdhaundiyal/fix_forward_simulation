import path from "node:path"
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// Built output goes to ../static, which the Python server already serves.
// Relative base keeps every URL relative, so hosting stays undecided.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: {
    outDir: path.resolve(import.meta.dirname, "../static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: path.resolve(import.meta.dirname, "index.html"),
        team: path.resolve(import.meta.dirname, "team.html"),
        projector: path.resolve(import.meta.dirname, "projector.html"),
        admin: path.resolve(import.meta.dirname, "admin.html"),
        stakeholder: path.resolve(import.meta.dirname, "stakeholder.html"),
      },
    },
  },
  server: {
    // Dev only: forward API calls to the Python server.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
})
