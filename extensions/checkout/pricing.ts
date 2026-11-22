import type { Order } from "./schema.ts";

export type Region = Order["customer"]["region"];
export type Tier = Order["customer"]["tier"];

export type OrderStatus = "ok" | "rejected";

export interface CheckoutResult {
  orderId: string | null;
  customerId: string | null;
  total: number;
  discount: number;
  shipping: number;
  tax: number;
  grandTotal: number;
  status: OrderStatus;
  problems: string[];
  servedFromCache: boolean;
  createdAt: string;
}

export const TIER_PERCENT = { gold: [15, 10, 5], silver: [10, 5, 2], bronze: [5, 0, 0] } as const satisfies Record<Tier, readonly [number, number, number]>;
export const HIGH_TOTAL = 500_000;
export const MID_TOTAL = 200_000;
export const DISCOUNT_CAP_PERCENT = 30;
export const VIP_BONUS_PERCENT = 5;
export const FLAT_COUPONS = { SALE10: 50_000, SALE20: 100_000 } as const satisfies Record<string, number>;
export type CouponCode = keyof typeof FLAT_COUPONS;
export const FREESHIP_COUPON = "FREESHIP";
export const REGION_SHIPPING = { north: 30_000, south: 30_000, central: 20_000 } as const satisfies Record<Region, number>;
export const EXPRESS_FEE = 50_000;
export const GIFT_WRAP_FEE = 15_000;
export const FREE_SHIPPING_TOTAL = 1_000_000;
export const TAX_PERCENT = 8;
export const PREMIUM_TAX_REGION: Region = "south";
export const PREMIUM_TAX_PERCENT = 110;
export const B2B_DISCOUNT_PERCENT = 20;

const percentOf = (amount: number, percent: number): number => Math.round((amount * percent) / 100);

const isFlatCoupon = (code: string | null | undefined): code is CouponCode =>
  code !== null && code !== undefined && Object.hasOwn(FLAT_COUPONS, code);

export function lineTotal(order: Order): number {
  return order.items.reduce((sum, item) => sum + item.price * item.qty, 0);
}

export function couponProblem(couponCode: string | null | undefined): string | null {
  if (!couponCode) return null;
  if (couponCode === FREESHIP_COUPON) return null;
  if (isFlatCoupon(couponCode)) return null;
  return "invalid coupon " + couponCode;
}

export function discountFor(order: Order, total: number): number {
  const [high, mid, low] = TIER_PERCENT[order.customer.tier];
  const tierPercent = total >= HIGH_TOTAL ? high : total >= MID_TOTAL ? mid : low;
  let discount = percentOf(total, tierPercent);
  if (order.customer.vip) discount += percentOf(total, VIP_BONUS_PERCENT);
  const couponCode = order.couponCode;
  if (isFlatCoupon(couponCode)) discount += FLAT_COUPONS[couponCode];
  return Math.min(discount, percentOf(total, DISCOUNT_CAP_PERCENT), total);
}

export function shippingFor(order: Order, total: number, b2b: boolean): number {
  const waived = order.couponCode === FREESHIP_COUPON || total >= FREE_SHIPPING_TOTAL;
  const base = b2b || waived ? 0 : REGION_SHIPPING[order.customer.region];
  let shipping = base;
  if (order.express) shipping += EXPRESS_FEE;
  if (order.giftWrap) shipping += GIFT_WRAP_FEE;
  return shipping;
}

export function taxFor(order: Order, total: number, discount: number): number {
  const taxable = Math.max(0, total - discount);
  const percent =
    order.customer.region === PREMIUM_TAX_REGION ? (TAX_PERCENT * PREMIUM_TAX_PERCENT) / 100 : TAX_PERCENT;
  return Math.round((taxable * percent) / 100);
}

export interface Priced {
  orderId: string;
  total: number;
  discount: number;
  shipping: number;
  tax: number;
  grandTotal: number;
}

export function priceOrder(order: Order, b2b: boolean): Priced {
  const total = lineTotal(order);
  const discount = b2b ? Math.min(percentOf(total, B2B_DISCOUNT_PERCENT), total) : discountFor(order, total);
  const shipping = shippingFor(order, total, b2b);
  const tax = taxFor(order, total, discount);
  return {
    orderId: order.id,
    total,
    discount,
    shipping,
    tax,
    grandTotal: total - discount + shipping + tax,
  };
}

export function representable(priced: Priced): boolean {
  return [priced.total, priced.discount, priced.shipping, priced.tax, priced.grandTotal].every(
    (value) => Number.isSafeInteger(value) && value >= 0,
  );
}

export function copyResult(result: CheckoutResult): CheckoutResult {
  return { ...result, problems: [...result.problems] };
}

export function reject(
  orderId: string | null,
  problems: string[],
  customerId: string | null = null,
  now: () => Date = () => new Date(),
): CheckoutResult {
  return {
    orderId,
    customerId,
    total: 0,
    discount: 0,
    shipping: 0,
    tax: 0,
    grandTotal: 0,
    status: "rejected",
    problems,
    servedFromCache: false,
    createdAt: now().toISOString(),
  };
}
