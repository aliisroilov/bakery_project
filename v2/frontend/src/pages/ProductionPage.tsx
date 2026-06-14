import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Factory, Plus, Pencil, Settings2, TrendingUp, Banknote } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "../lib/api";
import type { Paginated, Product } from "../lib/types";
import { C, TICK, mkTooltip } from "../lib/chart";
import { formatMoney, fmtDate, tashkentToISO } from "../lib/utils";

interface Production {
  id: number;
  product: number;
  product_name: string;
  nonvoy: number | null;
  nonvoy_name: string;
  group: number | null;
  group_name: string;
  actor_name: string;
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
  is_archived: boolean;
}

interface Nonvoy {
  id: number;
  display_name: string;
  role: string;
}

interface EmployeeGroup {
  id: number;
  name: string;
  members_display: { id: number; display_name: string }[];
  note: string;
}

interface SalaryRate {
  id: number;
  rate_type: string;
  rate_type_display: string;
  rate: string;
  currency: string;
}

const RATE_TYPE_SHORT: Record<string, string> = {
  per_meshok: "qop boshi",
  per_unit: "dona boshi",
  per_product: "mahsulot boshi",
  per_week: "haftalik",
  fixed_monthly: "oylik qat'iy",
};

/** Earned for one member given their rate and the qop/dona credited to them. */
function memberEarned(rate: SalaryRate | null | undefined, meshok: number, units: number): number {
  if (!rate) return 0;
  const r = parseFloat(rate.rate);
  if (rate.rate_type === "per_meshok") return meshok * r;
  if (rate.rate_type === "per_unit") return units * r;
  return 0;
}

/**
 * Total salary a production entry generates.
 * - Individual (nonvoy): the baker's full earning.
 * - Group: each member earns their OWN rate on the FULL qop/dona (no split),
 *   summed into the total labour cost of the batch — matching the backend.
 * Returns null when no rate info applies (e.g. all members on time-based rates).
 */
function entryEarned(
  p: Production,
  rateByUserId: Record<number, SalaryRate | null>,
  groupById: Record<number, EmployeeGroup>,
): { total: number; currency: "UZS" | "USD" } | null {
  const meshok = parseFloat(p.meshok_count || "0");
  const units = parseFloat(p.unit_count || "0");

  if (p.nonvoy) {
    const rate = rateByUserId[p.nonvoy];
    const v = memberEarned(rate, meshok, units);
    return v > 0 ? { total: v, currency: (rate?.currency as "UZS" | "USD") ?? "UZS" } : null;
  }

  if (p.group) {
    const g = groupById[p.group];
    const members = g?.members_display ?? [];
    if (members.length === 0) return null;
    let total = 0;
    let currency: "UZS" | "USD" = "UZS";
    for (const m of members) {
      const rate = rateByUserId[m.id];
      if (rate) currency = rate.currency as "UZS" | "USD";
      total += memberEarned(rate, meshok, units);
    }
    return total > 0 ? { total, currency } : null;
  }

  return null;
}

function ProductionTrendChart({ productions }: { productions: Production[] }) {
  const chartData = useMemo(() => {
    const byDate: Record<string, number> = {};
    for (const p of productions) {
      const date = fmtDate(p.occurred_at);
      byDate[date] = (byDate[date] ?? 0) + parseFloat(p.meshok_count || "0");
    }
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-14)
      .map(([date, meshok]) => ({
        date: date.slice(5),
        meshok: Math.round(meshok * 10) / 10,
      }));
  }, [productions]);

  if (chartData.length < 2) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Kunlik ishlab chiqarish (qop, so'nggi 14 kun)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="date" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} />
          <Tooltip content={mkTooltip((v) => `${v} qop`)} />
          <Bar dataKey="meshok" fill={C.bakery} radius={[3, 3, 0, 0]} name="Qop" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProductionPage() {
  const [open, setOpen] = useState(false);
  const [editProd, setEditProd] = useState<Production | null>(null);
  const [adjustStock, setAdjustStock] = useState<Stock | null>(null);

  const { data: productions } = useQuery<Paginated<Production>>({
    queryKey: ["production"],
    queryFn: async () =>
      (await api.get<Paginated<Production>>("/production/?page_size=200")).data,
  });

  const { data: salarySummary } = useQuery<{ results: { user_id: number; rate: SalaryRate | null }[] }>({
    queryKey: ["salary", "summary"],
    queryFn: async () =>
      (await api.get("/salary/employees/?role=nonvoy")).data,
  });

  const rateByUserId = useMemo(() => {
    const map: Record<number, SalaryRate | null> = {};
    for (const emp of salarySummary?.results ?? []) {
      map[emp.user_id] = emp.rate;
    }
    return map;
  }, [salarySummary]);

  const { data: groups } = useQuery<Paginated<EmployeeGroup>>({
    queryKey: ["users", "groups"],
    queryFn: async () =>
      (await api.get<Paginated<EmployeeGroup>>("/users/groups/")).data,
  });

  const groupById = useMemo(() => {
    const map: Record<number, EmployeeGroup> = {};
    for (const g of groups?.results ?? []) map[g.id] = g;
    return map;
  }, [groups]);

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

      <ProductionTrendChart productions={productions?.results ?? []} />

      <div className="grid gap-4 md:grid-cols-2">
        {/* Stock panel */}
        <div className="rounded-xl border bg-card p-4 sm:p-5">
          <h2 className="font-semibold mb-3">Tayyor mahsulot zaxirasi</h2>
          <ul className="divide-y text-sm">
            {stocks?.results.length === 0 && (
              <li className="py-6 text-center text-muted-foreground">Zaxira yo'q</li>
            )}
            {stocks?.results.map((s) => (
              <li key={s.id} className={`py-2 flex items-center justify-between gap-2 ${s.is_archived ? "opacity-50" : ""}`}>
                <span className="truncate">
                  {s.product_name}
                  {s.is_archived && <span className="ml-1 text-xs text-muted-foreground">(arxiv)</span>}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="tabular-nums font-medium">
                    {parseFloat(s.quantity).toFixed(0)} dona
                  </span>
                  <button
                    onClick={() => setAdjustStock(s)}
                    className="inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:text-foreground"
                    title="Zaxirani tuzatish"
                  >
                    <Settings2 className="size-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Production list panel */}
        <div className="rounded-xl border bg-card p-4 sm:p-5">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <Factory className="size-4 text-bakery-500" /> Barcha ishlab chiqarishlar
          </h2>
          <ul className="divide-y text-sm max-h-[60vh] overflow-y-auto">
            {productions?.results.length === 0 && (
              <li className="py-6 text-center text-muted-foreground">
                Hali ishlab chiqarish yo'q
              </li>
            )}
            {productions?.results.map((p) => {
              const earned = entryEarned(p, rateByUserId, groupById);
              const earnedForEntry = earned
                ? formatMoney(String(earned.total), earned.currency)
                : null;
              return (
                <li key={p.id} className="py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{p.product_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {fmtDate(p.occurred_at)} · {p.actor_name}
                    </div>
                    {earnedForEntry && (
                      <div className="text-xs text-emerald-600 flex items-center gap-0.5 mt-0.5">
                        <Banknote className="size-3" /> {earnedForEntry}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="text-right tabular-nums font-medium text-xs">
                      <div>{parseFloat(p.meshok_count).toFixed(1)} qop</div>
                      {parseFloat(p.unit_count) > 0 && (
                        <div className="text-muted-foreground">{parseFloat(p.unit_count).toFixed(0)} dona</div>
                      )}
                    </div>
                    <button
                      onClick={() => setEditProd(p)}
                      className="text-muted-foreground hover:text-foreground"
                      title="Tahrirlash"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {open && <ProductionModal rateByUserId={rateByUserId} onClose={() => setOpen(false)} />}
      {editProd && <ProductionModal prod={editProd} rateByUserId={rateByUserId} onClose={() => setEditProd(null)} />}
      {adjustStock && <AdjustStockModal stock={adjustStock} onClose={() => setAdjustStock(null)} />}
    </div>
  );
}

function ProductionModal({
  prod,
  rateByUserId,
  onClose,
}: {
  prod?: Production;
  rateByUserId: Record<number, SalaryRate | null>;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const isEdit = !!prod;

  const [productId, setProductId] = useState<number | "">(prod?.product ?? "");
  const [actorType, setActorType] = useState<"nonvoy" | "group">(
    prod?.group ? "group" : "nonvoy"
  );
  const [nonvoyId, setNonvoyId] = useState<number | "">(prod?.nonvoy ?? "");
  const [groupId, setGroupId] = useState<number | "">(prod?.group ?? "");
  const [meshokCount, setMeshokCount] = useState(prod?.meshok_count ?? "");
  const [unitCount, setUnitCount] = useState(prod?.unit_count ?? "");
  const [occurredAt, setOccurredAt] = useState(
    prod ? fmtDate(prod.occurred_at) : fmtDate(new Date().toISOString()),
  );
  const [note, setNote] = useState(prod?.note ?? "");

  const selectedRate = useMemo(() => {
    if (actorType !== "nonvoy" || !nonvoyId) return null;
    return rateByUserId[nonvoyId] ?? null;
  }, [actorType, nonvoyId, rateByUserId]);

  const previewSalary = useMemo(() => {
    if (!selectedRate || !meshokCount) return null;
    const meshok = parseFloat(meshokCount);
    const units = parseFloat(unitCount || "0");
    if (!isFinite(meshok) || meshok <= 0) return null;
    if (selectedRate.rate_type === "per_meshok") {
      return formatMoney(String(meshok * parseFloat(selectedRate.rate)), selectedRate.currency as "UZS" | "USD");
    }
    if (selectedRate.rate_type === "per_unit" && isFinite(units) && units > 0) {
      return formatMoney(String(units * parseFloat(selectedRate.rate)), selectedRate.currency as "UZS" | "USD");
    }
    return null;
  }, [selectedRate, meshokCount, unitCount]);

  const { data: products } = useQuery<Paginated<Product>>({
    queryKey: ["products", "active"],
    queryFn: async () =>
      (await api.get<Paginated<Product>>("/products/?archived=false")).data,
  });

  const { data: nonvoys } = useQuery<Paginated<Nonvoy>>({
    queryKey: ["users", "nonvoys"],
    queryFn: async () =>
      (await api.get<Paginated<Nonvoy>>("/users/?role=nonvoy&archived=false")).data,
  });

  const { data: groups } = useQuery<Paginated<EmployeeGroup>>({
    queryKey: ["users", "groups"],
    queryFn: async () =>
      (await api.get<Paginated<EmployeeGroup>>("/users/groups/")).data,
  });

  // Per-member group salary preview — each member earns their OWN rate on the
  // FULL qop/dona (no split), mirroring the backend.
  const groupPreview = useMemo(() => {
    if (actorType !== "group" || !groupId || !meshokCount) return null;
    const g = groups?.results.find((x) => x.id === groupId);
    const members = g?.members_display ?? [];
    if (members.length === 0) return null;
    const meshok = parseFloat(meshokCount);
    const units = parseFloat(unitCount || "0");
    if (!isFinite(meshok) || meshok <= 0) return null;
    let total = 0;
    let currency: "UZS" | "USD" = "UZS";
    const rows = members.map((m) => {
      const rate = rateByUserId[m.id];
      if (rate) currency = rate.currency as "UZS" | "USD";
      const amount = memberEarned(rate, meshok, units);
      total += amount;
      return { name: m.display_name, amount, hasRate: !!rate };
    });
    return { rows, total, currency, memberCount: members.length };
  }, [actorType, groupId, groups, meshokCount, unitCount, rateByUserId]);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        product: productId,
        meshok_count: meshokCount,
        unit_count: unitCount || "0",
        occurred_at: tashkentToISO(occurredAt + "T00:00"),
        note,
        nonvoy: actorType === "nonvoy" ? (nonvoyId || null) : null,
        group: actorType === "group" ? (groupId || null) : null,
      };
      if (isEdit) {
        return api.patch(`/production/${prod!.id}/`, payload);
      }
      return api.post("/production/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["production"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      qc.invalidateQueries({ queryKey: ["salary", "summary"] });
      onClose();
    },
  });

  // In edit mode, allow saving even if nonvoy/group is null (legacy V1 records)
  const actorOk = isEdit
    ? true
    : actorType === "nonvoy" ? !!nonvoyId : !!groupId;
  const canSave =
    productId &&
    parseFloat(String(meshokCount)) > 0 &&
    actorOk;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">
          {isEdit ? "Tahrirlash" : "Yangi ishlab chiqarish"}
        </h2>
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
                  {p.name}
                </option>
              ))}
            </select>
          </Field>

          <div>
            <label className="block text-xs text-muted-foreground mb-1">Kim ishlab chiqardi</label>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => setActorType("nonvoy")}
                className={`flex-1 h-9 rounded-lg border text-sm transition-colors ${
                  actorType === "nonvoy"
                    ? "bg-bakery-500 text-white border-bakery-500"
                    : "hover:bg-muted"
                }`}
              >
                Alohida nonvoy
              </button>
              <button
                type="button"
                onClick={() => setActorType("group")}
                className={`flex-1 h-9 rounded-lg border text-sm transition-colors ${
                  actorType === "group"
                    ? "bg-bakery-500 text-white border-bakery-500"
                    : "hover:bg-muted"
                }`}
              >
                Guruh
              </button>
            </div>
            {actorType === "nonvoy" ? (
              <select
                value={nonvoyId}
                onChange={(e) => setNonvoyId(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="">Nonvoy tanlang…</option>
                {nonvoys?.results.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.display_name}
                  </option>
                ))}
              </select>
            ) : (
              <select
                value={groupId}
                onChange={(e) => setGroupId(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="">Guruh tanlang…</option>
                {groups?.results.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                    {g.members_display.length > 0 &&
                      ` (${g.members_display.map((m) => m.display_name).join(", ")})`}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Qop soni">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={meshokCount}
                onChange={(e) => setMeshokCount(e.target.value)}
                inputMode="decimal"
                placeholder="0"
              />
            </Field>
            <Field label="Dona soni (qo'lda kiritiladi)">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={unitCount}
                onChange={(e) => setUnitCount(e.target.value)}
                inputMode="decimal"
                placeholder="0"
              />
            </Field>
          </div>
          <p className="text-xs text-muted-foreground -mt-1">
            Dona soni avtomatik hisoblanmaydi — har bir qopdan chiqish farq qilishi mumkin.
          </p>

          {previewSalary && (
            <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-3 py-2 text-sm flex items-center gap-2">
              <Banknote className="size-4 text-emerald-600 shrink-0" />
              <span className="text-emerald-700 dark:text-emerald-400">
                Maosh:{" "}
                <strong>{previewSalary}</strong>
                <span className="text-xs ml-1 opacity-70">
                  ({RATE_TYPE_SHORT[selectedRate!.rate_type] ?? selectedRate!.rate_type_display})
                </span>
              </span>
            </div>
          )}

          {groupPreview && (
            <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-3 py-2 text-sm">
              <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
                <Banknote className="size-4 text-emerald-600 shrink-0" />
                Guruh maoshi (jami): <strong>{formatMoney(String(groupPreview.total), groupPreview.currency)}</strong>
                <span className="text-xs opacity-70">(har a'zo o'z stavkasi bo'yicha to'liq qop uchun, {groupPreview.memberCount} a'zo)</span>
              </div>
              <ul className="mt-1.5 space-y-0.5 text-xs text-emerald-700/80 dark:text-emerald-400/80">
                {groupPreview.rows.map((r, i) => (
                  <li key={i} className="flex items-center justify-between">
                    <span>{r.name}{!r.hasRate && <span className="text-amber-500 ml-1">(stavka yo'q)</span>}</span>
                    <span className="tabular-nums">{formatMoney(String(r.amount), groupPreview.currency)}</span>
                  </li>
                ))}
              </ul>
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
        {save.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {(() => {
              const e = save.error as { response?: { data?: unknown }; message?: string };
              if (e?.response?.data) {
                const d = e.response.data;
                if (typeof d === "string") return d;
                if (typeof d === "object")
                  return Object.entries(d as Record<string, unknown>)
                    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
                    .join(" · ");
              }
              return e?.message ?? "Saqlashda xatolik yuz berdi.";
            })()}
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
            disabled={!canSave || save.isPending}
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

function AdjustStockModal({
  stock,
  onClose,
}: {
  stock: Stock;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [newQuantity, setNewQuantity] = useState(parseFloat(stock.quantity).toFixed(0));
  const [note, setNote] = useState("");

  const adjust = useMutation({
    mutationFn: () =>
      api.post(`/production/stock/${stock.id}/adjust/`, {
        new_quantity: newQuantity,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["production", "stock"] });
      qc.invalidateQueries({ queryKey: ["production"] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-card rounded-2xl shadow-xl border p-4 sm:p-6"
      >
        <h2 className="font-semibold text-lg mb-1">{stock.product_name} — zaxira tuzatish</h2>
        <p className="text-xs text-muted-foreground mb-4">
          Hozirgi: {parseFloat(stock.quantity).toFixed(0)} dona
        </p>
        <div className="space-y-3">
          <Field label="Yangi zaxira (dona)">
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
            {(() => {
              const e = adjust.error as { response?: { data?: unknown }; message?: string };
              const d = e?.response?.data;
              if (d && typeof d === "object")
                return Object.entries(d as Record<string, unknown>).map(([k, v]) => `${k}: ${v}`).join(" · ");
              return typeof d === "string" ? d : e?.message ?? "Xatolik yuz berdi.";
            })()}
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
            disabled={adjust.isPending}
            onClick={() => adjust.mutate()}
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
