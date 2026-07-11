import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

const _TZ = "Asia/Tashkent";

/** Current time as "YYYY-MM-DDTHH:MM" in Tashkent local time — for datetime-local inputs. */
export function nowTashkentStr(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: _TZ,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date()).replace(", ", "T");
}

/** Convert "YYYY-MM-DDTHH:MM" (Tashkent local, UTC+5) to UTC ISO string for API. */
export function tashkentToISO(localStr: string): string {
  if (!localStr) return new Date().toISOString();
  const [datePart, timePart] = localStr.split("T");
  const [y, mo, d] = datePart.split("-").map(Number);
  const [h, min] = timePart.split(":").map(Number);
  return new Date(Date.UTC(y, mo - 1, d, h - 5, min)).toISOString();
}

/** Format ISO timestamp as "YYYY-MM-DD HH:mm" in Tashkent time. */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: _TZ,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(iso)).replace(", ", " ");
}

/** Format ISO timestamp as "YYYY-MM-DD" in Tashkent time. */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: _TZ, year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(iso));
}

/** Format a "YYYY-MM-DD" (or ISO) date string as "DD-MM-YYYY". */
export function fmtDMY(d: string | null | undefined): string {
  if (!d) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : d;
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format money with locale (never sums UZS + USD). */
export function formatMoney(
  amount: number | string,
  currency: "UZS" | "USD",
  locale = "uz-UZ",
): string {
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (!Number.isFinite(n)) return "—";
  if (currency === "USD") {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    }).format(n);
  }
  // UZS is displayed without cents
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(
    Math.round(n),
  )} so'm`;
}
