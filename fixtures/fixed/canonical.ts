import type { Order } from "./schema.ts";

type AttemptKey = { readonly key: string; readonly fingerprint: string };

export function attemptKey(order: Order): AttemptKey {
  const items = order.items
    .map((item) => `${encode(item.sku)}x${item.qty.toString(36)}x${item.unitCents.toString(36)}`)
    .sort();
  const fingerprint = [encode(order.channel), encode(order.coupon ?? ""), ...items].join(";");
  return { key: encode(order.id), fingerprint };
}

function encode(value: string): string {
  return `${String(value.length)}:${value}`;
}
