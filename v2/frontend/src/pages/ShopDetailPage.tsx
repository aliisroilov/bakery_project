import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowLeft, Store, AlertTriangle, Truck, Plus } from "lucide-react";
import { api } from "../lib/api";
import type {
  OrderDetail,
  Paginated,
  Payment,
  Product,
  ShopDetail,
} from "../lib/types";
import { formatMoney } from "../lib/utils";

export function ShopDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: shop } = useQuery<ShopDetail>({
    queryKey: ["shop", id],
    queryFn: async () => (await api.get<ShopDetail>(`/shops/${id}/`)).data,
    enabled: !!id,
  });

  const { data: orders } = useQuery<Paginated<OrderDetail>>({
    queryKey: ["shop", id, "orders"],
    queryFn: async () =>
      (await api.get<Paginated<OrderDetail>>(`/orders/?shop=${id}`)).data,
    enabled: !!id,
  });

  const { data: payments } = useQuery<Paginated<Payment>>({
    queryKey: ["shop", id, "payments"],
    queryFn: async () =>
      (await api.get<Paginated<Payment>>(`/finance/payments/?shop=${id}`)).data,
    enabled: !!id,
  });

  if (!shop) {
    return <div className="text-muted-foreground">Yuklanmoqda…</div>;
  }

  return (
    <div className="space-y-4 sm:space-y-5">
      <Link
        to="/shops"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Do'konlar
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2 flex-wrap">
            <Store className="size-5 sm:size-6 text-bakery-500" />
            <span className="truncate">{shop.name}</span>
            {(shop.limit_exceeded_uzs || shop.limit_exceeded_usd) && (
              <span className="inline-flex items-center gap-1 text-xs sm:text-sm text-destructive">
                <AlertTriangle className="size-4" /> Limit oshgan
              </span>
            )}
          </h1>
          <p className="text-muted-foreground text-sm">
            {shop.region_name} · {shop.owner_name || "—"} · {shop.phone || "telefon yo'q"}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4">
        <Stat label="Qarz (UZS)" primary={formatMoney(shop.loan_balance_uzs, "UZS")} />
        <Stat label="Qarz (USD)" primary={formatMoney(shop.loan_balance_usd, "USD")} />
        <Stat label="Limit (UZS)" primary={
          parseFloat(shop.loan_limit_uzs) > 0
            ? formatMoney(shop.loan_limit_uzs, "UZS")
            : "Yo'q"
        } />
        <Stat label="Haydovchi" primary={shop.assigned_driver_name || "Biriktirilmagan"} />
      </div>

      <Prices shopId={shop.id} prices={shop.product_prices} />

      <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 sm:px-5 py-3 sm:py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <Truck className="size-4" /> Oxirgi buyurtmalar
            </h2>
            <span className="text-xs text-muted-foreground">
              {orders?.count ?? 0} ta
            </span>
          </div>
          <ul className="divide-y max-h-96 overflow-auto">
            {orders?.results.slice(0, 10).map((o) => (
              <li key={o.id} className="px-4 sm:px-5 py-3 flex items-center justify-between gap-3 text-sm">
                <Link to={`/orders/${o.id}`} className="hover:text-bakery-600 truncate">
                  #{o.id} · {o.order_date} · {o.status_display}
                </Link>
                <span className="tabular-nums font-medium shrink-0">
                  {formatMoney(o.total_amount, o.currency)}
                </span>
              </li>
            ))}
            {orders?.results.length === 0 && (
              <li className="px-4 sm:px-5 py-8 text-center text-sm text-muted-foreground">
                Buyurtmalar yo'q
              </li>
            )}
          </ul>
        </div>

        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 sm:px-5 py-3 sm:py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold">Oxirgi kirimlar</h2>
            <span className="text-xs text-muted-foreground">
              {payments?.count ?? 0} ta
            </span>
          </div>
          <ul className="divide-y max-h-96 overflow-auto">
            {payments?.results.slice(0, 10).map((p) => (
              <li key={p.id} className="px-4 sm:px-5 py-3 flex items-center justify-between gap-3 text-sm">
                <div className="min-w-0">
                  <div className="truncate">{p.payment_type_display}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {p.received_at.slice(0, 10)} · {p.account_name}
                  </div>
                </div>
                <span className="tabular-nums font-medium shrink-0">
                  {formatMoney(p.amount, p.currency)}
                </span>
              </li>
            ))}
            {payments?.results.length === 0 && (
              <li className="px-4 sm:px-5 py-8 text-center text-sm text-muted-foreground">
                Kirim yo'q
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, primary }: { label: string; primary: string }) {
  return (
    <div className="rounded-xl border bg-card p-3 sm:p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-base sm:text-lg font-semibold tabular-nums truncate">{primary}</div>
    </div>
  );
}

function Prices({
  shopId,
  prices,
}: {
  shopId: number;
  prices: ShopDetail["product_prices"];
}) {
  const [productId, setProductId] = useState<number | "">("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const qc = useQueryClient();

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", { archived: false }],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  const upsert = useMutation({
    mutationFn: () =>
      api.post(`/shops/${shopId}/prices/`, {
        product: productId,
        price,
        currency,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shop", String(shopId)] });
      setProductId("");
      setPrice("");
    },
  });

  const remove = useMutation({
    mutationFn: (priceId: number) => api.delete(`/shops/${shopId}/prices/${priceId}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shop", String(shopId)] }),
  });

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
        <h2 className="font-semibold">Mahsulot narxlari (shu do'kon uchun)</h2>
        <p className="text-xs text-muted-foreground">
          Buyurtma qilishda shu narxlar avtomatik tanlanadi.
        </p>
      </div>
      <div className="px-4 sm:px-5 py-3 sm:py-4 grid grid-cols-2 sm:flex sm:flex-wrap sm:items-end gap-3 border-b bg-muted/30">
        <div className="col-span-2 sm:col-span-1">
          <label className="block text-xs text-muted-foreground mb-1">Mahsulot</label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : "")}
            className="h-10 w-full sm:min-w-[160px] rounded-lg border bg-background px-2 text-sm"
          >
            <option value="">Tanlang…</option>
            {products?.results.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Narx</label>
          <input
            className="h-10 w-full sm:w-32 rounded-lg border bg-background px-2 text-sm tabular-nums"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            inputMode="decimal"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Valyuta</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as "UZS" | "USD")}
            className="h-10 w-full rounded-lg border bg-background px-2 text-sm"
          >
            <option value="UZS">UZS</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <button
          disabled={!productId || !price || upsert.isPending}
          onClick={() => upsert.mutate()}
          className="col-span-2 sm:col-span-1 h-10 inline-flex items-center justify-center gap-1 px-3 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
        >
          <Plus className="size-4" /> Saqlash
        </button>
      </div>
      <ul className="divide-y">
        {prices.length === 0 && (
          <li className="px-4 sm:px-5 py-6 text-sm text-muted-foreground text-center">
            Maxsus narxlar belgilanmagan (default narx ishlatiladi)
          </li>
        )}
        {prices.map((p) => (
          <li key={p.id} className="px-4 sm:px-5 py-3 flex items-center justify-between gap-3 text-sm">
            <span className="truncate">{p.product_name}</span>
            <span className="flex items-center gap-3 shrink-0">
              <span className="tabular-nums font-medium">
                {formatMoney(p.price, p.currency)}
              </span>
              <button
                onClick={() => remove.mutate(p.id)}
                className="text-xs text-muted-foreground hover:text-destructive"
              >
                O'chirish
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
