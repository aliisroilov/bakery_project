import { useQuery } from "@tanstack/react-query";
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
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import type { DashboardSummary } from "../lib/types";
import { formatMoney } from "../lib/utils";

function formatDeliveryTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DashboardPage() {
  const user = useAuth((s) => s.user);
  const { data, isLoading, error } = useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => (await api.get<DashboardSummary>("/dashboard/summary/")).data,
    refetchInterval: 30_000,
  });

  const seyf = data?.accounts.find((a) => a.slug === "seyf");
  const rizoxon = data?.accounts.find((a) => a.slug === "rizoxon");

  return (
    <div className="space-y-5 sm:space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
          Salom, {user?.display_name}
        </h1>
        <p className="text-muted-foreground text-sm">
          Bugungi umumiy holat bir qarashda.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-sm p-3">
          Ma'lumotni yuklashda xatolik: {(error as Error).message}
        </div>
      )}

      {/* Kassa + production + kirim */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<Wallet className="size-5" />}
          label="Seyf"
          primary={seyf ? formatMoney(seyf.balance_uzs, "UZS") : "—"}
          secondary={seyf ? formatMoney(seyf.balance_usd, "USD") : "UZS / USD"}
          loading={isLoading}
        />
        <StatCard
          icon={<Wallet className="size-5" />}
          label="Rizoxon"
          primary={rizoxon ? formatMoney(rizoxon.balance_uzs, "UZS") : "—"}
          secondary={rizoxon ? formatMoney(rizoxon.balance_usd, "USD") : "UZS / USD"}
          loading={isLoading}
        />
        <StatCard
          icon={<Factory className="size-5" />}
          label="Bugungi ishlab chiqarish"
          primary={data ? `${data.production.today.meshok} qop` : "—"}
          secondary={
            data
              ? `${data.production.today.units} dona · oy: ${data.production.month.meshok} qop`
              : "qop"
          }
          loading={isLoading}
        />
        <StatCard
          icon={<ShoppingCart className="size-5" />}
          label="Bugungi kirim"
          primary={data ? formatMoney(data.kirim_today.uzs, "UZS") : "—"}
          secondary={data ? formatMoney(data.kirim_today.usd, "USD") : "so'm + $"}
          loading={isLoading}
          tone="success"
        />
      </div>

      {/* Orders today */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<ShoppingCart className="size-5" />}
          label="Bugungi buyurtmalar"
          primary={data ? String(data.orders_today.total) : "—"}
          secondary="Jami bugun"
          loading={isLoading}
        />
        <StatCard
          icon={<Clock className="size-5" />}
          label="Kutilmoqda"
          primary={data ? String(data.orders_today.pending) : "—"}
          secondary="Bugun"
          loading={isLoading}
          tone="warning"
        />
        <StatCard
          icon={<PackageOpen className="size-5" />}
          label="Qisman yetkazilgan"
          primary={data ? String(data.orders_today.partial) : "—"}
          secondary="Bugun"
          loading={isLoading}
          tone="warning"
        />
        <StatCard
          icon={<CheckCircle2 className="size-5" />}
          label="Yetkazilgan"
          primary={data ? String(data.orders_today.delivered) : "—"}
          secondary="Bugun"
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

          <div className="rounded-xl border bg-card p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="size-4 text-bakery-500" />
              <h2 className="font-semibold">Net daromad (bugun)</h2>
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
                    <span>Kirim:</span>
                    <span className="tabular-nums text-emerald-600">
                      {formatMoney(data.net_income_today.revenue_uzs, "UZS")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Chiqim:</span>
                    <span className="tabular-nums text-destructive">
                      −{formatMoney(data.net_income_today.expenses_uzs, "UZS")}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-2xl font-semibold tracking-tight">—</div>
            )}
          </div>
        </div>
      </div>

      {/* Loan limit alerts */}
      {data?.over_loan_limit.length ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 sm:p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="size-4 text-destructive" />
            <h2 className="font-semibold text-destructive">
              Qarz limitidan oshgan do'konlar
            </h2>
          </div>
          <ul className="space-y-2 text-sm">
            {data.over_loan_limit.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-2"
              >
                <Link
                  to={`/shops/${s.id}`}
                  className="font-medium hover:underline truncate"
                >
                  {s.name}
                </Link>
                <span className="text-destructive tabular-nums shrink-0 text-xs sm:text-sm">
                  {formatMoney(s.loan_balance_uzs, "UZS")} /{" "}
                  {formatMoney(s.loan_limit_uzs, "UZS")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function StatCard({
  icon,
  label,
  primary,
  secondary,
  loading,
  tone,
}: {
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
  return (
    <div className="rounded-xl border bg-card p-3 sm:p-5 hover:border-bakery-200 transition-colors">
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
    </div>
  );
}
