import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// Version affichée dans l'interface et utilisée pour contourner le cache des fichiers du moteur Pyodide.
function appVersion() {
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA.slice(0, 7);
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return `local-${Date.now()}`;
  }
}

// base "./" + single-file : dist/index.html fonctionne sur GitHub Pages comme ouvert hors ligne
// (instantané et réponses pré-enregistrées embarqués ; le moteur Pyodide et le relais exigent le réseau).
export default defineConfig({
  root: "web",
  base: "./",
  publicDir: "public",
  build: { outDir: "../dist", emptyOutDir: true, chunkSizeWarningLimit: 4000 },
  plugins: [viteSingleFile()],
  define: { __APP_VERSION__: JSON.stringify(appVersion()) },
  worker: { format: "iife" },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
