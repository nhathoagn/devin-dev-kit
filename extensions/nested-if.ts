// Fixture file — không phải code sản phẩm, không import vào module thật.

interface CartItem {
  sku: string;
  name: string;
  price: number;
  qty: number;
  category: string;
}

interface Customer {
  id: string;
  tier: string;
  email: string;
  region: string;
  vip: boolean;
  orderCount: number;
}

interface Order {
  id: string;
  items: CartItem[];
  customer: Customer;
  couponCode?: string;
  giftWrap?: boolean;
  express?: boolean;
  note?: string;
}

type Snapshot = Omit<Order, "items"> & { items: unknown[] };

type OrderStatus = "ok" | "partial" | "empty" | "error";

interface CheckoutResult {
  orderId: string;
  customerId: string | null;
  total: number;
  discount: number;
  shipping: number;
  tax: number;
  grandTotal: number;
  status: OrderStatus;
  errors: string[];
  servedFromCache: boolean;
  createdAt: string;
}

interface AuditEntry {
  orderId: string;
  action: string;
  at: number;
}

interface Receipt {
  canonical: string;
  result: CheckoutResult;
}

const TIER_RATES = {
  gold: [0.15, 0.1, 0.05],
  silver: [0.1, 0.05, 0.02],
  bronze: [0.05, 0, 0],
} as const satisfies Record<string, readonly [high: number, mid: number, low: number]>;
type Tier = keyof typeof TIER_RATES;
const HIGH_TOTAL_THRESHOLD = 500_000;
const MID_TOTAL_THRESHOLD = 200_000;
const DISCOUNT_CAP_RATIO = 0.3;
const VIP_BONUS_RATIO = 0.05;
const FLAT_COUPONS: Record<string, number> = { SALE10: 50_000, SALE20: 100_000 };
const FREESHIP_COUPON = "FREESHIP";
const REGION_SHIPPING = { north: 30_000, south: 30_000, central: 20_000 } as const;
type Region = keyof typeof REGION_SHIPPING;
const EXPRESS_FEE = 50_000;
const GIFT_WRAP_FEE = 15_000;
const FREE_SHIPPING_TOTAL = 1_000_000;
const TAX_RATE = 0.08;
const TAX_PREMIUM_REGION = "south";
const PREMIUM_TAX_MULTIPLIER = 1.1;
const B2B_DISCOUNT_RATIO = 0.2;
const CHANNEL_ACTIONS: Record<string, string> = { retail: "checkout", b2b: "checkout_b2b" };
const MAX_AUDIT_ENTRIES = 10_000;

const receipts = new Map<string, Receipt>();
const pending = new Map<string, Pending>();
const auditLog: AuditEntry[] = [];
let auditHead = 0;

function blankOf(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function readOrderId(value: unknown): string {
  try {
    if (value && typeof value === "object" && "id" in value) {
      return blankOf(value.id) ?? "unknown";
    }
  } catch {
    return "unknown";
  }
  return "unknown";
}

const OPTIONAL_FIELD_CHECKS: readonly [key: string, test: (value: unknown) => boolean][] = [
  ["couponCode", (v) => typeof v === "string"],
  ["giftWrap", (v) => typeof v === "boolean"],
  ["express", (v) => typeof v === "boolean"],
  ["note", (v) => typeof v === "string"],
];

function isOrder(value: unknown): value is Order {
  if (!value || typeof value !== "object") return false;
  const order = value as Record<string, unknown>;
  if (!blankOf(order.id) || !Array.isArray(order.items)) return false;
  if (!order.customer || typeof order.customer !== "object") return false;
  const customer = order.customer as Record<string, unknown>;
  if (!blankOf(customer.id) || !blankOf(customer.tier) || !blankOf(customer.region)) return false;
  if (typeof customer.email !== "string") return false;
  if (typeof customer.vip !== "boolean") return false;
  if (typeof customer.orderCount !== "number" || !Number.isFinite(customer.orderCount)) {
    return false;
  }
  for (const [key, test] of OPTIONAL_FIELD_CHECKS) {
    const v = order[key];
    if (v !== undefined && v !== null && !test(v)) return false;
  }
  return true;
}

function normalizeCustomer(customer: Customer): Customer {
  return {
    ...customer,
    id: customer.id.trim(),
    tier: customer.tier.trim().toLowerCase(),
    region: customer.region.trim().toLowerCase(),
  };
}

function snapshotOrder(order: Order): Snapshot {
  const customer = order.customer;
  const items: unknown[] = [];
  for (const item of order.items) {
    if (!item || typeof item !== "object") {
      items.push(item);
      continue;
    }
    items.push({
      sku: item.sku,
      name: item.name,
      price: item.price,
      qty: item.qty,
      category: item.category,
    });
  }
  return {
    id: order.id,
    items,
    customer: {
      id: customer.id,
      tier: customer.tier,
      email: customer.email,
      region: customer.region,
      vip: customer.vip,
      orderCount: customer.orderCount,
    },
    couponCode: order.couponCode,
    giftWrap: order.giftWrap,
    express: order.express,
    note: order.note,
  };
}

function copyResult(result: CheckoutResult): CheckoutResult {
  return { ...result, errors: [...result.errors] };
}

function buildResult(
  orderId: string,
  customerId: string | null,
  total: number,
  discount: number,
  shipping: number,
  tax: number,
  status: OrderStatus,
  errors: string[],
): CheckoutResult {
  const money = {
    total: Math.round(total),
    discount: Math.round(discount),
    shipping: Math.round(shipping),
    tax: Math.round(tax),
  };
  const exact =
    money.total - money.discount + money.shipping + money.tax;
  return {
    orderId,
    customerId,
    ...money,
    grandTotal: exact,
    status,
    errors,
    servedFromCache: false,
    createdAt: new Date().toISOString(),
  };
}

function errorResult(orderId: string, errors: string[]): CheckoutResult {
  return buildResult(orderId, null, 0, 0, 0, 0, "error", errors);
}

interface LineCheck {
  total: number;
  errors: string[];
  needed: Map<string, number>;
  stock: Map<string, number>;
}

function checkItems(items: readonly unknown[], inventory: Record<string, number>): LineCheck {
  const qtyBySku = new Map<string, number>();
  const amountBySku = new Map<string, number>();
  const errors: string[] = [];

  for (const item of items) {
    const line = readLine(item);
    if (typeof line === "string") {
      errors.push(line);
      continue;
    }
    const summedQty = (qtyBySku.get(line.sku) ?? 0) + line.qty;
    if (!Number.isFinite(summedQty) || summedQty > Number.MAX_SAFE_INTEGER) {
      errors.push(line.sku + " bad qty");
      continue;
    }
    qtyBySku.set(line.sku, summedQty);
    amountBySku.set(line.sku, (amountBySku.get(line.sku) ?? 0) + line.price * line.qty);
  }

  let total = 0;
  const needed = new Map<string, number>();
  const stockSeen = new Map<string, number>();
  for (const [sku, qty] of qtyBySku) {
    const stock = stockOf(inventory, sku);
    if (stock === null) {
      errors.push(sku + " not found");
      continue;
    }
    if (stock < qty) {
      errors.push(sku + " only " + stock + " left");
      continue;
    }
    total += amountBySku.get(sku) ?? 0;
    needed.set(sku, qty);
    stockSeen.set(sku, stock);
  }
  if (!Number.isSafeInteger(Math.round(total))) {
    errors.push("order total too large");
    total = 0;
  }
  return { total, errors, needed, stock: stockSeen };
}

interface Pending {
  canonical: string;
  before: Map<string, number>;
  after: Map<string, number>;
}

interface WriteFailure {
  message: string;
  before: Map<string, number>;
  after: Map<string, number>;
}

function readStock(inventory: Record<string, number>, sku: string): number | undefined {
  try {
    const value = inventory[sku];
    return Number.isSafeInteger(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function applyDeductions(
  check: LineCheck,
  inventory: Record<string, number>,
): WriteFailure | null {
  const before = new Map<string, number>();
  const after = new Map<string, number>();
  for (const [sku, qty] of check.needed) {
    const stock = check.stock.get(sku);
    if (stock === undefined) {
      return { message: "inventory is not readable", before, after };
    }
    before.set(sku, stock);
    after.set(sku, stock - qty);
  }
  const applied: [sku: string, stock: number][] = [];
  let landed = true;
  try {
    for (const [sku, value] of after) {
      applied.push([sku, before.get(sku) as number]);
      inventory[sku] = value;
    }
    for (const [sku, value] of after) {
      if (readStock(inventory, sku) !== value) landed = false;
    }
  } catch {
    landed = false;
  }
  if (landed) return null;
  for (const [sku, stock] of applied) {
    try {
      inventory[sku] = stock;
    } catch {
      continue;
    }
  }
  return { message: "inventory write did not take effect", before, after };
}

function reconcile(
  orderId: string,
  entry: Pending,
  inventory: Record<string, number>,
): { state: "intact" } | { state: "landed" } | { state: "blocked"; drifted: string[] } {
  let unchanged = true;
  let deducted = true;
  const drifted: string[] = [];
  for (const [sku, stock] of entry.before) {
    const now = readStock(inventory, sku);
    const target = entry.after.get(sku);
    if (now !== stock) unchanged = false;
    if (now !== target) deducted = false;
    if (now !== stock && now !== target) drifted.push(sku);
  }
  if (unchanged) {
    pending.delete(orderId);
    return { state: "intact" };
  }
  if (deducted) return { state: "landed" };
  return { state: "blocked", drifted };
}

function isPlainRecord(value: unknown): value is Record<string, number> {
  try {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const proto = Object.getPrototypeOf(value);
    return proto === Object.prototype || proto === null;
  } catch {
    return false;
  }
}

function stockOf(inventory: Record<string, number>, sku: string): number | null {
  try {
    const stock = inventory[sku];
    return Number.isSafeInteger(stock) ? stock : null;
  } catch {
    return null;
  }
}

function tierOf(value: string): Tier | null {
  return Object.hasOwn(TIER_RATES, value) ? (value as Tier) : null;
}

function regionOf(value: string): Region | null {
  return Object.hasOwn(REGION_SHIPPING, value) ? (value as Region) : null;
}

function couponOf(order: Snapshot): string {
  return order.couponCode?.trim().toUpperCase() ?? "";
}

interface Line {
  sku: string;
  qty: number;
  price: number;
}

function readLine(item: unknown): Line | string {
  if (!item || typeof item !== "object") return "invalid item";
  const raw = item as CartItem;
  const sku = blankOf(raw.sku);
  if (!sku) return "invalid sku";
  if (!Number.isInteger(raw.qty) || raw.qty <= 0) return sku + " bad qty";
  if (typeof raw.price !== "number" || !Number.isFinite(raw.price) || raw.price <= 0) return sku + " bad price";
  const amount = Math.round(raw.price * raw.qty);
  if (!Number.isSafeInteger(amount)) return sku + " line too large";
  if (amount <= 0) return sku + " price too small";
  return { sku, qty: raw.qty, price: raw.price };
}

function canonicalOf(channel: string, order: Snapshot): string {
  const groups = new Map<string, [qty: number, price: number]>();
  let invalidItems = 0;
  for (const item of order.items) {
    if (!item || typeof item !== "object") {
      invalidItems += 1;
      continue;
    }
    const line = readLine(item);
    if (typeof line === "string") {
      invalidItems += 1;
      continue;
    }
    const key = JSON.stringify([line.sku, line.price]);
    const prev = groups.get(key);
    groups.set(key, prev ? [prev[0] + line.qty, line.price] : [line.qty, line.price]);
  }
  const lines = [...groups.entries()].sort();
  return JSON.stringify([
    channel,
    order.id,
    lines,
    invalidItems,
    couponOf(order),
    order.express === true,
    order.giftWrap === true,
    order.customer.id,
    order.customer.tier,
    order.customer.region,
    order.customer.vip,
  ]);
}

interface Discount {
  amount: number;
  couponError: string | null;
}

function couponErrorOf(order: Snapshot): string | null {
  const code = couponOf(order);
  if (code && code !== FREESHIP_COUPON && !Object.hasOwn(FLAT_COUPONS, code)) {
    return "invalid coupon " + code;
  }
  return null;
}

function computeDiscount(order: Snapshot, total: number, tier: Tier | null): Discount {
  let discount = 0;
  if (tier) {
    const rates = TIER_RATES[tier];
    const ratio = total >= HIGH_TOTAL_THRESHOLD ? rates[0] : total >= MID_TOTAL_THRESHOLD ? rates[1] : rates[2];
    discount += total * ratio;
  }
  if (order.customer.vip === true) discount += total * VIP_BONUS_RATIO;
  const code = couponOf(order);
  if (Object.hasOwn(FLAT_COUPONS, code)) discount += FLAT_COUPONS[code];
  return { amount: Math.min(discount, total * DISCOUNT_CAP_RATIO, total), couponError: couponErrorOf(order) };
}

function computeShipping(order: Snapshot, total: number, region: Region): number {
  const waived = couponOf(order) === FREESHIP_COUPON || total >= FREE_SHIPPING_TOTAL;
  let shipping = waived ? 0 : REGION_SHIPPING[region];
  if (order.express === true) shipping += EXPRESS_FEE;
  if (order.giftWrap === true) shipping += GIFT_WRAP_FEE;
  return shipping;
}

function computeTax(total: number, discount: number, region: Region): number {
  const taxable = Math.max(0, total - discount);
  return region === TAX_PREMIUM_REGION ? taxable * TAX_RATE * PREMIUM_TAX_MULTIPLIER : taxable * TAX_RATE;
}

type Gate = { rejection: CheckoutResult } | { region: Region; tier: Tier | null };

function orderGate(retail: boolean, order: unknown): Gate {
  if (!isOrder(order)) return { rejection: errorResult(readOrderId(order), ["order is invalid"]) };
  if (order.items.length === 0) {
    return {
      rejection: buildResult(order.id.trim(), order.customer.id.trim(), 0, 0, 0, 0, "empty", ["no items"]),
    };
  }
  const customer = normalizeCustomer(order.customer);
  const region = regionOf(customer.region);
  if (!region) return { rejection: errorResult(order.id.trim(), ["unknown region " + customer.region]) };
  const tier = tierOf(customer.tier);
  if (retail && !tier) return { rejection: errorResult(order.id.trim(), ["unknown tier " + customer.tier]) };
  return { region, tier };
}

function recordReceipt(orderId: string, canonical: string, result: CheckoutResult): void {
  receipts.set(orderId, { canonical, result: copyResult(result) });
}

function recordAudit(orderId: string, action: string): void {
  const entry: AuditEntry = { orderId, action, at: Date.now() };
  if (auditLog.length < MAX_AUDIT_ENTRIES) {
    auditLog.push(entry);
    return;
  }
  auditLog[auditHead] = entry;
  auditHead = (auditHead + 1) % MAX_AUDIT_ENTRIES;
}

type GateFacts = { region: Region; tier: Tier | null };

interface Pricing {
  discount: number;
  shipping: number;
  extraErrors: string[];
}

function runCheckout(
  channel: string,
  order: Order,
  inventory: Record<string, number>,
  computePricing: (order: Snapshot, total: number, gate: GateFacts) => Pricing,
): CheckoutResult {
  const action = CHANNEL_ACTIONS[channel] ?? channel;
  const rawId = readOrderId(order);
  let valid = false;
  try {
    valid = isOrder(order);
  } catch {
    valid = false;
  }
  if (!valid) {
    recordAudit(rawId, action + "_error");
    return errorResult(rawId, ["order is invalid"]);
  }
  let snap: Snapshot;
  try {
    snap = snapshotOrder(order);
  } catch {
    recordAudit(rawId, action + "_error");
    return errorResult(rawId, ["order is invalid"]);
  }

  const gate = orderGate(channel === "retail", snap);
  if ("rejection" in gate) {
    recordAudit(gate.rejection.orderId, action + "_" + gate.rejection.status);
    return gate.rejection;
  }

  const orderId = snap.id.trim();
  const customer = normalizeCustomer(snap.customer);
  const normalized: Snapshot = { ...snap, id: orderId, customer };
  const canonical = canonicalOf(channel, normalized);
  const open = pending.get(orderId);
  if (open) {
    if (open.canonical !== canonical) {
      recordAudit(orderId, action + "_conflict");
      return errorResult(orderId, ["order id " + orderId + " already processed with different payload"]);
    }
    const outcome = reconcile(orderId, open, inventory);
    if (outcome.state === "landed") {
      recordAudit(orderId, action + "_unsettled");
      return errorResult(orderId, [
        "order id " + orderId + " had its stock written but no receipt; inventory already reflects the deduction",
      ]);
    }
    if (outcome.state === "blocked") {
      recordAudit(orderId, action + "_unsettled");
      return errorResult(orderId, [
        "order id " + orderId + " cannot be reconciled; these skus match neither state: " + outcome.drifted.join(", "),
      ]);
    }
  }
  const receipt = receipts.get(orderId);
  if (receipt) {
    if (receipt.canonical !== canonical) {
      recordAudit(orderId, action + "_conflict");
      return errorResult(orderId, ["order id " + orderId + " already processed with different payload"]);
    }
    const served = copyResult(receipt.result);
    served.servedFromCache = true;
    recordAudit(orderId, action + "_cached");
    return served;
  }

  if (!isPlainRecord(inventory)) {
    recordAudit(orderId, action + "_error");
    return errorResult(orderId, ["inventory is invalid"]);
  }

  const check = checkItems(normalized.items, inventory);
  if (check.errors.length > 0) {
    recordAudit(orderId, action + "_failed");
    return buildResult(orderId, customer.id, 0, 0, 0, 0, "partial", check.errors);
  }

  const pricing = computePricing(normalized, check.total, gate);
  const errors = pricing.extraErrors;
  if (errors.length > 0) {
    recordAudit(orderId, action + "_failed");
    return buildResult(orderId, customer.id, 0, 0, 0, 0, "partial", errors);
  }

  const tax = computeTax(check.total, pricing.discount, gate.region);
  if (!Number.isSafeInteger(Math.round(check.total - pricing.discount + pricing.shipping + tax))) {
    recordAudit(orderId, action + "_failed");
    return buildResult(orderId, customer.id, 0, 0, 0, 0, "partial", ["order total too large"]);
  }
  const result = buildResult(
    orderId,
    customer.id,
    check.total,
    pricing.discount,
    pricing.shipping,
    tax,
    "ok",
    [],
  );
  const writeFailure = applyDeductions(check, inventory);
  if (writeFailure) {
    pending.set(orderId, {
      canonical,
      before: writeFailure.before,
      after: writeFailure.after,
    });
    recordAudit(orderId, action + "_error");
    return errorResult(orderId, [writeFailure.message]);
  }
  recordReceipt(orderId, canonical, result);
  recordAudit(orderId, action);
  return result;
}

export function processCheckout(order: Order, inventory: Record<string, number>): CheckoutResult {
  return runCheckout("retail", order, inventory, (o, total, gate) => {
    const { amount, couponError } = computeDiscount(o, total, gate.tier);
    return {
      discount: amount,
      shipping: computeShipping(o, total, gate.region),
      extraErrors: couponError ? [couponError] : [],
    };
  });
}

export function processB2BCheckout(order: Order, inventory: Record<string, number>): CheckoutResult {
  return runCheckout("b2b", order, inventory, (priced, total) => {
    const codeError = couponErrorOf(priced);
    return {
      discount: Math.min(total * B2B_DISCOUNT_RATIO, total),
      shipping: 0,
      extraErrors: codeError ? [codeError] : [],
    };
  });
}
