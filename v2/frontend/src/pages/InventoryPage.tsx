import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Archive, ArchiveRestore, ClipboardList, History, Plus, Settings2, Wheat } from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, Paginated } from "../lib/types";
import { formatMoney, fmtDate, fmtDateTime, nowTashkentStr, tashkentToISO } from "../lib/utils";

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

interface InventoryRevision {
  id: number;
  ingredient: number;
  ingredient_name: string;
  ingredient_unit: string;
  old_quantity: string;
  new_quantity: string;
  diff: string;
  note: string;
  batch_id: string | null;
  user_name: string;
  created_at: string;
}

export function InventoryPage() {
  const [purchaseOpen, setPurchaseOpen] = useState(false);
  const [reviziyaOpen, setReviziyaOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [adjustIng, setAdjustIng] = useState<Ingredient | null>(null);
  const [showArchivedIng, setShowArchivedIng] = useState(false);

  const qc = useQueryClient();

  const { data: ingredients } = useQuery<Paginated<Ingredient>>({
    queryKey: ["inventory", "ingredients", showArchivedIng],
    queryFn: async () =>
      (
        await api.get<Paginated<Ingredient>>(
          `/inventory/ingredients/?archived=${showArchivedIng}`,
        )
      ).data,
  });

  const { data: revisions } = useQuery<Paginated<InventoryRevision>>({
    queryKey: ["inventory", "revisions"],
    queryFn: async () =>
      (await api.get<Paginated<InventoryRevision>>("/inventory/revisions/?page_size=200&ordering=-created_at")).data,
    enabled: showHistory,
  });

  const archiveIng = useMutation({
    mutationFn: (id: number) =>
      api.patch(`/inventory/ingredients/${id}/`, { is_archived: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inventory", "ingredients"] }),
  });

  const unarchiveIng = useMutation({
    mutationFn: (id: number) =>
      api.patch(`/inventory/ingredients/${id}/`, { is_archived: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inventory", "ingredients"] }),
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
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setShowHistory((v) => !v)}
            className={`inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg border text-sm w-full sm:w-auto ${showHistory ? "bg-muted" : "hover:bg-muted"}`}
          >
            <History className="size-4" /> Reviziya tarixi
          </button>
          <button
            onClick={() => setReviziyaOpen(true)}
            className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg border border-amber-400 text-amber-700 hover:bg-amber-50 text-sm w-full sm:w-auto"
          >
            <ClipboardList className="size-4" /> Reviziya
          </button>
          <button
            onClick={() => setPurchaseOpen(true)}
            className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
          >
            <Plus className="size-4" /> Yangi xarid
          </button>
        </div>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b flex items-center justify-between gap-2">
          <h2 className="font-semibold">Ingredientlar</h2>
          <button
            onClick={() => setShowArchivedIng((v) => !v)}
            className={`inline-flex items-center gap-1 h-8 px-3 rounded-lg border text-xs ${
              showArchivedIng
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            <Archive className="size-3.5" />
            {showArchivedIng ? "Arxivlangan" : "Arxiv"}
          </button>
        </div>

        {/* Desktop table */}
        <table className="w-full text-sm hidden md:table">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Nomi</th>
              <th className="text-right px-4 py-3 font-medium">Zaxira</th>
              <th className="text-right px-4 py-3 font-medium">Minimum</th>
              <th className="text-right px-4 py-3 font-medium">O'rta narx</th>
              <th className="text-right px-4 py-3 font-medium w-36"></th>
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
                <td className="px-4 py-3 text-right space-x-2">
                  {!i.is_archived && (
                    <button
                      onClick={() => setAdjustIng(i)}
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      title="Zaxirani tuzatish"
                    >
                      <Settings2 className="size-3.5" /> Tuzatish
                    </button>
                  )}
                  {i.is_archived ? (
                    <button
                      onClick={() => unarchiveIng.mutate(i.id)}
                      className="inline-flex items-center gap-1 text-xs text-emerald-600 hover:underline"
                    >
                      <ArchiveRestore className="size-3.5" /> Qaytarish
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        if (confirm(`"${i.name}" arxivga o'tkazilsinmi?`))
                          archiveIng.mutate(i.id);
                      }}
                      className="inline-flex items-center gap-1 text-xs text-destructive hover:underline"
                    >
                      <Archive className="size-3.5" /> Arxiv
                    </button>
                  )}
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
              <div className="shrink-0 flex items-center gap-1">
                {!i.is_archived && (
                  <button
                    onClick={() => setAdjustIng(i)}
                    className="inline-flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-muted-foreground hover:text-foreground"
                  >
                    <Settings2 className="size-3.5" />
                  </button>
                )}
                {i.is_archived ? (
                  <button
                    onClick={() => unarchiveIng.mutate(i.id)}
                    className="inline-flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-emerald-600"
                  >
                    <ArchiveRestore className="size-3.5" />
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      if (confirm(`"${i.name}" arxivga o'tkazilsinmi?`))
                        archiveIng.mutate(i.id);
                    }}
                    className="inline-flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-destructive"
                  >
                    <Archive className="size-3.5" />
                  </button>
                )}
              </div>
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
                  {fmtDate(p.occurred_at)}
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
                  {fmtDate(p.occurred_at)} · {p.account_name}
                </span>
                <span className="tabular-nums">
                  {parseFloat(p.quantity).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showHistory && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 sm:px-5 py-4 border-b">
            <h2 className="font-semibold flex items-center gap-2">
              <History className="size-4 text-amber-600" /> Reviziya tarixi
            </h2>
            <p className="text-xs text-muted-foreground">Barcha inventarizatsiya o'zgarishlari</p>
          </div>

          {/* Desktop */}
          <table className="w-full text-sm hidden md:table">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Sana</th>
                <th className="text-left px-4 py-3 font-medium">Ingredient</th>
                <th className="text-right px-4 py-3 font-medium">Eski</th>
                <th className="text-right px-4 py-3 font-medium">Yangi</th>
                <th className="text-right px-4 py-3 font-medium">Farq</th>
                <th className="text-left px-4 py-3 font-medium">Sabab</th>
                <th className="text-left px-4 py-3 font-medium">Kim</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(revisions?.results.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                    Reviziya tarixi yo'q
                  </td>
                </tr>
              )}
              {revisions?.results.map((r) => {
                const diff = parseFloat(r.diff);
                return (
                  <tr key={r.id}>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">{fmtDateTime(r.created_at)}</td>
                    <td className="px-4 py-3 font-medium">{r.ingredient_name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                      {parseFloat(r.old_quantity).toFixed(2)} {r.ingredient_unit}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium">
                      {parseFloat(r.new_quantity).toFixed(2)} {r.ingredient_unit}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums font-semibold ${diff > 0 ? "text-emerald-700" : diff < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      {diff > 0 ? "+" : ""}{diff.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{r.note || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{r.user_name || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Mobile */}
          <div className="md:hidden divide-y">
            {(revisions?.results.length ?? 0) === 0 && (
              <div className="px-4 py-10 text-center text-muted-foreground text-sm">Reviziya tarixi yo'q</div>
            )}
            {revisions?.results.map((r) => {
              const diff = parseFloat(r.diff);
              return (
                <div key={r.id} className="p-3 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-medium">{r.ingredient_name}</div>
                    <div className={`font-semibold tabular-nums text-sm ${diff > 0 ? "text-emerald-700" : diff < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      {diff > 0 ? "+" : ""}{diff.toFixed(2)} {r.ingredient_unit}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground flex justify-between gap-2">
                    <span>{fmtDateTime(r.created_at)} · {r.user_name}</span>
                    <span>{parseFloat(r.old_quantity).toFixed(2)} → {parseFloat(r.new_quantity).toFixed(2)}</span>
                  </div>
                  {r.note && <div className="text-xs text-muted-foreground italic">{r.note}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {purchaseOpen && (
        <PurchaseModal
          ingredients={ingredients?.results ?? []}
          onClose={() => setPurchaseOpen(false)}
        />
      )}
      {reviziyaOpen && (
        <ReviziyaModal
          ingredients={(ingredients?.results ?? []).filter((i) => !i.is_archived)}
          onClose={() => {
            setReviziyaOpen(false);
            qc.invalidateQueries({ queryKey: ["inventory"] });
          }}
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
  const [occurredAt, setOccurredAt] = useState(() => nowTashkentStr().slice(0, 10));
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
        occurred_at: tashkentToISO(occurredAt + "T00:00"),
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
              type="date"
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

function ReviziyaModal({
  ingredients,
  onClose,
}: {
  ingredients: Ingredient[];
  onClose: () => void;
}) {
  const [quantities, setQuantities] = useState<Record<number, string>>(
    () => Object.fromEntries(ingredients.map((i) => [i.id, parseFloat(i.quantity).toFixed(2)]))
  );
  const [sessionNote, setSessionNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const changedItems = ingredients.filter((i) => {
    const newVal = parseFloat(quantities[i.id] ?? "");
    return !isNaN(newVal) && Math.abs(newVal - parseFloat(i.quantity)) > 0.001;
  });

  async function handleSave() {
    if (changedItems.length === 0) {
      setError("Hech qanday o'zgarish yo'q.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const items = changedItems.map((i) => ({
        ingredient_id: i.id,
        new_quantity: parseFloat(quantities[i.id]).toFixed(4),
        note: sessionNote,
      }));
      await api.post("/inventory/revisions/batch/", { items, note: sessionNote });
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: unknown }; message?: string };
      const d = err?.response?.data;
      setError(
        typeof d === "object" && d !== null
          ? Object.values(d as Record<string, unknown>).flat().join(" ")
          : typeof d === "string" ? d : err?.message ?? "Xatolik yuz berdi."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[92vh] overflow-y-auto"
      >
        <div className="flex items-center gap-2 mb-1">
          <ClipboardList className="size-5 text-amber-600" />
          <h2 className="font-semibold text-lg">Inventarizatsiya (Reviziya)</h2>
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          Har bir ingredientning haqiqiy zaxirasini kiriting. O'zgartirilmagan qatorlar saqlanmaydi.
        </p>

        <div className="rounded-xl border overflow-hidden mb-3">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Ingredient</th>
                <th className="text-right px-3 py-2 font-medium">Hozirgi</th>
                <th className="text-right px-3 py-2 font-medium w-36">Yangi zaxira</th>
                <th className="text-right px-3 py-2 font-medium w-20 hidden sm:table-cell">Farq</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {ingredients.map((i) => {
                const cur = parseFloat(i.quantity);
                const newVal = parseFloat(quantities[i.id] ?? "");
                const diff = isNaN(newVal) ? null : newVal - cur;
                const changed = diff !== null && Math.abs(diff) > 0.001;
                return (
                  <tr key={i.id} className={changed ? "bg-amber-500/5" : ""}>
                    <td className="px-3 py-2 font-medium">
                      {i.name}
                      <span className="text-xs text-muted-foreground ml-1">({i.unit_short})</span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                      {cur.toFixed(2)}
                    </td>
                    <td className="px-3 py-2">
                      <input
                        value={quantities[i.id] ?? ""}
                        onChange={(e) =>
                          setQuantities((prev) => ({ ...prev, [i.id]: e.target.value }))
                        }
                        inputMode="decimal"
                        className={`w-full h-8 rounded-md border px-2 text-sm tabular-nums text-right focus:ring-1 outline-none ${
                          changed
                            ? "border-amber-400 bg-amber-500/5 focus:ring-amber-400"
                            : "bg-background focus:ring-bakery-400"
                        }`}
                      />
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums text-xs font-semibold hidden sm:table-cell ${diff !== null && diff > 0 ? "text-emerald-700" : diff !== null && diff < 0 ? "text-destructive" : "text-muted-foreground"}`}>
                      {diff === null ? "—" : `${diff > 0 ? "+" : ""}${diff.toFixed(2)}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {changedItems.length > 0 && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 mb-3">
            {changedItems.length} ta ingredient o'zgartirildi
          </div>
        )}

        <Field label="Sabab / izoh (ixtiyoriy)">
          <input
            className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            value={sessionNote}
            onChange={(e) => setSessionNote(e.target.value)}
            placeholder="Masalan: oylik inventarizatsiya, yo'qotish..."
          />
        </Field>

        {error && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {error}
          </div>
        )}

        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button onClick={onClose} className="h-10 px-4 rounded-lg border text-sm hover:bg-muted">
            Bekor qilish
          </button>
          <button
            disabled={changedItems.length === 0 || saving}
            onClick={handleSave}
            className="h-10 px-4 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm disabled:opacity-50"
          >
            {saving ? "Saqlanmoqda…" : `Saqlash (${changedItems.length} ta o'zgarish)`}
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
