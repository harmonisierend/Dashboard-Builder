import "@testing-library/jest-dom/vitest";

// jsdom implements neither ResizeObserver nor real layout, both of which
// @tanstack/react-virtual needs to compute which rows are "visible". A
// no-op observer plus a fixed non-zero viewport size lets the virtualizer
// render a plausible set of rows in tests instead of nothing.
class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = ResizeObserverMock;
}

Object.defineProperties(HTMLElement.prototype, {
  offsetHeight: { configurable: true, value: 600 },
  offsetWidth: { configurable: true, value: 800 },
  clientHeight: { configurable: true, value: 600 },
  clientWidth: { configurable: true, value: 800 },
});

// jsdom's own URL.createObjectURL produces a real-looking but unstable
// "blob:nodedata:<uuid>" string. ImageUpload/DesignPage call it to preview
// an upload; component tests want a stable, predictable value instead, so
// this always overrides it (not just when absent).
Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: () => "blob:mock-url",
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: () => {},
});
