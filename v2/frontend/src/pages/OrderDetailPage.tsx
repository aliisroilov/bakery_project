import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ArrowLeft, ShoppingCart, Check, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import type { OrderDetail, OrderItem } from "../lib/types";
import { formatMoney } from "../lib/utils";

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: order } = useQuery<OrderDetail>({
    queryKey: ["order", id],
    queryFn: async () => (await api.get<OrderDetail>(`/orders/${id}/`)).data,
    enabled: !!id,
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
        <div className="sm:text-right">
          <div className="text-xs text-muted-foreground">Jami summa</div>
          <div className="text-xl sm:text-2xl font-semibold tabular-nums">
            {formatMoney(order.total_amount, order.currency)}
          </div>
          <div className="text-xs text-muted-foreground">
            Yetkazildi: {formatMoney(order.delivered_amount, order.currency)}
          </div>
        </div>
      </div>

      <ConfirmDeliveryForm
        order={order}
        onSaved={() => qc.invalidateQueries({ queryKey: ["order", id] })}
      />
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
            <th className="text-right px-4 py-3 font-medium">Narx</th>
            <th className="text-right px-4 py-3 font-medium">Miqdor</th>
            <th className="text-right px-4 py-3 font-medium">Yetkazildi</th>
            <th className="text-right px-4 py-3 font-medium">Qaytdi</th>
            <th className="text-right px-4 py-3 font-medium">Summa</th>
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
      <td className="px-4 py-3 text-right tabular-nums">
        {formatMoney(item.unit_price, currency)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{item.quantity}</td>
      <td className="px-4 py-3">
        <input
          type="number"
          min={0}
          max={item.quantity}
          value={delivered}
          disabled={readonly}
          onChange={(e) => onChange(Number(e.target.value), returned)}
          className="h-9 w-20 rounded-md border bg-background px-2 text-right text-sm tabular-nums disabled:opacity-60"
        />
      </td>
      <td className="px-4 py-3">
        <input
          type="number"
          min={0}
          max={delivered}
          value={returned}
          disabled={readonly}
          onChange={(e) => onChange(delivered, Number(e.target.value))}
          className="h-9 w-20 rounded-md border bg-background px-2 text-right text-sm tabular-nums disabled:opacity-60"
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
            Qaytdi
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
