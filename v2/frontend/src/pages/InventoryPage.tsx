import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Settings2, Wheat } from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, Paginated } from "../lib/types";
import { formatMoney } from "../lib/utils";

interface Ingredient {
  id: number;
  name: string;
  unit: number;
  unit_short: string;
  quantity: string;
  low_stock_threshold: string;
  avg_cost_uzs: string;
  is_low_stock: boolean;
  is_archived: boolean;
}

interface Purchase {
  id: number;
  ingredient: number;
  ingredient_name: string;
  quantity: string;
  currency: "UZS" | "USD";
  total_price: string;
  unit_price: string;
  account: number;
  account_name: string;
  occurred_at: string;
  note: string;
}

export function InventoryPage() {
  const [purchaseOpen, setPurchaseOpen] = useState(false);
  const [adjustIng, setAdjustIng] = useState<Ingredient | null>(null);

  const { data: ingredients } = useQuery<Paginated<Ingredient>>({
    queryKey: ["inventory", "ingredients"],
    queryFn: async () =>
      (await api.get<Paginated<Ingredient>>("/inventory/ingredients/?archived=false")).data,
  });

  const { data: purchases } = useQuery<Paginated<Purchase>>({
    queryKey: ["inventory", "purchases"],
    queryFn: async () =>
      (await api.get<Paginated<Purchase>>("/inventory/purchases/")).data,
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Xomashyo</h1>
          <p className="text-muted-foreground text-sm">Ingredientlar va xaridlar</p>
        </div>
        <button
          onClick={() => setPurchaseOpen(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi xarid
        </button>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b">
          <h2 className="font-semibold">Ingredientlar</h2>
        </div>

        {/* Desktop table */}
        <table className="w-full text-sm hidden md:table">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Nomi</th>
              <th className="text-right px-4 py-3 font-medium">Zaxira</th>
              <th className="text-right px-4 py-3 font-medium">Minimum</th>
              <th className="text-right px-4 py-3 font-medium">O'rta narx</th>
              <th className="text-right px-4 py-3 font-medium w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {ingredients?.results.map((i) => (
              <tr key={i.id} className="hover:bg-muted/30">
                <td className="px-4 py-3 flex items-center gap-2 font-medium">
                  <Wheat className="size-4 text-bakery-500" /> {i.name}
                  {i.is_low_stock && (
                    <AlertTriangle className="size-4 text-destructive" />
                  )}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${
                    i.is_low_stock ? "text-destructive font-medium" : ""
                  }`}
                >
                  {parseFloat(i.quantity).toFixed(2)} {i.unit_short}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(i.low_stock_threshold).toFixed(2)} {i.unit_short}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(i.avg_cost_uzs) > 0
                    ? formatMoney(i.avg_cost_uzs, "UZS")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setAdjustIng(i)}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                    title="Zaxirani tuzatish"
                  >
                    <Settings2 className="size-3.5" /> Tuzatish
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Mobile cards */}
        <div className="md:hidden divide-y">
          {ingredients?.results.map((i) => (
            <div key={i.id} className="p-3 flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 font-medium">
                  <Wheat className="size-4 text-bakery-500 shrink-0" />
                  <span className="truncate">{i.name}</span>
                  {i.is_low_stock && (
                    <AlertTriangle className="size-4 text-destructive shrink-0" />
                  )}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs tabular-nums">
                  <span
                    className={
                      i.is_low_stock
                        ? "text-destructive font-medium"
                        : ""
                    }
                  >
                    {parseFloat(i.quantity).toFixed(2)} {i.unit_short}
                  </span>
                  <span className="text-muted-foreground">
                    min {parseFloat(i.low_stock_threshold).toFixed(2)}
                  </span>
                  {parseFloat(i.avg_cost_uzs) > 0 && (
                    <span className="text-muted-foreground">
                      {formatMoney(i.avg_cost_uzs, "UZS")}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setAdjustIng(i)}
                className="shrink-0 inline-flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-muted-foreground hover:text-foreground"
              >
                <Settings2 className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b">
          <h2 className="font-semibold">Oxirgi xaridlar</h2>
        </div>

        {/* Desktop table */}
        <table className="w-full text-sm hidden md:table">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Sana</th>
              <th className="text-left px-4 py-3 font-medium">Ingredient</th>
              <th className="text-right px-4 py-3 font-medium">Miqdor</th>
              <th className="text-right px-4 py-3 font-medium">Narx</th>
              <th className="text-left px-4 py-3 font-medium">Kassa</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {purchases?.results.slice(0, 25).map((p) => (
              <tr key={p.id}>
                <td className="px-4 py-3 text-muted-foreground tabular-nums">
                  {p.occurred_at.slice(0, 10)}
                </td>
                <td className="px-4 py-3">{p.ingredient_name}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {parseFloat(p.quantity).toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {formatMoney(p.total_price, p.currency)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{p.account_name}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Mobile cards */}
        <div className="md:hidden divide-y">
          {purchases?.results.slice(0, 25).map((p) => (
            <div key={p.id} className="p-3 space-y-1">
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium truncate">{p.ingredient_name}</div>
                <div className="text-right tabular-nums text-sm shrink-0">
                  {formatMoney(p.total_price, p.currency)}
                </div>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  {p.occurred_at.slice(0, 10)} · {p.account_name}
                </span>
                <span className="tabular-nums">
                  {parseFloat(p.quantity).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {purchaseOpen && (
        <PurchaseModal
          ingredients={ingredients?.results ?? []}
          onClose={() => setPurchaseOpen(false)}
        />
      )}
      {adjustIng && (
        <AdjustModal ingredient={adjustIng} onClose={() => setAdjustIng(null)} />
      )}
    </div>
  );
}

function PurchaseModal({
  ingredients,
  onClose,
}: {
  ingredients: Ingredient[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [ingredientId, setIngredientId] = useState<number | "">("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [quantity, setQuantity] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [occurredAt, setOccurredAt] = useState(
    () => new Date().toISOString().slice(0, 16),
  );
  const [note, setNote] = useState("");

  const qtyNum = parseFloat(quantity) || 0;
  const unitNum = parseFloat(unitPrice) || 0;
  const totalPrice = qtyNum > 0 && unitNum > 0 ? (qtyNum * unitNum).toFixed(2) : "";

  const selectedIng = ingredients.find((i) => i.id === ingredientId);
  const unitShort = selectedIng?.unit_short ?? "";

  const { data: accounts } = useQuery<Paginated<KassaAccount>>({
    queryKey: ["kassa", "accounts"],
    queryFn: async () =>
      (await api.get<Paginated<KassaAccount>>("/finance/accounts/")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/inventory/purchases/", {
        ingredient: ingredientId,
        account: accountId,
        currency,
        quantity,
        total_price: totalPrice,
        occurred_at: new Date(occurredAt).toISOString(),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      onClose();
    },
  });

  const canSave =
    ingredientId && accountId && qtyNum > 0 && unitNum > 0;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">Yangi xarid</h2>
        <div className="space-y-3">
          <Field label="Ingredient">
            <select
              value={ingredientId}
              onChange={(e) =>
                setIngredientId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">Tanlang…</option>
              {ingredients.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.unit_short})
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Kassa">
              <select
                value={accountId}
                onChange={(e) =>
                  setAccountId(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="">Tanlang…</option>
                {accounts?.results.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Valyuta">
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as "UZS" | "USD")}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={`Miqdor${unitShort ? ` (${unitShort})` : ""}`}>
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                inputMode="decimal"
              />
            </Field>
            <Field label={`Narx${unitShort ? ` (1 ${unitShort} uchun)` : " (1 birlik uchun)"}`}>
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                inputMode="decimal"
              />
            </Field>
          </div>
          {totalPrice && (
            <div className="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground flex justify-between">
              <span>Umumiy summa ({currency}):</span>
              <span className="font-semibold text-foreground tabular-nums">
                {Number(totalPrice).toLocaleString()}
              </span>
            </div>
          )}
          <Field label="Sana">
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            />
          </Field>
          <Field label="Izoh">
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[60px]"
              value={note}
              onChange={(e) => setNote(e.target.value)}
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
            disabled={!canSave || create.isPending}
            onClick={() => create.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
          >
            Saqlash
          </button>
        </div>
      </div>
    </div>
  );
}

function AdjustModal({
  ingredient,
  onClose,
}: {
  ingredient: Ingredient;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [newQuantity, setNewQuantity] = useState(
    parseFloat(ingredient.quantity).toFixed(2),
  );
  const [note, setNote] = useState("");

  const adjust = useMutation({
    mutationFn: () =>
      api.post(`/inventory/ingredients/${ingredient.id}/adjust/`, {
        new_quantity: newQuantity,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      onClose();
    },
  });

  const canSave = parseFloat(newQuantity) >= 0 && !isNaN(parseFloat(newQuantity));

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-card rounded-2xl shadow-xl border p-4 sm:p-6"
      >
        <h2 className="font-semibold text-lg mb-1">{ingredient.name} — tuzatish</h2>
        <p className="text-xs text-muted-foreground mb-4">
          Hozirgi: {parseFloat(ingredient.quantity).toFixed(2)} {ingredient.unit_short}
        </p>
        <div className="space-y-3">
          <Field label={`Yangi zaxira (${ingredient.unit_short})`}>
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
              value={newQuantity}
              onChange={(e) => setNewQuantity(e.target.value)}
              inputMode="decimal"
            />
          </Field>
          <Field label="Sabab (ixtiyoriy)">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Masalan: inventarizatsiya"
            />
          </Field>
        </div>
        {adjust.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            Tuzatishda xatolik.
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
            disabled={!canSave || adjust.isPending}
            onClick={() => adjust.mutate()}
            className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50"
          >
            Tuzatish
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      {children}
    </div>
  );
}
