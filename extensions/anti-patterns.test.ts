import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canCheckout,
  discount,
  isCountry,
  isOrderStatus,
  isTier,
  orderProblem,
  orderTotal,
  parseConfig,
  processOrder,
  type Order,
} from "./anti-patterns.ts";

function orderFixture(overrides: Record<string, unknown> = {}): Order {
  return {
    id: "O1",
    status: "3",
    express: false,
    weightKg: 5,
    coupon: "",
    isMember: true,
    isFirstOrder: false,
    customer: { name: "N", email: "a@b.c", tier: "gold", country: "VN" },
    items: [{ sku: "A", price: 100, qty: 2 }],
    ...overrides,
  } as Order;
}

const BAD_VALUES = [undefined, null, "", " ", "abc", NaN, -1, 0];

function* corruptedOrders(): Generator<{ path: string; order: Order }> {
  const base = orderFixture();
  for (const field of Object.keys(base) as (keyof Order)[]) {
    for (const bad of BAD_VALUES) {
      yield { path: `order.${field}`, order: { ...base, [field]: bad } };
    }
  }
  const customer = base.customer;
  for (const field of Object.keys(customer) as (keyof typeof customer)[]) {
    for (const bad of BAD_VALUES) {
      yield {
        path: `customer.${field}`,
        order: { ...base, customer: { ...customer, [field]: bad } },
      };
    }
  }
  const item = base.items[0];
  for (const field of Object.keys(item) as (keyof typeof item)[]) {
    for (const bad of BAD_VALUES) {
      yield {
        path: `items[0].${field}`,
        order: { ...base, items: [{ ...item, [field]: bad }] },
      };
    }
  }
  yield { path: "items (not array)", order: { ...base, items: null as never } };
  yield { path: "items (empty)", order: { ...base, items: [] } };
}

test("invariant: orderProblem(order) === null implies orderTotal(order) does not throw", () => {
  for (const { path, order } of corruptedOrders()) {
    if (orderProblem(order) !== null) continue;
    assert.doesNotThrow(
      () => orderTotal(order),
      `orderProblem accepted ${path} but orderTotal threw`,
    );
  }
});

test("processOrder returns a Result and never throws for corrupted input", () => {
  for (const { order } of corruptedOrders()) {
    assert.doesNotThrow(() => processOrder(order));
    const result = processOrder(order);
    assert.equal(typeof result.ok, "boolean");
    if (result.ok) {
      assert.equal(typeof result.value, "number");
      assert.ok(Number.isFinite(result.value));
    } else {
      assert.equal(typeof result.error, "string");
    }
  }
});

test("canCheckout implies processOrder succeeds for the same order", () => {
  const ages = [...BAD_VALUES, 18, 20, 99];
  for (const { order } of corruptedOrders()) {
    for (const age of ages) {
      for (const country of ["VN", "US", "JP", ""]) {
        if (!canCheckout({ age: age as number, country }, order)) continue;
        const result = processOrder(order);
        assert.ok(
          result.ok,
          `canCheckout true but processOrder failed: ${JSON.stringify(result)}`,
        );
      }
    }
  }
});

test("boundary: orderProblem/processOrder/canCheckout handle null and non-object order", () => {
  for (const bad of [null, undefined, 0, "", "x", NaN]) {
    const problem = orderProblem(bad as never);
    assert.equal(problem, "invalid order");
    const result = processOrder(bad as never);
    assert.ok(!result.ok);
    assert.equal(result.error, "invalid order");
    assert.equal(canCheckout({ age: 20, country: "VN" }, bad as never), false);
  }
});

test("boundary: processOrder tolerates null context", () => {
  const result = processOrder(orderFixture(), null as never);
  assert.ok(result.ok);
});

test("boundary: parseConfig rejects non-string input as Result, not parsed value", () => {
  for (const bad of [null, 0, -1, undefined]) {
    const result = parseConfig(bad as never);
    assert.ok(!result.ok);
    assert.equal(result.error, "invalid JSON: input is not a string");
  }
});

test("guards: isCountry/isTier/isOrderStatus reject every non-member value", () => {
  for (const bad of BAD_VALUES) {
    assert.equal(isCountry(bad as string), false);
    assert.equal(isTier(bad as string), false);
    assert.equal(isOrderStatus(bad as string), false);
  }
  assert.equal(isCountry("VN"), true);
  assert.equal(isTier("gold"), true);
  assert.equal(isOrderStatus("3"), true);
});

test("invariant: processOrder ok implies finite total (no Infinity/NaN leak)", () => {
  const order = orderFixture({ items: [{ sku: "A", price: 1e308, qty: 1e308 }] });
  const result = processOrder(order);
  assert.ok(!result.ok, `overflow order got ok=${result.ok}`);
  assert.equal(result.ok ? null : result.error, "total out of range");
});

test("discount: tier rates, bulk, coupon, holiday-first, cap", () => {
  const d = (o: Partial<Parameters<typeof discount>[0]>) =>
    discount({
      subtotal: 100,
      tier: "gold",
      totalQuantity: 1,
      coupon: "",
      isMember: false,
      isHoliday: false,
      isFirstOrder: false,
      ...o,
    });
  assert.equal(d({}), 15);
  assert.equal(d({ totalQuantity: 10 }), 20);
  assert.equal(d({ isHoliday: true, isFirstOrder: true }), 17);
  assert.equal(d({ subtotal: 600, tier: "silver", coupon: "SALE50 ", isMember: true }), 98);
  assert.equal(d({ subtotal: 400, tier: "silver", coupon: "SALE50", isMember: true }), 32);
  assert.throws(() => d({ tier: "platinum" }), RangeError);
});
