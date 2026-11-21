export const COUNTRIES = ["VN", "US"] as const;
export type Country = (typeof COUNTRIES)[number];

export const ORDER_STATUSES = ["0", "1", "2", "3", "-1"] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const TIERS = ["gold", "silver", "bronze"] as const;
export type Tier = (typeof TIERS)[number];

export type Result<T> = { ok: true; value: T } | { ok: false; error: string };

export function isCountry(value: string): value is Country {
  return (COUNTRIES as readonly string[]).includes(value);
}

export function isOrderStatus(value: string): value is OrderStatus {
  return (ORDER_STATUSES as readonly string[]).includes(value);
}

export function isTier(value: string): value is Tier {
  return (TIERS as readonly string[]).includes(value);
}

export interface OrderItem {
  sku: string;
  price: number;
  qty: number;
}

export interface Order {
  id: string;
  status: OrderStatus;
  express: boolean;
  weightKg: number;
  coupon: string;
  isMember: boolean;
  isFirstOrder: boolean;
  customer: {
    name: string;
    email: string;
    tier: Tier;
    country: Country;
  };
  items: OrderItem[];
}

export interface DiscountInput {
  subtotal: number;
  tier: string;
  totalQuantity: number;
  coupon: string;
  isMember: boolean;
  isHoliday: boolean;
  isFirstOrder: boolean;
}

export interface PricingContext {
  isHoliday?: boolean;
}

const HEAVY_WEIGHT_KG = 10;
const MIN_CHECKOUT_AGE = 18;
const BULK_QUANTITY = 10;
const BULK_DISCOUNT_RATE = 0.05;
const MAX_DISCOUNT_RATIO = 0.4;
const SALE50_COUPON = "SALE50";
const SALE50_MIN_SUBTOTAL = 500;
const SALE50_AMOUNT = 50;
const FIRST_ORDER_HOLIDAY_RATE = 0.02;
const STATUS_DONE: OrderStatus = "3";

type ShippingKey = `${Country}:${"standard" | "express"}:${"light" | "heavy"}`;

const SHIPPING_FEES: Record<ShippingKey, number> = {
  "VN:standard:light": 5,
  "VN:standard:heavy": 8,
  "VN:express:light": 10,
  "VN:express:heavy": 15,
  "US:standard:light": 12,
  "US:standard:heavy": 25,
  "US:express:light": 20,
  "US:express:heavy": 30,
};

const TIER_DISCOUNT_RATES: Record<Tier, number> = {
  gold: 0.15,
  silver: 0.08,
  bronze: 0.03,
};

const TIER_LABELS: Record<Tier, string> = {
  gold: "VIP",
  silver: "STD",
  bronze: "BSC",
};

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  "0": "pending",
  "1": "paid",
  "2": "shipped",
  "3": "done",
  "-1": "cancel",
};

export function shippingFee(order: Order): number {
  if (order === null || typeof order !== "object" || order.customer === null || typeof order.customer !== "object") {
    throw new TypeError("shippingFee: order and order.customer must be objects");
  }
  const { country } = order.customer;
  if (!isCountry(country)) {
    throw new RangeError(`unknown country: ${country}`);
  }
  if (!Number.isFinite(order.weightKg) || order.weightKg < 0) {
    throw new RangeError(`invalid weight: ${order.weightKg}`);
  }
  const key: ShippingKey = `${country}:${order.express === true ? "express" : "standard"}:${order.weightKg > HEAVY_WEIGHT_KG ? "heavy" : "light"}`;
  return SHIPPING_FEES[key];
}

export function discount(input: DiscountInput): number {
  if (input === null || typeof input !== "object") {
    throw new TypeError("discount: input must be an object");
  }
  const tier = requireTier(input.tier);
  const { subtotal, totalQuantity, coupon, isMember, isHoliday, isFirstOrder } = input;
  if (!Number.isFinite(subtotal) || subtotal < 0) {
    throw new RangeError(`invalid subtotal: ${subtotal}`);
  }
  if (typeof coupon !== "string") {
    throw new TypeError(`invalid coupon: ${coupon}`);
  }
  const rate =
    TIER_DISCOUNT_RATES[tier] +
    (Number.isFinite(totalQuantity) && totalQuantity >= BULK_QUANTITY ? BULK_DISCOUNT_RATE : 0) +
    (isHoliday === true && isFirstOrder === true ? FIRST_ORDER_HOLIDAY_RATE : 0);
  const fixed =
    coupon.trim() === SALE50_COUPON && isMember === true && subtotal >= SALE50_MIN_SUBTOTAL ? SALE50_AMOUNT : 0;
  return Math.min(subtotal * rate + fixed, subtotal * MAX_DISCOUNT_RATIO);
}

export function calcSubtotal(items: OrderItem[]): number {
  if (!Array.isArray(items)) {
    throw new TypeError("calcSubtotal: items must be an array");
  }
  return items.reduce((sum, item) => {
    if (item === null || typeof item !== "object" || !Number.isFinite(item.price) || !Number.isFinite(item.qty)) {
      throw new RangeError("calcSubtotal: item needs finite price and qty");
    }
    return sum + item.price * item.qty;
  }, 0);
}

export function orderStatusLabel(code: string): string {
  if (!isOrderStatus(code)) {
    throw new RangeError(`unknown status code: ${code}`);
  }
  return ORDER_STATUS_LABELS[code];
}

export function orderProblem(order: Order): string | null {
  if (order === null || typeof order !== "object") {
    return "invalid order";
  }
  if (typeof order.id !== "string" || !order.id.trim()) {
    return "missing order id";
  }
  const customer = order.customer;
  if (customer === null || typeof customer !== "object") {
    return "missing customer";
  }
  if (typeof customer.name !== "string" || !customer.name.trim()) {
    return "missing customer name";
  }
  if (
    typeof customer.email !== "string" ||
    customer.email !== customer.email.trim() ||
    !customer.email.includes("@")
  ) {
    return "missing customer email";
  }
  if (!isCountry(customer.country)) {
    return "unknown country";
  }
  if (!isTier(customer.tier)) {
    return "unknown tier";
  }
  if (!isOrderStatus(order.status)) {
    return "unknown status";
  }
  if (typeof order.express !== "boolean") {
    return "invalid express flag";
  }
  if (!Number.isFinite(order.weightKg) || order.weightKg < 0) {
    return "invalid weight";
  }
  if (typeof order.coupon !== "string") {
    return "invalid coupon";
  }
  if (typeof order.isMember !== "boolean" || typeof order.isFirstOrder !== "boolean") {
    return "invalid member flag";
  }
  if (!Array.isArray(order.items) || order.items.length === 0) {
    return "empty order";
  }
  if (
    order.items.some(
      (item) =>
        item === null ||
        typeof item !== "object" ||
        typeof item.sku !== "string" ||
        !item.sku.trim() ||
        !Number.isFinite(item.price) ||
        item.price < 0 ||
        !Number.isFinite(item.qty) ||
        item.qty <= 0,
    )
  ) {
    return "invalid item";
  }
  const subtotal = calcSubtotal(order.items);
  if (!Number.isFinite(subtotal)) {
    return "total out of range";
  }
  return null;
}

/** Pure total (subtotal + shipping - discount). Caller must pass a valid order — see orderProblem. */
export function orderTotal(order: Order, context?: PricingContext): number {
  const subtotal = calcSubtotal(order.items);
  const totalQuantity = order.items.reduce((sum, item) => sum + item.qty, 0);
  return (
    subtotal +
    shippingFee(order) -
    discount({
      subtotal,
      tier: order.customer.tier,
      totalQuantity,
      coupon: order.coupon,
      isMember: order.isMember,
      isHoliday: context?.isHoliday === true,
      isFirstOrder: order.isFirstOrder,
    })
  );
}

export function processOrder(order: Order, context?: PricingContext): Result<number> {
  const problem = orderProblem(order);
  if (problem !== null) {
    return { ok: false, error: problem };
  }
  const total = orderTotal(order, context);
  if (!Number.isFinite(total)) {
    return { ok: false, error: "total out of range" };
  }
  return { ok: true, value: total };
}

export function orderNotification(order: Order): string {
  if (
    order === null ||
    typeof order !== "object" ||
    typeof order.id !== "string" ||
    !order.id.trim() ||
    !isCountry(order.customer?.country)
  ) {
    throw new RangeError("orderNotification: order needs an id and valid country");
  }
  return order.customer.country === "VN"
    ? `Don hang ${order.id} da duoc xu ly`
    : `Order ${order.id} processed`;
}

export function emailCustomers(orders: Order[], country: Country): string[] {
  if (!isCountry(country)) {
    throw new RangeError(`unknown country: ${country}`);
  }
  if (!Array.isArray(orders)) {
    throw new TypeError("emailCustomers: orders must be an array");
  }
  return orders
    .filter((order) => order?.customer?.country === country && order?.status === STATUS_DONE)
    .map((order) => order.customer.email)
    .filter(
      (email): email is string =>
        typeof email === "string" && email === email.trim() && email.includes("@"),
    );
}

export function canCheckout(user: { age: number; country: string }, order: Order): boolean {
  return (
    Number.isFinite(user?.age) &&
    user.age >= MIN_CHECKOUT_AGE &&
    isCountry(user?.country) &&
    orderProblem(order) === null
  );
}

export function parseConfig(text: string): Result<unknown> {
  if (typeof text !== "string") {
    return { ok: false, error: "invalid JSON: input is not a string" };
  }
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return { ok: false, error: `invalid JSON: ${detail}` };
  }
}

export function reportOrders(orders: Order[]): {
  orderCount: number;
  doneCount: number;
  avgSubtotal: number | null;
} {
  if (!Array.isArray(orders)) {
    throw new TypeError("reportOrders: orders must be an array");
  }
  const valid = orders.filter(
    (order) => order !== null && typeof order === "object" && Array.isArray(order.items),
  );
  const orderCount = valid.length;
  const doneCount = valid.filter((order) => order.status === STATUS_DONE).length;
  const totalSubtotal = valid.reduce((sum, order) => sum + calcSubtotal(order.items), 0);
  return {
    orderCount,
    doneCount,
    avgSubtotal: orderCount > 0 ? totalSubtotal / orderCount : null,
  };
}

function requireTier(tier: string): Tier {
  if (!isTier(tier)) {
    throw new RangeError(`unknown tier: ${tier}`);
  }
  return tier;
}

function tierLabel(tier: string): string {
  return TIER_LABELS[requireTier(tier)];
}

export function formatBill(order: Order, total?: number): string {
  if (order === null || typeof order !== "object" || typeof order.id !== "string" || !order.id.trim()) {
    throw new TypeError("formatBill: order must be an object with an id");
  }
  if (typeof order.customer?.name !== "string" || !order.customer.name.trim()) {
    throw new TypeError("formatBill: order needs a customer name");
  }
  const fields: [string, string][] = [
    ["ID", order.id],
    ["NAME", order.customer.name.trim()],
    ["TIER", tierLabel(order.customer.tier)],
  ];
  if (typeof total === "number" && Number.isFinite(total)) {
    fields.push(["TOTAL", String(total)]);
  }
  return fields.map(([key, value]) => `${key}:${value}`).join(";") + ";";
}
