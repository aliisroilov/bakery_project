import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  MapPin,
  ArrowLeft,
  Store,
  ShoppingCart,
  AlertTriangle,
  Calendar,
} from "lucide-react";
import { api } from "../lib/api";
import type { Order, OrderStatus, Paginated, Region, Shop } from "../lib/types";
import { formatMoney } from "../lib/utils";

const STATUS_BADGE: Record<OrderStatus, string> = {
  pending: "bg-amber-500/15 text-amber-700",
  partial: "bg-sky-500/15 text-sky-700",
  delivered: "bg-emerald-500/15 text-emerald-700",
  cancelled: "bg-muted text-muted-foreground",
};

const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Kutilmoqda",
  partial: "Qisman",
  delivered: "Yetkazildi",
  cancelled: "Bekor",
};

function todayISO(): string {
  // Local date, YYYY-MM-DD.
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function RegionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const regionId = Number(id);
  const [date, setDate] = useState<string>(todayISO());

  const { data: region } = useQuery<Region>({
    queryKey: ["region", regionId],
    queryFn: async () =>
      (await api.get<Region>(`/regions/${regionId}/`)).data,
    enabled: Number.isFinite(regionId),
  });

  const { data: shops, isLoading: shopsLoading } = useQuery<Paginated<Shop>>({
    queryKey: ["shops", { region: regionId }],
    queryFn: async () =>
      (
        await api.get<Paginated<Shop>>(
          `/shops/?region=${regionId}&archived=false`,
        )
      ).data,
    enabled: Number.isFinite(regionId),
  });

  const { data: orders, isLoading: ordersLoading } = useQuery<Paginated<Order>>(
    {
      queryKey: ["orders", { region: regionId, date }],
      queryFn: async () =>
        (
          await api.get<Paginated<Order>>(
            `/orders/?region=${regionId}&date=${date}`,
          )
        ).data,
      enabled: Number.isFinite(regionId),
    },
  );

  const counts = (orders?.results ?? []).reduce(
    (acc, o) => {
      acc.total += 1;
      acc[o.status] = (acc[o.status] ?? 0) + 1;
      return acc;
    },
    { total: 0, pending: 0, partial: 0, delivered: 0, cancelled: 0 } as Record<
      string,
      number
    >,
  );

  return (
    <div className="space-y-4 sm:space-y-5">
      <div>
        <Link
          to="/regions"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Hududlar
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="size-11 rounded-xl bg-bakery-500/10 text-bakery-600 grid place-items-center shrink-0">
            <MapPin className="size-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight truncate">
              {region?.name ?? "—"}
            </h1>
            <p className="text-muted-foreground text-sm">
              {region?.shop_count ?? shops?.count ?? 0} ta do&apos;kon
              {region?.note ? ` · ${region.note}` : ""}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Calendar className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="h-10 pl-9 pr-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
            />
          </div>
          {date !== todayISO() && (
            <button
              onClick={() => setDate(todayISO())}
              className="h-10 px-3 rounded-lg border text-sm hover:bg-muted"
            >
              Bugun
            </button>
          )}
        </div>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
        <SummaryTile
          label="Jami"
          value={counts.total}
          icon={<ShoppingCart className="size-4" />}
        />
        <SummaryTile label="Kutilmoqda" value={counts.pending} tone="amber" />
        <SummaryTile label="Qisman" value={counts.partial} tone="blue" />
        <SummaryTile
          label="Yetkazilgan"
          value={counts.delivered}
          tone="green"
        />
      </div>

      {/* Orders section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <header className="px-4 py-3 border-b flex items-center justify-between">
          <h2 className="font-semibold text-sm">
            Buyurtmalar ({date === todayISO() ? "bugun" : date})
          </h2>
          <span className="text-xs text-muted-foreground">
            {counts.total} ta
          </span>
        </header>
        {ordersLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            Yuklanmoqda…
          </div>
        ) : counts.total === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            Bu hududda ushbu sanaga buyurtma mavjud emas.
          </div>
        ) : (
          <ul className="divide-y">
            {orders!.results.map((o) => (
              <li key={o.id}>
                <Link
                  to={`/orders/${o.id}`}
                  className="flex items-start gap-3 px-4 py-3 hover:bg-muted/30 transition-colors"
                >
                  <div className="mt-0.5 size-8 rounded-lg bg-bakery-500/10 text-bakery-600 grid place-items-center shrink-0">
                    <ShoppingCart className="size-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium truncate">
                        {o.shop_name}
                      </span>
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full ${STATUS_BADGE[o.status]}`}
                      >
                        {STATUS_LABEL[o.status]}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {o.item_count} ta mahsulot · {o.priority_display}
                    </div>
                  </div>
                  <div className="text-right text-sm tabular-nums shrink-0">
                    <div className="font-medium">
                      {formatMoney(o.total_amount, o.currency)}
                    </div>
                    {parseFloat(o.delivered_amount) > 0 &&
                      o.delivered_amount !== o.total_amount && (
                        <div className="text-xs text-muted-foreground">
                          Yetk.: {formatMoney(o.delivered_amount, o.currency)}
                        </div>
                      )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Shops section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <header className="px-4 py-3 border-b flex items-center justify-between">
          <h2 className="font-semibold text-sm">Hududdagi do&apos;konlar</h2>
          <span className="text-xs text-muted-foreground">
            {shops?.count ?? 0} ta
          </span>
        </header>
        {shopsLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            Yuklanmoqda…
          </div>
        ) : (shops?.results.length ?? 0) === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            Bu hududga do&apos;kon biriktirilmagan.
          </div>
        ) : (
          <ul className="divide-y">
            {shops!.results.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/shops/${s.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors"
                >
                  <div className="size-8 rounded-lg bg-muted grid place-items-center shrink-0">
                    <Store className="size-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{s.name}</span>
                      {(s.limit_exceeded_uzs || s.limit_exceeded_usd) && (
                        <AlertTriangle className="size-4 text-destructive shrink-0" />
                      )}
                    </div>
                    {s.assigned_driver_name && (
                      <div className="text-xs text-muted-foreground truncate">
                        {s.assigned_driver_name}
                      </div>
                    )}
                  </div>
                  <div className="text-right text-sm tabular-nums shrink-0">
                    <div
                      className={
                        s.limit_exceeded_uzs
                          ? "text-destructive font-medium"
                          : ""
                      }
                    >
                      {formatMoney(s.loan_balance_uzs, "UZS")}
                    </div>
                    {parseFloat(s.loan_balance_usd) > 0 && (
                      <div
                        className={
                          s.limit_exceeded_usd
                            ? "text-destructive font-medium text-xs"
                            : "text-xs text-muted-foreground"
                        }
                      >
                        {formatMoney(s.loan_balance_usd, "USD")}
                      </div>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function SummaryTile({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number;
  tone?: "amber" | "blue" | "green";
  icon?: React.ReactNode;
}) {
  const toneMap: Record<string, string> = {
    amber: "text-amber-700",
    blue: "text-sky-700",
    green: "text-emerald-700",
  };
  return (
    <div className="rounded-xl border bg-card p-3 sm:p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div
        className={`mt-1 text-2xl font-semibold tabular-nums ${tone ? toneMap[tone] : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
