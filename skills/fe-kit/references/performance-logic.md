# Business Logic Performance Checks

`references/performance.md` covers render and bundle cost on the client. This file covers the hot paths of domain logic: services, jobs, use-case handlers, and data access. Apply in priority order. Fix higher-impact issues before lower ones.

## 1. Data Layer (CRITICAL)

- Paginate reads. Do not load a full table to filter or count it in memory.
- Use a cursor or keyset for a page consumed in order. Offset pagination rescans rows on every page.
- Select the columns the use case reads. Do not select `*` on a table with wide rows.
- Push aggregation to the data layer: `COUNT`, `SUM`, `GROUP BY` belong in the query, not in a loop over fetched rows.
- One query per entity shape, not per row. An N+1 loop belongs in P1 of `REVIEW_CHECKLIST.md`; the fix here is a `WHERE IN` batch or a join, not a cache.
- A read-modify-write over many rows belongs in one update statement or one transaction, not in a per-row round trip.
- Check that a new frequent query hits an index. State the key it filters on.

## 2. Concurrency (CRITICAL)

- Cap fan-out. `Promise.all` over an unbounded list is a throughput and memory hazard; use a worker pool or a bounded mapper with a named constant.
- Break sequential `await` chains between independent operations. `Promise.all` the independent ones.
- Order dependent steps explicitly. A hidden dependency discovered by accident is a correctness bug, not a perf fix.
- Do not hold a lock, a transaction, or a connection across an external call.
- A job that can be started twice needs idempotency or a lock at entry, not luck.

## 3. Domain Computation

- Hoist invariant work out of loops: parsing config, compiling a regex, building a lookup map used for every row.
- Replace a per-row linear scan with a `Map` keyed once when the inner lookup runs per row. O(n²) by accident is the common shape of P2.
- Do not clone or serialize a large structure inside a loop. Copy once outside, or pass a reference with an explicit no-mutation contract.
- On a compiled hot path, avoid avoidable allocation, copying, and computation per iteration.
- Precompute a value read many times when the inputs change rarely. Name the invalidation point.

## 4. Batch and Jobs

- Size batches explicitly. A batch with no limit grows with the data and turns a job into a memory leak.
- Stream or chunk a large input. Do not materialize it in memory to count it first.
- Checkpoint long jobs so a restart does not redo finished work.
- Free or let go of per-item state inside the loop; do not accumulate results you never read.
- A job log per row at full detail is an I/O hot path. Log at batch boundaries.

## 5. Caching

- Name the key, the TTL or invalidation trigger, and the size bound before adding a cache.
- Invalidate on write, not on read. A cache invalidated lazily serves stale data in between.
- Do not cache to hide an N+1. Fix the query first; cache only what stays expensive after that.
- A cache without a bound is a memory leak with extra steps.

## 6. Measurement

- A claim of faster logic needs a before/after timing: a benchmark, a query plan, or a log line with duration, on a realistic input size.
- State the input size the measurement used. A timing at n=10 says nothing about n=100_000.
- Report the complexity class of a new hot path (rows × per-row cost), not just the measured number.
- Report remaining performance risk, and whether that risk is acceptable for this change.

## Concrete Anti-Patterns to Reject

- `Promise.all` over an unbounded list.
- A sequential `await` chain of independent calls inside one use case.
- Loading a full table to filter, count, or aggregate in memory.
- `SELECT *` feeding a use case that reads two columns.
- A lookup scan inside a row loop where a `Map` built once would do.
- Per-row round trips in a read-modify-write over many rows.
- A batch or job with no explicit size limit.
- An external call made while holding a transaction, lock, or connection.
- A cache with no key naming, no invalidation trigger, or no size bound.
- Memoization or caching added to hide a fixable N+1.
- A claim of speedup with no before/after measurement at a stated input size.

## Rules

- Do not optimize a cold path. Name the input size and frequency that make the path hot.
- Do not add concurrency, caching, or precomputation by default. Add each against a measured or clearly stated cost.
- Prefer pushing work to the data layer over doing it per row in code.
- Keep a measurement artifact in the report: the query plan, the benchmark number, or the timing log line.
