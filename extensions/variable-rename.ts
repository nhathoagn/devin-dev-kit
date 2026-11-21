export interface Order {
  weightKg: number;
  express: boolean;
  remote: boolean;
}

const HEAVY_KG = 10;

const SHIPPING_FEES = {
  local: {
    standard: { normal: 0, heavy: 3 },
    express: { normal: 4, heavy: 7 },
  },
  remote: {
    standard: { normal: 5, heavy: 8 },
    express: { normal: 10, heavy: 15 },
  },
} as const;

export function shippingFeeSmell(d: Order): number {
  const t = d.weightKg > HEAVY_KG;
  if (d.remote) {
    return d.express ? (t ? 15 : 10) : t ? 8 : 5;
  }
  return d.express ? (t ? 7 : 4) : t ? 3 : 0;
}

export function shippingFee({ weightKg, express, remote }: Order): number {
  const zone = remote ? "remote" : "local";
  const speed = express ? "express" : "standard";
  const tier = weightKg > HEAVY_KG ? "heavy" : "normal";
  return SHIPPING_FEES[zone][speed][tier];
}

/** `amount`, `dailyLimit`, and `balance` must use the same currency unit. */
export interface WithdrawalCheck {
  balance: number;
  amount: number;
  dailyLimit: number;
  frozen: boolean;
}

export type WithdrawalVerdict =
  | "ACCOUNT_FROZEN"
  | "INVALID_AMOUNT"
  | "OVER_DAILY_LIMIT"
  | "INSUFFICIENT_BALANCE"
  | "OK";

export function verdictSmell(b: number, a: number, l: number, f: boolean): string {
  if (f) {
    return "ACCOUNT_FROZEN";
  }
  if (a <= 0) {
    return "INVALID_AMOUNT";
  }
  if (a > l) {
    return "OVER_DAILY_LIMIT";
  }
  if (a > b) {
    return "INSUFFICIENT_BALANCE";
  }
  return "OK";
}

const WITHDRAWAL_RULES: ReadonlyArray<{
  fails: (c: WithdrawalCheck) => boolean;
  verdict: Exclude<WithdrawalVerdict, "OK">;
}> = [
  { fails: ({ frozen }) => frozen, verdict: "ACCOUNT_FROZEN" },
  { fails: ({ amount }) => amount <= 0, verdict: "INVALID_AMOUNT" },
  { fails: ({ amount, dailyLimit }) => amount > dailyLimit, verdict: "OVER_DAILY_LIMIT" },
  { fails: ({ amount, balance }) => amount > balance, verdict: "INSUFFICIENT_BALANCE" },
];

export function withdrawalVerdict(check: WithdrawalCheck): WithdrawalVerdict {
  return WITHDRAWAL_RULES.find((rule) => rule.fails(check))?.verdict ?? "OK";
}

export type Grade = "A+" | "A" | "B" | "C" | "D" | "F";

export function gradeSmell(x: number): string {
  if (x >= 95) {
    return "A+";
  }
  if (x >= 90) {
    return "A";
  }
  if (x >= 80) {
    return "B";
  }
  if (x >= 70) {
    return "C";
  }
  if (x >= 60) {
    return "D";
  }
  return "F";
}

const GRADE_BANDS = [
  [95, "A+"],
  [90, "A"],
  [80, "B"],
  [70, "C"],
  [60, "D"],
] as const;

export function gradeOf(score: number): Grade {
  if (score < 0) {
    throw new RangeError("score must be >= 0");
  }
  return GRADE_BANDS.find(([min]) => score >= min)?.[1] ?? "F";
}
