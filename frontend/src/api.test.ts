import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  ApiError,
  describeApiError,
  fetchExampleScenario,
  fetchWorkspace,
  resetApiBaseUrlCache,
  saveWorkspace
} from "./api";
import { createEmptyScenario } from "./types";

describe("api client", () => {
  beforeEach(() => {
    resetApiBaseUrlCache();
    window.history.replaceState({}, "", "/");
  });

  test("discovers a reachable backend in dev mode when 8000 is unavailable", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "http://127.0.0.1:8000/api/health") {
        throw new TypeError("fetch failed");
      }
      if (url === "http://127.0.0.1:8001/api/health") {
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "http://127.0.0.1:8001/api/example") {
        return new Response(JSON.stringify(createEmptyScenario()), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const scenario = await fetchExampleScenario();

    expect(scenario.settings.groups_per_period).toBe(10);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8001/api/example", undefined);
  });

  test("returns a helpful HTTP error message", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "http://127.0.0.1:8000/api/health") {
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "http://127.0.0.1:8000/api/example") {
        return new Response(JSON.stringify({ detail: "Example generation failed." }), {
          status: 500,
          headers: { "Content-Type": "application/json" }
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    }));

    await expect(fetchExampleScenario()).rejects.toMatchObject({
      kind: "http",
      status: 500
    });

    try {
      await fetchExampleScenario();
    } catch (error) {
      expect(describeApiError(error)).toContain("Backend returned HTTP 500");
      expect(describeApiError(error)).toContain("Example generation failed.");
    }
  });

  test("returns a helpful parse error message for malformed JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "http://127.0.0.1:8000/api/health") {
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "http://127.0.0.1:8000/api/example") {
        return new Response("not-json", {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    }));

    try {
      await fetchExampleScenario();
      throw new Error("Expected request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(describeApiError(error)).toContain("not valid JSON");
    }
  });

  test("returns a helpful network error message", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL) => {
      throw new TypeError("Failed to fetch");
    }));

    try {
      await fetchExampleScenario();
      throw new Error("Expected request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(describeApiError(error)).toContain("Could not reach the backend");
      expect(describeApiError(error)).toContain("/api/example");
    }
  });

  test("loads and saves workspace state through the API", async () => {
    const workspace = { scenario: createEmptyScenario(), saved_proposals: [] };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "http://127.0.0.1:8000/api/health") {
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url === "http://127.0.0.1:8000/api/workspace") {
        if (init?.method === "POST") {
          return new Response(String(init.body), {
            status: 200,
            headers: { "Content-Type": "application/json" }
          });
        }
        return new Response(JSON.stringify(workspace), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchWorkspace()).toEqual(workspace);
    expect(await saveWorkspace(workspace)).toEqual(workspace);
  });
});
