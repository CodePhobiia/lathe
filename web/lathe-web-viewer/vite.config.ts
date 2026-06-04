import { defineConfig } from "vite";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      // When running locally without a published @lathe/three package,
      // alias to the source-tree workspace path.
      "@lathe/three": resolve(here, "../lathe-three/src/index.ts"),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    fs: {
      allow: [
        resolve(here, "../.."),
      ],
    },
  },
  build: {
    target: "es2020",
  },
});
