import stringify from "fast-json-stable-stringify";
import { createHash } from "node:crypto";

import type { Order } from "./schema.ts";

function canonicalItems(order: Order): [sku: string, qty: number, price: number][] {
  const grouped = new Map<string, [sku: string, qty: number, price: number]>();
  for (const item of order.items) {
    const key = `${item.sku}\u0000${String(item.price)}`;
    const previous = grouped.get(key);
    grouped.set(key, previous ? [item.sku, previous[1] + item.qty, item.price] : [item.sku, item.qty, item.price]);
  }
  return [...grouped.values()].sort((left, right) => {
    if (left[0] !== right[0]) return left[0] < right[0] ? -1 : 1;
    return left[2] - right[2];
  });
}

export function canonicalForm(order: Order): string {
  return stringify({
    id: order.id,
    items: canonicalItems(order),
    customer: [order.customer.id, order.customer.tier, order.customer.region, order.customer.vip],
    email: order.customer.email,
    couponCode: order.couponCode ?? "",
    express: order.express === true,
    giftWrap: order.giftWrap === true,
    note: order.note ?? "",
  });
}

export function idempotencyKey(order: Order): string {
  return createHash("sha256").update(canonicalForm(order)).digest("hex");
}
