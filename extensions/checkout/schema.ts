import * as v from "valibot";

const MAX_UNITS = 1_000_000_000;

const Sku = v.pipe(
  v.string(),
  v.trim(),
  v.minLength(1, "sku is required"),
  v.maxLength(64, "sku is too long"),
  v.regex(/^[A-Za-z0-9._:-]+$/, "sku has unsupported characters"),
);

const Units = v.pipe(
  v.number(),
  v.safeInteger("must be a safe whole number"),
  v.minValue(1, "must be at least 1"),
  v.maxValue(MAX_UNITS, "is too large"),
);

export const OrderId = v.pipe(
  v.string(),
  v.trim(),
  v.toLowerCase(),
  v.minLength(1, "order id is required"),
  v.maxLength(64, "order id is too long"),
  v.regex(/^[a-z0-9._:-]+$/, "order id has unsupported characters"),
);

export const CartItemSchema = v.strictObject({
  sku: Sku,
  qty: Units,
  price: Units,
});

export const CustomerSchema = v.strictObject({
  id: v.pipe(v.string(), v.trim(), v.minLength(1, "customer id is required"), v.maxLength(64)),
  tier: v.pipe(v.string(), v.trim(), v.toLowerCase(), v.picklist(["gold", "silver", "bronze"], "unknown tier")),
  email: v.pipe(
    v.string(),
    v.trim(),
    v.minLength(3, "email is required"),
    v.maxLength(254),
    v.regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "email is not an address"),
  ),
  region: v.pipe(v.string(), v.trim(), v.toLowerCase(), v.picklist(["north", "south", "central"], "unknown region")),
  vip: v.boolean(),
});

export const OrderSchema = v.pipe(
  v.strictObject({
    id: OrderId,
    items: v.pipe(v.array(CartItemSchema), v.minLength(1, "at least one item"), v.maxLength(500)),
    customer: CustomerSchema,
    couponCode: v.optional(v.nullable(v.pipe(v.string(), v.trim(), v.toUpperCase(), v.maxLength(32)))),
    express: v.optional(v.nullable(v.boolean())),
    giftWrap: v.optional(v.nullable(v.boolean())),
    note: v.optional(v.nullable(v.pipe(v.string(), v.trim(), v.maxLength(500)))),
  }),
  v.check(
    (order) => order.items.every((item) => Number.isSafeInteger(item.price * item.qty)),
    "line total is too large",
  ),
  v.check(
    (order) => Number.isSafeInteger(order.items.reduce((sum, item) => sum + item.price * item.qty, 0)),
    "order total is too large",
  ),
);

export type Order = v.InferOutput<typeof OrderSchema>;
export type CartItem = Order["items"][number];

export type ParsedOrder = { ok: true; order: Order } | { ok: false; problems: string[] };

export function readOrder(input: unknown): ParsedOrder {
  const result = v.safeParse(OrderSchema, input);
  if (result.success) return { ok: true, order: result.output };
  const problems = result.issues.map((issue) => {
    const path = issue.path?.map((segment) => String(segment.key)).join(".") ?? "";
    return (path ? path + ": " : "") + issue.message;
  });
  return { ok: false, problems };
}
