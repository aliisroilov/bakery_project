import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3, Download, Search, RefreshCw, ArrowUpDown, ArrowUp, ArrowDown,
  Copy, ChevronDown, ChevronRight, TrendingUp, DollarSign, Package, Warehouse,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "../lib/api";
import { C, TICK, mkTooltip } from "../lib/chart";
import type { Paginated, Product } from "../lib/types";
import { formatMoney, fmtDMY } from "../lib/utils";

type ReportType =
  | "payments"
  | "orders"
  | "production"
  | "expenses"
  | "salary"
  | "shop_debts"
  | "pnl_daily"
  | "gross_overall"
  | "gross_daily"
  | "cos"
  | "sofp";

interface ReportDef {
  type: ReportType;
  title: string;
  description: string;
  xlsxEndpoint?: string;
  supportsDateRange: boolean;
  moneyCols?: number[];
  currencyCol?: number;
  // Fixed per-column currency for reports WITHOUT a per-row currencyCol
  // (e.g. shop_debts has separate UZS and USD columns).
  colCurrency?: Record<number, "UZS" | "USD">;
  // Money columns that must NOT be summed in the footer (e.g. loan limits).
  noTotalCols?: number[];
  allowNegative?: boolean;
  special?: boolean;
}

const REPORTS: ReportDef[] = [
  {
    type: "payments",
    title: "Kirim",
    description: "Har kun uchun jami kirim — kassalar va xodimlar bo'yicha.",
    xlsxEndpoint: "/reports/payments.xlsx",
    supportsDateRange: true,
    moneyCols: [4, 5],
    currencyCol: 3,
  },
  {
    type: "orders",
    title: "Buyurtmalar",
    description: "Oylik bo'yicha jami sotuv, yetkazilgan va jami summa.",
    xlsxEndpoint: "/reports/orders.xlsx",
    supportsDateRange: true,
    moneyCols: [5, 6],
    currencyCol: 4,
  },
  {
    type: "expenses",
    title: "Xarajatlar",
    description: "Xomashyo xaridlari + umumiy xarajatlar birgalikda.",
    xlsxEndpoint: "/reports/expenses.xlsx",
    supportsDateRange: true,
    moneyCols: [4],
    currencyCol: 3,
  },
  {
    type: "salary",
    title: "Oylik",
    description: "Oylik, avans, bonuslar xodim bo'yicha.",
    xlsxEndpoint: "/reports/salary.xlsx",
    supportsDateRange: true,
    moneyCols: [4],
    currencyCol: 3,
  },
  {
    type: "shop_debts",
    title: "Qarzdor do'konlar",
    description: "Limitdan oshgan do'konlar va eng katta qarzdorlar.",
    xlsxEndpoint: "/reports/shop-debts.xlsx",
    supportsDateRange: false,
    moneyCols: [2, 3, 4, 5],
    colCurrency: { 2: "UZS", 3: "UZS", 4: "USD", 5: "USD" },
    noTotalCols: [3, 5], // loan limits — summing them is meaningless
  },
  {
    type: "production",
    title: "Ishlab chiqarish",
    description: "Mahsulot va nonvoylar bo'yicha ishlab chiqarish.",
    xlsxEndpoint: "/reports/production.xlsx",
    supportsDateRange: true,
  },
  {
    type: "pnl_daily",
    title: "Kunlik P&L",
    description: "Har kun: savdo, tan narxi, yalpi va sof foyda.",
    xlsxEndpoint: "/reports/pnl-daily.xlsx",
    supportsDateRange: true,
    moneyCols: [1, 2, 3, 4, 5, 6, 7],
    allowNegative: true,
  },
  {
    type: "gross_overall",
    title: "Gross Overall",
    description: "Oylik P&L — kunlik qatorlar, haftalik jami va oy jami.",
    xlsxEndpoint: "/reports/gross-overall.xlsx",
    supportsDateRange: true,
    moneyCols: [1, 2, 3, 4, 5, 6, 7],
    allowNegative: true,
  },
  {
    type: "gross_daily",
    title: "Gross Daily",
    description: "Bir kun bo'yicha do'kon × mahsulot sotuv jadval.",
    supportsDateRange: false,
    special: true,
  },
  {
    type: "cos",
    title: "Tan narxi",
    description: "Mahsulot tan narxi xomashyo narxlari bilan (jonli hisob).",
    supportsDateRange: false,
    special: true,
  },
  {
    type: "sofp",
    title: "Moliyaviy holat",
    description: "Kassa, do'kon qarzlari va ombor qiymati.",
    supportsDateRange: false,
    special: true,
  },
];

interface ReportData {
  type: ReportType;
  title: string;
  headers: string[];
  rows: (string | number)[][];
  summary: Record<string, number>;
}

// ─── Multi-select product filter ─────────────────────────────────────────────
function ProductMultiSelect({
  products,
  selected,
  onChange,
}: {
  products: Product[];
  selected: number[];
  onChange: (ids: number[]) => void;
}) {
  const [open, setOpen] = useState(false);

  const toggle = (id: number) => {
    if (selected.includes(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  const label =
    selected.length === 0
      ? "Barchasi"
      : selected.length === 1
        ? (products.find((p) => p.id === selected[0])?.name ?? "1 ta")
        : `${selected.length} ta tanlangan`;

  return (
    <div className="relative">
      <label className="block text-xs text-muted-foreground mb-1">Mahsulot</label>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="h-10 min-w-[180px] rounded-lg border bg-background px-3 text-sm flex items-center justify-between gap-2"
      >
        <span className="truncate">{label}</span>
        <ChevronDown className={`size-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 z-20 w-64 rounded-xl border bg-card shadow-xl p-2 max-h-64 overflow-y-auto">
          <button
            className="w-full text-left px-2 py-1.5 rounded-md text-xs text-muted-foreground hover:bg-muted"
            onClick={() => { onChange([]); setOpen(false); }}
          >
            Barchasi (tozalash)
          </button>
          {products.map((p) => (
            <label key={p.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted cursor-pointer">
              <input
                type="checkbox"
                checked={selected.includes(p.id)}
                onChange={() => toggle(p.id)}
                className="rounded"
              />
              <span className="text-sm truncate">{p.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Charts ──────────────────────────────────────────────────────────────────
function ProductionChart({ rows }: { rows: (string | number)[][] }) {
  const chartData = useMemo(() => {
    const byDate: Record<string, number> = {};
    for (const row of rows) {
      const date = String(row[0]).slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + (Number(row[3]) || 0);
    }
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-30)
      .map(([date, qop]) => ({ date: date.slice(5), qop: Math.round(qop * 10) / 10 }));
  }, [rows]);

  if (chartData.length < 2) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Ishlab chiqarish (kunlik, qop)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} />
          <Tooltip content={mkTooltip((v) => `${v} qop`)} />
          <Bar dataKey="qop" fill={C.bakery} radius={[3, 3, 0, 0]} name="Qop" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function PaymentsChart({ rows }: { rows: (string | number)[][] }) {
  const chartData = useMemo(() => {
    const byDate: Record<string, number> = {};
    for (const row of rows) {
      if (row[3] !== "UZS") continue;
      const date = String(row[0]).slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + (Number(row[4]) || 0);
    }
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-30)
      .map(([date, sum]) => ({ date: date.slice(5), sum: Math.round(sum / 1_000_000 * 10) / 10 }));
  }, [rows]);

  if (chartData.length < 2) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Kirim (kunlik, mln UZS)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} unit="M" />
          <Tooltip content={mkTooltip((v) => `${v} mln UZS`)} />
          <Bar dataKey="sum" fill={C.green} radius={[3, 3, 0, 0]} name="Kirim" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function OrdersChart({ rows }: { rows: (string | number)[][] }) {
  const chartData = useMemo(() => {
    const byDate: Record<string, number> = {};
    for (const row of rows) {
      if (row[4] !== "UZS") continue;
      const date = String(row[0]).slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + (Number(row[5]) || 0);
    }
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-30)
      .map(([date, sum]) => ({ date: date.slice(5), sum: Math.round(sum / 1_000_000 * 10) / 10 }));
  }, [rows]);

  if (chartData.length < 2) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Buyurtmalar jami summa (kunlik, mln UZS)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} unit="M" />
          <Tooltip content={mkTooltip((v) => `${v} mln UZS`)} />
          <Bar dataKey="sum" fill={C.blue} radius={[3, 3, 0, 0]} name="Summa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function PnlChart({ rows }: { rows: (string | number)[][] }) {
  const chartData = useMemo(() => {
    return rows
      .slice(-31)
      .map((row) => ({
        date: String(row[0]).slice(5),
        savdo: Math.round(Number(row[1]) / 1_000_000 * 10) / 10,
        foyda: Math.round(Number(row[7]) / 1_000_000 * 10) / 10,
      }));
  }, [rows]);

  if (chartData.length < 2) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Savdo va sof foyda (mln UZS)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} unit="M" />
          <Tooltip content={mkTooltip((v) => `${v} mln UZS`)} />
          <Bar dataKey="savdo" fill={C.blue} radius={[3, 3, 0, 0]} name="Savdo" />
          <Bar dataKey="foyda" fill={C.green} radius={[3, 3, 0, 0]} name="Sof foyda" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── COS tab ─────────────────────────────────────────────────────────────────
function ProductCosCard({ product }: { product: any }) {
  const hasMargin = product.sale_price_uzs > 0;
  const isProfit = product.margin_per_unit >= 0;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-5 py-3 border-b bg-muted/40 flex items-center justify-between">
        <span className="font-semibold">{product.product}</span>
        <span className="text-xs text-muted-foreground">{product.meshok_size} dona/qop</span>
      </div>

      <div className="p-4 space-y-4">
        {product.missing_prices?.length > 0 && (
          <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
            Narxi yo'q xomashyo (tan narxi to'liq emas): {product.missing_prices.join(", ")}
          </div>
        )}
        {/* Key metrics row */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-muted/40 p-3">
            <div className="text-xs text-muted-foreground mb-0.5">Tan narxi / qop</div>
            <div className="font-bold tabular-nums text-base">
              {formatMoney(String(Math.round(product.cos_per_meshok)), "UZS")}
            </div>
          </div>
          <div className="rounded-lg bg-muted/40 p-3">
            <div className="text-xs text-muted-foreground mb-0.5">Tan narxi / dona</div>
            <div className="font-bold tabular-nums text-base">
              {formatMoney(String(Math.round(product.cos_per_unit)), "UZS")}
            </div>
          </div>
          {hasMargin && (
            <>
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground mb-0.5">Sotuv narxi</div>
                <div className="font-semibold tabular-nums">
                  {formatMoney(String(product.sale_price_uzs), "UZS")}
                </div>
              </div>
              <div className={`rounded-lg p-3 ${isProfit ? "bg-green-50 dark:bg-green-950/30" : "bg-red-50 dark:bg-red-950/30"}`}>
                <div className="text-xs text-muted-foreground mb-0.5">Foyda / dona</div>
                <div className={`font-semibold tabular-nums ${isProfit ? "text-green-700 dark:text-green-400" : "text-red-600"}`}>
                  {formatMoney(String(Math.round(product.margin_per_unit)), "UZS")}
                  <span className="text-xs ml-1 font-normal">
                    ({product.margin_pct.toFixed(1)}%)
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Ingredient breakdown */}
        {product.ingredients.length > 0 && (
          <div className="border rounded-lg overflow-hidden text-xs">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Xomashyo</th>
                  <th className="px-3 py-2 text-right font-medium">Miqdor</th>
                  <th className="px-3 py-2 text-right font-medium">Narx</th>
                  <th className="px-3 py-2 text-right font-medium">Summa</th>
                </tr>
              </thead>
              <tbody>
                {product.ingredients.map((ing: any, i: number) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-1.5">{ing.name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {ing.qty} {ing.unit}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {ing.price_per_unit > 0
                        ? formatMoney(String(Math.round(ing.price_per_unit)), "UZS")
                        : <span className="text-amber-500">—</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {ing.cost > 0
                        ? formatMoney(String(Math.round(ing.cost)), "UZS")
                        : "—"}
                    </td>
                  </tr>
                ))}
                <tr className="border-t bg-muted/50">
                  <td className="px-3 py-1.5 font-medium" colSpan={3}>Xomashyo jami</td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-medium">
                    {formatMoney(String(Math.round(product.ingredient_total)), "UZS")}
                  </td>
                </tr>
                <tr className="border-t">
                  <td className="px-3 py-1.5 text-muted-foreground" colSpan={3}>Ish haqi (nonvoy)</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">
                    {formatMoney(String(Math.round(product.labour)), "UZS")}
                  </td>
                </tr>
                <tr className="border-t bg-muted font-semibold">
                  <td className="px-3 py-2" colSpan={3}>Jami tan narxi / qop</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatMoney(String(Math.round(product.cos_per_meshok)), "UZS")}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {product.ingredients.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-2">
            Retsept kiritilmagan
          </p>
        )}
      </div>
    </div>
  );
}

function CosTab() {
  const { data, isFetching, refetch } = useQuery<any>({
    queryKey: ["reports", "cos"],
    queryFn: async () => (await api.get("/reports/cos/")).data,
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Xomashyo narxlari Ombor sahifasida qo'lda kiritilgan narxdan olinadi. Tan narxiga nonvoy ish haqi ham qo'shilgan.
        </p>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="h-9 px-3 rounded-lg border text-sm hover:bg-muted inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCw className={"size-3.5 " + (isFetching ? "animate-spin" : "")} />
          Yangilash
        </button>
      </div>

      {isFetching && !data && (
        <div className="py-16 text-center text-muted-foreground text-sm">Yuklanmoqda…</div>
      )}

      {data && (
        <>
          {/* Ingredient price reference table */}
          <div className="rounded-xl border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
              <Package className="size-4 text-bakery-500" />
              Xomashyo narxlari (qo'lda kiritilgan)
            </div>
            <div className="overflow-auto max-h-72">
              <table className="w-full text-sm border-separate border-spacing-0">
                <thead className="bg-muted text-xs">
                  <tr>
                    <th className="sticky top-0 bg-muted px-4 py-2 text-left font-medium border-b">Xomashyo</th>
                    <th className="sticky top-0 bg-muted px-4 py-2 text-left font-medium border-b">Birlik</th>
                    <th className="sticky top-0 bg-muted px-4 py-2 text-right font-medium border-b">Narx (birlik)</th>
                    <th className="sticky top-0 bg-muted px-4 py-2 text-left font-medium border-b">Oxirgi xarid</th>
                    <th className="sticky top-0 bg-muted px-4 py-2 text-right font-medium border-b">Stok</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.ingredient_prices as any[]).map((ing) => (
                    <tr key={ing.id} className="border-t hover:bg-muted/40">
                      <td className="px-4 py-2">{ing.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">{ing.unit}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {ing.price > 0
                          ? formatMoney(String(Math.round(ing.price)), "UZS")
                          : <span className="text-amber-500 text-xs">Narx yo'q</span>}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground text-xs">{ing.last_date ?? "—"}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {ing.stock > 0
                          ? <span className="font-medium">{ing.stock}</span>
                          : <span className="text-red-500 text-xs">0</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-product COS cards */}
          {(data.products as any[]).length === 0 ? (
            <div className="rounded-xl border bg-card py-12 text-center text-muted-foreground text-sm">
              Mahsulot topilmadi
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {(data.products as any[]).map((p) => (
                <ProductCosCard key={p.product_id} product={p} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── SOFP tab ─────────────────────────────────────────────────────────────────
function SofpTab() {
  const { data, isFetching, refetch } = useQuery<any>({
    queryKey: ["reports", "sofp"],
    queryFn: async () => (await api.get("/reports/sofp/")).data,
  });

  if (isFetching && !data) {
    return <div className="py-16 text-center text-muted-foreground text-sm">Yuklanmoqda…</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        {data && (
          <p className="text-sm text-muted-foreground">Sana: <strong>{data.as_of}</strong></p>
        )}
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="h-9 px-3 rounded-lg border text-sm hover:bg-muted inline-flex items-center gap-1.5 disabled:opacity-50 ml-auto"
        >
          <RefreshCw className={"size-3.5 " + (isFetching ? "animate-spin" : "")} />
          Yangilash
        </button>
      </div>

      {data && (
        <>
          {/* Summary cards */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="size-4 text-green-500" />
                <span className="text-xs text-muted-foreground">Naqd pul (kassalar)</span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {formatMoney(String(Math.round(data.cash.total_uzs)), "UZS")}
              </div>
              {data.cash.total_usd > 0 && (
                <div className="text-sm font-semibold tabular-nums text-muted-foreground">
                  {formatMoney(String(data.cash.total_usd), "USD")}
                </div>
              )}
            </div>
            <div className="rounded-xl border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="size-4 text-blue-500" />
                <span className="text-xs text-muted-foreground">Do'kon qarzlari</span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {formatMoney(String(Math.round(data.receivables.total_uzs)), "UZS")}
              </div>
              {data.receivables.total_usd > 0 && (
                <div className="text-sm font-semibold tabular-nums text-muted-foreground">
                  {formatMoney(String(data.receivables.total_usd), "USD")}
                </div>
              )}
            </div>
            <div className="rounded-xl border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <Warehouse className="size-4 text-amber-500" />
                <span className="text-xs text-muted-foreground">Ombor qiymati</span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {formatMoney(String(Math.round(data.inventory.total_uzs)), "UZS")}
              </div>
            </div>
            <div className="rounded-xl border bg-bakery-500 text-white p-4">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="size-4 text-white/80" />
                <span className="text-xs text-white/80">Jami aktivlar</span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {formatMoney(String(Math.round(data.total_assets_uzs)), "UZS")}
              </div>
              {data.total_assets_usd > 0 && (
                <div className="text-sm font-semibold tabular-nums text-white/80">
                  {formatMoney(String(data.total_assets_usd), "USD")}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Cash */}
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <DollarSign className="size-4 text-green-500" />
                Kassalar
              </div>
              <div className="divide-y">
                {(data.cash.items as any[]).map((a, i) => (
                  <div key={i} className="px-5 py-3 flex items-center justify-between text-sm">
                    <span>{a.name}</span>
                    <div className="text-right">
                      <div className="tabular-nums font-semibold">
                        {formatMoney(String(Math.round(a.uzs)), "UZS")}
                      </div>
                      {a.usd > 0 && (
                        <div className="tabular-nums text-xs text-muted-foreground">
                          {formatMoney(String(a.usd), "USD")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div className="px-5 py-3 flex items-center justify-between text-sm bg-muted/40 font-semibold">
                  <span>Jami</span>
                  <div className="text-right">
                    <div className="tabular-nums">{formatMoney(String(Math.round(data.cash.total_uzs)), "UZS")}</div>
                    {data.cash.total_usd > 0 && (
                      <div className="tabular-nums text-xs text-muted-foreground">
                        {formatMoney(String(data.cash.total_usd), "USD")}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Receivables */}
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <TrendingUp className="size-4 text-blue-500" />
                Do'kon qarzlari
              </div>
              {(data.receivables.items as any[]).length === 0 ? (
                <div className="px-5 py-8 text-center text-sm text-muted-foreground">Qarz yo'q</div>
              ) : (
                <div className="divide-y max-h-64 overflow-auto">
                  {(data.receivables.items as any[]).map((r, i) => (
                    <div key={i} className="px-5 py-2.5 flex items-center justify-between text-sm">
                      <span className="truncate mr-2">{r.name}</span>
                      <div className="text-right whitespace-nowrap">
                        {r.uzs > 0 && (
                          <div className="tabular-nums font-medium">
                            {formatMoney(String(Math.round(r.uzs)), "UZS")}
                          </div>
                        )}
                        {r.usd > 0 && (
                          <div className="tabular-nums text-xs text-muted-foreground">
                            {formatMoney(String(r.usd), "USD")}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="px-5 py-3 flex items-center justify-between text-sm bg-muted/40 font-semibold">
                    <span>Jami</span>
                    <div className="text-right">
                      <div className="tabular-nums">{formatMoney(String(Math.round(data.receivables.total_uzs)), "UZS")}</div>
                      {data.receivables.total_usd > 0 && (
                        <div className="tabular-nums text-xs text-muted-foreground">
                          {formatMoney(String(data.receivables.total_usd), "USD")}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Inventory */}
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <Warehouse className="size-4 text-amber-500" />
                Ombor (tan narxi bo'yicha)
              </div>
              <div className="overflow-auto max-h-64">
                <table className="w-full text-sm border-separate border-spacing-0">
                  <thead className="bg-muted text-xs">
                    <tr>
                      <th className="sticky top-0 bg-muted px-4 py-2 text-left font-medium border-b">Xomashyo</th>
                      <th className="sticky top-0 bg-muted px-4 py-2 text-right font-medium border-b">Miqdor</th>
                      <th className="sticky top-0 bg-muted px-4 py-2 text-right font-medium border-b">Qiymat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.inventory.items as any[]).map((item, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-4 py-1.5">{item.name}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-muted-foreground text-xs">
                          {item.qty} {item.unit}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums font-medium">
                          {formatMoney(String(Math.round(item.value)), "UZS")}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t bg-muted">
                      <td className="px-4 py-2 font-semibold" colSpan={2}>Jami</td>
                      <td className="px-4 py-2 text-right tabular-nums font-semibold">
                        {formatMoney(String(Math.round(data.inventory.total_uzs)), "UZS")}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Liabilities (customer credits) + net worth */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <TrendingUp className="size-4 rotate-180 text-red-500" />
                Majburiyatlar — do'kon kreditlari
              </div>
              {(data.liabilities?.customer_credits?.items as any[] ?? []).length === 0 ? (
                <div className="px-5 py-8 text-center text-sm text-muted-foreground">Majburiyat yo'q</div>
              ) : (
                <div className="divide-y max-h-64 overflow-auto">
                  {(data.liabilities.customer_credits.items as any[]).map((r, i) => (
                    <div key={i} className="px-5 py-2.5 flex items-center justify-between text-sm">
                      <span className="truncate mr-2">{r.name}</span>
                      <div className="text-right whitespace-nowrap">
                        {r.uzs > 0 && (
                          <div className="tabular-nums font-medium">{formatMoney(String(Math.round(r.uzs)), "UZS")}</div>
                        )}
                        {r.usd > 0 && (
                          <div className="tabular-nums text-xs text-muted-foreground">{formatMoney(String(r.usd), "USD")}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="px-5 py-3 flex items-center justify-between text-sm bg-muted/40 font-semibold">
                    <span>Jami</span>
                    <div className="text-right">
                      <div className="tabular-nums">{formatMoney(String(Math.round(data.liabilities.total_uzs)), "UZS")}</div>
                      {data.liabilities.total_usd > 0 && (
                        <div className="tabular-nums text-xs text-muted-foreground">{formatMoney(String(data.liabilities.total_usd), "USD")}</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="rounded-xl border bg-card p-5 flex flex-col justify-center">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="size-4 text-bakery-500" />
                <span className="text-sm text-muted-foreground">Sof qiymat (aktivlar − majburiyatlar)</span>
              </div>
              <div className="text-2xl font-bold tabular-nums">
                {formatMoney(String(Math.round(data.net_worth_uzs ?? data.total_assets_uzs)), "UZS")}
              </div>
              {(data.net_worth_usd ?? 0) !== 0 && (
                <div className="text-sm font-semibold tabular-nums text-muted-foreground mt-0.5">
                  {formatMoney(String(data.net_worth_usd), "USD")}
                </div>
              )}
              <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                Naqd + do'kon qarzlari + ombor qiymati, do'kon kreditlari ayirilgan holda.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Gross Daily tab ──────────────────────────────────────────────────────────
function GrossDailyTab() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);

  const { data, isFetching, refetch } = useQuery<any>({
    queryKey: ["reports", "gross-daily", date],
    queryFn: async () => (await api.get(`/reports/gross-daily/?date=${date}`)).data,
  });

  const pnl = data?.pnl;
  const isProfit = pnl ? pnl.net_profit >= 0 : false;

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="rounded-xl border bg-card p-3 sm:p-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Sana</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="h-10 rounded-lg border bg-background px-3 text-sm"
          />
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="h-10 px-4 rounded-lg border text-sm hover:bg-muted inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCw className={"size-4 " + (isFetching ? "animate-spin" : "")} />
          Yangilash
        </button>
      </div>

      {isFetching && !data && (
        <div className="py-16 text-center text-muted-foreground text-sm">Yuklanmoqda…</div>
      )}

      {data && (
        <>
          {/* P&L summary cards */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Savdo", val: pnl.sales, icon: <TrendingUp className="size-4 text-blue-500" /> },
              { label: "Tan narxi", val: pnl.cos, icon: <Package className="size-4 text-amber-500" /> },
              { label: "Yalpi foyda", val: pnl.gross_profit, icon: <DollarSign className="size-4 text-green-500" /> },
            ].map((c) => (
              <div key={c.label} className="rounded-xl border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">{c.icon}<span className="text-xs text-muted-foreground">{c.label}</span></div>
                <div className="text-lg font-bold tabular-nums">{formatMoney(String(Math.round(c.val)), "UZS")}</div>
              </div>
            ))}
            <div className={`rounded-xl border p-4 ${isProfit ? "bg-bakery-500 text-white" : "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900"}`}>
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className={`size-4 ${isProfit ? "text-white/80" : "text-red-500"}`} />
                <span className={`text-xs ${isProfit ? "text-white/80" : "text-red-600 dark:text-red-400"}`}>Sof foyda</span>
              </div>
              <div className={`text-lg font-bold tabular-nums ${isProfit ? "" : "text-red-600 dark:text-red-400"}`}>
                {formatMoney(String(Math.round(pnl.net_profit)), "UZS")}
              </div>
            </div>
          </div>

          {/* Expenses detail row */}
          {(pnl.expenses > 0 || pnl.salary > 0) && (
            <div className="grid gap-3 grid-cols-2">
              <div className="rounded-xl border bg-card p-3 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Xarajatlar</span>
                <span className="font-semibold tabular-nums">{formatMoney(String(Math.round(pnl.expenses)), "UZS")}</span>
              </div>
              <div className="rounded-xl border bg-card p-3 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Oylik to'lovlar</span>
                <span className="font-semibold tabular-nums">{formatMoney(String(Math.round(pnl.salary)), "UZS")}</span>
              </div>
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            Tan narxi = materiallar + kommunal (gaz/svet) + nonvoy ish haqi · Oylik to'lovlar = boshqa xodimlar.
          </p>

          {/* Cross-tab: clients × products */}
          {data.clients.length > 0 ? (
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <TrendingUp className="size-4 text-bakery-500" />
                Do'konlar bo'yicha sotuv — {date}
                <span className="ml-auto text-muted-foreground font-normal">{data.clients.length} do'kon</span>
              </div>
              <div className="overflow-auto">
                <table className="w-full text-sm border-separate border-spacing-0">
                  <thead className="bg-muted text-xs">
                    <tr>
                      <th className="sticky top-0 left-0 z-20 bg-muted px-4 py-2.5 text-left font-medium border-b min-w-[140px]">Do'kon</th>
                      {(data.products as any[]).map((p: any) => (
                        <th key={p.id} className="sticky top-0 bg-muted px-3 py-2.5 text-right font-medium border-b whitespace-nowrap">{p.name}</th>
                      ))}
                      <th className="sticky top-0 bg-muted px-4 py-2.5 text-right font-medium border-b">Jami</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.clients as any[]).map((client: any, ri: number) => (
                      <tr key={ri} className={ri % 2 === 1 ? "bg-muted/20" : "bg-card"}>
                        <td className="sticky left-0 bg-inherit px-4 py-2 font-medium border-b whitespace-nowrap">{client.shop}</td>
                        {(client.cells as any[]).map((cell: any, ci: number) => (
                          <td key={ci} className="px-3 py-2 text-right tabular-nums border-b">
                            {cell.qty > 0 ? (
                              <div>
                                <div className="font-medium">{cell.qty.toLocaleString()}</div>
                                <div className="text-xs text-muted-foreground">{formatMoney(String(Math.round(cell.total)), "UZS")}</div>
                              </div>
                            ) : <span className="text-muted-foreground/40">—</span>}
                          </td>
                        ))}
                        <td className="px-4 py-2 text-right tabular-nums font-semibold border-b">
                          {formatMoney(String(Math.round(client.total)), "UZS")}
                        </td>
                      </tr>
                    ))}
                    {/* Column totals */}
                    <tr className="bg-muted font-semibold text-xs">
                      <td className="sticky left-0 bg-muted px-4 py-2.5 border-t">Jami</td>
                      {(data.column_totals as any[]).map((ct: any, ci: number) => (
                        <td key={ci} className="px-3 py-2.5 text-right tabular-nums border-t">
                          <div>{ct.qty > 0 ? ct.qty.toLocaleString() : "—"}</div>
                          {ct.total > 0 && <div className="text-muted-foreground font-normal">{formatMoney(String(Math.round(ct.total)), "UZS")}</div>}
                        </td>
                      ))}
                      <td className="px-4 py-2.5 text-right tabular-nums border-t">
                        {formatMoney(String(Math.round(data.grand_total_sales)), "UZS")}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border bg-card py-12 text-center text-muted-foreground text-sm">
              {date} kuni buyurtma topilmadi
            </div>
          )}

          {/* Production batches */}
          {data.production.length > 0 && (
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b font-semibold text-sm flex items-center gap-2">
                <Package className="size-4 text-amber-500" />
                Ishlab chiqarish (tan narxi hisob-kitobi)
              </div>
              <table className="w-full text-sm border-separate border-spacing-0">
                <thead className="bg-muted text-xs">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium border-b">Mahsulot</th>
                    <th className="px-4 py-2 text-right font-medium border-b">Qop</th>
                    <th className="px-4 py-2 text-right font-medium border-b">Tan narxi / qop</th>
                    <th className="px-4 py-2 text-right font-medium border-b">Jami COS</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.production as any[]).map((p: any, i: number) => (
                    <tr key={i} className={i % 2 === 1 ? "bg-muted/20" : ""}>
                      <td className="px-4 py-2 border-b">{p.product}</td>
                      <td className="px-4 py-2 text-right tabular-nums border-b">{p.meshoks}</td>
                      <td className="px-4 py-2 text-right tabular-nums border-b">{formatMoney(String(Math.round(p.cos_per_meshok)), "UZS")}</td>
                      <td className="px-4 py-2 text-right tabular-nums border-b font-medium">{formatMoney(String(Math.round(p.cos_total)), "UZS")}</td>
                    </tr>
                  ))}
                  <tr className="bg-muted font-semibold">
                    <td className="px-4 py-2.5 border-t" colSpan={3}>Ishlab chiqarilgan tan narxi jami</td>
                    <td className="px-4 py-2.5 text-right tabular-nums border-t">{formatMoney(String(Math.round(data.production_cos_total ?? 0)), "UZS")}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Summary cards ────────────────────────────────────────────────────────────
function SummaryCards({ data, type }: { data: ReportData | undefined; type: ReportType }) {
  if (!data) return null;
  const s = data.summary;
  const cards: { label: string; value: string; accent?: boolean }[] = [];

  if (type === "pnl_daily" || type === "gross_overall") {
    cards.push({ label: "Savdo", value: formatMoney(String(s.total_sales ?? 0), "UZS") });
    cards.push({ label: "Tan narxi", value: formatMoney(String(s.total_cos ?? 0), "UZS") });
    cards.push({ label: "Yalpi foyda", value: formatMoney(String(s.total_gross_profit ?? 0), "UZS") });
    cards.push({
      label: "Sof foyda",
      value: formatMoney(String(s.total_net_profit ?? 0), "UZS"),
      accent: (s.total_net_profit ?? 0) >= 0,
    });
  } else {
    if (s.total_uzs !== undefined) {
      cards.push({
        label: type === "orders" ? "Buyurtma (UZS)" : "Jami (UZS)",
        value: formatMoney(String(s.total_uzs), "UZS"),
      });
    }
    if (s.total_usd !== undefined && s.total_usd > 0) {
      cards.push({ label: "Jami (USD)", value: formatMoney(String(s.total_usd), "USD") });
    }
    if (type === "orders") {
      cards.push({ label: "Yetkazilgan (UZS)", value: formatMoney(String(s.total_delivered_uzs ?? 0), "UZS") });
      if ((s.total_delivered_usd ?? 0) > 0) {
        cards.push({ label: "Yetkazilgan (USD)", value: formatMoney(String(s.total_delivered_usd ?? 0), "USD") });
      }
    }
    if (type === "production") {
      cards.push({ label: "Jami qop", value: String(s.total_meshok ?? 0) });
      cards.push({ label: "Jami dona", value: String(s.total_units ?? 0) });
    }
    if (type === "shop_debts") {
      cards.push({ label: "Jami qarz (UZS)", value: formatMoney(String(s.total_uzs_debt ?? 0), "UZS") });
      if ((s.total_usd_debt ?? 0) > 0) {
        cards.push({ label: "Jami qarz (USD)", value: formatMoney(String(s.total_usd_debt ?? 0), "USD") });
      }
      cards.push({ label: "Limitdan oshgan", value: String(s.over_count ?? 0) });
    }
    cards.push({ label: "Yozuvlar", value: String(s.count ?? 0) });
  }

  return (
    <div className="grid gap-2 sm:gap-3 grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className={
            "rounded-xl border p-3 sm:p-4 " +
            (c.accent ? "bg-bakery-500 text-white border-bakery-500" : "bg-card")
          }
        >
          <div className={c.accent ? "text-xs text-white/80 truncate" : "text-xs text-muted-foreground truncate"}>
            {c.label}
          </div>
          <div className="mt-1 text-base sm:text-lg font-semibold tabular-nums truncate">{c.value}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Gross Overall drill-down modal ──────────────────────────────────────────
// Which gross_overall column maps to which detail metric.
const GROSS_METRICS: Record<number, { key: string; label: string }> = {
  1: { key: "sales", label: "Savdo" },
  2: { key: "cos", label: "Tan narxi" },
  3: { key: "gross_profit", label: "Yalpi foyda" },
  4: { key: "expenses", label: "Xarajatlar" },
  5: { key: "op_profit", label: "Op. foyda" },
  6: { key: "salary", label: "Oylik" },
  7: { key: "net_profit", label: "Sof foyda" },
};

function Money({ v }: { v: number }) {
  return (
    <span className={"tabular-nums " + (v < 0 ? "text-red-600 dark:text-red-400" : "")}>
      {formatMoney(String(Math.round(v)), "UZS")}
    </span>
  );
}

const fm = (v: number) => formatMoney(String(Math.round(v)), "UZS");

function PnlDetailModal({
  from, to, weekLabel, metricKey, metricLabel, onClose,
}: {
  from: string; to: string; weekLabel: string;
  metricKey: string; metricLabel: string; onClose: () => void;
}) {
  const { data, isFetching } = useQuery<any>({
    queryKey: ["reports", "pnl-detail", from, to],
    queryFn: async () => (await api.get(`/reports/pnl-detail/?date_from=${from}&date_to=${to}`)).data,
  });

  // Every waterfall row is expandable — click it to drill into its breakdown
  // inline. Seed the row the user clicked from the Gross Overall table as open.
  const [open, setOpen] = useState<Record<string, boolean>>({ [metricKey]: true });
  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  const waterfall = data ? [
    { key: "sales", label: "Savdo", val: data.sales.total, sum: false },
    { key: "cos", label: "− Tan narxi", val: -data.cos.total, sum: false },
    { key: "gross_profit", label: "= Yalpi foyda", val: data.gross_profit, sum: true },
    { key: "expenses", label: "− Xarajatlar", val: -data.expenses.total, sum: false },
    { key: "op_profit", label: "= Op. foyda", val: data.op_profit, sum: true },
    { key: "salary", label: "− Oylik", val: -data.salary.total, sum: false },
    { key: "net_profit", label: "= Sof foyda", val: data.net_profit, sum: true },
  ] : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="bg-card rounded-2xl border shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-4 border-b flex items-start justify-between gap-3">
          <div>
            <div className="text-xs text-muted-foreground">{weekLabel} · {fmtDMY(from)} → {fmtDMY(to)}</div>
            <h3 className="font-semibold text-lg flex items-center gap-2">
              <BarChart3 className="size-5 text-bakery-500" /> {metricLabel}
            </h3>
          </div>
          <button onClick={onClose} className="rounded-lg border px-2 py-1 text-sm hover:bg-muted">✕</button>
        </header>

        <div className="overflow-auto p-5 space-y-3">
          {isFetching && !data && <div className="py-10 text-center text-muted-foreground text-sm">Yuklanmoqda…</div>}

          {data && (
            <>
              <p className="text-xs text-muted-foreground">Har bir qatorni bosib tafsilotlarini oching.</p>
              <div className="rounded-xl border overflow-hidden text-sm divide-y">
                {waterfall.map((r) => {
                  const isOpen = !!open[r.key];
                  return (
                    <div key={r.key} className={r.sum ? "bg-muted/30" : ""}>
                      <button
                        onClick={() => toggle(r.key)}
                        className={
                          "w-full px-4 py-2.5 flex items-center justify-between gap-2 text-left transition hover:bg-bakery-500/5 " +
                          (r.key === metricKey ? "bg-bakery-500/10 " : "") +
                          (r.sum ? "font-semibold" : "font-medium")
                        }
                      >
                        <span className="flex items-center gap-1.5">
                          <ChevronRight className={"size-4 text-muted-foreground transition-transform " + (isOpen ? "rotate-90" : "")} />
                          {r.label}
                        </span>
                        <Money v={r.val} />
                      </button>
                      {isOpen && (
                        <div className="px-3 pb-3 pt-1 bg-muted/10">
                          <MetricDetail k={r.key} data={data} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Inline breakdown for one waterfall row. Component rows show their line items;
// derived rows (gross/op/net) show the formula that produced them.
function MetricDetail({ k, data }: { k: string; data: any }) {
  if (k === "sales") {
    return (
      <DetailTable
        title="Mahsulot bo'yicha (yetkazilgan)"
        head={["Mahsulot", "Miqdor", "Summa"]}
        rows={data.sales.items.map((i: any) => [i.name, i.qty.toLocaleString(), <Money v={i.amount} />])}
        foot={["Jami", "", <Money v={data.sales.total} />]}
        empty="Savdo yo'q"
      />
    );
  }
  if (k === "cos") return <CosDetail cos={data.cos} />;
  if (k === "expenses") {
    return (
      <GroupedDetail
        items={data.expenses.items}
        total={data.expenses.total}
        groupKey={(i: any) => i.category}
        cols={[
          { render: (i: any) => fmtDMY(i.date) },
          { render: (i: any) => i.title },
          { render: (i: any) => <Money v={i.amount} />, align: "right" },
        ]}
        empty="Xarajat yo'q"
      />
    );
  }
  if (k === "salary") {
    return (
      <GroupedDetail
        items={data.salary.items}
        total={data.salary.total}
        groupKey={(i: any) => i.user}
        cols={[
          { render: (i: any) => fmtDMY(i.date) },
          { render: (i: any) => i.kind },
          { render: (i: any) => <Money v={i.amount} />, align: "right" },
        ]}
        empty="Oylik to'lovi yo'q"
      />
    );
  }
  if (k === "gross_profit")
    return <Formula text={`Yalpi foyda = Savdo − Tan narxi = ${fm(data.sales.total)} − ${fm(data.cos.total)} = ${fm(data.gross_profit)}`} />;
  if (k === "op_profit")
    return <Formula text={`Op. foyda = Yalpi foyda − Xarajatlar = ${fm(data.gross_profit)} − ${fm(data.expenses.total)} = ${fm(data.op_profit)}`} />;
  if (k === "net_profit")
    return <Formula text={`Sof foyda = Op. foyda − Oylik = ${fm(data.op_profit)} − ${fm(data.salary.total)} = ${fm(data.net_profit)}`} />;
  return null;
}

// Tan narxi = materials (recipe cost of goods sold) + nonvoy production wages.
function CosDetail({ cos }: { cos: any }) {
  return (
    <div className="space-y-3">
      <DetailTable
        title={`Materiallar — ${fm(cos.materials_total ?? cos.total)}`}
        head={["Mahsulot", "Miqdor", "Tannarx/dona", "Summa"]}
        rows={(cos.items ?? []).map((i: any) => [i.name, i.qty.toLocaleString(), <Money v={i.unit_cost} />, <Money v={i.amount} />])}
        foot={["Jami", "", "", <Money v={cos.materials_total ?? cos.total} />]}
        empty="Material tannarxi yo'q"
      />
      {(cos.communal_total ?? 0) > 0 && (
        <DetailTable
          title={`Kommunal (gaz/svet) — ${fm(cos.communal_total)}`}
          head={["Mahsulot", "Miqdor", "1 dona", "Summa"]}
          rows={(cos.communal_items ?? []).map((i: any) => [i.name, i.qty.toLocaleString(), <Money v={i.unit_cost} />, <Money v={i.amount} />])}
          foot={["Jami", "", "", <Money v={cos.communal_total} />]}
          empty="Kommunal xarajat yo'q"
        />
      )}
      <div>
        <div className="text-sm font-semibold mb-2">Ishlab chiqarish ish haqi (nonvoy) — {fm(cos.salary_total ?? 0)}</div>
        <GroupedDetail
          items={cos.salary_items ?? []}
          total={cos.salary_total ?? 0}
          groupKey={(i: any) => i.user}
          cols={[
            { render: (i: any) => fmtDMY(i.date) },
            { render: (i: any) => i.kind },
            { render: (i: any) => <Money v={i.amount} />, align: "right" },
          ]}
          empty="Ishlab chiqarish ish haqi yo'q"
        />
      </div>
    </div>
  );
}

// Records grouped by a key (category / employee). Click a group to expand its rows.
function GroupedDetail({
  items, total, groupKey, cols, empty,
}: {
  items: any[];
  total: number;
  groupKey: (i: any) => string;
  cols: { render: (i: any) => any; align?: "left" | "right" }[];
  empty?: string;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (!items || items.length === 0)
    return <div className="rounded-lg border bg-card text-center text-muted-foreground text-sm py-4">{empty ?? "Ma'lumot yo'q"}</div>;

  const groups = new Map<string, { total: number; rows: any[] }>();
  for (const it of items) {
    const key = groupKey(it) || "—";
    const g = groups.get(key) ?? { total: 0, rows: [] };
    g.total += it.amount;
    g.rows.push(it);
    groups.set(key, g);
  }
  const sorted = [...groups.entries()].sort((a, b) => Math.abs(b[1].total) - Math.abs(a[1].total));

  return (
    <div className="rounded-lg border overflow-hidden divide-y bg-card">
      {sorted.map(([name, g]) => {
        const isOpen = !!open[name];
        return (
          <div key={name}>
            <button
              onClick={() => setOpen((o) => ({ ...o, [name]: !o[name] }))}
              className="w-full px-3 py-2 flex items-center justify-between gap-2 text-left text-sm hover:bg-muted/40"
            >
              <span className="flex items-center gap-1.5 font-medium min-w-0">
                <ChevronRight className={"size-3.5 shrink-0 text-muted-foreground transition-transform " + (isOpen ? "rotate-90" : "")} />
                <span className="truncate">{name}</span>
                <span className="text-xs text-muted-foreground shrink-0">({g.rows.length})</span>
              </span>
              <Money v={g.total} />
            </button>
            {isOpen && (
              <div className="overflow-x-auto bg-muted/20">
                <table className="w-full text-sm">
                  <tbody>
                    {g.rows.map((it, ri) => (
                      <tr key={ri} className="border-t">
                        {cols.map((c, ci) => (
                          <td
                            key={ci}
                            className={"px-3 py-1.5 " + (c.align === "right" ? "text-right tabular-nums" : "text-left") + (ci === 0 ? " text-muted-foreground whitespace-nowrap tabular-nums" : "")}
                          >
                            {c.render(it)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
      <div className="px-3 py-2 flex items-center justify-between bg-muted font-semibold text-sm">
        <span>Jami</span>
        <Money v={total} />
      </div>
    </div>
  );
}

function Formula({ text }: { text: string }) {
  return <div className="rounded-lg border bg-card p-3 text-sm tabular-nums">{text}</div>;
}

function DetailTable({
  title, head, rows, foot, empty,
}: {
  title?: string; head: string[]; rows: any[][]; foot?: any[]; empty?: string;
}) {
  return (
    <div>
      {title && <div className="text-sm font-semibold mb-2">{title}</div>}
      <div className="rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-xs text-muted-foreground">
            <tr>{head.map((h, i) => <th key={i} className={"px-3 py-2 " + (i === 0 ? "text-left" : "text-right")}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={head.length} className="px-3 py-6 text-center text-muted-foreground">{empty ?? "Ma'lumot yo'q"}</td></tr>
            ) : rows.map((r, ri) => (
              <tr key={ri} className="border-t">
                {r.map((c, ci) => <td key={ci} className={"px-3 py-1.5 " + (ci === 0 ? "text-left" : "text-right")}>{c}</td>)}
              </tr>
            ))}
          </tbody>
          {foot && rows.length > 0 && (
            <tfoot className="bg-muted font-semibold">
              <tr>{foot.map((c, ci) => <td key={ci} className={"px-3 py-2 " + (ci === 0 ? "text-left" : "text-right")}>{c}</td>)}</tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = new Date();
  monthStart.setDate(1);
  const [dateFrom, setDateFrom] = useState(monthStart.toISOString().slice(0, 10));
  const [dateTo, setDateTo] = useState(today);
  const [active, setActive] = useState<ReportType>("pnl_daily");
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [pinFirst, setPinFirst] = useState(true);
  const [productFilter, setProductFilter] = useState<number[]>([]);
  // Gross Overall drill-down modal
  const [detail, setDetail] = useState<
    { from: string; to: string; weekLabel: string; metricKey: string; metricLabel: string } | null
  >(null);

  const report = REPORTS.find((r) => r.type === active)!;

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "for-report"],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false&page_size=200")).data,
    enabled: active === "production",
  });

  const { data, isFetching, refetch } = useQuery<ReportData>({
    queryKey: [
      "reports", "data", active,
      report.supportsDateRange ? dateFrom : "",
      report.supportsDateRange ? dateTo : "",
      active === "production" ? productFilter : [],
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("type", active);
      if (report.supportsDateRange) {
        params.set("date_from", dateFrom);
        params.set("date_to", dateTo);
      }
      if (active === "production" && productFilter.length > 0) {
        for (const id of productFilter) params.append("products[]", String(id));
      }
      return (await api.get<ReportData>(`/reports/data/?${params}`)).data;
    },
    enabled: !report.special,
  });

  const filteredRows = useMemo(() => {
    if (!data) return [];
    // gross_overall has subtotal rows that must stay in order — skip search/sort
    if (active === "gross_overall") return data.rows.slice();
    const q = search.trim().toLowerCase();
    const base = q
      ? data.rows.filter((row) => row.some((cell) => String(cell).toLowerCase().includes(q)))
      : data.rows.slice();
    if (sortCol == null) return base;
    const isMoney = report.moneyCols?.includes(sortCol);
    return [...base].sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      let cmp = 0;
      if (isMoney || (typeof av === "number" && typeof bv === "number")) {
        cmp = Number(av) - Number(bv);
      } else {
        cmp = String(av).localeCompare(String(bv), "uz");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, search, sortCol, sortDir, report.moneyCols, active]);

  const columnTotals = useMemo(() => {
    if (!data || !report.moneyCols?.length) return null;
    // gross_overall already contains week + month total rows — no footer needed
    if (active === "gross_overall") return null;
    // Totals are split per currency so UZS and USD are never added together.
    const totals: Record<number, { UZS: number; USD: number }> = {};
    for (const col of report.moneyCols) {
      if (report.noTotalCols?.includes(col)) continue;
      const acc = { UZS: 0, USD: 0 };
      for (const r of filteredRows) {
        const cur = (
          report.currencyCol != null
            ? String(r[report.currencyCol])
            : report.colCurrency?.[col] ?? "UZS"
        ) as "UZS" | "USD";
        const v = Number(r[col]) || 0;
        if (cur === "USD") acc.USD += v;
        else acc.UZS += v;
      }
      totals[col] = acc;
    }
    return totals;
  }, [data, filteredRows, report.moneyCols, report.currencyCol, report.colCurrency, report.noTotalCols, active]);

  const toggleSort = (col: number) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const copyToClipboard = async () => {
    if (!data) return;
    const tsv = [
      data.headers.join("\t"),
      ...filteredRows.map((r) => r.map((c) => String(c)).join("\t")),
    ].join("\n");
    await navigator.clipboard.writeText(tsv);
  };

  const downloadXlsx = async () => {
    if (!report.xlsxEndpoint) return;
    const params = new URLSearchParams();
    if (report.supportsDateRange) {
      params.set("date_from", dateFrom);
      params.set("date_to", dateTo);
    }
    if (active === "production" && productFilter.length > 0) {
      for (const id of productFilter) params.append("products[]", String(id));
    }
    const res = await api.get(report.xlsxEndpoint, {
      params,
      responseType: "blob",
    });
    const blob = new Blob([res.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const cd = (res.headers as Record<string, string>)["content-disposition"] || "";
    const match = /filename="?([^";]+)"?/.exec(cd);
    link.href = url;
    link.download = match ? match[1] : `${report.title}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart3 className="size-5 sm:size-6 text-bakery-500" /> Hisobotlar
          </h1>
          <p className="text-muted-foreground text-sm">
            Savdo · tan narxi · moliyaviy holat
          </p>
        </div>
        {report.xlsxEndpoint && (
          <button
            onClick={downloadXlsx}
            className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
          >
            <Download className="size-4" /> Excel yuklab olish
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {REPORTS.map((r) => (
          <button
            key={r.type}
            onClick={() => {
              setActive(r.type);
              if (r.type !== "production") setProductFilter([]);
              setSearch("");
              setSortCol(null);
            }}
            className={
              "h-9 px-4 rounded-full border text-sm transition-colors " +
              (active === r.type
                ? "bg-bakery-500 border-bakery-500 text-white"
                : "bg-card hover:bg-muted")
            }
          >
            {r.title}
          </button>
        ))}
      </div>

      {/* Special tabs bypass the generic table */}
      {active === "gross_daily" && <GrossDailyTab />}
      {active === "cos" && <CosTab />}
      {active === "sofp" && <SofpTab />}

      {/* Standard table-based reports */}
      {!report.special && (
        <>
          {/* Filter bar */}
          <div className="rounded-xl border bg-card p-3 sm:p-4 grid grid-cols-2 sm:flex sm:flex-wrap sm:items-end gap-2 sm:gap-3">
            {report.supportsDateRange && (
              <>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Sana boshi</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Sana oxiri</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                  />
                </div>
              </>
            )}
            {active === "production" && (
              <ProductMultiSelect
                products={products?.results ?? []}
                selected={productFilter}
                onChange={setProductFilter}
              />
            )}
            <div className="col-span-2 sm:flex-1 sm:min-w-[220px]">
              <label className="block text-xs text-muted-foreground mb-1">Qidiruv</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Istalgan ustun bo'yicha filtr…"
                  className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm"
                />
              </div>
            </div>
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="col-span-2 sm:col-auto h-10 px-4 rounded-lg border text-sm hover:bg-muted inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
              title="Yangilash"
            >
              <RefreshCw className={"size-4 " + (isFetching ? "animate-spin" : "")} />
              Yangilash
            </button>
          </div>

          <SummaryCards data={data} type={active} />

          {(active === "pnl_daily" || active === "gross_overall") && (
            <p className="text-xs text-muted-foreground -mt-1">
              <span className="font-medium text-foreground">Tan narxi</span> = materiallar + kommunal + nonvoy ish haqi ·{" "}
              <span className="font-medium text-foreground">Oylik</span> = boshqa xodimlar (menejer, haydovchi…).{" "}
              {active === "gross_overall" && "Har bir raqamni bosib tarkibini oching."}
            </p>
          )}

          {/* Charts */}
          {active === "production" && filteredRows.length > 1 && (
            <ProductionChart rows={filteredRows} />
          )}
          {active === "payments" && filteredRows.length > 1 && (
            <PaymentsChart rows={filteredRows} />
          )}
          {active === "orders" && filteredRows.length > 1 && (
            <OrdersChart rows={filteredRows} />
          )}
          {active === "pnl_daily" && filteredRows.length > 1 && (
            <PnlChart rows={filteredRows} />
          )}

          {/* Table */}
          <div className="rounded-xl border bg-card overflow-hidden">
            <div className="px-4 sm:px-5 py-3 border-b flex items-center justify-between text-sm gap-3 flex-wrap">
              <span className="font-semibold">{report.title}</span>
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pinFirst}
                    onChange={(e) => setPinFirst(e.target.checked)}
                    className="rounded"
                  />
                  Birinchi ustun qotirilgan
                </label>
                <button
                  onClick={copyToClipboard}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  title="Clipboard ga nusxa (Excel ga yopishtiriladi)"
                >
                  <Copy className="size-3.5" /> Nusxa
                </button>
                <span className="text-muted-foreground">
                  {isFetching ? "Yuklanmoqda…" : `${filteredRows.length} qator`}
                </span>
              </div>
            </div>
            <div className="overflow-auto max-h-[560px] relative">
              <table className="w-full text-sm border-separate border-spacing-0">
                <thead className="bg-muted text-xs text-muted-foreground">
                  <tr>
                    <th className="sticky top-0 left-0 z-30 bg-muted border-b border-r px-2 py-3 font-medium text-center w-10">
                      #
                    </th>
                    {data?.headers.map((h, i) => {
                      const isMoney = report.moneyCols?.includes(i);
                      const isSort = sortCol === i;
                      const sticky = pinFirst && i === 0 ? "sticky left-10 z-20 bg-muted" : "";
                      return (
                        <th
                          key={i}
                          onClick={() => toggleSort(i)}
                          className={
                            "sticky top-0 z-10 bg-muted border-b px-4 py-3 font-medium cursor-pointer select-none hover:bg-muted/70 " +
                            (isMoney ? "text-right " : "text-left ") +
                            sticky
                          }
                        >
                          <span className="inline-flex items-center gap-1">
                            {h}
                            {isSort ? (
                              sortDir === "asc" ? (
                                <ArrowUp className="size-3" />
                              ) : (
                                <ArrowDown className="size-3" />
                              )
                            ) : (
                              <ArrowUpDown className="size-3 opacity-30" />
                            )}
                          </span>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {!isFetching && filteredRows.length === 0 && (
                    <tr>
                      <td
                        colSpan={(data?.headers.length ?? 0) + 1}
                        className="px-4 py-10 text-center text-muted-foreground border-b"
                      >
                        Ma'lumot yo'q
                      </td>
                    </tr>
                  )}
                  {filteredRows.slice(0, 600).map((row, ri) => {
                    const isOverall = active === "gross_overall";
                    // gross_overall: row[8] → 1=week row (main data), 2=period total
                    // pnl_daily: no row[8], all rows are plain day rows
                    const rowType = isOverall ? Number(row[8] ?? 0) : 0;
                    const isWeekRow = isOverall && rowType === 1;   // weekly aggregate — primary data row
                    const isMonthTotal = isOverall && rowType === 2; // period grand total

                    // Row colouring — pnl rows (daily or weekly) coloured by net profit sign
                    const isPnl = active === "pnl_daily" || isWeekRow;
                    const netProfit = isPnl ? Number(row[7]) : 0;
                    let rowBg = "";
                    if (isMonthTotal) {
                      rowBg = "bg-muted/80 dark:bg-muted/60 font-bold text-sm";
                    } else if (isPnl) {
                      rowBg = netProfit >= 0
                        ? ri % 2 === 1 ? "bg-green-50/60 dark:bg-green-950/20" : "bg-green-50/30 dark:bg-green-950/10"
                        : ri % 2 === 1 ? "bg-red-50/60 dark:bg-red-950/20" : "bg-red-50/30 dark:bg-red-950/10";
                    } else {
                      rowBg = ri % 2 === 1 ? "bg-muted/20" : "bg-card";
                    }

                    // Only render cells up to the number of headers (hides the hidden row_type column)
                    const visibleCells = row.slice(0, data!.headers.length);

                    return (
                      <tr key={ri} className={"hover:bg-bakery-50/60 " + rowBg}>
                        <td className="border-b border-r px-2 py-2 text-center text-xs text-muted-foreground tabular-nums sticky left-0 z-10 bg-inherit">
                          {isMonthTotal ? "" : ri + 1}
                        </td>
                        {visibleCells.map((cell, ci) => {
                          const isMoney = report.moneyCols?.includes(ci);
                          const currency = report.currencyCol != null
                            ? (row[report.currencyCol] as string)
                            : (report.colCurrency?.[ci] ?? "UZS");
                          const sticky = pinFirst && ci === 0 ? "sticky left-10 z-[5] bg-inherit" : "";
                          const numVal = Number(cell);
                          const isNeg = isMoney && numVal < 0;
                          const isZero = isMoney && numVal === 0;

                          // Gross Overall: money cells are clickable → detail modal.
                          const metric = isOverall && isMoney ? GROSS_METRICS[ci] : undefined;
                          const rangeFrom = row[9] as string | undefined;
                          const rangeTo = row[10] as string | undefined;
                          const clickable = !!(metric && rangeFrom && rangeTo);

                          return (
                            <td
                              key={ci}
                              onClick={clickable ? () => setDetail({
                                from: rangeFrom!, to: rangeTo!,
                                weekLabel: String(row[0]),
                                metricKey: metric!.key, metricLabel: metric!.label,
                              }) : undefined}
                              className={
                                "border-b px-4 py-2 " +
                                (isMoney ? "text-right tabular-nums" : "text-left") +
                                " " + sticky +
                                (isNeg ? " text-red-600 dark:text-red-400" : "") +
                                (clickable ? " cursor-pointer hover:bg-bakery-500/10 hover:underline decoration-dotted underline-offset-4" : "")
                              }
                              title={clickable ? "Tafsilotni ko'rish" : undefined}
                            >
                              {isMoney
                                ? isZero && !report.allowNegative
                                  ? "—"
                                  : numVal !== 0 || report.allowNegative
                                    ? formatMoney(String(cell), currency as "UZS" | "USD")
                                    : "—"
                                : String(cell)}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
                {columnTotals && filteredRows.length > 0 && (
                  <tfoot className="sticky bottom-0 z-10 bg-muted font-semibold">
                    <tr>
                      <td className="sticky left-0 z-20 bg-muted border-t border-r px-2 py-2 text-center text-xs text-muted-foreground">
                        Σ
                      </td>
                      {data?.headers.map((_, ci) => {
                        const isMoney = report.moneyCols?.includes(ci);
                        const sticky = pinFirst && ci === 0 ? "sticky left-10 z-10 bg-muted" : "";
                        const t = columnTotals[ci];
                        return (
                          <td
                            key={ci}
                            className={
                              "border-t px-4 py-2 " +
                              (isMoney ? "text-right tabular-nums" : "text-left text-muted-foreground text-xs") +
                              " " + sticky
                            }
                          >
                            {isMoney
                              ? t
                                ? (t.UZS === 0 && t.USD === 0
                                    ? "—"
                                    : <>
                                        {t.UZS !== 0 && (
                                          <div className={t.UZS < 0 ? "text-red-600 dark:text-red-400" : ""}>
                                            {formatMoney(String(t.UZS), "UZS")}
                                          </div>
                                        )}
                                        {t.USD !== 0 && (
                                          <div className={"text-xs " + (t.USD < 0 ? "text-red-600 dark:text-red-400" : "text-muted-foreground")}>
                                            {formatMoney(String(t.USD), "USD")}
                                          </div>
                                        )}
                                      </>)
                                : ""
                              : ci === 0
                                ? "Jami"
                                : ""}
                          </td>
                        );
                      })}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            {filteredRows.length > 600 && (
              <div className="px-5 py-3 border-t text-xs text-muted-foreground text-center">
                Jadvalda dastlabki 600 qator ko'rsatilgan (Σ jami — barcha {filteredRows.length} qator bo'yicha) · to'liq ro'yxat uchun Excel yuklab oling
              </div>
            )}
          </div>
        </>
      )}

      {detail && (
        <PnlDetailModal
          from={detail.from}
          to={detail.to}
          weekLabel={detail.weekLabel}
          metricKey={detail.metricKey}
          metricLabel={detail.metricLabel}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}
