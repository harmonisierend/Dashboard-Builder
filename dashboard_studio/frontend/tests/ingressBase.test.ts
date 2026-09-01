import { describe, expect, it } from "vitest";
import { apiUrl } from "../src/lib/ingressBase";

describe("apiUrl", () => {
  it("resolves a path relative to a root page location", () => {
    window.history.pushState({}, "", "/");
    expect(apiUrl("api/status")).toBe(`${window.location.origin}/api/status`);
  });

  it("preserves a dynamic Ingress prefix in the current path", () => {
    window.history.pushState({}, "", "/api/hassio_ingress/abc123/");
    expect(apiUrl("api/registry")).toBe(
      `${window.location.origin}/api/hassio_ingress/abc123/api/registry`,
    );
  });

  it("strips a leading slash from the requested path so it can't override the current prefix", () => {
    window.history.pushState({}, "", "/api/hassio_ingress/abc123/");
    expect(apiUrl("/api/registry")).toBe(
      `${window.location.origin}/api/hassio_ingress/abc123/api/registry`,
    );
  });

  it("resolves relative to the directory of a nested current path", () => {
    window.history.pushState({}, "", "/api/hassio_ingress/abc123/some/sub/page");
    expect(apiUrl("api/status")).toBe(
      `${window.location.origin}/api/hassio_ingress/abc123/some/sub/api/status`,
    );
  });
});
