/**
 * Home Assistant serves this app under a per-installation Ingress prefix
 * (e.g. /api/hassio_ingress/<hash>/) that is only known at runtime and can
 * differ between installations -- it must never be baked into the build or
 * parsed from response headers client-side. Resolving every request URL
 * relative to the current page URL is the only approach that works
 * unconditionally, whether served through Ingress, `vite dev`, or a bare
 * `docker run` with no Ingress at all.
 */
export function apiUrl(path: string): string {
  const relativePath = path.replace(/^\/+/, "");
  return new URL(relativePath, window.location.href).toString();
}
