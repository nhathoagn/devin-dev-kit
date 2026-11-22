import { attemptKey } from "./canonical.ts";
import type { Totals } from "./pricing.ts";
import type { Order } from "./schema.ts";

const DEFAULT_ATTEMPTS = 3;
const DEFAULT_TIMEOUT_MS = 2000;
const DEFAULT_BACKOFF_MS = 100;

export type DeliveryOptions = {
  readonly attempts?: number;
  readonly timeoutMs?: number;
  readonly backoffMs?: number;
};

type AttemptResult = { readonly ok: boolean; readonly retryable: boolean; readonly failure: unknown };

export async function notifyWarehouse(
  url: string,
  token: string,
  order: Order,
  totals: Totals,
  options: DeliveryOptions = {},
): Promise<void> {
  const target = new URL(url);
  if (token.length === 0) throw new RangeError("delivery: empty token");
  const attempts = Math.max(1, Math.trunc(options.attempts ?? DEFAULT_ATTEMPTS));
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const backoffMs = options.backoffMs ?? DEFAULT_BACKOFF_MS;
  const init = buildInit(token, attemptKey(order).key, order, totals);
  let failure: unknown = new Error("delivery: no attempt made");
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const outcome = await attemptOnce(target, init, timeoutMs);
    if (outcome.ok) return;
    failure = outcome.failure;
    if (!outcome.retryable) break;
    if (attempt < attempts) await sleep(backoffMs * 2 ** (attempt - 1));
  }
  throw new Error(`delivery: gave up after ${String(attempts)} attempts`, { cause: failure });
}

function buildInit(token: string, key: string, order: Order, totals: Totals): RequestInit {
  return {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
      "idempotency-key": key,
    },
    body: JSON.stringify({ order, totals }),
  };
}

async function attemptOnce(target: URL, init: RequestInit, timeoutMs: number): Promise<AttemptResult> {
  try {
    const response = await fetch(target, { ...init, signal: AbortSignal.timeout(timeoutMs) });
    if (response.body !== null) await response.body.cancel();
    if (response.ok) return { ok: true, retryable: false, failure: undefined };
    return {
      ok: false,
      retryable: isRetryable(response.status),
      failure: new Error(`delivery: rejected with status ${String(response.status)}`),
    };
  } catch (error) {
    return { ok: false, retryable: true, failure: error };
  }
}

function isRetryable(status: number): boolean {
  return status === 408 || status === 429 || status >= 500;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
