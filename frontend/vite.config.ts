// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, nitro (build-only using cloudflare as a default target),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      // Pin the dev server port. Without this, the Lovable config picks 8080
      // and ignores the --port flag that run.py passes.
      host: "127.0.0.1",
      port: Number(process.env.JOI_FRONTEND_PORT ?? 5173),
      strictPort: true,
      proxy: {
        // In dev, /api/** → FastAPI backend (avoids CORS entirely in the browser).
        // The path is forwarded unchanged: the backend serves /api/chat etc.
        "/api": {
          target: process.env.JOI_BACKEND_URL ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  },
});
