import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { ImageUpload } from "../src/components/design/ImageUpload";

let uploadCallCount = 0;

const server = setupServer(
  http.post("/api/design/upload", () => {
    uploadCallCount += 1;
    return HttpResponse.json({ upload_id: "upload-1", media_type: "image/png", size_bytes: 3 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  uploadCallCount = 0;
});
afterAll(() => server.close());

function getFileInput(): HTMLInputElement {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

function getDropZone(): HTMLElement {
  return screen.getByRole("button", {
    name: /Design-Referenz hierher ziehen oder klicken zum Auswählen/,
  });
}

describe("ImageUpload", () => {
  it("shows the copyright/abstraction-only disclaimer", () => {
    render(<ImageUpload onUploaded={vi.fn()} />);
    expect(
      screen.getByText(/dient nur der Ableitung abstrakter Design-Token/),
    ).toBeInTheDocument();
  });

  // Drag-and-drop, not userEvent.upload(), for the two rejection cases:
  // a real browser's file picker itself filters by the input's `accept`
  // attribute, but drag-and-drop does not -- validate()'s client-side
  // check exists precisely for that unfiltered path (userEvent.upload()
  // faithfully emulates the accept-attribute filtering too, so it can't
  // even deliver a non-matching file to the component to reject).
  it("rejects a disallowed MIME type dropped onto the zone, without calling the API", async () => {
    render(<ImageUpload onUploaded={vi.fn()} />);

    const file = new File(["%PDF-1.4"], "test.pdf", { type: "application/pdf" });
    fireEvent.drop(getDropZone(), { dataTransfer: { files: [file] } });

    expect(await screen.findByText(/Nicht unterstützter Dateityp/)).toBeInTheDocument();
    expect(uploadCallCount).toBe(0);
  });

  it("rejects an oversized file dropped onto the zone, without calling the API", async () => {
    render(<ImageUpload onUploaded={vi.fn()} />);

    const oversized = new File([new Uint8Array(6_000_001)], "big.png", { type: "image/png" });
    fireEvent.drop(getDropZone(), { dataTransfer: { files: [oversized] } });

    expect(await screen.findByText(/zu groß/)).toBeInTheDocument();
    expect(uploadCallCount).toBe(0);
  });

  it("uploads a valid file and calls onUploaded with the upload id and a preview URL", async () => {
    const user = userEvent.setup();
    const onUploaded = vi.fn();
    render(<ImageUpload onUploaded={onUploaded} />);

    const file = new File(["fake-png-bytes"], "test.png", { type: "image/png" });
    await user.upload(getFileInput(), file);

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith("upload-1", "blob:mock-url"));
    expect(uploadCallCount).toBe(1);
  });
});
