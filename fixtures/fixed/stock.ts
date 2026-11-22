export class SettlementConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SettlementConflictError";
  }
}

export type StockPort = {
  /**
   * Decrements `sku` by `qty` in one atomic step. Returns false and leaves stock untouched when the
   * quantity on hand is smaller than `qty`.
   */
  reserve(sku: string, qty: number): boolean;
  release(sku: string, qty: number): void;
};

export type SettlementStore = {
  /**
   * Runs `run` at most once per `key`. A later call with the same `key` and `fingerprint` returns the
   * first result with `replayed: true`; the same `key` with a different `fingerprint` rejects with
   * `SettlementConflictError`. A run that throws is not recorded.
   */
  attempt<T>(
    key: string,
    fingerprint: string,
    run: () => Promise<T>,
  ): Promise<{ readonly value: T; readonly replayed: boolean }>;
};
