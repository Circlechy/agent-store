import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { copyFileSync, mkdirSync, existsSync, readdirSync, statSync } from "fs";

// Simple plugin to copy extension files
function copyExtensionFiles() {
  return {
    name: "copy-extension-files",
    buildStart() {
      // Copy files at build start for watch mode
      this.addWatchFile(path.resolve(process.cwd(), "manifest.json"));
      this.addWatchFile(path.resolve(process.cwd(), "background.js"));
    },
    writeBundle() {
      const distDir = path.resolve(process.cwd(), "dist");
      const srcDir = process.cwd();

      // Copy manifest.json
      if (existsSync(path.join(srcDir, "manifest.json"))) {
        copyFileSync(
          path.join(srcDir, "manifest.json"),
          path.join(distDir, "manifest.json")
        );
      }

      // Copy background.js
      if (existsSync(path.join(srcDir, "background.js"))) {
        copyFileSync(
          path.join(srcDir, "background.js"),
          path.join(distDir, "background.js")
        );
      }

      // Copy icons directory
      const iconsSrc = path.join(srcDir, "icons");
      const iconsDest = path.join(distDir, "icons");
      if (existsSync(iconsSrc)) {
        mkdirSync(iconsDest, { recursive: true });
        const files = readdirSync(iconsSrc);
        for (const file of files) {
          const srcPath = path.join(iconsSrc, file);
          const destPath = path.join(iconsDest, file);
          if (statSync(srcPath).isFile()) {
            copyFileSync(srcPath, destPath);
          }
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), copyExtensionFiles()],
  base: "./",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        sidepanel: path.resolve(__dirname, "sidepanel/index.html"),
      },
    },
    emptyOutDir: true,
  },
  css: {
    postcss: "./postcss.config.mjs",
  },
});

