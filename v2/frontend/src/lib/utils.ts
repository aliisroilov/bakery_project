import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

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
