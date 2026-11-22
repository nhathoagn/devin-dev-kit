import { idempotencyKey } from "./canonical.ts";
import { couponProblem, priceOrder, representable, reject, type CheckoutResult } from "./pricing.ts";
import { readOrder, type Order } from "./schema.ts";
import type { CheckoutStore } from "./store.ts";

export type Channel = "retail" | "b2b";

export interface CheckoutDeps {
  store: CheckoutStore;
  now?: () => Date;
}

function render(order: Order, channel: Channel, now: () => Date): CheckoutResult {
  const priced = priceOrder(order, channel === "b2b");
  if (!representable(priced)) throw new RangeError("order total is too large");
  return {
    ...priced,
    customerId: order.customer.id,
    status: "ok",
    problems: [],
    servedFromCache: false,
    createdAt: now().toISOString(),
  };
}

export async function checkout(
  input: unknown,
  channel: Channel,
  deps: CheckoutDeps,
): Promise<CheckoutResult> {
  const now = deps.now ?? (() => new Date());
  const parsed = readOrder(input);
  if (!parsed.ok) return reject(null, parsed.problems, null, now);
  const order = parsed.order;

  const problem = couponProblem(order.couponCode);
  if (problem) return reject(order.id, [problem], order.customer.id, now);

  if (!representable(priceOrder(order, channel === "b2b"))) {
    return reject(order.id, ["order total is too large"], order.customer.id, now);
  }

  const outcome = await deps.store.attempt({
    key: channel + ":" + order.id,
    digest: idempotencyKey(order),
    reservations: order.items.map((item) => ({ sku: item.sku, qty: item.qty })),
    render: () => render(order, channel, now),
  });

  if (outcome.kind === "replay") return { ...outcome.result, servedFromCache: true };
  if (outcome.kind === "conflict") {
    return reject(
      order.id,
      ["order id " + order.id + " was already settled with a different payload"],
      order.customer.id,
      now,
    );
  }
  if (outcome.kind === "short") {
    return reject(
      order.id,
      outcome.short.map((sku) => sku + ": insufficient stock"),
      order.customer.id,
      now,
    );
  }
  return outcome.result;
}
