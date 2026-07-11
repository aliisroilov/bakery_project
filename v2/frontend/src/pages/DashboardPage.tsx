import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Factory,
  Wallet,
  ShoppingCart,
  TrendingUp,
  AlertTriangle,
  Users,
  Clock,
  CheckCircle2,
  PackageOpen,
  Banknote,
  ArrowRight,
  HandCoins,
  Truck,
  X,
  ChevronLeft,
  ChevronRight,
  CalendarDays,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
  CartesianGrid, ReferenceLine,
} from "recharts";
import { useAuth } from "../lib/auth";
import { C, TICK, mkTooltip } from "../lib/chart";
import { api } from "../lib/api";
import type { DashboardSummary } from "../lib/types";
import { formatMoney, nowTashkentStr } from "../lib/utils";

/** Shift a YYYY-MM-DD date string by `delta` days (UTC-safe). */
function shiftDay(d: string, delta: number): string {
  const [y, m, dd] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, dd + delta)).toISOString().slice(0, 10);
}

/** Short DD.MM label for a YYYY-MM-DD date ("Bugun" for today), e.g. "27.06". */
function dayLabel(d: string, today: string): string {
  if (d === today) return "Bugun";
  const [y, m, dd] = d.split("-");
  const base = `${dd}.${m}`;
  return y !== today.slice(0, 4) ? `${base}.${y}` : base;
}

function formatDeliveryTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DashboardPage() {
  const user = useAuth((s) => s.user);
  const [netIncomeOpen, setNetIncomeOpen] = useState(false);
  const today = nowTashkentStr().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);

  if (user?.role === "driver") return <DriverDashboard />;

  const isToday = selectedDate === today;

  const { data, isLoading, error } = useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary", selectedDate],
    queryFn: async () =>
      (await api.get<DashboardSummary>(`/dashboard/summary/?date=${selectedDate}`)).data,
    refetchInterval: isToday ? 30_000 : false,
  });

  const seyf = data?.accounts.find((a) => a.slug === "seyf");
  const rizoxon = data?.accounts.find((a) => a.slug === "rizoxon");

  // Prefix for day-scoped stat labels ("Bugungi" today, else the date).
  const pfx = isToday ? "Bugungi" : dayLabel(selectedDate, today);

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Salom, {user?.display_name}
          </h1>
          <p className="text-muted-foreground text-sm">
            {isToday ? "Bugungi umumiy holat bir qarashda." : `${dayLabel(selectedDate, today)} kunining holati.`}
          </p>
        </div>

        {/* Day navigator */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          <button
            onClick={() => setSelectedDate((d) => shiftDay(d, -1))}
            className="size-9 grid place-items-center rounded-lg border bg-card hover:bg-muted transition-colors"
            title="Oldingi kun"
          >
            <ChevronLeft className="size-4" />
          </button>
          <label className="relative flex items-center gap-2 h-9 px-3 rounded-lg border bg-card hover:bg-muted transition-colors cursor-pointer">
            <CalendarDays className="size-4 text-bakery-500 shrink-0" />
            <span className="text-sm font-medium tabular-nums">{dayLabel(selectedDate, today)}</span>
            <input
              type="date"
              value={selectedDate}
              max={today}
              onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
          </label>
          <button
            onClick={() => setSelectedDate((d) => shiftDay(d, 1))}
            disabled={isToday}
            className="size-9 grid place-items-center rounded-lg border bg-card hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Keyingi kun"
          >
            <ChevronRight className="size-4" />
          </button>
          {!isToday && (
            <button
              onClick={() => setSelectedDate(today)}
              className="h-9 px-3 rounded-lg border bg-bakery-500 text-white text-sm hover:bg-bakery-600 transition-colors"
            >
              Bugun
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-sm p-3">
          Ma'lumotni yuklashda xatolik: {(error as Error).message}
        </div>
      )}

      {/* Loan limit alerts — shown prominently at the top */}
      {data?.over_loan_limit && data.over_loan_limit.length > 0 && (
        <div className="rounded-xl border-2 border-destructive/50 bg-destructive/8 p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="size-5 text-destructive" />
            <h2 className="font-semibold text-destructive text-sm sm:text-base">
              Qarz limitidan oshgan do'konlar ({data.over_loan_limit.length} ta)
            </h2>
          </div>
          <ul className="space-y-2 text-sm">
            {data.over_loan_limit.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-2">
                <Link
                  to={`/shops/${s.id}`}
                  className="font-medium hover:underline truncate text-destructive"
                >
                  {s.name}
                </Link>
                <span className="text-destructive tabular-nums shrink-0 text-xs sm:text-sm font-semibold">
                  {formatMoney(s.loan_balance_uzs, "UZS")} /{" "}
                  {formatMoney(s.loan_limit_uzs, "UZS")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Kassa + production + kirim */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 xl:grid-cols-4">
        <StatCard
          to="/finance"
          icon={<Wallet className="size-5" />}
          label="Seyf"
          primary={seyf ? formatMoney(seyf.balance_uzs, "UZS") : "—"}
          secondary={seyf ? formatMoney(seyf.balance_usd, "USD") : "UZS / USD"}
          loading={isLoading}
        />
        <StatCard
          to="/finance"
          icon={<Wallet className="size-5" />}
          label="Rizoxon"
          primary={rizoxon ? formatMoney(rizoxon.balance_uzs, "UZS") : "—"}
          secondary={rizoxon ? formatMoney(rizoxon.balance_usd, "USD") : "UZS / USD"}
          loading={isLoading}
        />
        <StatCard
          to="/production"
          icon={<Factory className="size-5" />}
          label={`${pfx} ishlab chiqarish`}
          primary={data ? `${parseFloat(data.production.today.meshok).toFixed(1)} qop` : "—"}
          secondary={
            data
              ? `${parseFloat(data.production.today.units).toFixed(0)} dona · oy: ${parseFloat(data.production.month.meshok).toFixed(1)} qop`
              : "qop"
          }
          loading={isLoading}
        />
        <StatCard
          to="/finance"
          icon={<ShoppingCart className="size-5" />}
          label={`${pfx} kirim`}
          primary={data ? formatMoney(data.kirim_today.uzs, "UZS") : "—"}
          secondary={data ? formatMoney(data.kirim_today.usd, "USD") : "so'm + $"}
          loading={isLoading}
          tone="success"
        />
      </div>

      {/* Orders today */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 xl:grid-cols-4">
        <StatCard
          to="/orders"
          icon={<ShoppingCart className="size-5" />}
          label={`${pfx} buyurtmalar`}
          primary={data ? String(data.orders_today.total) : "—"}
          secondary={isToday ? "Jami bugun" : "Jami"}
          loading={isLoading}
        />
        <StatCard
          to="/orders?status=pending"
          icon={<Clock className="size-5" />}
          label="Kutilmoqda"
          primary={data ? String(data.orders_today.pending) : "—"}
          secondary={isToday ? "Bugun" : dayLabel(selectedDate, today)}
          loading={isLoading}
          tone="warning"
        />
        <StatCard
          to="/orders?status=partial"
          icon={<PackageOpen className="size-5" />}
          label="Qisman yetkazilgan"
          primary={data ? String(data.orders_today.partial) : "—"}
          secondary={isToday ? "Bugun" : dayLabel(selectedDate, today)}
          loading={isLoading}
          tone="warning"
        />
        <StatCard
          to="/orders?status=delivered"
          icon={<CheckCircle2 className="size-5" />}
          label="Yetkazilgan"
          primary={data ? String(data.orders_today.delivered) : "—"}
          secondary={isToday ? "Bugun" : dayLabel(selectedDate, today)}
          loading={isLoading}
          tone="success"
        />
      </div>

      {/* Total loans banner */}
      {data?.loans_total && (
        <Link
          to="/shops"
          className="rounded-xl border bg-card p-4 sm:p-5 flex items-center justify-between gap-3 hover:border-bakery-200 transition-colors group"
        >
          <div className="flex items-center gap-3 min-w-0">
            <div className="size-10 shrink-0 rounded-lg bg-amber-500/15 text-amber-700 grid place-items-center">
              <Banknote className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs sm:text-sm text-muted-foreground">
                Jami do'kon qarzlari
              </div>
              <div className="text-lg sm:text-xl font-semibold tabular-nums truncate">
                {formatMoney(data.loans_total.uzs, "UZS")}
                {parseFloat(data.loans_total.usd) > 0 && (
                  <span className="ml-3 text-muted-foreground text-sm sm:text-base">
                    · {formatMoney(data.loans_total.usd, "USD")}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="text-sm text-bakery-600 group-hover:translate-x-0.5 transition-transform shrink-0">
            <ArrowRight className="size-5" />
          </div>
        </Link>
      )}

      {/* Urgent orders + side column */}
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border bg-card p-4 sm:p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold flex items-center gap-2">
              <AlertTriangle className="size-4 text-amber-600" />
              Shoshilinch buyurtmalar
            </h2>
            <span className="text-xs text-muted-foreground">
              {data?.urgent_orders.length ?? 0} ta
            </span>
          </div>
          {!data || data.urgent_orders.length === 0 ? (
            <div className="text-sm text-muted-foreground py-10 text-center border-2 border-dashed rounded-lg">
              Shoshilinch buyurtmalar yo'q
            </div>
          ) : (
            <ul className="divide-y -mx-4 sm:-mx-5">
              {data.urgent_orders.map((o) => {
                const overdue =
                  o.delivery_time && new Date(o.delivery_time).getTime() < Date.now();
                return (
                  <li key={o.id}>
                    <Link
                      to={`/orders/${o.id}`}
                      className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3 hover:bg-muted/30 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">
                          #{o.id} · {o.shop_name}
                        </div>
                        <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-x-2 mt-0.5">
                          <span>{o.status}</span>
                          {o.delivery_time && (
                            <span
                              className={`inline-flex items-center gap-1 ${
                                overdue ? "text-destructive font-medium" : ""
                              }`}
                            >
                              <Clock className="size-3" />
                              {formatDeliveryTime(o.delivery_time)}
                            </span>
                          )}
                        </div>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                          o.priority === "urgent"
                            ? "bg-destructive/15 text-destructive"
                            : "bg-amber-500/15 text-amber-700"
                        }`}
                      >
                        {o.priority}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-3 sm:space-y-4">
          <div className="rounded-xl border bg-card p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <Users className="size-4 text-bakery-500" />
              <h2 className="font-semibold">Kirim bo'yicha xodimlar</h2>
            </div>
            {!data || data.kirim_today.by_collector.length === 0 ? (
              <div className="text-xs text-muted-foreground">
                Bugun hali kirim yo'q
              </div>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.kirim_today.by_collector.map((c) => (
                  <li key={c.user_id ?? c.name} className="flex justify-between gap-2">
                    <span className="truncate">{c.name}</span>
                    <span className="font-medium tabular-nums shrink-0">
                      {formatMoney(c.uzs, "UZS")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div
            className="rounded-xl border bg-card p-4 sm:p-5 cursor-pointer hover:border-bakery-300 transition-colors"
            onClick={() => setNetIncomeOpen(true)}
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="size-4 text-bakery-500" />
                <h2 className="font-semibold">Net daromad ({isToday ? "bugun" : dayLabel(selectedDate, today)})</h2>
              </div>
              <ArrowRight className="size-4 text-muted-foreground" />
            </div>
            {data ? (
              <>
                <div
                  className={`text-xl sm:text-2xl font-semibold tracking-tight tabular-nums ${
                    parseFloat(data.net_income_today.uzs) >= 0
                      ? "text-emerald-600"
                      : "text-destructive"
                  }`}
                >
                  {formatMoney(data.net_income_today.uzs, "UZS")}
                </div>
                {parseFloat(data.net_income_today.usd) !== 0 && (
                  <div
                    className={`text-sm font-medium tabular-nums ${
                      parseFloat(data.net_income_today.usd) >= 0
                        ? "text-emerald-600"
                        : "text-destructive"
                    }`}
                  >
                    {formatMoney(data.net_income_today.usd, "USD")}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-3 space-y-1 pt-3 border-t">
                  <div className="flex justify-between">
                    <span>Kirim (to'lov):</span>
                    <span className="tabular-nums text-emerald-600">
                      +{formatMoney(data.net_income_today.revenue_uzs, "UZS")}
                    </span>
                  </div>
                  {parseFloat(data.net_income_today.breakdown.purchases_uzs) > 0 && (
                    <div className="flex justify-between text-muted-foreground/80">
                      <span>· Xomashyo:</span>
                      <span className="tabular-nums">
                        −{formatMoney(data.net_income_today.breakdown.purchases_uzs, "UZS")}
                      </span>
                    </div>
                  )}
                  {parseFloat(data.net_income_today.breakdown.general_expenses_uzs) > 0 && (
                    <div className="flex justify-between text-muted-foreground/80">
                      <span>· Xarajatlar:</span>
                      <span className="tabular-nums">
                        −{formatMoney(data.net_income_today.breakdown.general_expenses_uzs, "UZS")}
                      </span>
                    </div>
                  )}
                  {parseFloat(data.net_income_today.breakdown.salary_uzs) > 0 && (
                    <div className="flex justify-between text-muted-foreground/80">
                      <span>· Oylik/avans:</span>
                      <span className="tabular-nums">
                        −{formatMoney(data.net_income_today.breakdown.salary_uzs, "UZS")}
                      </span>
                    </div>
                  )}
                  {parseFloat(data.net_income_today.expenses_uzs) > 0 && (
                    <div className="flex justify-between font-medium border-t pt-1 mt-1">
                      <span>Jami chiqim:</span>
                      <span className="tabular-nums text-destructive">
                        −{formatMoney(data.net_income_today.expenses_uzs, "UZS")}
                      </span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-2xl font-semibold tracking-tight">—</div>
            )}
          </div>
        </div>
      </div>

      {/* Charts row */}
      {data && (
        <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
          {/* Orders by status donut */}
          <div className="rounded-xl border bg-card p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <ShoppingCart className="size-4 text-bakery-500" />
              <h2 className="font-semibold text-sm">{pfx} buyurtmalar holati</h2>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={[
                    { name: "Kutilmoqda", value: data.orders_today.pending, fill: C.amber },
                    { name: "Qisman", value: data.orders_today.partial, fill: C.blue },
                    { name: "Yetkazildi", value: data.orders_today.delivered, fill: C.green },
                  ].filter((d) => d.value > 0)}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={65}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {[
                    { name: "Kutilmoqda", value: data.orders_today.pending, fill: C.amber },
                    { name: "Qisman", value: data.orders_today.partial, fill: C.blue },
                    { name: "Yetkazildi", value: data.orders_today.delivered, fill: C.green },
                  ].filter((d) => d.value > 0).map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip content={mkTooltip((v) => `${v} ta`)} />
                <Legend wrapperStyle={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Production by product bar */}
          {data.production.today_by_product.length > 0 && (
            <div className="rounded-xl border bg-card p-4 sm:p-5">
              <div className="flex items-center gap-2 mb-3">
                <Factory className="size-4 text-bakery-500" />
                <h2 className="font-semibold text-sm">{pfx} ishlab chiqarish (qop)</h2>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={data.production.today_by_product.map((p) => ({
                    name: p.product_name.length > 12 ? p.product_name.slice(0, 12) + "…" : p.product_name,
                    qop: parseFloat(p.meshok),
                  }))}
                  margin={{ top: 4, right: 4, left: -20, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
                  <XAxis dataKey="name" tick={TICK} axisLine={false} tickLine={false} />
                  <YAxis tick={TICK} axisLine={false} tickLine={false} />
                  <Tooltip content={mkTooltip((v) => `${v} qop`)} />
                  <Bar dataKey="qop" fill={C.bakery} radius={[3, 3, 0, 0]} name="Qop" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {netIncomeOpen && <NetIncomeHistoryModal onClose={() => setNetIncomeOpen(false)} />}
    </div>
  );
}

// ─── Net Income History Modal ─────────────────────────────────────────────────

interface NetIncomeDay {
  date: string;
  revenue_uzs: string;
  expenses_uzs: string;
  net_uzs: string;
}

function NetIncomeHistoryModal({ onClose }: { onClose: () => void }) {
  const { data, isLoading } = useQuery<{ results: NetIncomeDay[] }>({
    queryKey: ["net-income-history"],
    queryFn: async () =>
      (await api.get<{ results: NetIncomeDay[] }>("/dashboard/net-income-history/")).data,
  });

  const chartData = (data?.results ?? []).map((r) => ({
    date: r.date.slice(5),
    kirim: Math.round(parseFloat(r.revenue_uzs) / 1_000_000 * 10) / 10,
    chiqim: Math.round(parseFloat(r.expenses_uzs) / 1_000_000 * 10) / 10,
    net: Math.round(parseFloat(r.net_uzs) / 1_000_000 * 10) / 10,
  }));

  // One-month totals across the whole range shown.
  const totals = (data?.results ?? []).reduce(
    (a, r) => ({
      kirim: a.kirim + parseFloat(r.revenue_uzs || "0"),
      chiqim: a.chiqim + parseFloat(r.expenses_uzs || "0"),
      net: a.net + parseFloat(r.net_uzs || "0"),
    }),
    { kirim: 0, chiqim: 0, net: 0 },
  );

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full sm:max-w-2xl bg-card rounded-t-2xl sm:rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg flex items-center gap-2">
            <TrendingUp className="size-5 text-bakery-500" />
            Net daromad tarixi (so'nggi 30 kun)
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
            Yuklanmoqda…
          </div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
                <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} interval={4} />
                <YAxis tick={TICK} axisLine={false} tickLine={false} unit="M" />
                <Tooltip content={mkTooltip((v) => `${v} mln`)} />
                <ReferenceLine y={0} stroke="hsl(var(--border))" />
                <Bar dataKey="kirim" fill={C.green} radius={[2, 2, 0, 0]} name="Kirim" />
                <Bar dataKey="chiqim" fill={C.amber} radius={[2, 2, 0, 0]} name="Chiqim" />
                <Bar dataKey="net" fill={C.bakery} radius={[2, 2, 0, 0]} name="Net" />
              </BarChart>
            </ResponsiveContainer>

            {/* One-month totals */}
            <div className="mt-4 grid grid-cols-3 gap-2 sm:gap-3">
              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">Kirim (30 kun jami)</div>
                <div className="font-semibold tabular-nums text-emerald-600 text-sm sm:text-base mt-0.5">
                  {formatMoney(String(totals.kirim), "UZS")}
                </div>
              </div>
              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">Chiqim (30 kun jami)</div>
                <div className="font-semibold tabular-nums text-destructive text-sm sm:text-base mt-0.5">
                  {formatMoney(String(totals.chiqim), "UZS")}
                </div>
              </div>
              <div className="rounded-xl border bg-muted/30 p-3">
                <div className="text-[11px] text-muted-foreground">Net (30 kun jami)</div>
                <div className={`font-semibold tabular-nums text-sm sm:text-base mt-0.5 ${totals.net >= 0 ? "text-emerald-600" : "text-destructive"}`}>
                  {totals.net >= 0 ? "+" : ""}{formatMoney(String(totals.net), "UZS")}
                </div>
              </div>
            </div>

            <div className="mt-4 max-h-64 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Sana</th>
                    <th className="text-right px-3 py-2 font-medium">Kirim</th>
                    <th className="text-right px-3 py-2 font-medium">Chiqim</th>
                    <th className="text-right px-3 py-2 font-medium">Net</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {[...(data?.results ?? [])].reverse().map((r) => {
                    const net = parseFloat(r.net_uzs);
                    return (
                      <tr key={r.date} className="hover:bg-muted/20">
                        <td className="px-3 py-2 tabular-nums">{r.date}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-emerald-600">
                          {formatMoney(r.revenue_uzs, "UZS")}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-destructive">
                          {formatMoney(r.expenses_uzs, "UZS")}
                        </td>
                        <td className={`px-3 py-2 text-right tabular-nums font-semibold ${net >= 0 ? "text-emerald-600" : "text-destructive"}`}>
                          {net >= 0 ? "+" : ""}{formatMoney(r.net_uzs, "UZS")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="sticky bottom-0 bg-muted border-t-2 font-semibold">
                  <tr>
                    <td className="px-3 py-2">Jami</td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-700">
                      {formatMoney(String(totals.kirim), "UZS")}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-destructive">
                      {formatMoney(String(totals.chiqim), "UZS")}
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${totals.net >= 0 ? "text-emerald-700" : "text-destructive"}`}>
                      {totals.net >= 0 ? "+" : ""}{formatMoney(String(totals.net), "UZS")}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Driver-specific dashboard ───────────────────────────────────────────────

interface SimplePaged<T> { results: T[]; count: number }
interface CashRow { currency: string; amount: string }

function DriverDashboard() {
  const user = useAuth((s) => s.user);
  const today = new Date().toISOString().slice(0, 10);

  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => (await api.get<DashboardSummary>("/dashboard/summary/")).data,
    refetchInterval: 30_000,
  });

  const { data: myPayments } = useQuery<SimplePaged<CashRow>>({
    queryKey: ["payments", "mine", today],
    queryFn: async () =>
      (await api.get<SimplePaged<CashRow>>(
        `/finance/payments/?collected_by=${user!.id}&date_from=${today}&date_to=${today}&page_size=500`,
      )).data,
    enabled: !!user?.id,
    refetchInterval: 30_000,
  });

  const { data: myHandovers } = useQuery<SimplePaged<CashRow & { occurred_at: string; note: string }>>({
    queryKey: ["handovers", "mine", today],
    queryFn: async () =>
      (await api.get<SimplePaged<CashRow & { occurred_at: string; note: string }>>(
        `/finance/handovers/?driver=${user!.id}&date_from=${today}&date_to=${today}&page_size=500`,
      )).data,
    enabled: !!user?.id,
    refetchInterval: 30_000,
  });

  const sum = (rows: CashRow[] | undefined, cur: string) =>
    (rows ?? []).filter((r) => r.currency === cur).reduce((s, r) => s + parseFloat(r.amount), 0);

  const colUzs = sum(myPayments?.results, "UZS");
  const colUsd = sum(myPayments?.results, "USD");
  const handUzs = sum(myHandovers?.results, "UZS");
  const handUsd = sum(myHandovers?.results, "USD");
  const pendUzs = colUzs - handUzs;
  const pendUsd = colUsd - handUsd;
  const hasPending = pendUzs > 0 || pendUsd > 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
          Salom, {user?.display_name}
        </h1>
        <p className="text-muted-foreground text-sm">
          Bugungi yetkazish va naqd pul holati.
        </p>
      </div>

      {/* Today's delivery counts */}
      <div className="grid gap-3 grid-cols-3">
        <StatCard
          to="/orders?status=pending"
          icon={<Clock className="size-5" />}
          label="Kutilmoqda"
          primary={summary ? String(summary.orders_today.pending) : "—"}
          secondary="bugun"
          loading={!summary}
          tone="warning"
        />
        <StatCard
          to="/orders?status=partial"
          icon={<PackageOpen className="size-5" />}
          label="Qisman"
          primary={summary ? String(summary.orders_today.partial) : "—"}
          secondary="bugun"
          loading={!summary}
          tone="warning"
        />
        <StatCard
          to="/orders?status=delivered"
          icon={<CheckCircle2 className="size-5" />}
          label="Yetkazildi"
          primary={summary ? String(summary.orders_today.delivered) : "—"}
          secondary="bugun"
          loading={!summary}
          tone="success"
        />
      </div>

      {/* Cash summary */}
      <div className="rounded-xl border bg-card p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-4">
          <HandCoins className="size-4 text-bakery-500" />
          <h2 className="font-semibold">Naqd pul holati (bugun)</h2>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-muted/40 p-3">
            <div className="text-xs text-muted-foreground mb-1">Yig'ildi</div>
            <div className="font-semibold tabular-nums text-sm sm:text-base">
              {formatMoney(String(colUzs), "UZS")}
            </div>
            {colUsd > 0 && (
              <div className="text-xs text-muted-foreground tabular-nums">
                {formatMoney(String(colUsd), "USD")}
              </div>
            )}
          </div>
          <div className="rounded-lg bg-emerald-500/10 text-emerald-700 p-3">
            <div className="text-xs opacity-80 mb-1">Topshirildi</div>
            <div className="font-semibold tabular-nums text-sm sm:text-base">
              {formatMoney(String(handUzs), "UZS")}
            </div>
            {handUsd > 0 && (
              <div className="text-xs opacity-70 tabular-nums">
                {formatMoney(String(handUsd), "USD")}
              </div>
            )}
          </div>
          <div
            className={`rounded-lg p-3 ${
              hasPending
                ? "bg-amber-500/10 text-amber-700"
                : "bg-muted/40 text-muted-foreground"
            }`}
          >
            <div className="text-xs opacity-80 mb-1">Qoldiq</div>
            <div className="font-semibold tabular-nums text-sm sm:text-base">
              {formatMoney(String(pendUzs), "UZS")}
            </div>
            {pendUsd !== 0 && (
              <div className="text-xs opacity-70 tabular-nums">
                {formatMoney(String(pendUsd), "USD")}
              </div>
            )}
          </div>
        </div>
        {hasPending && (
          <Link
            to="/finance"
            className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-amber-500/10 border border-amber-200 px-3 py-2 text-sm text-amber-700 hover:bg-amber-500/20 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Truck className="size-4 shrink-0" />
              Qoldiq pul topshiring
            </span>
            <ArrowRight className="size-4 shrink-0" />
          </Link>
        )}
      </div>

      {/* Urgent orders */}
      <div className="rounded-xl border bg-card p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-600" />
            Shoshilinch buyurtmalar
          </h2>
          <Link
            to="/orders"
            className="text-xs text-bakery-600 hover:underline flex items-center gap-1"
          >
            Barchasi <ArrowRight className="size-3" />
          </Link>
        </div>
        {!summary || summary.urgent_orders.length === 0 ? (
          <div className="text-sm text-muted-foreground py-8 text-center border-2 border-dashed rounded-lg">
            Shoshilinch buyurtmalar yo'q
          </div>
        ) : (
          <ul className="divide-y -mx-4 sm:-mx-5">
            {summary.urgent_orders.map((o) => {
              const overdue =
                o.delivery_time && new Date(o.delivery_time).getTime() < Date.now();
              return (
                <li key={o.id}>
                  <Link
                    to={`/orders/${o.id}`}
                    className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3 hover:bg-muted/30 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">
                        #{o.id} · {o.shop_name}
                      </div>
                      <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-x-2 mt-0.5">
                        <span>{o.status}</span>
                        {o.delivery_time && (
                          <span
                            className={`inline-flex items-center gap-1 ${
                              overdue ? "text-destructive font-medium" : ""
                            }`}
                          >
                            <Clock className="size-3" />
                            {formatDeliveryTime(o.delivery_time)}
                          </span>
                        )}
                      </div>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                        o.priority === "urgent"
                          ? "bg-destructive/15 text-destructive"
                          : "bg-amber-500/15 text-amber-700"
                      }`}
                    >
                      {o.priority}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

// ─── Shared stat card ─────────────────────────────────────────────────────────

function StatCard({
  to,
  icon,
  label,
  primary,
  secondary,
  loading,
  tone,
}: {
  to?: string;
  icon: React.ReactNode;
  label: string;
  primary: string;
  secondary: string;
  loading?: boolean;
  tone?: "success" | "warning" | "danger";
}) {
  const toneCls =
    tone === "success"
      ? "text-emerald-600"
      : tone === "warning"
        ? "text-amber-600"
        : tone === "danger"
          ? "text-destructive"
          : "";
  const inner = (
    <>
      <div className="flex items-center gap-2 text-muted-foreground text-xs sm:text-sm">
        <span className="shrink-0">{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      <div
        className={`mt-2 sm:mt-3 text-lg sm:text-2xl font-semibold tracking-tight tabular-nums ${toneCls} ${
          loading ? "animate-pulse text-muted" : ""
        }`}
      >
        {primary}
      </div>
      <div className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 sm:mt-1 truncate">
        {secondary}
      </div>
    </>
  );
  const cls = "rounded-xl border bg-card p-3 sm:p-5 hover:border-bakery-300 hover:shadow-sm transition-all cursor-pointer block";
  if (to) {
    return <Link to={to} className={cls}>{inner}</Link>;
  }
  return <div className={cls}>{inner}</div>;
}
