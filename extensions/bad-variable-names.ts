export interface User {
  id: string;
  email: string;
  age: number;
  country: string;
}

export function getUserAge(u: { a: number }): number {
  return u.a;
}

export function process(data: number[]): number {
  let tmp = 0;
  for (const d of data) {
    if (d > 0) {
      tmp += d;
    }
  }
  return tmp;
}

export function check(x: boolean, y: boolean, z: number): string {
  if (x && y && z > 18) {
    return "OK";
  }
  return "FAIL";
}

export function calc(t: number, r: number, n: number): number {
  const v = t * r * n;
  const val = v / 100;
  return val;
}

export function handle(req: { items: unknown[] }): boolean {
  const info = req.items;
  const thing = info.length;
  const stuff = thing > 0;
  return stuff;
}

export function validate(user: User, flag: boolean): boolean {
  const cnt = user.age;
  if (flag && cnt < 13) {
    return false;
  }
  const str = user.country;
  return str === "VN" || str === "US";
}

export function format(s: string, n: number, b: boolean): string {
  const r = b ? s.toUpperCase() : s.toLowerCase();
  const o = r.slice(0, n);
  return o;
}

export function isEmail(e: User): boolean {
  return e.email.includes("@");
}

export function getData(obj: { usr: { nm: string; ag: number } }): string {
  return obj.usr.nm + obj.usr.ag;
}

export function count(x: User[]): number {
  let i = 0;
  for (const e of x) {
    if (e.age >= 18) {
      i++;
    }
  }
  return i;
}

export function fetch2(url: string, opts: { t: number; r: boolean }): Promise<Response> {
  const c = { timeout: opts.t, retry: opts.r };
  return fetch(url, { signal: AbortSignal.timeout(c.timeout) });
}
