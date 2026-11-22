import * as v from "valibot";

const DEFAULT_INTERVAL_MS = 2000;
const DEFAULT_TIMEOUT_MS = 2000;
const MIN_INTERVAL_MS = 250;

const StockPayloadSchema = v.strictObject({
  qty: v.pipe(v.number(), v.integer(), v.minValue(0), v.maxValue(Number.MAX_SAFE_INTEGER)),
});

export type StockSnapshotPort = { applySnapshot(sku: string, qty: number): void };

export type PollingOptions = {
  readonly onError: (error: unknown) => void;
  readonly intervalMs?: number;
  readonly timeoutMs?: number;
};

export async function pollStockOnce(
  port: StockSnapshotPort,
  skus: readonly string[],
  baseUrl: string,
  options: PollingOptions,
  signal?: AbortSignal,
): Promise<void> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const isAborted = (): boolean => signal?.aborted === true;
  await Promise.all(
    skus.map(async (sku) => {
      if (isAborted()) return;
      try {
        const response = await fetch(`${baseUrl}/${encodeURIComponent(sku)}`, {
          signal: AbortSignal.timeout(timeoutMs),
        });
        if (!response.ok) throw new Error(`stock ${sku}: status ${String(response.status)}`);
        const payload: unknown = await response.json();
        if (isAborted()) return;
        port.applySnapshot(sku, v.parse(StockPayloadSchema, payload).qty);
      } catch (error) {
        options.onError(error);
      }
    }),
  );
}

export function startStockPolling(
  port: StockSnapshotPort,
  skus: readonly string[],
  baseUrl: string,
  options: PollingOptions,
): () => void {
  const controller = new AbortController();
  const intervalMs = Math.max(MIN_INTERVAL_MS, Math.trunc(options.intervalMs ?? DEFAULT_INTERVAL_MS));
  let running = false;
  const timer = setInterval(() => {
    if (running || controller.signal.aborted) return;
    running = true;
    pollStockOnce(port, skus, baseUrl, options, controller.signal).then(
      () => {
        running = false;
      },
      (error: unknown) => {
        running = false;
        options.onError(error);
      },
    );
  }, intervalMs);
  return () => {
    controller.abort();
    clearInterval(timer);
  };
}
