import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShoppingCart,
  Search,
  RotateCw,
  Plus,
  Trash2,
  Clock,
} from "lucide-react";
import { api } from "../lib/api";
import type { Order, OrderStatus, Paginated, Product, Shop } from "../lib/types";
import { formatMoney } from "../lib/utils";

interface OrderLine {
  key: string;
  product: number | "";
  unit_price: string;
  quantity: string;
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
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | OrderStatus>("");
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
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi buyurtma
        </button>
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
              <th className="text-right px-4 py-3 font-medium"></th>
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
            </div>
          );
        })}
      </div>

      {creating && <NewOrderModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function NewOrderModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [shop, setShop] = useState<number | "">("");
  // Feature #3/UX: default to tomorrow so new orders are for next delivery day.
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const [orderDate, setOrderDate] = useState(tomorrow.toISOString().slice(0, 10));
  const [deliveryTime, setDeliveryTime] = useState("");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<OrderLine[]>([
    { key: crypto.randomUUID(), product: "", unit_price: "", quantity: "1" },
  ]);

  const { data: shops } = useQuery<Paginated<Shop>>({
    queryKey: ["shops", "for-order"],
    queryFn: async () =>
      (await api.get<Paginated<Shop>>("/shops/?archived=false")).data,
  });

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "for-order"],
    queryFn: async () => (await api.get<Paginated<Product>>("/products/")).data,
  });

  const validLines = lines.filter(
    (l) => l.product && parseFloat(l.unit_price) > 0 && parseInt(l.quantity) > 0,
  );

  const total = validLines.reduce(
    (sum, l) => sum + parseFloat(l.unit_price) * parseInt(l.quantity),
    0,
  );

  const create = useMutation({
    mutationFn: () =>
      api.post("/orders/", {
        shop: Number(shop),
        order_date: orderDate,
        // Combine order date + entered HH:MM as local time → ISO datetime.
        delivery_time: deliveryTime
          ? new Date(`${orderDate}T${deliveryTime}`).toISOString()
          : null,
        currency,
        note,
        items: validLines.map((l) => ({
          product: Number(l.product),
          unit_price: l.unit_price,
          quantity: parseInt(l.quantity),
        })),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      onClose();
    },
  });

  const addLine = () =>
    setLines((ls) => [
      ...ls,
      { key: crypto.randomUUID(), product: "", unit_price: "", quantity: "1" },
    ]);

  const removeLine = (key: string) =>
    setLines((ls) => (ls.length === 1 ? ls : ls.filter((l) => l.key !== key)));

  const updateLine = (key: string, patch: Partial<OrderLine>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const canSave = shop !== "" && validLines.length > 0 && !create.isPending;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
          </div>
          <div className="rounded-xl border bg-muted/30 p-3 sm:p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">Mahsulotlar</h3>
              <button
                type="button"
                onClick={addLine}
                className="inline-flex items-center gap-1 h-8 px-3 rounded-lg border text-xs hover:bg-card"
              >
                <Plus className="size-3.5" /> Qo'shish
              </button>
            </div>
            <div className="space-y-2">
              {lines.map((l) => {
                const prod = products?.results.find((p) => p.id === l.product);
                return (
                  <div
                    key={l.key}
                    className="flex flex-col sm:flex-row gap-2 sm:items-center p-2 sm:p-0 rounded-lg bg-card sm:bg-transparent"
                  >
                    <select
                      value={l.product}
                      onChange={(e) => {
                        const pid = e.target.value
                          ? Number(e.target.value)
                          : "";
                        const picked = products?.results.find(
                          (p) => p.id === pid,
                        );
                        updateLine(l.key, {
                          product: pid,
                          unit_price:
                            picked && !l.unit_price
                              ? (currency === "UZS"
                                  ? picked.default_price_uzs
                                  : picked.default_price_usd) || ""
                              : l.unit_price,
                        });
                      }}
                      className="flex-1 h-10 rounded-lg border bg-background px-3 text-sm min-w-0"
                    >
                      <option value="">Mahsulot tanlang…</option>
                      {products?.results.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <div className="flex gap-2 items-center">
                      <input
                        value={l.unit_price}
                        onChange={(e) =>
                          updateLine(l.key, { unit_price: e.target.value })
                        }
                        placeholder="Narx"
                        inputMode="decimal"
                        className="flex-1 sm:w-32 h-10 rounded-lg border bg-background px-3 text-sm tabular-nums text-right"
                      />
                      <input
                        value={l.quantity}
                        onChange={(e) =>
                          updateLine(l.key, { quantity: e.target.value })
                        }
                        placeholder="Soni"
                        inputMode="numeric"
                        className="w-20 h-10 rounded-lg border bg-background px-3 text-sm tabular-nums text-right"
                      />
                      <button
                        type="button"
                        onClick={() => removeLine(l.key)}
                        disabled={lines.length === 1}
                        className="size-10 shrink-0 rounded-lg border grid place-items-center text-muted-foreground hover:text-destructive disabled:opacity-30"
                        aria-label="O'chirish"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </div>
                    <div className="w-full sm:w-28 text-right text-xs text-muted-foreground tabular-nums">
                      {prod &&
                      parseFloat(l.unit_price) > 0 &&
                      parseInt(l.quantity) > 0
                        ? formatMoney(
                            (
                              parseFloat(l.unit_price) * parseInt(l.quantity)
                            ).toString(),
                            currency,
                          )
                        : "—"}
                    </div>
                  </div>
                );
              })}
            </div>
            {validLines.length > 0 && (
              <div className="mt-3 flex justify-between text-sm font-semibold">
                <span>Jami:</span>
                <span className="tabular-nums">
                  {formatMoney(total.toString(), currency)}
                </span>
              </div>
            )}
          </div>
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
            Saqlashda xatolik.
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            onClick={onClose}
            className="h-10 px-4 rounded-lg border text-sm hover:bg-muted"
          >
            Bekor qilish
          </button>
          <button
            disabled={!canSave}
            onClick={() => create.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {create.isPending ? "Saqlanmoqda…" : "Saqlash"}
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
