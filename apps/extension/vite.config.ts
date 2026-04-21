import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = fileURLToPath(new URL(".", import.meta.url));
const manifestPath = path.resolve(rootDir, "manifest.json");
const sourceManifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8")) as Record<string, any>;

function buildManifest() {
  return {
    ...sourceManifest,
    background: {
      ...(sourceManifest.background ?? {}),
      service_worker: "src/background/service-worker.js",
      type: "module",
    },
    side_panel: {
      ...(sourceManifest.side_panel ?? {}),
      default_path: "public/sidepanel.html",
    },
    content_scripts: Array.isArray(sourceManifest.content_scripts)
      ? sourceManifest.content_scripts.map((script: Record<string, any>) => ({
          ...script,
          js: Array.isArray(script.js)
            ? script.js.map((entry: string) => entry.replace(/\.ts$/, ".js"))
            : script.js,
        }))
      : [],
    icons: Object.fromEntries(
      Object.entries(sourceManifest.icons ?? {}).map(([size, iconPath]) => [
        size,
        String(iconPath).replace(/^public\//, ""),
      ])
    ),
  };
}

function emitExtensionManifest() {
  return {
    name: "emit-extension-manifest",
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "manifest.json",
        source: JSON.stringify(buildManifest(), null, 2),
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), emitExtensionManifest()],
  resolve: {
    alias: {
      "@itx/portal-adapters": path.resolve(rootDir, "../../packages/portal-adapters/src"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "public/sidepanel": path.resolve(rootDir, "public/sidepanel.html"),
        "src/background/service-worker": path.resolve(rootDir, "src/background/service-worker.ts"),
        "src/content/index": path.resolve(rootDir, "src/content/index.ts"),
      },
      output: {
        entryFileNames: "[name].js",
      },
    },
  },
});
