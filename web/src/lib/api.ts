export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly retryAfterSeconds?: number;

  constructor(
    status: number,
    code: string,
    detail: string,
    retryAfterSeconds?: number,
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    if (retryAfterSeconds !== undefined) {
      this.retryAfterSeconds = retryAfterSeconds;
    }
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

type ErrorBody = {
  code: string;
  detail: string;
};

const UNKNOWN_ERROR_BODY: ErrorBody = {
  code: "unknown",
  detail: "Request failed",
};

function apiUrl(path: string): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }

  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  const normalizedPath = path.replace(/^\/+/, "");
  return new URL(normalizedPath, normalizedBase).toString();
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { code?: unknown }).code === "string" &&
    typeof (value as { detail?: unknown }).detail === "string"
  );
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  const text = await response.text();
  if (!text) {
    return UNKNOWN_ERROR_BODY;
  }

  try {
    const parsed: unknown = JSON.parse(text);
    if (isErrorBody(parsed)) {
      return parsed;
    }
  } catch {
    // Non-JSON bodies (proxy HTML, etc.) must not crash the client.
  }

  return UNKNOWN_ERROR_BODY;
}

function parseRetryAfterSeconds(header: string | null): number | undefined {
  if (header == null || header.trim() === "") {
    return undefined;
  }

  const seconds = Number.parseInt(header, 10);
  if (!Number.isFinite(seconds)) {
    return undefined;
  }

  return seconds;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "include",
  });

  if (!response.ok) {
    const { code, detail } = await readErrorBody(response);
    const retryAfterSeconds =
      response.status === 429
        ? parseRetryAfterSeconds(response.headers.get("Retry-After"))
        : undefined;
    throw new ApiError(response.status, code, detail, retryAfterSeconds);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
