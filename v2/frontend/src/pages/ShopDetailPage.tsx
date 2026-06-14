import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ArrowLeft, Store, AlertTriangle, Truck } from "lucide-react";
import { api } from "../lib/api";
import type {
  OrderDetail,
  Paginated,
  Payment,
  Product,
  ShopDetail,
  ShopProductPrice,
} from "../lib/types";
import { formatMoney, fmtDate } from "../lib/utils";

export function ShopDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: shop } = useQuery<ShopDetail>({
    queryKey: ["shop", id],
    queryFn: async () => (await api.get<ShopDetail>(`/shops/${id}/`)).data,
    enabled: !!id,
  });

  // Date filter state for orders and payments
  const [orderDateFrom, setOrderDateFrom] = useState("");
  const [orderDateTo, setOrderDateTo] = useState("");
  const [payDateFrom, setPayDateFrom] = useState("");
  const [payDateTo, setPayDateTo] = useState("");

  const { data: orders } = useQuery<Paginated<OrderDetail>>({
    queryKey: ["shop", id, "orders", { orderDateFrom, orderDateTo }],
    queryFn: async () => {
      const p = new URLSearchParams({ shop: id!, ordering: "-id", page_size: "50" });
      if (orderDateFrom) p.set("date_from", orderDateFrom);
      if (orderDateTo) p.set("date_to", orderDateTo);
      return (await api.get<Paginated<OrderDetail>>(`/orders/?${p}`)).data;
    },
    enabled: !!id,
  });

  const { data: payments } = useQuery<Paginated<Payment>>({
    queryKey: ["shop", id, "payments", { payDateFrom, payDateTo }],
    queryFn: async () => {
      const p = new URLSearchParams({ shop: id!, ordering: "-received_at", page_size: "50" });
      if (payDateFrom) p.set("date_from", payDateFrom);
      if (payDateTo) p.set("date_to", payDateTo);
      return (await api.get<Paginated<Payment>>(`/finance/payments/?${p}`)).data;
    },
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
        {/* Orders */}
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h2 className="font-semibold flex items-center gap-2">
                <Truck className="size-4" /> Buyurtmalar
              </h2>
              <span className="text-xs text-muted-foreground">
                {orders?.count ?? 0} ta
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={orderDateFrom}
                onChange={(e) => setOrderDateFrom(e.target.value)}
                className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
              />
              <span className="text-xs text-muted-foreground">—</span>
              <input
                type="date"
                value={orderDateTo}
                onChange={(e) => setOrderDateTo(e.target.value)}
                className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
              />
              {(orderDateFrom || orderDateTo) && (
                <button
                  onClick={() => { setOrderDateFrom(""); setOrderDateTo(""); }}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
          <ul className="divide-y max-h-96 overflow-auto">
            {orders?.results.map((o) => (
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

        {/* Payments */}
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
            <div className="flex items-center justify-between gap-2 mb-2">
              <h2 className="font-semibold">Kirimlar</h2>
              <span className="text-xs text-muted-foreground">
                {payments?.count ?? 0} ta
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={payDateFrom}
                onChange={(e) => setPayDateFrom(e.target.value)}
                className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
              />
              <span className="text-xs text-muted-foreground">—</span>
              <input
                type="date"
                value={payDateTo}
                onChange={(e) => setPayDateTo(e.target.value)}
                className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
              />
              {(payDateFrom || payDateTo) && (
                <button
                  onClick={() => { setPayDateFrom(""); setPayDateTo(""); }}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
          <ul className="divide-y max-h-96 overflow-auto">
            {payments?.results.map((p) => (
              <li key={p.id} className="px-4 sm:px-5 py-3 flex items-center justify-between gap-3 text-sm">
                <div className="min-w-0">
                  <div className="truncate">{p.payment_type_display}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {fmtDate(p.received_at)} · {p.account_name}
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
  const qc = useQueryClient();

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", { archived: false }],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  // Build map: product_id → existing price
  const priceByProduct = new Map<number, ShopProductPrice>();
  for (const p of prices) {
    priceByProduct.set(p.product, p);
  }

  const onSaved = () => qc.invalidateQueries({ queryKey: ["shop", String(shopId)] });

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 sm:px-5 py-3 sm:py-4 border-b">
        <h2 className="font-semibold">Mahsulot narxlari (shu do'kon uchun)</h2>
        <p className="text-xs text-muted-foreground">
          Buyurtma qilishda shu narxlar avtomatik tanlanadi. Bo'sh qoldirilsa default narx ishlatiladi.
        </p>
      </div>
      <div className="divide-y">
        {products?.results.map((product) => (
          <PriceRow
            key={`${product.id}-${priceByProduct.get(product.id)?.id ?? "new"}`}
            shopId={shopId}
            product={product}
            existing={priceByProduct.get(product.id)}
            onSaved={onSaved}
          />
        ))}
        {!products && (
          <div className="px-4 py-6 text-sm text-muted-foreground text-center">
            Yuklanmoqda…
          </div>
        )}
      </div>
    </div>
  );
}

function PriceRow({
  shopId,
  product,
  existing,
  onSaved,
}: {
  shopId: number;
  product: Product;
  existing: ShopProductPrice | undefined;
  onSaved: () => void;
}) {
  const [price, setPrice] = useState(existing?.price ?? "");
  const [currency, setCurrency] = useState<"UZS" | "USD">(existing?.currency ?? "UZS");

  useEffect(() => {
    setPrice(existing?.price ?? "");
    setCurrency(existing?.currency ?? "UZS");
  }, [existing?.id, existing?.price, existing?.currency]);

  const save = useMutation({
    mutationFn: () =>
      api.post(`/shops/${shopId}/prices/`, {
        product: product.id,
        price,
        currency,
      }),
    onSuccess: onSaved,
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/shops/${shopId}/prices/${existing!.id}/`),
    onSuccess: () => {
      setPrice("");
      onSaved();
    },
  });

  const hasPrice = !!price && parseFloat(price) > 0;

  return (
    <div className="px-4 sm:px-5 py-2.5 flex items-center gap-2 sm:gap-3 text-sm">
      <span className="flex-1 truncate">{product.name}</span>
      <input
        className="h-9 w-28 rounded-lg border bg-background px-2 text-right text-sm tabular-nums focus:outline-none focus:ring-1 focus:ring-bakery-400"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        inputMode="decimal"
        placeholder={existing ? existing.price : "—"}
      />
      <select
        value={currency}
        onChange={(e) => setCurrency(e.target.value as "UZS" | "USD")}
        className="h-9 rounded-lg border bg-background px-2 text-sm"
      >
        <option value="UZS">UZS</option>
        <option value="USD">USD</option>
      </select>
      <button
        disabled={!hasPrice || save.isPending}
        onClick={() => save.mutate()}
        className="h-9 px-3 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-xs disabled:opacity-40 shrink-0"
      >
        {save.isPending ? "…" : "Saqlash"}
      </button>
      {existing && (
        <button
          disabled={remove.isPending}
          onClick={() => remove.mutate()}
          className="h-9 w-9 flex items-center justify-center rounded-lg border text-xs text-muted-foreground hover:text-destructive hover:border-destructive disabled:opacity-40 shrink-0"
          title="Narxni o'chirish"
        >
          ✕
        </button>
      )}
    </div>
  );
}
