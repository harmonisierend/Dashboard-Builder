import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `base: './'` is required, not cosmetic: HA serves this app under a
// per-installation Ingress prefix (e.g. /api/hassio_ingress/<hash>/) that
// is only known at runtime. Relative asset paths resolve correctly against
// whatever prefix is already in the page URL; an absolute base would break
// as soon as it's served through Ingress instead of `vite dev`.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
  },
});
