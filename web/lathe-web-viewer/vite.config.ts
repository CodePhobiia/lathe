import { defineConfig } from "vite";

export default defineConfig({
  resolve: {
    alias: {
      // When running locally without a published @lathe/three package,
      // alias to the source-tree workspace path.
      "@lathe/three": new URL("../lathe-three/src/index.ts", import.meta.url).pathname,
    },
  },
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    target: "es2020",
  },
});
