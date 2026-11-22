// Before/after demo: the original smell-seeded code is kept verbatim inside
// `export namespace Smelly` below; the clean version follows at the bottom.
// Compare `Smelly.<fn>` against `<fn>` for each change.

export type Result<T> = { ok: true; value: T; warning?: string } | { ok: false; error: string };

export interface FormState {
  id?: string;
  mode?: string;
  country?: string;
  currency?: string;
  taxRate?: number;
  coupon?: string;
  shippingZone?: string;
  giftOption?: boolean;
  giftMessage?: string;
  loyaltyDiscount?: number;
  weightKg?: number;
  items?: { sku?: string; price?: number; qty?: number }[];
  customer?: { name?: string; email?: string; vip?: boolean };
  lastTotal?: number | string;
}

interface Session {
  user?: { age?: number; region?: string; lang?: string };
}

export namespace Smelly {
  const submittedOrders: FormState[] = [];
  const history: FormState[] = [];
  const stats = { submitted: 0, revenue: 0, lastError: "" };
  const sharedState: { cache: Record<string, number>; timers: number[] } = { cache: {}, timers: [] };
  let current: FormState = {};

  function taxTable(c: string): number {
    if (c == "VN") return 0.1;
    if (c == "US") return 0.07;
    return 0;
  }

  // always returns the discounted total
  function base(items: FormState["items"]): number {
    let t = 0;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        t += (it.price ?? 0) * (it.qty ?? 0);
      }
    }
    return t;
  }

  export function applyCountry(state: FormState, c: string): void {
    state.country = c;
    if (c === "VN") {
      state.currency = "VND";
      state.taxRate = 0.1;
      state.coupon = undefined;
    } else if (c === "US") {
      state.currency = "USD";
      state.taxRate = 0.07;
      state.coupon = undefined;
    } else {
      state.currency = "USD";
      state.taxRate = 0;
    }
    // shippingZone, giftOption, loyaltyDiscount stay from the previous country
  }

  export function applyCoupon(state: FormState, code: string): string | null {
    const rules: Record<string, { codes: string[]; pct: number }> = {
      VN: { codes: ["TET", "FREESHIP"], pct: 0.05 },
      US: { codes: ["JULY4"], pct: 0.08 },
    };
    const r = rules[state.country ?? ""];
    if (!r) return "";
    if (!r.codes.includes(code.trim())) {
      return null;
    }
    state.coupon = code;
    state.loyaltyDiscount = r.pct;
    return code;
  }

  export function selectRecord(state: FormState, next: FormState): boolean {
    if (next.id === state.id) return false;
    Object.assign(state, next);
    history.push(state);
    return true;
  }

  function zoneOf(c: string, w: number): string {
    if (c == "VN") {
      if (w < 5) return "A";
      else if (w < 20) return "B";
      else return "C";
    } else {
      if (w < 5) return "X";
      else if (w < 20) return "Y";
      else return "Z";
    }
  }

  export function setWeight(state: FormState, w: number): void {
    if (typeof w === "number" && w > 0) {
      state.shippingZone = zoneOf(state.country ?? "", w);
    }
  }

  export function computeShipping(state: FormState): number {
    const w = base(state.items);
    if (state.shippingZone === "A") {
      if (w < 300) {
        return 3;
      } else {
        return 0;
      }
    } else if (state.shippingZone === "B") {
      if (w < 300) {
        return 6;
      } else {
        if (state.customer?.vip) {
          return 3;
        } else {
          return 6;
        }
      }
    } else if (state.shippingZone === "C") {
      return 12;
    } else if (state.shippingZone === "X") {
      if (w < 100) {
        return 9;
      } else {
        return 5;
      }
    } else if (state.shippingZone === "Y") {
      if (state.customer?.vip) {
        if (w < 100) {
          return 7;
        } else {
          return 4;
        }
      } else {
        return 11;
      }
    } else {
      return 18;
    }
  }

  export function computeTotal(state: FormState): number | string {
    const sub = base(state.items);
    const fee = computeShipping(state);
    let d = 0;
    if (state.loyaltyDiscount) {
      d = sub * state.loyaltyDiscount;
    }
    if (state.coupon === "TET") {
      d += 2;
    }
    const tax = sub * (state.taxRate ?? 0);
    const total = sub + tax + fee - d;
    state.lastTotal = total;
    if (state.giftOption && !state.giftMessage) {
      return "gift message required";
    }
    return total;
  }

  function validate(state: FormState): string | null {
    if (!state.customer?.email?.includes("@")) return "bad email";
    if (!state.items || state.items.length === 0) return "empty";
    for (const it of state.items) {
      if ((it.price ?? -1) < 0) return "bad price";
    }
    return null;
  }

  export function dedupeItems(state: FormState): void {
    const seen: string[] = [];
    const out: NonNullable<FormState["items"]> = [];
    for (const it of state.items ?? []) {
      if (seen.includes(it.sku ?? "")) {
        it.qty = (it.qty ?? 0) + 1;
      } else {
        seen.push(it.sku ?? "");
        out.push(it);
      }
    }
    state.items = out;
  }

  export function mergeItems(state: FormState, more: NonNullable<FormState["items"]>): void {
    const copy = [...(state.items ?? [])];
    for (const it of copy) {
      state.items?.push(it);
    }
    for (const m of more) {
      state.items?.push(m);
    }
  }

  export function applyGift(state: FormState, on: boolean): void {
    state.giftOption = on;
    if (!on) {
      delete state.giftMessage;
    }
  }

  export function submitOrder(state: FormState, session: Session, flag: boolean, retry: boolean): number | string | null {
    // validate
    let err: string | null = null;
    if (!flag) {
      err = validate(state);
      if (err) {
        stats.lastError = err;
        return null;
      }
    }

    // compute
    const t = computeTotal(state);
    if (typeof t === "string") {
      stats.lastError = t;
      return t;
    }

    // save
    submittedOrders.push(state);
    stats.submitted++;
    stats.revenue += typeof t === "number" ? t : 0;

    // notify
    const lang = session.user?.lang ?? "en";
    if (lang === "vi") {
      console.log("gui mail toi " + state.customer?.email + ": don " + state.id + " tong " + t);
    } else {
      console.log("emailing " + state.customer?.email + ": order " + state.id + " total " + t);
    }

    // audit trail
    let tries = 0;
    while (tries < 3) {
      try {
        recordAudit(state, t);
        break;
      } catch (e) {
        tries++;
        if (!retry) break;
      }
    }

    // receipt
    const parts: string[] = [];
    if (state.id) parts.push(state.id);
    if (state.country) parts.push(state.country);
    if (state.customer?.name) parts.push(state.customer.name);
    return "RCP|" + parts.join("|") + "|" + t;
  }

  function recordAudit(state: FormState, t: number): void {
    if (!state.id) throw new Error("no id");
    sharedState.cache["audit:" + state.id] = t;
  }

  export function parseOrderRef(s: string): { id: string; status: string; country: string } {
    const p = s.split("|");
    return { id: p[2], status: p[1], country: p[0] };
  }

  export function statusName(s: string): string {
    switch (s) {
      case "P":
        return "pending";
      case "C":
      case "X":
        return "closed";
      case "D":
        return "done";
      default:
        return s;
    }
  }

  export function startAutoSave(state: FormState): void {
    const timer = setInterval(() => {
      sharedState.cache["draft"] = base(state.items);
    }, 5000);
    sharedState.timers.push(timer as unknown as number);
  }

  export function warmCache(state: FormState): void {
    const cache = sharedState.cache;
    const total = computeTotal(state);
    if (typeof total === "number") {
      cache["warm:" + (state.id ?? "?")] = total;
    }
    for (const k of Object.keys(cache)) {
      if (k.startsWith("warm:")) {
        cache[k + ":seen"] = cache[k];
      }
    }
  }

  export function undoLast(state: FormState): void {
    const prev = history.pop();
    if (prev) {
      Object.assign(state, prev);
    }
  }

  export function buildReceiptHtml(state: FormState): string {
    let h = "<div class='receipt'>";
    h += "<b>" + (state.id ?? "") + "</b>";
    h += "<i>" + (state.customer?.name ?? "") + "</i>";
    if (state.giftMessage) h += "<em>" + state.giftMessage + "</em>";
    h += "</div>";
    return h;
  }

  export function resetForm(state: FormState): void {
    for (const k of Object.keys(state)) {
      delete (state as Record<string, unknown>)[k];
    }
    Object.assign(state, { mode: "new", currency: "VND", taxRate: 0.1, shippingZone: "A" });
  }

  export function getStats(): typeof stats {
    return stats;
  }

  export function getSubmitted(): FormState[] {
    return submittedOrders;
  }

  export function setCurrent(state: FormState): void {
    current = state;
  }

  export function getCurrent(): FormState {
    return current;
  }
}

// Clean version: same exported names, strict contracts, no sentinel unions.
const RECEIPT_PREFIX = "RCP";

const COUNTRY_RULES: Record<string, { currency: string; taxRate: number; zones: [string, string, string] }> = {
  VN: { currency: "VND", taxRate: 0.1, zones: ["A", "B", "C"] },
  US: { currency: "USD", taxRate: 0.07, zones: ["X", "Y", "Z"] },
};

const COUPON_RULES: Record<string, { codes: string[]; pct: number }> = {
  VN: { codes: ["TET", "FREESHIP"], pct: 0.05 },
  US: { codes: ["JULY4"], pct: 0.08 },
};

const ZONE_BUCKETS = [
  { maxKg: 5, index: 0 },
  { maxKg: 20, index: 1 },
  { maxKg: Infinity, index: 2 },
] as const;

// Per-zone fee rule; was a 40-line if-chain. `threshold` compares the money
// subtotal while `zoneOf` uses weightKg — two quantities now named.
const SHIPPING_FEES: Record<string, { threshold: number; below: number; at: number; vipBelow?: number; vipAt?: number }> = {
  A: { threshold: 300, below: 3, at: 0 },
  B: { threshold: 300, below: 6, at: 6, vipAt: 3 },
  C: { threshold: Infinity, below: 12, at: 12 },
  X: { threshold: 100, below: 9, at: 5 },
  Y: { threshold: 100, below: 11, at: 11, vipBelow: 7, vipAt: 4 },
  Z: { threshold: Infinity, below: 18, at: 18 },
};


const STATUS_NAMES = new Map<string, string>([["P", "pending"], ["C", "closed"], ["X", "closed"], ["D", "done"]]);
const TET_BONUS = 2;
const AUTO_SAVE_MS = 5000;
const AUDIT_TRIES = 3;
const CACHE_LIMIT = 128;

const submittedOrders: FormState[] = [];
const submittedIds = new Set<string>();
const undoStacks = new WeakMap<FormState, FormState[]>();
const stats = { submitted: 0, revenue: 0, lastError: "" };
const auditCache = new Map<string, number>();
const warmTotals = new Map<string, number>();
const drafts = new Map<string, number>();
let current: FormState = {};

function cartSubtotal(items: FormState["items"]): number {
  let total = 0;
  for (const it of items ?? []) {
    if (!it || typeof it !== "object") return NaN;
    total += (it.price ?? 0) * (it.qty ?? 0);
  }
  return total;
}

function zoneOf(country: string | undefined, weightKg: number): string | null {
  const rule = typeof country === "string" && Object.hasOwn(COUNTRY_RULES, country) ? COUNTRY_RULES[country] : undefined;
  if (!rule || !Number.isFinite(weightKg) || weightKg <= 0) return null;
  return rule.zones[ZONE_BUCKETS.find((b) => weightKg < b.maxKg)!.index];
}

// Before: country change left stale coupon, loyaltyDiscount, and shippingZone.
export function applyCountry(state: FormState, country: string): Result<FormState> {
  if (!isObject(state)) return { ok: false, error: "state required" };
  const rule = typeof country === "string" && Object.hasOwn(COUNTRY_RULES, country) ? COUNTRY_RULES[country] : undefined;
  if (!rule) return { ok: false, error: `unsupported country: ${country}` };
  state.country = country;
  state.currency = rule.currency;
  state.taxRate = rule.taxRate;
  delete state.coupon;
  delete state.loyaltyDiscount;
  state.shippingZone = zoneOf(country, state.weightKg ?? 0) ?? undefined;
  return { ok: true, value: state };
}

// Before: three falsy-ish sentinels on one channel and stored the untrimmed code.
export function applyCoupon(state: FormState, code: string): Result<string> {
  if (!isObject(state)) return { ok: false, error: "state required" };
  const rule = typeof state.country === "string" && Object.hasOwn(COUPON_RULES, state.country) ? COUPON_RULES[state.country] : undefined;
  if (!rule) return { ok: false, error: `no coupons for country: ${state.country ?? "unset"}` };
  if (typeof code !== "string") return { ok: false, error: "coupon must be a string" };
  const trimmed = code.trim();
  if (!rule.codes.includes(trimmed)) return { ok: false, error: `invalid coupon: ${trimmed}` };
  state.coupon = trimmed;
  state.loyaltyDiscount = rule.pct;
  return { ok: true, value: trimmed };
}

// Before: pushed the post-assign live object, so undo could never restore it.
function isObject(x: unknown): x is FormState {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function replaceContents(state: FormState, next: FormState): void {
  for (const k of Object.keys(state)) {
    delete (state as Record<string, unknown>)[k];
  }
  Object.assign(state, next);
}

export function selectRecord(state: FormState, next: FormState): boolean {
  if (!isObject(state) || !isObject(next) || (state.id !== undefined && next.id === state.id)) return false;
  let stack = undoStacks.get(state);
  if (!stack) undoStacks.set(state, (stack = []));
  if (stack.length >= CACHE_LIMIT) stack.shift();
  stack.push(structuredClone(state));
  replaceContents(state, next);
  return true;
}

// Before: `w <= 0` or NaN silently kept the stale zone.
export function setWeight(state: FormState, weightKg: number): Result<FormState> {
  if (!isObject(state)) return { ok: false, error: "state required" };
  const zone = zoneOf(state.country, weightKg);
  if (zone === null) return { ok: false, error: `cannot zone weight ${weightKg} for country ${state.country ?? "unset"}` };
  state.weightKg = weightKg;
  state.shippingZone = zone;
  return { ok: true, value: state };
}

// Before: a zone it didn't recognize billed the maximum fee.
export function computeShipping(state: Readonly<FormState>): Result<number> {
  if (!isObject(state)) return { ok: false, error: "state required" };
  const rule = typeof state.shippingZone === "string" && Object.hasOwn(SHIPPING_FEES, state.shippingZone) ? SHIPPING_FEES[state.shippingZone] : undefined;
  if (!rule) return { ok: false, error: `unknown shipping zone: ${state.shippingZone ?? "unset"}` };
  const subtotal = cartSubtotal(state.items);
  if (!Number.isFinite(subtotal)) return { ok: false, error: "cart contains a non-numeric price or qty" };
  const vip = Boolean(state.customer?.vip);
  if (subtotal < rule.threshold) return { ok: true, value: vip ? rule.vipBelow ?? rule.below : rule.below };
  return { ok: true, value: vip ? rule.vipAt ?? rule.at : rule.at };
}

// Before: `number | string` sentinel plus a hidden state.lastTotal write.
export function computeTotal(state: Readonly<FormState>): Result<number> {
  if (!isObject(state)) return { ok: false, error: "state required" };
  if (state.giftOption && !(typeof state.giftMessage === "string" && state.giftMessage.trim())) {
    return { ok: false, error: "gift message required" };
  }
  const fee = computeShipping(state);
  if (!fee.ok) return fee;

  const subtotal = cartSubtotal(state.items);
  const discount = subtotal * (state.loyaltyDiscount ?? 0) + (state.coupon === "TET" ? TET_BONUS : 0);
  const total = subtotal + subtotal * (state.taxRate ?? 0) + fee.value - discount;
  if (!Number.isFinite(total)) return { ok: false, error: "non-numeric taxRate or loyaltyDiscount" };
  return { ok: true, value: total };
}

// Before: missed negative qty, NaN price/qty, and missing sku.
const STATE_CHECKS: { error: string; ok: (s: Readonly<FormState>) => boolean }[] = [
  { error: "missing order id", ok: (s) => typeof s.id === "string" && Boolean(s.id.trim()) },
  { error: "bad email", ok: (s) => typeof s.customer?.email === "string" && s.customer.email.includes("@") },
  { error: "empty", ok: (s) => Boolean(s.items?.length) },
];

const ITEM_CHECKS: { error: string; ok: (it: NonNullable<FormState["items"]>[number]) => boolean }[] = [
  { error: "missing sku", ok: (it) => typeof it?.sku === "string" && Boolean(it.sku.trim()) },
  { error: "bad price", ok: (it) => Number.isFinite(it.price) && (it.price as number) >= 0 },
  { error: "bad qty", ok: (it) => Number.isFinite(it.qty) && (it.qty as number) > 0 },
];

function firstError<T>(checks: { error: string; ok: (x: T) => boolean }[], x: T): string | null {
  return checks.find((c) => !c.ok(x))?.error ?? null;
}

function validate(state: Readonly<FormState>): string | null {
  const err = firstError(STATE_CHECKS, state);
  return err ?? (state.items ?? []).map((it) => firstError(ITEM_CHECKS, it)).find((e) => e != null) ?? null;
}

// Before: merged qty onto the dropped duplicate and collapsed all sku-less items.
export function dedupeItems(state: FormState): void {
  if (!isObject(state)) return;
  const bySku = new Map<string, NonNullable<FormState["items"]>[number]>();
  const out: NonNullable<FormState["items"]> = [];
  for (const it of (state.items ?? []).filter((i) => i && typeof i === "object" && !Array.isArray(i))) {
    const sku = typeof it.sku === "string" ? it.sku.trim() : "";
    const kept = sku ? bySku.get(sku) : undefined;
    if (kept) {
      kept.qty = (kept.qty ?? 0) + (it.qty ?? 0);
    } else {
      const clone = structuredClone(it);
      if (sku) bySku.set(sku, clone);
      out.push(clone);
    }
  }
  state.items = out;
}

// Before: pushed a copy of every existing item back, doubling the cart.
export function mergeItems(state: FormState, more: NonNullable<FormState["items"]>): void {
  if (!isObject(state)) return;
  state.items = [...(state.items ?? []), ...(Array.isArray(more) ? more : [])];
  dedupeItems(state);
}

export function applyGift(state: FormState, on: boolean): void {
  if (!isObject(state)) return;
  state.giftOption = Boolean(on);
  if (!on) {
    delete state.giftMessage;
  }
}

export interface SubmitOptions {
  skipValidation?: boolean;
  auditAttempts?: number;
}

// Before: inverted boolean flags, `number | string | null` return, live-object
// storage, no idempotency, swallowed audit errors, crash after side effects.
export function submitOrder(state: FormState, session: Session | undefined, opts: SubmitOptions = {}): Result<string> {
  const options = isObject(opts) ? opts : {};
  const err = !isObject(state) ? "state required" : options.skipValidation === true ? null : validate(state);
  if (err) return reject(err);

  const total = computeTotal(state);
  if (!total.ok) return reject(total.error);

  const orderId = typeof state.id === "string" ? state.id.trim() : "";
  if (!orderId) return reject("missing order id");
  if (submittedIds.has(orderId)) return reject(`duplicate order: ${orderId}`);

  notify(state, session, total.value);
  recordOrder(state, orderId, total.value);

  const attempts = Number.isInteger(options.auditAttempts) && (options.auditAttempts as number) > 0 ? (options.auditAttempts as number) : AUDIT_TRIES;
  const warning = auditWithRetries(state, total.value, attempts);
  return { ok: true, value: receiptFor(state, total.value), ...(warning ? { warning } : {}) };
}

function reject(error: string): { ok: false; error: string } {
  stats.lastError = error;
  return { ok: false, error };
}

const receiptField = (v: unknown): string => encodeURIComponent(typeof v === "string" ? v.trim() : "");

function receiptFor(state: Readonly<FormState>, total: number): string {
  return `${RECEIPT_PREFIX}|${receiptField(state.id)}|${receiptField(state.country)}|${receiptField(state.customer?.name)}|${total}`;
}

function notify(state: Readonly<FormState>, session: Session | undefined, total: number): void {
  const email = state.customer?.email;
  const message =
    session?.user?.lang === "vi"
      ? `gui mail toi ${email}: don ${state.id} tong ${total}`
      : `emailing ${email}: order ${state.id} total ${total}`;
  console.log(message);
}

function recordOrder(state: FormState, orderId: string, total: number): void {
  submittedOrders.push(structuredClone(state));
  submittedIds.add(orderId);
  stats.submitted++;
  stats.revenue += total;
}

function auditWithRetries(state: Readonly<FormState>, total: number, tries: number): string | null {
  let error: string | null = null;
  while (tries-- > 0) {
    try {
      recordAudit(state, total);
      return null;
    } catch (e) {
      error = e instanceof Error ? `audit: ${e.message}` : String(e);
    }
  }
  return error;
}

function recordAudit(state: Readonly<FormState>, total: number): void {
  if (!state.id) throw new Error("no id");
  setBounded(auditCache, state.id.trim(), total);
}

export interface Receipt {
  id: string;
  country: string;
  customerName: string;
  total: number;
}

// Before: parsed a `country|status|id` ref that never matched the receipt
// submitOrder emits, and undefined fields sat under a `string` type.
export function parseReceipt(s: string): Result<Receipt> {
  if (typeof s !== "string") return { ok: false, error: "receipt must be a string" };
  const p = s.split("|");
  if (p[0] !== RECEIPT_PREFIX || p.length !== 5 || !p[1] || !p[4]) {
    return { ok: false, error: `malformed receipt: ${s}` };
  }
  const total = Number(p[4]);
  if (!Number.isFinite(total)) return { ok: false, error: `malformed receipt: ${s}` };
  return { ok: true, value: { id: decodeURIComponent(p[1]), country: decodeURIComponent(p[2]), customerName: decodeURIComponent(p[3]), total } };
}

export function statusName(s: string): string {
  const key = typeof s === "string" ? s.trim() : "";
  return STATUS_NAMES.get(key) ?? (key || "unknown");
}

// Before: every call leaked a permanent interval writing to one shared "draft" key.
export function startAutoSave(state: FormState): () => void {
  if (!isObject(state)) return () => {};
  const keys = new Set<string>();
  const timer = setInterval(() => {
    const key = typeof state.id === "string" && state.id.trim() ? state.id.trim() : `anon:${anonId(state)}`;
    keys.add(key);
    setBounded(drafts, key, cartSubtotal(state.items));
  }, AUTO_SAVE_MS);
  return () => {
    clearInterval(timer);
    for (const k of keys) drafts.delete(k);
  };
}

const anonSeq = new WeakMap<FormState, number>();
let anonCount = 0;
function anonId(state: FormState): number {
  let n = anonSeq.get(state);
  if (n === undefined) anonSeq.set(state, (n = ++anonCount));
  return n;
}

// Before: keys it wrote (`warm:X:seen`) matched its own `warm:` prefix, so the
// cache grew geometrically; no bound or invalidation.
function setBounded(map: Map<string, number>, key: string, value: number): void {
  map.delete(key);
  map.set(key, value);
  if (map.size > CACHE_LIMIT) {
    map.delete(map.keys().next().value as string);
  }
}

export function warmCache(state: Readonly<FormState>): void {
  if (!isObject(state)) return;
  const total = computeTotal(state);
  if (total.ok && typeof state.id === "string" && state.id.trim()) {
    setBounded(warmTotals, state.id.trim(), total.value);
  }
}

// Before: history held the mutated live object, making undo a silent no-op.
export function undoLast(state: FormState): boolean {
  if (!isObject(state)) return false;
  const prev = undoStacks.get(state)?.pop();
  if (!prev) return false;
  replaceContents(state, prev);
  return true;
}

function escapeHtml(s: unknown): string {
  return (typeof s === "string" ? s : "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Before: unescaped interpolation — a giftMessage could inject markup.
export function buildReceiptHtml(state: Readonly<FormState>): string {
  if (!isObject(state)) return "<div class='receipt'></div>";
  let h = "<div class='receipt'>";
  h += "<b>" + escapeHtml(state.id ?? "") + "</b>";
  h += "<i>" + escapeHtml(state.customer?.name ?? "") + "</i>";
  if (typeof state.giftMessage === "string" && state.giftMessage) h += "<em>" + escapeHtml(state.giftMessage) + "</em>";
  h += "</div>";
  return h;
}

// Before: reset hardcoded VN defaults without a country.
export function resetForm(state: FormState): void {
  if (!isObject(state)) return;
  replaceContents(state, { mode: "new" });
  undoStacks.delete(state);
}

// Before: getters handed out live mutable internals.
export function getStats(): Readonly<typeof stats> {
  return { ...stats };
}

export function getSubmitted(): readonly FormState[] {
  return submittedOrders.map((o) => structuredClone(o));
}

export function setCurrent(state: FormState): void {
  if (!isObject(state)) return;
  current = structuredClone(state);
}

export function getCurrent(): FormState {
  return structuredClone(current);
}
