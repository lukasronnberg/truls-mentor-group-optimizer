import type {
  BlockedPair,
  Mentor,
  ScenarioInput,
  SavedProposal,
  SolveResponse,
  ValidationResponse,
  WorkspaceState
} from "./types";

type HttpMethod = "GET" | "POST";
type ApiErrorKind = "network" | "http" | "parse";

const DEV_BACKEND_PORTS = [8000, 8001, 8002, 8003, 8004, 8005];
const DISCOVERY_TIMEOUT_MS = 1500;

let cachedApiBaseUrl: string | null | undefined;

export class ApiError extends Error {
  kind: ApiErrorKind;
  method: HttpMethod;
  path: string;
  url: string;
  status: number | null;
  responseBody: string | null;
  causeText: string | null;

  constructor({
    kind,
    method,
    path,
    url,
    status = null,
    responseBody = null,
    causeText = null
  }: {
    kind: ApiErrorKind;
    method: HttpMethod;
    path: string;
    url: string;
    status?: number | null;
    responseBody?: string | null;
    causeText?: string | null;
  }) {
    super(buildApiErrorMessage({ kind, method, path, url, status, responseBody, causeText }));
    this.name = "ApiError";
    this.kind = kind;
    this.method = method;
    this.path = path;
    this.url = url;
    this.status = status;
    this.responseBody = responseBody;
    this.causeText = causeText;
  }
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function getConfiguredApiBaseUrl(): string | null {
  const rawValue = import.meta.env.VITE_API_BASE_URL?.trim();
  return rawValue ? trimTrailingSlash(rawValue) : null;
}

function isDevFrontend(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return import.meta.env.DEV && window.location.port === "5173";
}

function buildUrl(baseUrl: string | null, path: string): string {
  return baseUrl ? `${baseUrl}${path}` : path;
}

async function tryHealthCheck(origin: string): Promise<boolean> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DISCOVERY_TIMEOUT_MS);
  try {
    const response = await fetch(`${origin}/api/health`, {
      method: "GET",
      signal: controller.signal
    });
    if (!response.ok) {
      return false;
    }
    const payload = (await response.json()) as { status?: string };
    return payload.status === "ok";
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function discoverApiBaseUrl(): Promise<string | null> {
  if (!isDevFrontend()) {
    return null;
  }
  if (cachedApiBaseUrl !== undefined) {
    return cachedApiBaseUrl;
  }

  const host = window.location.hostname || "127.0.0.1";
  for (const port of DEV_BACKEND_PORTS) {
    const origin = `${window.location.protocol}//${host}:${port}`;
    if (await tryHealthCheck(origin)) {
      cachedApiBaseUrl = origin;
      return origin;
    }
  }

  cachedApiBaseUrl = null;
  return null;
}

async function resolveApiBaseUrl(): Promise<string | null> {
  const configuredBaseUrl = getConfiguredApiBaseUrl();
  if (configuredBaseUrl) {
    return configuredBaseUrl;
  }
  return discoverApiBaseUrl();
}

async function readErrorBody(response: Response): Promise<string | null> {
  const responseText = await response.text();
  if (!responseText) {
    return null;
  }
  try {
    const parsed = JSON.parse(responseText) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    return responseText;
  } catch {
    return responseText;
  }
}

async function parseJsonResponse<T>(response: Response, context: { method: HttpMethod; path: string; url: string }): Promise<T> {
  if (!response.ok) {
    throw new ApiError({
      kind: "http",
      method: context.method,
      path: context.path,
      url: context.url,
      status: response.status,
      responseBody: await readErrorBody(response)
    });
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiError({
      kind: "parse",
      method: context.method,
      path: context.path,
      url: context.url,
      status: response.status,
      causeText: error instanceof Error ? error.message : "Invalid JSON response."
    });
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method?.toUpperCase() as HttpMethod | undefined) ?? "GET";
  const baseUrl = await resolveApiBaseUrl();
  const url = buildUrl(baseUrl, path);

  try {
    const response = await fetch(url, init);
    return parseJsonResponse<T>(response, { method, path, url });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError({
      kind: "network",
      method,
      path,
      url,
      causeText: error instanceof Error ? error.message : "Network request failed."
    });
  }
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const method = (init?.method?.toUpperCase() as HttpMethod | undefined) ?? "GET";
  const baseUrl = await resolveApiBaseUrl();
  const url = buildUrl(baseUrl, path);

  try {
    const response = await fetch(url, init);
    if (!response.ok) {
      throw new ApiError({
        kind: "http",
        method,
        path,
        url,
        status: response.status,
        responseBody: await readErrorBody(response)
      });
    }
    return response.blob();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError({
      kind: "network",
      method,
      path,
      url,
      causeText: error instanceof Error ? error.message : "Network request failed."
    });
  }
}

function buildApiErrorMessage({
  kind,
  method,
  path,
  url,
  status,
  responseBody,
  causeText
}: {
  kind: ApiErrorKind;
  method: HttpMethod;
  path: string;
  url: string;
  status: number | null;
  responseBody: string | null;
  causeText: string | null;
}): string {
  if (kind === "network") {
    return `Network error while calling ${method} ${path} at ${url}. ${causeText ?? "The backend may not be running, the dev proxy may be pointing at the wrong port, or the request may have been blocked by the browser."}`;
  }
  if (kind === "parse") {
    return `Invalid JSON response from ${method} ${path} at ${url}.${status ? ` HTTP ${status}.` : ""} ${causeText ?? ""}`.trim();
  }
  return `API request failed for ${method} ${path} at ${url} with HTTP ${status ?? "unknown"}.${responseBody ? ` ${responseBody}` : ""}`;
}

export function describeApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : "Unexpected error.";
  }
  if (error.kind === "network") {
    return `Could not reach the backend for ${error.method} ${error.path}. Tried ${error.url}. Start the backend, verify the API base URL or proxy target, and retry.`;
  }
  if (error.kind === "parse") {
    return `The backend responded to ${error.method} ${error.path}, but the response was not valid JSON. ${error.causeText ?? ""}`.trim();
  }
  return `Backend returned HTTP ${error.status ?? "unknown"} for ${error.method} ${error.path}.${error.responseBody ? ` ${error.responseBody}` : ""}`;
}

export async function fetchExampleScenario(): Promise<ScenarioInput> {
  return requestJson<ScenarioInput>("/api/example");
}

export async function fetchWorkspace(): Promise<WorkspaceState> {
  return requestJson<WorkspaceState>("/api/workspace");
}

export async function saveWorkspace(payload: {
  scenario: ScenarioInput;
  saved_proposals: SavedProposal[];
}): Promise<WorkspaceState> {
  return requestJson<WorkspaceState>("/api/workspace", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function validateScenario(scenario: ScenarioInput): Promise<ValidationResponse> {
  return requestJson<ValidationResponse>("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scenario)
  });
}

export async function solveScenario(scenario: ScenarioInput): Promise<SolveResponse> {
  return requestJson<SolveResponse>("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scenario)
  });
}

export async function importScenarioJson(file: File): Promise<ScenarioInput> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<ScenarioInput>("/api/import/scenario-json", {
    method: "POST",
    body: form
  });
}

export async function importMentorsCsv(file: File): Promise<Mentor[]> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<Mentor[]>("/api/import/mentors-csv", {
    method: "POST",
    body: form
  });
}

export async function importBlockedPairsCsv(file: File): Promise<BlockedPair[]> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<BlockedPair[]>("/api/import/blocked-pairs-csv", {
    method: "POST",
    body: form
  });
}

export async function exportGroupsCsv(solution: SolveResponse): Promise<Blob> {
  return requestBlob("/api/export/groups-csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(solution)
  });
}

export function resetApiBaseUrlCache() {
  cachedApiBaseUrl = undefined;
}
