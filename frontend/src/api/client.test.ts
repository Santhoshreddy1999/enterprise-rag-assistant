import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

const fetchMock = vi.fn();

describe("API client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("uses the versioned contract and cookie credentials for authentication", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ id: "user-1", email: "engineer@example.com" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");

    const user = await api.login({
      email: "engineer@example.com",
      password: "correct horse battery staple",
    });

    expect(user.email).toBe("engineer@example.com");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/login");
    expect(options.credentials).toBe("include");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      email: "engineer@example.com",
      password: "correct horse battery staple",
    });
    expect(new Headers(options.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("uploads the contract multipart field without forcing a content type", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "doc-1",
          filename: "handbook.pdf",
          media_type: "application/pdf",
          status: "ready",
          chunk_count: 12,
          created_at: "2026-11-09T10:00:00Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await api.uploadDocument(
      new File(["document"], "handbook.pdf", { type: "application/pdf" }),
    );

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/documents");
    expect(options.credentials).toBe("include");
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBeInstanceOf(File);
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
  });

  it("surfaces backend detail and status through ApiError", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unsupported file type." }), {
        status: 415,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const request = api.uploadDocument(
      new File(["data"], "archive.zip", { type: "application/zip" }),
    );

    await expect(request).rejects.toMatchObject({
      name: "ApiError",
      message: "Unsupported file type.",
      status: 415,
    });
  });
});
