import { describe, expect, test } from "bun:test";
import fc from "fast-check";

import { idempotencyKey, canonicalForm } from "./canonical.ts";
import { checkout } from "./checkout.ts";
import { MemoryCheckoutStore, type Attempt, type CheckoutStore } from "./store.ts";
import { readOrder } from "./schema.ts";

const customer = { id: "c1", tier: "gold", email: "a@b.co", region: "north", vip: false };
const order = (over: Record<string, unknown> = {}, id = "o1") => ({
  id,
  customer,
  items: [{ sku: "A", qty: 2, price: 1000 }],
  ...over,
});

const setup = (stock: Record<string, number>, now: () => Date = () => new Date("2026-01-01T00:00:00.000Z")) => {
  const store = MemoryCheckoutStore.from(stock);
  return {
    store,
    stockStore: store,
    run: (input: unknown, channel: "retail" | "b2b" = "retail") => checkout(input, channel, { store, now }),
  };
};

describe("schema is the boundary", () => {
  for (const bad of [undefined, null, "", " ", 0, -1, NaN, []] as unknown[]) {
    test(`rejects order ${String(bad)} without touching stock`, async () => {
      const { stockStore, run } = setup({ A: 5 });
      expect((await run(bad)).status).toBe("rejected");
      expect(stockStore.read("A")).toBe(5);
    });
  }

  test("rejects unknown keys instead of ignoring them", async () => {
    const { run, stockStore } = setup({ A: 5 });
    const result = await run(order({ surprise: true }));
    expect(result.status).toBe("rejected");
    expect(stockStore.read("A")).toBe(5);
  });

  const rejected: [string, Record<string, unknown>][] = [
    ["qty as string", { items: [{ sku: "A", qty: "5", price: 1000 }] }],
    ["fractional qty", { items: [{ sku: "A", qty: 1.5, price: 1000 }] }],
    ["zero price", { items: [{ sku: "A", qty: 1, price: 0 }] }],
    ["huge price", { items: [{ sku: "A", qty: 1, price: 1e17 }] }],
    ["prototype sku", { items: [{ sku: "__proto__", qty: 1, price: 10 }] }],
    ["unknown tier", { customer: { ...customer, tier: "toString" } }],
    ["unknown region", { customer: { ...customer, region: "__proto__" } }],
    ["blank email", { customer: { ...customer, email: "" } }],
    ["space email", { customer: { ...customer, email: "   " } }],
    ["empty items", { items: [] as unknown[] }],
  ];
  for (const [label, over] of rejected) {
    test(`rejects ${label}`, async () => {
      const { run, stockStore } = setup({ A: 5 });
      expect((await run(order(over))).status).toBe("rejected");
      expect(stockStore.read("A")).toBe(5);
    });
  }

  test("padded, spaced, and upper-case ids collapse to one order", async () => {
    const { run, stockStore } = setup({ A: 10 });
    expect((await run(order({}, " o1 "))).status).toBe("ok");
    expect((await run(order({}, "O1"))).servedFromCache).toBe(true);
    expect((await run(order({}, "o1"))).servedFromCache).toBe(true);
    expect(stockStore.read("A")).toBe(8);
  });
});

describe("stock store owns atomacy", () => {
  for (const value of [2 ** 53, 1.5, "10", NaN] as unknown[]) {
    test(`treats an unusable stock value ${String(value)} as unavailable`, async () => {
      const { run, stockStore } = setup({ A: value as number });
      expect((await run(order())).status).toBe("rejected");
      expect(stockStore.read("A")).toBeUndefined();
    });
  }

  test("never deducts part of a cart", async () => {
    const { run, stockStore } = setup({ A: 10, B: 1 });
    const result = await run(
      order({ items: [{ sku: "A", qty: 2, price: 1000 }, { sku: "B", qty: 5, price: 1000 }] }),
    );
    expect(result.status).toBe("rejected");
    expect(stockStore.read("A")).toBe(10);
    expect(stockStore.read("B")).toBe(1);
  });

  test("exact stock settles to zero and the next order is refused", async () => {
    const { run, stockStore } = setup({ A: 2 });
    expect((await run(order({ items: [{ sku: "A", qty: 2, price: 1000 }] }))).status).toBe("ok");
    expect(stockStore.read("A")).toBe(0);
    expect((await run(order({}, "o2"))).status).toBe("rejected");
    expect(stockStore.read("A")).toBe(0);
  });
});

describe("idempotency", () => {
  test("a replay deducts nothing, even after many other orders", async () => {
    const { run, stockStore } = setup({ A: 1000 });
    await run(order());
    for (let index = 0; index < 500; index += 1) await run(order({ items: [{ sku: "A", qty: 1, price: 1 }] }, `n${String(index)}`));
    const before = stockStore.read("A");
    const replay = await run(order());
    expect(replay.servedFromCache).toBe(true);
    expect(stockStore.read("A")).toBe(before);
  });

  test("the same id with a different payload is a conflict, not a replay", async () => {
    const { run, stockStore } = setup({ A: 100 });
    await run(order());
    const conflict = await run(order({ items: [{ sku: "A", qty: 3, price: 1000 }] }));
    expect(conflict.status).toBe("rejected");
    expect(stockStore.read("A")).toBe(98);
  });

  test("retail and b2b key spaces do not collide", async () => {
    const { run, stockStore } = setup({ A: 100 });
    expect((await run(order(), "retail")).status).toBe("ok");
    expect((await run(order(), "b2b")).status).toBe("ok");
    expect(stockStore.read("A")).toBe(96);
  });
});

describe("money", () => {
  test("b2b still charges express and gift wrap", async () => {
    const { run } = setup({ A: 100 });
    const result = await run(order({ express: true, giftWrap: true }), "b2b");
    expect(result.shipping).toBe(65_000);
    expect(result.grandTotal).toBe(result.total - result.discount + result.shipping + result.tax);
  });

  test("free shipping waives the region fee but keeps the paid options", async () => {
    const { run } = setup({ A: 100 });
    const result = await run(order({ express: true, items: [{ sku: "A", qty: 1, price: 1_000_000 }] }));
    expect(result.shipping).toBe(50_000);
  });

  test("an unknown coupon is rejected on both channels", async () => {
    for (const channel of ["retail", "b2b"] as const) {
      const { run, stockStore } = setup({ A: 5 });
      const result = await run(order({ couponCode: "SALE99" }), channel);
      expect(result.status).toBe("rejected");
      expect(result.problems.join()).toContain("invalid coupon SALE99");
      expect(stockStore.read("A")).toBe(5);
    }
  });
});

const validOrder = fc.record({
  id: fc.stringMatching(/^[a-z0-9]{1,8}$/),
  sku: fc.stringMatching(/^[A-Z0-9]{1,4}$/),
  qty: fc.integer({ min: 1, max: 9 }),
  price: fc.integer({ min: 1, max: 1_000_000 }),
  tier: fc.constantFrom("gold", "silver", "bronze"),
  region: fc.constantFrom("north", "south", "central"),
  vip: fc.boolean(),
  express: fc.boolean(),
  giftWrap: fc.boolean(),
  couponCode: fc.constantFrom(undefined, "SALE10", "SALE20", "FREESHIP"),
});

const toInput = (sample: {
  id: string;
  sku: string;
  qty: number;
  price: number;
  tier: string;
  region: string;
  vip: boolean;
  express: boolean;
  giftWrap: boolean;
  couponCode: string | undefined;
}) => ({
  id: sample.id,
  customer: { ...customer, tier: sample.tier, region: sample.region, vip: sample.vip },
  items: [{ sku: sample.sku, qty: sample.qty, price: sample.price }],
  express: sample.express,
  giftWrap: sample.giftWrap,
  ...(sample.couponCode ? { couponCode: sample.couponCode } : {}),
});

describe("properties", () => {
  test("stock never goes negative", async () => {
    fc.assert(
      fc.asyncProperty(fc.array(validOrder, { maxLength: 40 }), async (samples) => {
        const { run, stockStore } = setup({ A: 15, B: 15 });
        for (const sample of samples) await run(toInput(sample));
        for (const sku of ["A", "B"]) {
          const value = stockStore.read(sku);
          expect(value === undefined || value >= 0).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  test("one payload always yields one key, and a one-field change yields another", async () => {
    fc.assert(
      fc.asyncProperty(validOrder, async (sample) => {
        const base = readOrder(toInput(sample));
        expect(base.ok).toBe(true);
        if (!base.ok) return;
        const keyOf = (value: typeof base.order) => idempotencyKey(value);
        expect(keyOf(base.order)).toBe(keyOf({ ...base.order }));

        const first = base.order.items[0] as { sku: string; qty: number; price: number };
        const changed = [{ ...first, qty: first.qty + 1 }];
        const reparsed = readOrder({ ...toInput(sample), items: changed });
        expect(reparsed.ok).toBe(true);
        if (reparsed.ok) expect(keyOf(reparsed.order)).not.toBe(keyOf(base.order));
      }),
      { numRuns: 200 },
    );
  });

  test("a settled payload deducts exactly once no matter how often it is replayed", async () => {
    fc.assert(
      fc.asyncProperty(validOrder, fc.integer({ min: 1, max: 6 }), async (sample, repeats) => {
        const { run, stockStore } = setup({ [sample.sku]: 1000, A: 1000 });
        const input = { ...toInput(sample), items: [{ ...toInput(sample).items[0], qty: 1 }] };
        const first = await run(input);
        const afterFirst = stockStore.read(sample.sku);
        for (let index = 0; index < repeats; index += 1) {
          const replay = await run(input);
          if (first.status === "ok") expect(replay.servedFromCache).toBe(true);
        }
        expect(stockStore.read(sample.sku)).toBe(afterFirst);
      }),
      { numRuns: 150 },
    );
  });

  test("money stays integral and self-consistent", async () => {
    fc.assert(
      fc.asyncProperty(validOrder, async (sample) => {
        const { run } = setup({ [sample.sku]: 10_000 });
        const result = await run(toInput(sample));
        if (result.status !== "ok") return;
        for (const value of [result.total, result.discount, result.shipping, result.tax, result.grandTotal]) {
          expect(Number.isSafeInteger(value)).toBe(true);
        }
        expect(result.grandTotal).toBe(result.total - result.discount + result.shipping + result.tax);
        expect(result.discount).toBeLessThanOrEqual(result.total);
        expect(result.grandTotal).toBeGreaterThanOrEqual(0);
      }),
      { numRuns: 300 },
    );
  });

  test("an ok result moves stock by exactly the ordered quantity", async () => {
    fc.assert(
      fc.asyncProperty(validOrder, async (sample) => {
        const starting = 10_000;
        const { run, stockStore } = setup({ [sample.sku]: starting });
        const result = await run(toInput(sample));
        if (result.status !== "ok") return;
        expect(stockStore.read(sample.sku)).toBe(starting - sample.qty);
      }),
      { numRuns: 200 },
    );
  });
});

describe("canonical form", () => {
  test("is order-of-keys independent", async () => {
    const a = readOrder(
      toInput({
        id: "x",
        sku: "A",
        qty: 1,
        price: 10,
        tier: "gold",
        region: "north",
        vip: false,
        express: false,
        giftWrap: false,
        couponCode: undefined,
      }),
    );
    expect(a.ok).toBe(true);
    if (a.ok) {
      const shuffled = Object.fromEntries(Object.entries(a.order).reverse());
      const again = readOrder(shuffled);
      expect(again.ok).toBe(true);
      if (again.ok) expect(canonicalForm(again.order)).toBe(canonicalForm(a.order));
    }
  });
});

describe("tolerance that the schema allows", () => {
  test("reordered items and merged duplicate lines replay instead of conflicting", async () => {
    const { run, stockStore } = setup({ A: 100, B: 100 });
    const first = await run(order({ items: [{ sku: "A", qty: 1, price: 1000 }, { sku: "B", qty: 2, price: 500 }] }));
    expect(first.status).toBe("ok");

    const reordered = await run(order({ items: [{ sku: "B", qty: 2, price: 500 }, { sku: "A", qty: 1, price: 1000 }] }));
    expect(reordered.servedFromCache).toBe(true);

    const split = await run(order({ items: [{ sku: "A", qty: 1, price: 1000 }, { sku: "B", qty: 1, price: 500 }, { sku: "B", qty: 1, price: 500 }] }));
    expect(split.servedFromCache).toBe(true);
    expect(stockStore.read("A")).toBe(99);
    expect(stockStore.read("B")).toBe(98);
  });

  test("null optionals mean absent, not a different payload", async () => {
    const { run } = setup({ A: 100 });
    expect((await run(order({ express: false, giftWrap: false, couponCode: undefined }))).status).toBe("ok");
    const replay = await run(order({ express: null, giftWrap: null, couponCode: null }));
    expect(replay.servedFromCache).toBe(true);
  });

  test("tier and region are normalized before they are validated", async () => {
    const { run } = setup({ A: 100 });
    const result = await run(order({ customer: { ...customer, tier: "GOLD", region: " NORTH " } }));
    expect(result.status).toBe("ok");
    expect(result.discount).toBeGreaterThan(0);
    expect(result.shipping).toBe(30_000);
  });
});

describe("adapter contract", () => {
  test("a short cart leaves every sku untouched", async () => {
    const attempts: Record<string, number> = { A: 10, B: 1 };
    const { run, stockStore } = setup(attempts);
    const result = await run(order({ items: [{ sku: "A", qty: 2, price: 1000 }, { sku: "B", qty: 5, price: 1000 }] }));
    expect(result.status).toBe("rejected");
    expect(result.problems).toEqual(["B: insufficient stock"]);
    expect(stockStore.read("A")).toBe(10);
    expect(stockStore.read("B")).toBe(1);
  });

  test("the premium tax region is rounded once, not twice", async () => {
    const { run } = setup({ A: 100 });
    const result = await run(order({ customer: { ...customer, region: "south", tier: "bronze" }, items: [{ sku: "A", qty: 1, price: 95 }] }));
    expect(result.tax).toBe(8);
    expect(result.grandTotal).toBe(95 + result.shipping + 8);
  });
});

describe("boundary depth and normalization", () => {
  test("unknown keys are rejected inside nested objects too", async () => {
    const { run, stockStore } = setup({ A: 5 });
    expect((await run(order({ customer: { ...customer, nickname: "x" } }))).status).toBe("rejected");
    expect((await run(order({ items: [{ sku: "A", qty: 1, price: 1000, colour: "red" }] }))).status).toBe("rejected");
    expect(stockStore.read("A")).toBe(5);
  });

  test("coupon case is normalized, so sale10 and SALE10 are one payload", async () => {
    const { run } = setup({ A: 100 });
    const first = await run(order({ couponCode: "SALE10" }));
    expect(first.status).toBe("ok");
    expect((await run(order({ couponCode: "sale10" }))).servedFromCache).toBe(true);
    expect((await run(order({ couponCode: " Sale10 " }))).servedFromCache).toBe(true);
  });

  test("duplicate lines for one sku are aggregated before the stock check", async () => {
    const { run, stockStore } = setup({ A: 5 });
    const result = await run(
      order({ items: [{ sku: "A", qty: 3, price: 1000 }, { sku: "A", qty: 3, price: 1000 }] }),
    );
    expect(result.status).toBe("rejected");
    expect(result.problems).toEqual(["A: insufficient stock"]);
    expect(stockStore.read("A")).toBe(5);
  });

  test("the same sku at a different unit price stays a distinct payload", async () => {
    const { run, stockStore } = setup({ A: 100 });
    expect((await run(order({ items: [{ sku: "A", qty: 1, price: 1000 }] }))).status).toBe("ok");
    const conflict = await run(order({ items: [{ sku: "A", qty: 1, price: 1001 }] }));
    expect(conflict.status).toBe("rejected");
    expect(stockStore.read("A")).toBe(99);
  });

  test("a replay returns the settled money rather than recomputing it", async () => {
    const { run } = setup({ A: 100 });
    const first = await run(order({ couponCode: "SALE10" }));
    const replay = await run(order({ couponCode: "SALE10" }));
    expect(replay.servedFromCache).toBe(true);
    expect(replay.grandTotal).toBe(first.grandTotal);
    expect(replay.discount).toBe(first.discount);
    expect(replay.createdAt).toBe(first.createdAt);
  });

  test("a rejected attempt leaves no receipt, so a restock lets the retry settle", async () => {
    const { run, store } = setup({ A: 1 });
    const rejected = await run(order({ items: [{ sku: "A", qty: 5, price: 1000 }] }));
    expect(rejected.status).toBe("rejected");
    store.restock("A", 10);
    const retried = await run(order({ items: [{ sku: "A", qty: 5, price: 1000 }] }));
    expect(retried.status).toBe("ok");
    expect(retried.servedFromCache).toBe(false);
    expect(store.read("A")).toBe(6);
  });

  test("a prototype-shaped sku cannot pollute shared state", async () => {
    const { run, stockStore } = setup({ A: 5 });
    for (const sku of ["__proto__", "constructor", "toString", "hasOwnProperty"]) {
      expect((await run(order({ items: [{ sku, qty: 1, price: 10 }] }))).status).toBe("rejected");
    }
    expect(stockStore.read("A")).toBe(5);
    expect(({} as Record<string, unknown>)["polluted"]).toBeUndefined();
  });
});

describe("transactional attempt", () => {
  test("a settled order is attempted once; replays never reach the store's deduct", async () => {
    let attempts = 0;
    const inner = MemoryCheckoutStore.from({ A: 100 });
    const counting: CheckoutStore = {
      attempt: (entry: Attempt) => {
        attempts += 1;
        return inner.attempt(entry);
      },
    };
    const run = (input: unknown) => checkout(input, "retail", { store: counting });
    await run(order());
    await run(order());
    await run(order());
    expect(attempts).toBe(3);
    expect(inner.read("A")).toBe(98);
  });

  test("an attempt that throws before settling leaves stock and key untouched", async () => {
    const inner = MemoryCheckoutStore.from({ A: 5 });
    let crash = true;
    const flaky: CheckoutStore = {
      attempt: (entry: Attempt) => {
        if (crash) {
          crash = false;
          return inner.attempt({
            ...entry,
            render: () => {
              throw new Error("transaction aborted");
            },
          });
        }
        return inner.attempt(entry);
      },
    };
    let crashed: unknown = null;
    try {
      await checkout(order(), "retail", { store: flaky });
    } catch (error) {
      crashed = error;
    }
    expect(crashed).toBeInstanceOf(Error);
    expect((crashed as Error).message).toContain("transaction aborted");
    const afterCrash = inner.read("A") as number;
    expect(afterCrash).toBe(5);
    const retry = await checkout(order(), "retail", { store: inner });
    expect(retry.status).toBe("ok");
    expect(retry.servedFromCache).toBe(false);
    expect(inner.read("A")).toBe(afterCrash - 2);
  });

  test("money above the safe-integer range is refused, not settled", async () => {
    const { run, stockStore } = setup({ A: 1_000_000_000 });
    const twoLines = await run(
      order({
        items: [
          { sku: "A", qty: 100_000_000, price: 90_000_000 },
          { sku: "A", qty: 100_000_000, price: 90_000_000 },
        ],
      }),
    );
    expect(twoLines.status).toBe("rejected");
    expect(stockStore.read("A")).toBe(1_000_000_000);

    const oneLineTax = await run(
      order({
        customer: { ...customer, tier: "bronze" },
        items: [{ sku: "A", qty: 100_000_000, price: 90_000_000 }],
      }),
    );
    expect(oneLineTax.status).toBe("rejected");
    expect(oneLineTax.problems).toEqual(["order total is too large"]);
    expect(stockStore.read("A")).toBe(1_000_000_000);
  });

  test("a receipt is immutable, so a caller cannot rewrite what is cached", async () => {
    const { run } = setup({ A: 100 });
    const first = await run(order());
    const originalGrandTotal = first.grandTotal;
    const originalProblems = [...first.problems];
    first.problems.push("CALLER WROTE THIS");
    first.grandTotal = -1;
    const replay = await run(order());
    expect(replay.servedFromCache).toBe(true);
    expect(replay.problems).toEqual(originalProblems);
    expect(replay.grandTotal).toBe(originalGrandTotal);
    expect(replay.grandTotal).toBeGreaterThan(0);
  });
});

describe("store contract", () => {
  test("concurrent attempts on one key settle exactly once", async () => {
    const store = MemoryCheckoutStore.from({ A: 50 });
    const deps = { store, now: () => new Date("2026-01-01T00:00:00.000Z") };
    const results = await Promise.all(
      Array.from({ length: 8 }, () => checkout(order({ items: [{ sku: "A", qty: 2, price: 1000 }] }), "retail", deps)),
    );
    const settled = results.filter((result) => result.status === "ok" && !result.servedFromCache);
    const replayed = results.filter((result) => result.servedFromCache);
    expect(settled).toHaveLength(1);
    expect(replayed).toHaveLength(7);
    expect(store.read("A")).toBe(48);
    expect(new Set(results.map((result) => result.grandTotal)).size).toBe(1);
  });

  test("concurrent attempts on different keys cannot both take the last unit", async () => {
    const store = MemoryCheckoutStore.from({ A: 1 });
    const deps = { store, now: () => new Date("2026-01-01T00:00:00.000Z") };
    const results = await Promise.all(
      Array.from({ length: 5 }, (_unused, index) =>
        checkout(order({ items: [{ sku: "A", qty: 1, price: 1000 }] }, `o${String(index)}`), "retail", deps),
      ),
    );
    const settled = results.filter((result) => result.status === "ok");
    expect(settled).toHaveLength(1);
    expect(results.filter((result) => result.status === "rejected")).toHaveLength(4);
    expect(store.read("A")).toBe(0);
    expect(settled.length + 4).toBe(5);
  });

  test("a conflict under concurrency still deducts nothing", async () => {
    const store = MemoryCheckoutStore.from({ A: 10 });
    const deps = { store, now: () => new Date("2026-01-01T00:00:00.000Z") };
    const same = order({ items: [{ sku: "A", qty: 1, price: 1000 }] });
    const changed = order({ items: [{ sku: "A", qty: 3, price: 1000 }] });
    const [first, second] = await Promise.all([
      checkout(same, "retail", deps),
      checkout(changed, "retail", deps),
    ]);
    const outcomes = [first.status, second.status].sort();
    expect(outcomes).toEqual(["ok", "rejected"]);
    expect(store.read("A")).toBe(9);
  });

  test("the injected clock decides createdAt, so a replay keeps the first timestamp", async () => {
    const store = MemoryCheckoutStore.from({ A: 10 });
    const early = { store, now: () => new Date("2020-01-01T00:00:00.000Z") };
    const late = { store, now: () => new Date("2030-01-01T00:00:00.000Z") };
    const first = await checkout(order(), "retail", early);
    const replay = await checkout(order(), "retail", late);
    expect(first.createdAt).toBe("2020-01-01T00:00:00.000Z");
    expect(replay.createdAt).toBe("2020-01-01T00:00:00.000Z");
    expect(replay.servedFromCache).toBe(true);
  });
});
