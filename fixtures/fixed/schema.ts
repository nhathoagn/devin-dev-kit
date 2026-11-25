import * as v from "valibot";

const CHANNELS = ["web", "mobile", "partner"] as const;
const COUPONS = ["SAVE10", "SAVE20"] as const;

export type Channel = (typeof CHANNELS)[number];
export type Coupon = (typeof COUPONS)[number];

const MAX_CENTS = 1_000_000_000_000_000;
const MAX_UNIT_CENTS = 1_000_000_000;
const MAX_ITEMS = 100;
const MAX_QTY = 999;
const MONEY_PATTERN = /^(\d{1,12})(?:\.(\d{1,2}))?$/;

const ItemSchema = v.strictObject({
  sku: v.pipe(
    v.string(),
    v.minLength(1),
    v.maxLength(64),
    v.check((sku) => sku === sku.trim(), "sku: no surrounding whitespace"),
  ),
  qty: v.pipe(v.number(), v.integer(), v.minValue(1), v.maxValue(MAX_QTY)),
  unitCents: v.pipe(v.number(), v.integer(), v.minValue(0), v.maxValue(MAX_UNIT_CENTS)),
});

const orderFields = {
  channel: v.picklist(CHANNELS),
  items: v.pipe(v.array(ItemSchema), v.minLength(1), v.maxLength(MAX_ITEMS)),
  coupon: v.optional(v.picklist(COUPONS)),
};

const OrderInputSchema = v.strictObject(orderFields);

const OrderSchema = v.strictObject({
  ...orderFields,
  id: v.pipe(
    v.string(),
    v.minLength(1),
    v.maxLength(128),
    v.check((id) => id === id.trim(), "id: no surrounding whitespace"),
  ),
  createdAt: v.date(),
});

const MoneyTextSchema = v.pipe(
  v.string(),
  v.regex(MONEY_PATTERN, "money: digits with at most 2 decimals"),
);

export type Item = v.InferOutput<typeof ItemSchema>;
export type OrderInput = v.InferOutput<typeof OrderInputSchema>;
export type Order = v.InferOutput<typeof OrderSchema>;

export function representable(cents: number): number {
  if (!Number.isSafeInteger(cents) || cents < 0 || cents > MAX_CENTS) {
    throw new RangeError(`money: ${String(cents)} is not a representable cent amount`);
  }
  return cents;
}

export function parseMoneyCents(raw: unknown): number {
  const text = v.parse(MoneyTextSchema, typeof raw === "string" ? raw.trim() : raw);
  const [whole = "", fraction = ""] = text.split(".");
  return representable(Number(whole) * 100 + Number(fraction.padEnd(2, "0")));
}

export function readOrder(raw: unknown): OrderInput {
  return v.parse(OrderInputSchema, raw);
}

export function snapshotOrder(raw: unknown): Order {
  return v.parse(OrderSchema, raw);
}
