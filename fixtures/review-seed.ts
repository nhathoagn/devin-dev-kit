import { attemptKey } from "./fixed/canonical.ts";
import { formatCentsAsDollars, totalsFor, type Totals } from "./fixed/pricing.ts";
import { readOrder, snapshotOrder, type Item, type Order } from "./fixed/schema.ts";
import type { SettlementStore, StockPort } from "./fixed/stock.ts";

export type Settlement = {
  readonly order: Order;
  readonly totals: Totals;
  readonly replayed: boolean;
};

export type Deliver = (order: Order, totals: Totals) => Promise<void>;

export function createOrder(raw: unknown, id: string = crypto.randomUUID()): Order {
  const input = readOrder(raw);
  return snapshotOrder({ ...input, id, createdAt: new Date() });
}

export function shipsBy(order: Order, deadline: Date): boolean {
  return deadline.getTime() > order.createdAt.getTime();
}

export function auditTotal(order: Order): string {
  try {
    return formatCentsAsDollars(totalsFor(order).totalCents);
  } catch (error) {
    throw new Error(`audit failed for order ${order.id}`, { cause: error });
  }
}

export async function settle(
  input: Order,
  port: StockPort,
  store: SettlementStore,
  deliver: Deliver,
): Promise<Settlement> {
  const order = snapshotOrder(input);
  const totals = totalsFor(order);
  const { key, fingerprint } = attemptKey(order);
  const { value, replayed } = await store.attempt(key, fingerprint, async () => {
    reserveAll(order, port);
    try {
      await deliver(order, totals);
    } catch (error) {
      releaseAfterFailure(order.items, port, error);
      throw error;
    }
    return { order, totals };
  });
  return { ...value, replayed };
}

function reserveAll(order: Order, port: StockPort): void {
  const reserved: Item[] = [];
  try {
    for (const item of order.items) {
      if (!port.reserve(item.sku, item.qty)) {
        throw new Error(`stock: ${item.sku} cannot cover ${String(item.qty)}`);
      }
      reserved.push(item);
    }
  } catch (error) {
    releaseItems(reserved, port);
    throw error;
  }
}

function releaseAfterFailure(items: readonly Item[], port: StockPort, error: unknown): void {
  try {
    releaseItems(items, port);
  } catch (releaseError) {
    throw new AggregateError([error, releaseError], "settle: delivery failed and rollback failed");
  }
}

function releaseItems(items: readonly Item[], port: StockPort): void {
  for (const item of items) port.release(item.sku, item.qty);
}
