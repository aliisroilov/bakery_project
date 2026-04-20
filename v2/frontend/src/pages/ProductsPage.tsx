import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Wheat, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated, Product } from "../lib/types";
import { formatMoney } from "../lib/utils";

interface Ingredient {
  id: number;
  name: string;
  unit_short: string;
}

interface RecipeLine {
  key: string;
  ingredient: number | "";
  amount_per_meshok: string;
}

export function ProductsPage() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Paginated<Product>>({
    queryKey: ["products"],
    queryFn: async () => (await api.get<Paginated<Product>>("/products/")).data,
  });

  const recalc = useMutation({
    mutationFn: () => api.post("/products/recalc-costs/"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["products"] }),
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Mahsulotlar</h1>
          <p className="text-muted-foreground text-sm">
            {data?.count ?? 0} ta mahsulot · tan narx retsept × xomashyo narxidan hisoblanadi
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => recalc.mutate()}
            disabled={recalc.isPending}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border text-sm hover:bg-muted disabled:opacity-50"
            title="Tan narxni qayta hisoblash"
          >
            <RefreshCw className={`size-4 ${recalc.isPending ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Tan narxni yangilash</span>
            <span className="sm:hidden">Yangilash</span>
          </button>
          <button
            onClick={() => setOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm"
          >
            <Plus className="size-4" /> <span className="hidden sm:inline">Yangi mahsulot</span>
            <span className="sm:hidden">Yangi</span>
          </button>
        </div>
      </div>

      {/* Desktop table */}
      <div className="rounded-xl border bg-card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Nomi</th>
              <th className="text-right px-4 py-3 font-medium">Narx (UZS)</th>
              <th className="text-right px-4 py-3 font-medium">Narx (USD)</th>
              <th className="text-right px-4 py-3 font-medium">Tan narx</th>
              <th className="text-right px-4 py-3 font-medium">Meshok</th>
              <th className="text-right px-4 py-3 font-medium">Ishlab chiqarish oyligi</th>
              <th className="text-right px-4 py-3 font-medium">Zaxira</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  Yuklanmoqda…
                </td>
              </tr>
            )}
            {data?.results.map((p) => (
              <tr key={p.id} className="hover:bg-muted/30">
                <td className="px-4 py-3 font-medium flex items-center gap-2">
                  <Wheat className="size-4 text-bakery-500" /> {p.name}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {parseFloat(p.default_price_uzs) > 0
                    ? formatMoney(p.default_price_uzs, "UZS")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {parseFloat(p.default_price_usd) > 0
                    ? formatMoney(p.default_price_usd, "USD")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(p.cost_price_uzs) > 0
                    ? formatMoney(p.cost_price_uzs, "UZS")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(p.meshok_size)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(p.production_salary_per_unit_uzs) > 0
                    ? formatMoney(p.production_salary_per_unit_uzs, "UZS")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {parseFloat(p.stock_quantity).toFixed(0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-2">
        {isLoading && (
          <div className="rounded-xl border bg-card p-6 text-center text-muted-foreground text-sm">
            Yuklanmoqda…
          </div>
        )}
        {data?.results.map((p) => (
          <div key={p.id} className="rounded-xl border bg-card p-3 space-y-2">
            <div className="flex items-center gap-2 font-medium">
              <Wheat className="size-4 text-bakery-500 shrink-0" />
              <span className="truncate">{p.name}</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 text-xs">
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">Narx:</span>
                <span className="tabular-nums">
                  {parseFloat(p.default_price_uzs) > 0
                    ? formatMoney(p.default_price_uzs, "UZS")
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">Tan narx:</span>
                <span className="tabular-nums">
                  {parseFloat(p.cost_price_uzs) > 0
                    ? formatMoney(p.cost_price_uzs, "UZS")
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">Meshok:</span>
                <span className="tabular-nums">{parseFloat(p.meshok_size)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-muted-foreground">Zaxira:</span>
                <span className="tabular-nums">
                  {parseFloat(p.stock_quantity).toFixed(0)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
      {open && <NewProductModal onClose={() => setOpen(false)} />}
    </div>
  );
}

function NewProductModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [defaultUzs, setDefaultUzs] = useState("0");
  const [meshokSize, setMeshokSize] = useState("160");
  const [salary, setSalary] = useState("0");
  const [lines, setLines] = useState<RecipeLine[]>([
    { key: crypto.randomUUID(), ingredient: "", amount_per_meshok: "" },
  ]);

  const { data: ingredients } = useQuery<Paginated<Ingredient>>({
    queryKey: ["inventory", "ingredients", "for-recipe"],
    queryFn: async () =>
      (await api.get<Paginated<Ingredient>>("/inventory/ingredients/?archived=false"))
        .data,
  });

  const validLines = lines.filter(
    (l) => l.ingredient && parseFloat(l.amount_per_meshok) > 0,
  );

  const create = useMutation({
    mutationFn: async () => {
      const res = await api.post<Product>("/products/", {
        name,
        default_price_uzs: defaultUzs,
        meshok_size: meshokSize,
        production_salary_per_unit_uzs: salary,
      });
      const productId = res.data.id;
      await Promise.all(
        validLines.map((l) =>
          api.post("/inventory/recipes/", {
            product: productId,
            ingredient: l.ingredient,
            amount_per_meshok: l.amount_per_meshok,
          }),
        ),
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      onClose();
    },
  });

  const addLine = () =>
    setLines((ls) => [
      ...ls,
      { key: crypto.randomUUID(), ingredient: "", amount_per_meshok: "" },
    ]);

  const removeLine = (key: string) =>
    setLines((ls) => (ls.length === 1 ? ls : ls.filter((l) => l.key !== key)));

  const updateLine = (key: string, patch: Partial<RecipeLine>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const canSave = name.trim().length > 0;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">Yangi mahsulot</h2>
        <div className="space-y-3">
          <Field label="Nomi">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Masalan: Sutli non"
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Narx (UZS)">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm tabular-nums"
                value={defaultUzs}
                onChange={(e) => setDefaultUzs(e.target.value)}
                inputMode="decimal"
              />
            </Field>
            <Field label="Meshok hajmi (dona)">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm tabular-nums"
                value={meshokSize}
                onChange={(e) => setMeshokSize(e.target.value)}
                inputMode="decimal"
              />
            </Field>
            <Field label="Nonvoyga 1 dona">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm tabular-nums"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                inputMode="decimal"
              />
            </Field>
          </div>

          <div className="rounded-xl border bg-muted/30 p-3 sm:p-4">
            <div className="flex items-start justify-between gap-2 mb-3">
              <div>
                <h3 className="font-semibold text-sm">Retsept (xomashyo)</h3>
                <p className="text-xs text-muted-foreground">
                  1 qop (meshok) uchun kerakli xomashyo — tan narx shu asosda hisoblanadi
                </p>
              </div>
              <button
                type="button"
                onClick={addLine}
                className="shrink-0 inline-flex items-center gap-1 h-8 px-3 rounded-lg border text-xs hover:bg-card"
              >
                <Plus className="size-3.5" /> Qo'shish
              </button>
            </div>
            <div className="space-y-2">
              {lines.map((l) => {
                const ing = ingredients?.results.find((i) => i.id === l.ingredient);
                return (
                  <div key={l.key} className="flex gap-2 items-center">
                    <select
                      value={l.ingredient}
                      onChange={(e) =>
                        updateLine(l.key, {
                          ingredient: e.target.value ? Number(e.target.value) : "",
                        })
                      }
                      className="flex-1 min-w-0 h-10 rounded-lg border bg-background px-3 text-sm"
                    >
                      <option value="">Xomashyo tanlang…</option>
                      {ingredients?.results.map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.name} ({i.unit_short})
                        </option>
                      ))}
                    </select>
                    <div className="relative w-28 sm:w-40 shrink-0">
                      <input
                        value={l.amount_per_meshok}
                        onChange={(e) =>
                          updateLine(l.key, { amount_per_meshok: e.target.value })
                        }
                        placeholder="0.00"
                        inputMode="decimal"
                        className="w-full h-10 rounded-lg border bg-background pl-3 pr-10 text-sm tabular-nums text-right"
                      />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                        {ing?.unit_short ?? ""}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeLine(l.key)}
                      disabled={lines.length === 1}
                      className="shrink-0 size-10 rounded-lg border grid place-items-center text-muted-foreground hover:text-destructive disabled:opacity-30"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                );
              })}
            </div>
            {validLines.length === 0 && (
              <p className="text-xs text-muted-foreground mt-3">
                Retsept bo'sh — mahsulot yaratilgandan keyin qo'shishingiz mumkin.
              </p>
            )}
          </div>
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
            {create.isPending ? "Saqlanmoqda…" : "Saqlash"}
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
