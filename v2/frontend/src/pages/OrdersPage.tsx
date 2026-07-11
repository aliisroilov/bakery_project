import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShoppingCart,
  Search,
  RotateCw,
  Plus,
  Clock,
  Banknote,
} from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, Order, OrderStatus, Paginated, Product, Shop, ShopProductPrice } from "../lib/types";
import { formatMoney, nowTashkentStr, tashkentToISO } from "../lib/utils";
import { useAuth } from "../lib/auth";

interface ProductLine {
  price: string;
  qty: string;
  delivered: string;
}

const STATUS_CHOICES: { value: "" | OrderStatus; label: string }[] = [
  { value: "", label: "Barchasi" },
  { value: "pending", label: "Kutilmoqda" },
  { value: "partial", label: "Qisman" },
  { value: "delivered", label: "Yetkazildi" },
  { value: "cancelled", label: "Bekor" },
];

const STATUS_BADGE: Record<OrderStatus, string> = {
  pending: "bg-amber-500/15 text-amber-700",
  partial: "bg-sky-500/15 text-sky-700",
  delivered: "bg-emerald-500/15 text-emerald-700",
  cancelled: "bg-muted text-muted-foreground",
};

function formatDeliveryTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function deliveryUrgency(iso: string | null): "overdue" | "soon" | "later" | "none" {
  if (!iso) return "none";
  const target = new Date(iso).getTime();
  const now = Date.now();
  const diffH = (target - now) / 3_600_000;
  if (diffH < 0) return "overdue";
  if (diffH < 6) return "soon";
  return "later";
}

export function OrdersPage() {
  const role = useAuth((s) => s.user?.role);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | OrderStatus>(
    (searchParams.get("status") as OrderStatus) || ""
  );
  const [creating, setCreating] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<Paginated<Order>>({
    queryKey: ["orders", { search, status }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (status) params.set("status", status);
      return (await api.get<Paginated<Order>>(`/orders/?${params}`)).data;
    },
  });

  const repeat = useMutation({
    mutationFn: (id: number) => api.post(`/orders/${id}/repeat/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Buyurtmalar
          </h1>
          <p className="text-muted-foreground text-sm">
            {data?.count ?? 0} ta buyurtma
          </p>
        </div>
        {role !== "driver" && (
          <button
            onClick={() => setCreating(true)}
            className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
          >
            <Plus className="size-4" /> Yangi buyurtma
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            className="w-full h-10 pl-9 pr-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
            placeholder="Do'kon nomi yoki izoh…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as OrderStatus | "")}
          className="h-10 rounded-lg border bg-background px-3 text-sm"
        >
          {STATUS_CHOICES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      {/* Desktop table */}
      <div className="rounded-xl border bg-card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">#</th>
              <th className="text-left px-4 py-3 font-medium">Do'kon</th>
              <th className="text-left px-4 py-3 font-medium">Yetkazish vaqti</th>
              <th className="text-left px-4 py-3 font-medium">Sana</th>
              <th className="text-left px-4 py-3 font-medium">Holati</th>
              <th className="text-right px-4 py-3 font-medium">Summa</th>
              <th className="text-right px-4 py-3 font-medium">Yetkazildi</th>
              {role !== "driver" && <th className="text-right px-4 py-3 font-medium"></th>}
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                  Yuklanmoqda…
                </td>
              </tr>
            )}
            {data?.results.length === 0 && !isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                  Buyurtma topilmadi
                </td>
              </tr>
            )}
            {data?.results.map((o) => {
              const urgency = deliveryUrgency(o.delivery_time);
              return (
                <tr
                  key={o.id}
                  onClick={() => navigate(`/orders/${o.id}`)}
                  className="hover:bg-muted/30 cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium flex items-center gap-1">
                      <ShoppingCart className="size-4 text-muted-foreground" />
                      #{o.id}
                    </span>
                  </td>
                  <td className="px-4 py-3">{o.shop_name}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {o.delivery_time ? (
                      <span
                        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                          urgency === "overdue"
                            ? "bg-destructive/15 text-destructive"
                            : urgency === "soon"
                              ? "bg-amber-500/15 text-amber-700"
                              : "bg-muted text-foreground/70"
                        }`}
                      >
                        <Clock className="size-3" />
                        {formatDeliveryTime(o.delivery_time)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">
                    {o.order_date}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[o.status]}`}
                    >
                      {o.status_display}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatMoney(o.total_amount, o.currency)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatMoney(o.delivered_amount, o.currency)}
                  </td>
                  {role !== "driver" && (
                    <td className="px-4 py-3 text-right">
                      <button
                        disabled={repeat.isPending}
                        onClick={(e) => {
                          e.stopPropagation();
                          repeat.mutate(o.id);
                        }}
                        title="Takrorlash (feature #3)"
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-bakery-600"
                      >
                        <RotateCw className="size-3" /> Takrorlash
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-2">
        {isLoading && (
          <div className="rounded-xl border bg-card p-8 text-center text-muted-foreground text-sm">
            Yuklanmoqda…
          </div>
        )}
        {data?.results.length === 0 && !isLoading && (
          <div className="rounded-xl border bg-card p-8 text-center text-muted-foreground text-sm">
            Buyurtma topilmadi
          </div>
        )}
        {data?.results.map((o) => {
          const urgency = deliveryUrgency(o.delivery_time);
          return (
            <div
              key={o.id}
              onClick={() => navigate(`/orders/${o.id}`)}
              className="rounded-xl border bg-card p-4 active:bg-muted/30 cursor-pointer"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <ShoppingCart className="size-4 text-muted-foreground" />
                    <span className="font-semibold">#{o.id}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full ${STATUS_BADGE[o.status]}`}
                    >
                      {o.status_display}
                    </span>
                  </div>
                  <div className="mt-1 font-medium truncate">{o.shop_name}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                    <span className="tabular-nums">{o.order_date}</span>
                    {o.delivery_time && (
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${
                          urgency === "overdue"
                            ? "bg-destructive/15 text-destructive"
                            : urgency === "soon"
                              ? "bg-amber-500/15 text-amber-700"
                              : "bg-muted text-foreground/70"
                        }`}
                      >
                        <Clock className="size-3" />
                        {formatDeliveryTime(o.delivery_time)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-semibold tabular-nums">
                    {formatMoney(o.total_amount, o.currency)}
                  </div>
                  <div className="text-xs text-muted-foreground tabular-nums">
                    Y: {formatMoney(o.delivered_amount, o.currency)}
                  </div>
                </div>
              </div>
              {role !== "driver" && (
                <div className="mt-3 pt-3 border-t flex justify-end">
                  <button
                    disabled={repeat.isPending}
                    onClick={(e) => {
                      e.stopPropagation();
                      repeat.mutate(o.id);
                    }}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-bakery-600"
                  >
                    <RotateCw className="size-3" /> Takrorlash
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {creating && <NewOrderModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function getApiError(err: unknown): string {
  if (!err) return "";
  const e = err as { response?: { data?: unknown }; message?: string };
  if (e?.response?.data) {
    const d = e.response.data;
    if (typeof d === "string") return d;
    if (typeof d === "object") {
      return Object.entries(d as Record<string, unknown>)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
        .join(" · ");
    }
  }
  return e?.message ?? "Noma'lum xatolik";
}

function NewOrderModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [shop, setShop] = useState<number | "">("");
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const [orderDate, setOrderDate] = useState(tomorrow.toISOString().slice(0, 10));
  const [deliveryTime, setDeliveryTime] = useState("");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [orderStatus, setOrderStatus] = useState<OrderStatus>("pending");
  const [note, setNote] = useState("");
  // Map<productId, {price, qty, delivered}>
  const [lineMap, setLineMap] = useState<Record<number, ProductLine>>({});

  // Inline payment ("Pul oldingizmi?") for delivered/partial orders.
  const [payAmount, setPayAmount] = useState("");
  const [payAccountId, setPayAccountId] = useState<number | "">("");

  const isDelivering = orderStatus === "delivered" || orderStatus === "partial";

  const { data: shops } = useQuery<Paginated<Shop>>({
    queryKey: ["shops", "for-order"],
    queryFn: async () =>
      (await api.get<Paginated<Shop>>("/shops/?archived=false")).data,
  });

  const { data: accounts } = useQuery<{ results: KassaAccount[] }>({
    queryKey: ["kassa", "accounts"],
    queryFn: async () =>
      (await api.get<{ results: KassaAccount[] }>("/finance/accounts/")).data,
    enabled: isDelivering,
  });

  // Auto-select first kassa account once accounts load.
  useEffect(() => {
    const accs = accounts?.results ?? [];
    if (accs.length > 0 && payAccountId === "") setPayAccountId(accs[0].id);
  }, [accounts, payAccountId]);

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "for-order"],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  // Fetch per-shop prices when a shop is selected.
  const { data: shopPrices } = useQuery<ShopProductPrice[]>({
    queryKey: ["shop-prices", shop, currency],
    queryFn: async () =>
      (await api.get<ShopProductPrice[]>(`/shops/${shop}/prices/`)).data,
    enabled: !!shop,
  });

  // Reset prices when shop, products or currency changes.
  // Priority: shop-specific price for matching currency → product default → ""
  useEffect(() => {
    if (!products?.results) return;
    setLineMap((prev) => {
      const next: Record<number, ProductLine> = {};
      const priceMap: Record<number, string> = {};
      if (shopPrices) {
        for (const sp of shopPrices) {
          if (sp.currency === currency) {
            priceMap[sp.product] = sp.price;
          }
        }
      }
      for (const p of products.results) {
        const shopPrice = priceMap[p.id];
        const defaultPrice = currency === "UZS" ? p.default_price_uzs : p.default_price_usd;
        next[p.id] = {
          price: shopPrice ?? defaultPrice ?? "",
          qty: prev[p.id]?.qty ?? "",
          delivered: prev[p.id]?.delivered ?? "",
        };
      }
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products?.results, currency, shopPrices]);

  const updateLine = (id: number, patch: Partial<ProductLine>) =>
    setLineMap((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));

  // Lines where qty > 0. For a "partial" order we send the per-item delivered
  // amount (defaulting to the full qty when left blank); "delivered" lets the
  // backend fill in the full quantity automatically.
  const validLines = (products?.results ?? []).flatMap((p) => {
    const line = lineMap[p.id];
    const qty = parseInt(line?.qty ?? "");
    if (!qty || qty <= 0) return [];
    const base = { product: p.id, unit_price: line.price || "0", quantity: qty };
    if (orderStatus === "partial") {
      const deliveredRaw = line.delivered;
      const delivered = deliveredRaw === "" ? qty : Math.min(parseInt(deliveredRaw) || 0, qty);
      return [{ ...base, delivered_quantity: delivered }];
    }
    return [base];
  });

  const total = (products?.results ?? []).reduce((sum, p) => {
    const line = lineMap[p.id];
    const qty = parseInt(line?.qty ?? "") || 0;
    const price = parseFloat(line?.price ?? "") || 0;
    return sum + price * qty;
  }, 0);

  const create = useMutation({
    mutationFn: async () => {
      const res = await api.post<{ id: number }>("/orders/", {
        shop: Number(shop),
        order_date: orderDate,
        delivery_time: deliveryTime
          ? new Date(`${orderDate}T${deliveryTime}`).toISOString()
          : null,
        currency,
        status: orderStatus,
        note,
        items: validLines,
      });
      // Record the received cash inline (same as the old payment popup) when a
      // delivered/partial order was paid for at handover.
      const amt = parseFloat(payAmount);
      if (isDelivering && payAccountId !== "" && amt > 0) {
        await api.post("/finance/payments/", {
          shop: Number(shop),
          order: res.data.id,
          account: payAccountId,
          currency,
          amount: payAmount,
          discount: "0",
          note: `Buyurtma #${res.data.id} to'lovi`,
          received_at: tashkentToISO(`${orderDate}T${nowTashkentStr().slice(11, 16)}`),
          payment_type: "collection",
        });
      }
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      qc.invalidateQueries({ queryKey: ["shops"] });
      onClose();
    },
  });

  const canSave = shop !== "" && validLines.length > 0 && !create.isPending;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={() => onClose()}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[92vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">Yangi buyurtma</h2>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Do'kon">
              <select
                value={shop}
                onChange={(e) =>
                  setShop(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="">Tanlang…</option>
                {shops?.results.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Sana">
              <input
                type="date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              />
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Yetkazish vaqti (ixtiyoriy)">
              <input
                type="time"
                value={deliveryTime}
                onChange={(e) => setDeliveryTime(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              />
            </Field>
            <Field label="Valyuta">
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as "UZS" | "USD")}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
              </select>
            </Field>
            <Field label="Holati">
              <select
                value={orderStatus}
                onChange={(e) => setOrderStatus(e.target.value as OrderStatus)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="pending">Kutilmoqda</option>
                <option value="partial">Qisman yetkazildi</option>
                <option value="delivered">Yetkazildi</option>
                <option value="cancelled">Bekor qilindi</option>
              </select>
            </Field>
          </div>

          {/* Product table — all products pre-listed */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">Mahsulotlar</h3>
              {validLines.length > 0 && (
                <span className="text-xs text-bakery-600 font-medium">
                  {validLines.length} ta tanlangan
                </span>
              )}
            </div>
            <div className="rounded-xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Mahsulot</th>
                    <th className="text-right px-3 py-2 font-medium w-24">Soni</th>
                    {orderStatus === "partial" && (
                      <th className="text-right px-3 py-2 font-medium w-24">Yetkazildi</th>
                    )}
                    <th className="text-right px-3 py-2 font-medium w-32">Narx</th>
                    <th className="text-right px-3 py-2 font-medium w-28 hidden sm:table-cell">Jami</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {!products && (
                    <tr>
                      <td colSpan={orderStatus === "partial" ? 5 : 4} className="px-3 py-4 text-center text-muted-foreground text-xs">
                        Yuklanmoqda…
                      </td>
                    </tr>
                  )}
                  {products?.results.map((p) => {
                    const line = lineMap[p.id] ?? { price: "", qty: "" };
                    const qty = parseInt(line.qty) || 0;
                    const price = parseFloat(line.price) || 0;
                    const lineTotal = qty * price;
                    const active = qty > 0;
                    return (
                      <tr
                        key={p.id}
                        className={active ? "bg-bakery-500/5" : "hover:bg-muted/20"}
                      >
                        <td className="px-3 py-1.5 font-medium">{p.name}</td>
                        <td className="px-3 py-1.5">
                          <input
                            type="number"
                            min="0"
                            step="1"
                            value={line.qty}
                            onChange={(e) =>
                              updateLine(p.id, { qty: e.target.value.replace(/[^0-9]/g, "") })
                            }
                            onKeyDown={(e) => {
                              if (["e", "E", "+", "-", "."].includes(e.key)) e.preventDefault();
                            }}
                            placeholder="0"
                            className={`w-full h-8 rounded-md border px-2 text-sm tabular-nums text-right focus:ring-1 outline-none ${
                              active
                                ? "border-bakery-400 bg-bakery-500/5 focus:ring-bakery-400"
                                : "bg-background focus:ring-bakery-400"
                            }`}
                          />
                        </td>
                        {orderStatus === "partial" && (
                          <td className="px-3 py-1.5">
                            <input
                              type="number"
                              min="0"
                              step="1"
                              value={line.delivered}
                              onChange={(e) =>
                                updateLine(p.id, { delivered: e.target.value.replace(/[^0-9]/g, "") })
                              }
                              onKeyDown={(e) => {
                                if (["e", "E", "+", "-", "."].includes(e.key)) e.preventDefault();
                              }}
                              placeholder={active ? String(qty) : "0"}
                              disabled={!active}
                              className="w-full h-8 rounded-md border bg-background px-2 text-sm tabular-nums text-right focus:ring-1 focus:ring-emerald-400 outline-none disabled:opacity-40"
                            />
                          </td>
                        )}
                        <td className="px-3 py-1.5">
                          <input
                            value={line.price}
                            onChange={(e) =>
                              updateLine(p.id, { price: e.target.value })
                            }
                            inputMode="decimal"
                            placeholder="0"
                            className="w-full h-8 rounded-md border bg-background px-2 text-sm tabular-nums text-right focus:ring-1 focus:ring-bakery-400 outline-none"
                          />
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground hidden sm:table-cell">
                          {active
                            ? formatMoney(lineTotal.toString(), currency)
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {validLines.length > 0 && (
                  <tfoot>
                    <tr className="border-t bg-muted/30 font-semibold">
                      <td colSpan={orderStatus === "partial" ? 4 : 3} className="px-3 py-2 text-sm">
                        Jami ({validLines.length} mahsulot):
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums hidden sm:table-cell">
                        {formatMoney(total.toString(), currency)}
                      </td>
                    </tr>
                    <tr className="sm:hidden border-t bg-muted/30">
                      <td colSpan={orderStatus === "partial" ? 4 : 3} className="px-3 py-1.5 text-right font-semibold tabular-nums">
                        {formatMoney(total.toString(), currency)}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>

          {isDelivering && (
            <div className="rounded-xl border bg-background p-3 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Banknote className="size-4 text-muted-foreground" />
                Pul oldingizmi? (ixtiyoriy)
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label={`Olingan summa (${currency})`}>
                  <input
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                    value={payAmount}
                    onChange={(e) => setPayAmount(e.target.value)}
                    inputMode="decimal"
                    placeholder="0"
                  />
                </Field>
                <Field label="Kassa">
                  <select
                    value={payAccountId}
                    onChange={(e) => setPayAccountId(e.target.value ? Number(e.target.value) : "")}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                  >
                    <option value="">Tanlang…</option>
                    {(accounts?.results ?? []).map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <p className="text-xs text-muted-foreground">
                {orderStatus === "partial"
                  ? "Yetkazilgan miqdorni har bir mahsulot uchun yuqorida kiriting. Bo'sh qolsa, to'liq yetkazilgan deb hisoblanadi."
                  : "Barcha mahsulotlar to'liq yetkazilgan deb belgilanadi."}
              </p>
            </div>
          )}

          <Field label="Izoh">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="(ixtiyoriy)"
            />
          </Field>
        </div>
        {create.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {getApiError(create.error)}
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            onClick={() => onClose()}
            className="h-10 px-4 rounded-lg border text-sm hover:bg-muted"
          >
            Bekor qilish
          </button>
          <button
            disabled={!canSave}
            onClick={() => create.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {create.isPending ? "Saqlanmoqda…" : `Saqlash${validLines.length > 0 ? ` (${validLines.length})` : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      {children}
    </div>
  );
}
