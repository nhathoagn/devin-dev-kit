import {
  gradeOf,
  gradeSmell,
  shippingFee,
  shippingFeeSmell,
  verdictSmell,
  withdrawalVerdict,
} from "./variable-rename";

let failures = 0;

function check(name: string, actual: unknown, expected: unknown) {
  const pass = actual === expected;
  if (!pass) {
    failures += 1;
  }
  console.log(`${pass ? "PASS" : "FAIL"} ${name}: ${JSON.stringify(actual)} (expected ${JSON.stringify(expected)})`);
}

const feeCases: [boolean, boolean, number, number][] = [
  // remote, express, weightKg -> fee
  [true, true, 5, 10],
  [true, true, 10, 10],
  [true, true, 15, 15],
  [true, false, 5, 5],
  [true, false, 10, 5],
  [true, false, 15, 8],
  [false, true, 5, 4],
  [false, true, 10, 4],
  [false, true, 15, 7],
  [false, false, 5, 0],
  [false, false, 10, 0],
  [false, false, 15, 3],
];
for (const [remote, express, weightKg, expected] of feeCases) {
  const order = { weightKg, express, remote };
  check(`fee remote=${remote} express=${express} kg=${weightKg}`, shippingFee(order), expected);
  check(`fee smell parity remote=${remote} express=${express} kg=${weightKg}`, shippingFeeSmell(order), expected);
}

const gradeCases: [number, string][] = [
  [59.9, "F"],
  [60, "D"],
  [69.9, "D"],
  [70, "C"],
  [79.9, "C"],
  [80, "B"],
  [89.9, "B"],
  [90, "A"],
  [94.9, "A"],
  [95, "A+"],
  [100, "A+"],
  [150, "A+"],
];
for (const [score, expected] of gradeCases) {
  check(`grade score=${score}`, gradeOf(score), expected);
  check(`grade smell parity score=${score}`, gradeSmell(score), expected);
}

const base = { balance: 100, amount: 50, dailyLimit: 1000, frozen: false };
const withdrawalCases: [typeof base, string][] = [
  [base, "OK"],
  [{ ...base, frozen: true, amount: -1 }, "ACCOUNT_FROZEN"],
  [{ ...base, amount: 0, dailyLimit: 40 }, "INVALID_AMOUNT"],
  [{ ...base, amount: 150, dailyLimit: 40 }, "OVER_DAILY_LIMIT"],
  [{ ...base, amount: 150 }, "INSUFFICIENT_BALANCE"],
  [{ ...base, amount: 40, dailyLimit: 40 }, "OK"],
  [{ ...base, amount: 100 }, "OK"],
];
for (const [check_, expected] of withdrawalCases) {
  const name = JSON.stringify(check_);
  check(`withdrawal ${name}`, withdrawalVerdict(check_), expected);
  check(`withdrawal smell parity ${name}`, verdictSmell(check_.balance, check_.amount, check_.dailyLimit, check_.frozen), expected);
}

console.log(failures === 0 ? "\nAll checks passed" : `\n${failures} check(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
