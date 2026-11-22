import { copyResult, type CheckoutResult } from "./pricing.ts";

export type Reservation = { sku: string; qty: number };

export type Attempt = {
  key: string;
  digest: string;
  reservations: readonly Reservation[];
  render: () => CheckoutResult;
};

export type AttemptOutcome =
  | { kind: "settled"; result: CheckoutResult }
  | { kind: "replay"; result: CheckoutResult }
  | { kind: "conflict" }
  | { kind: "short"; short: string[] };

/**
 * One durable unit of work: reserve the idempotency key, deduct every reservation
 * or none, and store the receipt — all inside one transaction. A crash between the
 * deduct and the receipt is not representable, so an interrupted attempt leaves
 * both the stock and the key untouched and the retry starts clean.
 *
 * The contract is asynchronous on purpose: a database adapter cannot answer
 * synchronously, and every invariant above has to hold across the await.
 */
export interface CheckoutStore {
  attempt(entry: Attempt): Promise<AttemptOutcome>;
}

export class MemoryCheckoutStore implements CheckoutStore {
  private readonly stock = new Map<string, number>();
  private readonly settled = new Map<string, { digest: string; result: CheckoutResult }>();
  private tail: Promise<undefined> = Promise.resolve(undefined);

  static from(record: Record<string, number>): MemoryCheckoutStore {
    const store = new MemoryCheckoutStore();
    for (const [sku, qty] of Object.entries(record)) {
      if (Number.isSafeInteger(qty) && qty >= 0) store.stock.set(sku, qty);
    }
    return store;
  }

  read(sku: string): number | undefined {
    return this.stock.get(sku);
  }

  restock(sku: string, qty: number): void {
    if (!Number.isSafeInteger(qty) || qty < 0) return;
    this.stock.set(sku, (this.stock.get(sku) ?? 0) + qty);
  }

  async attempt(entry: Attempt): Promise<AttemptOutcome> {
    const gate = Promise.withResolvers<undefined>();
    const previous = this.tail;
    this.tail = gate.promise;
    await previous;
    try {
      return this.settle(entry);
    } finally {
      gate.resolve(undefined);
    }
  }

  private settle(entry: Attempt): AttemptOutcome {
    const existing = this.settled.get(entry.key);
    if (existing) {
      if (existing.digest !== entry.digest) return { kind: "conflict" };
      return { kind: "replay", result: copyResult(existing.result) };
    }

    const needed = new Map<string, number>();
    for (const { sku, qty } of entry.reservations) {
      needed.set(sku, (needed.get(sku) ?? 0) + qty);
    }
    const short: string[] = [];
    for (const [sku, qty] of needed) {
      const available = this.stock.get(sku);
      if (available === undefined || available < qty) short.push(sku);
    }
    if (short.length > 0) return { kind: "short", short };

    const rendered = entry.render();
    for (const [sku, qty] of needed) {
      this.stock.set(sku, (this.stock.get(sku) as number) - qty);
    }
    this.settled.set(entry.key, { digest: entry.digest, result: copyResult(rendered) });
    return { kind: "settled", result: copyResult(rendered) };
  }
}
