import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// base "./" + single-file : dist/index.html fonctionne sur GitHub Pages comme ouvert hors ligne
// (instantané et réponses pré-enregistrées embarqués ; le moteur Pyodide et le relais exigent le réseau).
export default defineConfig({
  root: "web",
  base: "./",
  publicDir: "public",
  build: { outDir: "../dist", emptyOutDir: true, chunkSizeWarningLimit: 4000 },
  plugins: [viteSingleFile()],
  worker: { format: "iife" },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
