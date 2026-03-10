import type {
  AuthResponse,
  AuthUser,
  ScannerPayload,
  SnapshotPayload,
  StrategyBacktestPayload,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "http://127.0.0.1:8000";

type JsonMethod = "GET" | "POST";

function buildUrl(path: string, params?: Record<string, string | number>): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function fetchJson<T>(
  path: string,
  options?: {
    method?: JsonMethod;
    params?: Record<string, string | number>;
    body?: unknown;
    token?: string | null;
  },
): Promise<T> {
  const requestUrl = buildUrl(path, options?.params);
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (options?.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  let res: Response;
  try {
    res = await fetch(requestUrl, {
      method: options?.method ?? "GET",
      headers,
      body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Cannot reach API at ${API_BASE_URL}. Start backend (uvicorn) and database first. Original error: ${message}`,
    );
  }
  if (!res.ok) {
    const text = await res.text();
    let parsed: { detail?: unknown } | null = null;
    try {
      parsed = JSON.parse(text) as { detail?: unknown };
    } catch {
      parsed = null;
    }
    if (parsed && parsed.detail !== undefined) {
      throw new Error(
        `API ${res.status}: ${typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail)}`,
      );
    }
    throw new Error(`API ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

export async function registerUser(payload: {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}): Promise<AuthResponse> {
  return fetchJson<AuthResponse>("/auth/register", { method: "POST", body: payload });
}

export async function loginUser(payload: { identifier: string; password: string }): Promise<AuthResponse> {
  return fetchJson<AuthResponse>("/auth/login", { method: "POST", body: payload });
}

export async function getCurrentUser(token: string): Promise<AuthUser> {
  const payload = await fetchJson<{ user: AuthUser }>("/auth/me", { token });
  return payload.user;
}

export async function submitContact(payload: {
  full_name: string;
  email: string;
  subject: string;
  message: string;
}): Promise<{ status: string }> {
  return fetchJson<{ status: string }>("/public/contact", { method: "POST", body: payload });
}

export async function getSymbols(): Promise<string[]> {
  const payload = await fetchJson<{ symbols: string[] }>("/market/symbols");
  return payload.symbols ?? [];
}

export async function getSnapshot(params: {
  symbol: string;
  timeframe: string;
  candleLimit: number;
  historyLimit: number;
}): Promise<SnapshotPayload> {
  return fetchJson<SnapshotPayload>("/dashboard/snapshot", {
    params: {
      symbol: params.symbol,
      timeframe: params.timeframe,
      candle_limit: params.candleLimit,
      history_limit: params.historyLimit,
    },
  });
}

export async function getStrategyBacktest(params: {
  symbol: string;
  timeframe: string;
  strategy: string;
  candleLimit: number;
  costBps: number;
}): Promise<StrategyBacktestPayload> {
  return fetchJson<StrategyBacktestPayload>("/analytics/backtest/strategy", {
    params: {
      symbol: params.symbol,
      timeframe: params.timeframe,
      strategy: params.strategy,
      candle_limit: params.candleLimit,
      cost_bps: params.costBps,
    },
  });
}

export async function getScanner(params: {
  timeframe: string;
  signal: string;
  minConfidence: number;
  limit: number;
}): Promise<ScannerPayload> {
  return fetchJson<ScannerPayload>("/scanner/intraday", {
    params: {
      timeframe: params.timeframe,
      signal: params.signal,
      min_confidence: params.minConfidence,
      limit: params.limit,
    },
  });
}
