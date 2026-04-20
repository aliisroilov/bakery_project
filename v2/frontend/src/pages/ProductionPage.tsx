import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Factory, Plus } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated, Product } from "../lib/types";

interface Production {
  id: number;
  product: number;
  product_name: string;
  nonvoy: number;
  nonvoy_name: string;
  meshok_count: string;
  unit_count: string;
  occurred_at: string;
  note: string;
}

interface Stock {
  id: number;
  product: number;
  product_name: string;
  quantity: string;
  pinned: boolean;
}

interface Nonvoy {
  id: number;
  display_name: string;
  role: string;
}

export function ProductionPage() {
  const [open, setOpen] = useState(false);
  const { data: productions } = useQuery<Paginated<Production>>({
    queryKey: ["production"],
    queryFn: async () =>
      (await api.get<Paginated<Production>>("/production/")).data,
  });

  const { data: stocks } = useQuery<Paginated<Stock>>({
    queryKey: ["production", "stock"],
    queryFn: async () =>
      (await api.get<Paginated<Stock>>("/production/stock/")).data,
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Ishlab chiqarish</h1>
          <p className="text-muted-foreground text-sm">
            Nonvoylarning kunlik ishi va tayyor mahsulot zaxirasi
          </p>
        </div>
        <button
          onClick={() => setOpen(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> <span className="hidden sm:inline">Yangi ishlab chiqarish</span>
          <span className="sm:hidden">Yangi</span>
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border bg-card p-4 sm:p-5">
          <h2 className="font-semibold mb-3">Tayyor mahsulot zaxirasi</h2>
          <ul className="divide-y text-sm">
            {stocks?.results.length === 0 && (
              <li className="py-6 text-center text-muted-foreground">Zaxira yo'q</li>
            )}
            {stocks?.results.map((s) => (
              <li key={s.id} className="py-2 flex justify-between">
                <span>{s.product_name}</span>
                <span className="tabular-nums font-medium">
                  {parseFloat(s.quantity).toFixed(0)} dona
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border bg-card p-4 sm:p-5">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <Factory className="size-4 text-bakery-500" /> Oxirgi ishlab chiqarishlar
          </h2>
          <ul className="divide-y text-sm">
            {productions?.results.length === 0 && (
              <li className="py-6 text-center text-muted-foreground">
                Hali ishlab chiqarish yo'q
              </li>
            )}
            {productions?.results.slice(0, 10).map((p) => (
              <li key={p.id} className="py-2 flex items-center justify-between">
                <div>
                  <div className="font-medium">{p.product_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.occurred_at.slice(0, 10)} · {p.nonvoy_name}
                  </div>
                </div>
                <span className="tabular-nums font-medium">
                  {parseFloat(p.meshok_count).toFixed(1)} qop
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {open && <ProductionModal onClose={() => setOpen(false)} />}
    </div>
  );
}

function ProductionModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [productId, setProductId] = useState<number | "">("");
  const [nonvoyId, setNonvoyId] = useState<number | "">("");
  const [meshokCount, setMeshokCount] = useState("");
  const [occurredAt, setOccurredAt] = useState(
    () => new Date().toISOString().slice(0, 16),
  );
  const [note, setNote] = useState("");

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", { archived: false }],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  const { data: users } = useQuery<Paginated<Nonvoy>>({
    queryKey: ["users", { role: "nonvoy" }],
    queryFn: async () =>
      (await api.get<Paginated<Nonvoy>>("/users/?role=nonvoy&archived=false")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/production/", {
        product: productId,
        nonvoy: nonvoyId,
        meshok_count: meshokCount,
        occurred_at: new Date(occurredAt).toISOString(),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["production"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      onClose();
    },
  });

  const canSave = productId && nonvoyId && parseFloat(meshokCount) > 0;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">Yangi ishlab chiqarish</h2>
        <div className="space-y-3">
          <Field label="Mahsulot">
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : "")}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">Tanlang…</option>
              {products?.results.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.meshok_size} dona / qop)
                </option>
              ))}
            </select>
          </Field>
          <Field label="Nonvoy">
            <select
              value={nonvoyId}
              onChange={(e) => setNonvoyId(e.target.value ? Number(e.target.value) : "")}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">Tanlang…</option>
              {users?.results.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Qop soni">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={meshokCount}
                onChange={(e) => setMeshokCount(e.target.value)}
                inputMode="decimal"
                placeholder="0.0"
              />
            </Field>
            <Field label="Vaqt">
              <input
                type="datetime-local"
                value={occurredAt}
                onChange={(e) => setOccurredAt(e.target.value)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              />
            </Field>
          </div>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      {children}
    </div>
  );
}
