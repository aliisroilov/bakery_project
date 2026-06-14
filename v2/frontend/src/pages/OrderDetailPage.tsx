import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ArrowLeft, ShoppingCart, Check, CheckCircle2, Banknote, Pencil, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, OrderDetail, OrderItem, Paginated, Product } from "../lib/types";
import { formatMoney } from "../lib/utils";
import { useAuth } from "../lib/auth";

function getApiError(err: unknown): string {
  const e = err as { response?: { data?: unknown }; message?: string };
  const d = e?.response?.data;
  if (d && typeof d === "object")
    return Object.entries(d as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
      .join(" · ");
  return typeof d === "string" ? d : e?.message ?? "Xatolik yuz berdi.";
}

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const { data: order } = useQuery<OrderDetail>({
    queryKey: ["order", id],
    queryFn: async () => (await api.get<OrderDetail>(`/orders/${id}/`)).data,
    enabled: !!id,
  });

  const deleteOrder = useMutation({
    mutationFn: () => api.delete(`/orders/${id}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      navigate("/orders");
    },
  });

  if (!order) return <div className="text-muted-foreground">Yuklanmoqda…</div>;

  return (
    <div className="space-y-5">
      <Link
        to="/orders"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Buyurtmalar
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <ShoppingCart className="size-5 sm:size-6 text-bakery-500" />
            Buyurtma #{order.id}
          </h1>
          <p className="text-muted-foreground text-sm">
            <Link to={`/shops/${order.shop}`} className="hover:underline">
              {order.shop_name}
            </Link>{" "}
            · {order.order_date} · {order.status_display}
            {order.delivery_time && (
              <span>
                {" "}
                ·{" "}
                <span className="text-bakery-600 font-medium">
                  {new Date(order.delivery_time).toLocaleTimeString("uz-UZ", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-col sm:items-end gap-2">
          <div className="sm:text-right">
            <div className="text-xs text-muted-foreground">Jami summa</div>
            <div className="text-xl sm:text-2xl font-semibold tabular-nums">
              {formatMoney(order.total_amount, order.currency)}
            </div>
            <div className="text-xs text-muted-foreground">
              Yetkazildi: {formatMoney(order.delivered_amount, order.currency)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditOpen(true)}
              className="inline-flex items-center gap-1 h-9 px-3 rounded-lg border text-sm hover:bg-muted"
            >
              <Pencil className="size-3.5" /> Tahrirlash
            </button>
            {!deleteConfirm ? (
              <button
                onClick={() => setDeleteConfirm(true)}
                className="inline-flex items-center gap-1 h-9 px-3 rounded-lg border border-destructive/40 text-destructive text-sm hover:bg-destructive/10"
              >
                <Trash2 className="size-3.5" /> O'chirish
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <span className="text-xs text-destructive">Ishonchingiz komilmi?</span>
                <button
                  onClick={() => deleteOrder.mutate()}
                  disabled={deleteOrder.isPending}
                  className="h-8 px-3 rounded-lg bg-destructive text-white text-xs hover:bg-destructive/90 disabled:opacity-50"
                >
                  {deleteOrder.isPending ? "…" : "Ha, o'chir"}
                </button>
                <button
                  onClick={() => setDeleteConfirm(false)}
                  className="h-8 px-3 rounded-lg border text-xs hover:bg-muted"
                >
                  Bekor
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmDeliveryForm
        order={order}
        onSaved={() => qc.invalidateQueries({ queryKey: ["order", id] })}
      />

      <DriverHandoverForm order={order} />

      {editOpen && (
        <EditOrderModal
          order={order}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["order", id] });
            setEditOpen(false);
          }}
        />
      )}
    </div>
  );
}

interface EditItem {
  id?: number;
  product: number;
  product_name: string;
  unit_price: string;
  quantity: string;
}

function EditOrderModal({
  order,
  onClose,
  onSaved,
}: {
  order: OrderDetail;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [orderDate, setOrderDate] = useState(order.order_date);
  const [deliveryTime, setDeliveryTime] = useState(
    order.delivery_time
      ? new Date(order.delivery_time).toISOString().slice(0, 16)
      : ""
  );
  const [note, setNote] = useState(order.note || "");
  const [priority, setPriority] = useState(order.priority);
  const [orderStatus, setOrderStatus] = useState(order.status);
  const [editItems, setEditItems] = useState<EditItem[]>(() =>
    order.items.map((it) => ({
      id: it.id,
      product: it.product,
      product_name: it.product_name,
      unit_price: it.unit_price,
      quantity: String(it.quantity),
    }))
  );

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "for-order-edit"],
    queryFn: async () => (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  const availableProducts = products?.results ?? [];

  function updateItem(idx: number, patch: Partial<EditItem>) {
    setEditItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  function removeItem(idx: number) {
    setEditItems((prev) => prev.filter((_, i) => i !== idx));
  }

  function addProduct(productId: number) {
    const p = availableProducts.find((p) => p.id === productId);
    if (!p) return;
    if (editItems.some((it) => it.product === productId)) return;
    setEditItems((prev) => [
      ...prev,
      {
        product: p.id,
        product_name: p.name,
        unit_price: order.currency === "UZS" ? (p.default_price_uzs ?? "0") : (p.default_price_usd ?? "0"),
        quantity: "1",
      },
    ]);
  }

  const total = editItems.reduce((s, it) => {
    return s + (parseFloat(it.unit_price) || 0) * (parseInt(it.quantity) || 0);
  }, 0);

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/orders/${order.id}/`, {
        order_date: orderDate,
        delivery_time: deliveryTime ? new Date(deliveryTime).toISOString() : null,
        note,
        priority,
        status: orderStatus,
        items: editItems
          .filter((it) => parseInt(it.quantity) > 0)
          .map((it) => ({
            ...(it.id ? { id: it.id } : {}),
            product: it.product,
            unit_price: it.unit_price,
            quantity: parseInt(it.quantity),
          })),
      }),
    onSuccess: onSaved,
  });

  const unusedProducts = availableProducts.filter(
    (p) => !editItems.some((it) => it.product === p.id)
  );

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[92vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">Buyurtmani tahrirlash</h2>
        <div className="space-y-3">
          {/* Metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Sana</label>
              <input
                type="date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Yetkazish vaqti</label>
              <input
                type="datetime-local"
                value={deliveryTime}
                onChange={(e) => setDeliveryTime(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Holati</label>
              <select
                value={orderStatus}
                onChange={(e) => setOrderStatus(e.target.value as typeof orderStatus)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="pending">Kutilmoqda</option>
                <option value="partial">Qisman yetkazildi</option>
                <option value="delivered">Yetkazildi</option>
                <option value="cancelled">Bekor qilindi</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Prioritet</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as typeof priority)}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="low">Past</option>
                <option value="normal">Oddiy</option>
                <option value="high">Yuqori</option>
                <option value="urgent">Shoshilinch</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Izoh</label>
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[60px]"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          {/* Items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-muted-foreground font-medium">Mahsulotlar</label>
              <span className="text-xs font-medium text-bakery-600">
                Jami: {formatMoney(total.toString(), order.currency as "UZS" | "USD")}
              </span>
            </div>
            <div className="rounded-xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Mahsulot</th>
                    <th className="text-right px-3 py-2 font-medium w-20">Soni</th>
                    <th className="text-right px-3 py-2 font-medium w-28">Narx</th>
                    <th className="text-right px-3 py-2 font-medium w-28 hidden sm:table-cell">Jami</th>
                    <th className="w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {editItems.map((it, idx) => {
                    const lineTotal = (parseFloat(it.unit_price) || 0) * (parseInt(it.quantity) || 0);
                    return (
                      <tr key={it.id ?? `new-${idx}`}>
                        <td className="px-3 py-1.5 font-medium text-sm">{it.product_name}</td>
                        <td className="px-3 py-1.5">
                          <input
                            value={it.quantity}
                            onChange={(e) => updateItem(idx, { quantity: e.target.value })}
                            inputMode="numeric"
                            className="w-full h-8 rounded-md border bg-background px-2 text-sm tabular-nums text-right focus:ring-1 focus:ring-bakery-400 outline-none"
                          />
                        </td>
                        <td className="px-3 py-1.5">
                          <input
                            value={it.unit_price}
                            onChange={(e) => updateItem(idx, { unit_price: e.target.value })}
                            inputMode="decimal"
                            className="w-full h-8 rounded-md border bg-background px-2 text-sm tabular-nums text-right focus:ring-1 focus:ring-bakery-400 outline-none"
                          />
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground hidden sm:table-cell">
                          {formatMoney(lineTotal.toString(), order.currency as "UZS" | "USD")}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button
                            onClick={() => removeItem(idx)}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <X className="size-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {editItems.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-muted-foreground text-xs">
                        Mahsulot yo'q — quyidan qo'shing
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {unusedProducts.length > 0 && (
              <div className="mt-2">
                <select
                  value=""
                  onChange={(e) => { if (e.target.value) addProduct(Number(e.target.value)); }}
                  className="w-full h-9 px-3 rounded-lg border bg-background text-sm text-muted-foreground"
                >
                  <option value="">+ Mahsulot qo'shish…</option>
                  {unusedProducts.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {save.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {getApiError(save.error)}
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button onClick={onClose} className="h-10 px-4 rounded-lg border text-sm hover:bg-muted">
            Bekor qilish
          </button>
          <button
            disabled={save.isPending || editItems.length === 0}
            onClick={() => save.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
          >
            {save.isPending ? "Saqlanmoqda…" : "Saqlash"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfirmDeliveryForm({
  order,
  onSaved,
}: {
  order: OrderDetail;
  onSaved: () => void;
}) {
  const [rows, setRows] = useState<
    Record<number, { delivered: number; returned: number }>
  >({});

  useEffect(() => {
    const init: typeof rows = {};
    for (const it of order.items) {
      init[it.id] = {
        delivered: it.delivered_quantity,
        returned: it.returned_quantity,
      };
    }
    setRows(init);
  }, [order.items]);

  const confirm = useMutation({
    mutationFn: () =>
      api.post(`/orders/${order.id}/confirm_delivery/`, {
        items: Object.entries(rows).map(([id, v]) => ({
          item_id: Number(id),
          delivered_quantity: v.delivered,
          returned_quantity: v.returned,
        })),
      }),
    onSuccess: onSaved,
  });

  const fullyDelivered = order.status === "delivered";
  const canSubmit = !fullyDelivered && !confirm.isPending && order.items.length > 0;
  const buttonLabel = fullyDelivered
    ? "Yetkazilgan"
    : confirm.isPending
      ? "Saqlanmoqda…"
      : "Yetkazildi deb belgilash";

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="font-semibold">Mahsulotlar</h2>
        <button
          onClick={() => canSubmit && confirm.mutate()}
          disabled={!canSubmit}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto"
        >
          {fullyDelivered ? (
            <CheckCircle2 className="size-4" />
          ) : (
            <Check className="size-4" />
          )}{" "}
          {buttonLabel}
        </button>
      </div>

      {/* Desktop table */}
      <table className="w-full text-sm hidden md:table">
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <th className="text-left px-4 py-3 font-medium">Mahsulot</th>
            <th className="text-right px-4 py-3 font-medium w-16">Son</th>
            <th className="text-right px-4 py-3 font-medium w-28">Narx</th>
            <th className="text-center px-4 py-3 font-medium w-28">Yetkazildi</th>
            <th className="text-center px-4 py-3 font-medium w-24">Vozvrat</th>
            <th className="text-right px-4 py-3 font-medium w-32">Summa</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {order.items.map((it) => (
            <ItemRow
              key={it.id}
              item={it}
              currency={order.currency}
              readonly={fullyDelivered}
              delivered={rows[it.id]?.delivered ?? 0}
              returned={rows[it.id]?.returned ?? 0}
              onChange={(delivered, returned) =>
                setRows((r) => ({ ...r, [it.id]: { delivered, returned } }))
              }
            />
          ))}
        </tbody>
      </table>

      {/* Mobile cards */}
      <div className="md:hidden divide-y">
        {order.items.map((it) => (
          <ItemCard
            key={it.id}
            item={it}
            currency={order.currency}
            readonly={fullyDelivered}
            delivered={rows[it.id]?.delivered ?? 0}
            returned={rows[it.id]?.returned ?? 0}
            onChange={(delivered, returned) =>
              setRows((r) => ({ ...r, [it.id]: { delivered, returned } }))
            }
          />
        ))}
      </div>
    </div>
  );
}

function ItemRow({
  item,
  currency,
  delivered,
  returned,
  readonly,
  onChange,
}: {
  item: OrderItem;
  currency: "UZS" | "USD";
  delivered: number;
  returned: number;
  readonly: boolean;
  onChange: (delivered: number, returned: number) => void;
}) {
  const net = Math.max(delivered - returned, 0);
  const lineTotal = net * parseFloat(item.unit_price);
  return (
    <tr>
      <td className="px-4 py-3 font-medium">{item.product_name}</td>
      <td className="px-4 py-3 text-right tabular-nums">{item.quantity}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {formatMoney(item.unit_price, currency)}
      </td>
      <td className="px-2 py-3 text-center">
        <input
          type="number"
          min={0}
          max={item.quantity}
          value={delivered}
          disabled={readonly}
          onChange={(e) => onChange(Number(e.target.value), returned)}
          className="h-9 w-full rounded-md border bg-background px-2 text-center text-sm tabular-nums disabled:opacity-60"
        />
      </td>
      <td className="px-2 py-3 text-center">
        <input
          type="number"
          min={0}
          max={delivered}
          value={returned}
          disabled={readonly}
          onChange={(e) => onChange(delivered, Number(e.target.value))}
          className="h-9 w-full rounded-md border bg-background px-2 text-center text-sm tabular-nums disabled:opacity-60"
        />
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        {formatMoney(lineTotal.toFixed(2), currency)}
      </td>
    </tr>
  );
}

function ItemCard({
  item,
  currency,
  delivered,
  returned,
  readonly,
  onChange,
}: {
  item: OrderItem;
  currency: "UZS" | "USD";
  delivered: number;
  returned: number;
  readonly: boolean;
  onChange: (delivered: number, returned: number) => void;
}) {
  const net = Math.max(delivered - returned, 0);
  const lineTotal = net * parseFloat(item.unit_price);
  return (
    <div className="p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium">{item.product_name}</div>
        <div className="text-right tabular-nums text-sm">
          <div className="font-semibold">
            {formatMoney(lineTotal.toFixed(2), currency)}
          </div>
          <div className="text-xs text-muted-foreground">
            {formatMoney(item.unit_price, currency)} × {item.quantity}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 pt-1">
        <label className="block">
          <span className="block text-xs text-muted-foreground mb-1">
            Yetkazildi
          </span>
          <input
            type="number"
            min={0}
            max={item.quantity}
            value={delivered}
            disabled={readonly}
            onChange={(e) => onChange(Number(e.target.value), returned)}
            className="h-10 w-full rounded-md border bg-background px-3 text-right text-sm tabular-nums disabled:opacity-60"
          />
        </label>
        <label className="block">
          <span className="block text-xs text-muted-foreground mb-1">
            Vozvrat
          </span>
          <input
            type="number"
            min={0}
            max={delivered}
            value={returned}
            disabled={readonly}
            onChange={(e) => onChange(delivered, Number(e.target.value))}
            className="h-10 w-full rounded-md border bg-background px-3 text-right text-sm tabular-nums disabled:opacity-60"
          />
        </label>
      </div>
    </div>
  );
}

function DriverHandoverForm({ order }: { order: OrderDetail }) {
  const qc = useQueryClient();
  const currentUser = useAuth((s) => s.user);
  const [amount, setAmount] = useState("");
  const [discount, setDiscount] = useState("0");
  const [currency, setCurrency] = useState<"UZS" | "USD">(order.currency as "UZS" | "USD");
  const [note, setNote] = useState("");

  // Fetch accounts silently — driver doesn't choose, we auto-use the first one.
  const { data: accounts } = useQuery<KassaAccount[]>({
    queryKey: ["kassa-accounts"],
    queryFn: async () => (await api.get<KassaAccount[]>("/finance/accounts/")).data,
  });

  const accountsList = Array.isArray(accounts)
    ? accounts
    : (accounts as unknown as { results: KassaAccount[] })?.results ?? [];
  const defaultAccount = accountsList[0]?.id;

  const save = useMutation({
    mutationFn: () =>
      api.post("/finance/payments/", {
        shop: order.shop,
        order: order.id,
        payment_type: "collection",
        currency,
        amount,
        discount: discount || "0",
        account: defaultAccount,
        collected_by: currentUser?.id,
        received_at: new Date().toISOString(),
        note: note || `Buyurtma #${order.id} · ${order.shop_name}`,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setAmount("");
      setDiscount("0");
      setNote("");
    },
  });

  const canSave = !!amount && parseFloat(amount) > 0 && !!defaultAccount && !save.isPending;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b">
        <h2 className="font-semibold flex items-center gap-2">
          <Banknote className="size-4 text-bakery-500" /> Haydovchi qabul qildi
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Naqd pul qabul qilindi — mening balansimga yoziladi
        </p>
      </div>
      <div className="px-4 sm:px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Summa</label>
          <input
            type="number"
            min={0}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0"
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm tabular-nums"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Skidka</label>
          <input
            type="number"
            min={0}
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
            placeholder="0"
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm tabular-nums"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Valyuta</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as "UZS" | "USD")}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          >
            <option value="UZS">UZS</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div className="flex items-end col-span-2 sm:col-span-1">
          <button
            disabled={!canSave}
            onClick={() => save.mutate()}
            className="h-10 w-full rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
          >
            {save.isPending ? "Saqlanmoqda…" : "Saqlash"}
          </button>
        </div>
      </div>
      {save.isSuccess && (
        <div className="px-4 sm:px-5 pb-3 text-sm text-emerald-600">
          Muvaffaqiyatli saqlandi — balansga yozildi
        </div>
      )}
      {save.isError && (
        <div className="px-4 sm:px-5 pb-3 text-sm text-destructive">
          Saqlashda xatolik yuz berdi
        </div>
      )}
    </div>
  );
}
