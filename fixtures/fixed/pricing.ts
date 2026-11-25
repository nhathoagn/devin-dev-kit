import { representable, type Channel, type Coupon, type Item, type Order } from "./schema.ts";

const TAX_RATE = 0.0825;
const SHIPPING_CENTS = 799;
const FREE_SHIPPING_CENTS = 4999;

const CHANNEL_FEE_RATES = { web: 0.05, mobile: 0.0501, partner: 0 } as const satisfies Record<
  Channel,
  number
>;
const COUPON_FACTORS = { SAVE10: 0.9, SAVE20: 0.8 } as const satisfies Record<Coupon, number>;

export type Totals = {
  readonly merchandiseCents: number;
  readonly discountCents: number;
  readonly taxCents: number;
  readonly feeCents: number;
  readonly shippingCents: number;
  readonly totalCents: number;
};

export function totalsFor(order: Order): Totals {
  const grossCents = subtotal(order.items);
  const discountCents = discountOn(grossCents, order.coupon);
  const merchandiseCents = representable(grossCents - discountCents);
  const taxCents = representable(Math.round(merchandiseCents * TAX_RATE));
  const feeCents = representable(Math.round(merchandiseCents * CHANNEL_FEE_RATES[order.channel]));
  const shippingCents = grossCents >= FREE_SHIPPING_CENTS ? 0 : SHIPPING_CENTS;
  const totalCents = representable(merchandiseCents + taxCents + feeCents + shippingCents);
  return { merchandiseCents, discountCents, taxCents, feeCents, shippingCents, totalCents };
}

export function formatCentsAsDollars(cents: number): string {
  return (representable(cents) / 100).toFixed(2);
}

function subtotal(items: readonly Item[]): number {
  return representable(items.reduce((sum, item) => sum + lineTotal(item), 0));
}

function lineTotal(item: Item): number {
  return representable(item.unitCents * item.qty);
}

function discountOn(grossCents: number, coupon: Coupon | undefined): number {
  if (coupon === undefined) return 0;
  return representable(grossCents - Math.round(grossCents * COUPON_FACTORS[coupon]));
}
