import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapPin,
  Plus,
  Pencil,
  Store,
  ChevronRight,
  Search,
} from "lucide-react";
import { api } from "../lib/api";
import type { Region, RegionTodayStats } from "../lib/types";

/**
 * Hududlar — per-region overview page.
 *
 * Mirrors V1's `districts_view`: a card grid where each card shows the number
 * of orders for a region *today*, split by status (pending / partial /
 * delivered). Clicking a card opens the detail page. Adds V2 extras:
 *   • Create / edit / archive regions directly from this page.
 *   • Client-side search.
 *   • Mobile-friendly layout.
 */
export function RegionsPage() {
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Region | null>(null);

  const { data, isLoading } = useQuery<RegionTodayStats[]>({
    queryKey: ["regions", "today_stats"],
    queryFn: async () =>
      (await api.get<RegionTodayStats[]>("/regions/today_stats/")).data,
  });

  const filtered = (data ?? []).filter((r) =>
    r.name.toLowerCase().includes(search.toLowerCase()),
  );

  const totalToday = filtered.reduce((sum, r) => sum + r.total, 0);

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Hududlar
          </h1>
          <p className="text-muted-foreground text-sm">
            {filtered.length} ta hudud · bugun {totalToday} ta buyurtma
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi hudud
        </button>
      </div>

      <div className="relative flex-1 sm:max-w-sm">
        <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          className="w-full h-10 pl-9 pr-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
          placeholder="Qidirish…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading && (
        <div className="rounded-xl border bg-card p-10 text-center text-muted-foreground text-sm">
          Yuklanmoqda…
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="rounded-xl border bg-card p-10 text-center text-muted-foreground text-sm">
          Hududlar topilmadi
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
        {filtered.map((r) => (
          <RegionCard
            key={r.id}
            stats={r}
            onEdit={() =>
              setEditing({
                id: r.id,
                name: r.name,
                note: r.note,
                shop_count: r.shop_count,
                is_archived: false,
                created_at: "",
              })
            }
          />
        ))}
      </div>

      {creating && <RegionModal onClose={() => setCreating(false)} />}
      {editing && (
        <RegionModal region={editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function RegionCard({
  stats,
  onEdit,
}: {
  stats: RegionTodayStats;
  onEdit: () => void;
}) {
  return (
    <div className="group relative rounded-xl border bg-card hover:shadow-md transition-shadow overflow-hidden">
      <Link
        to={`/regions/${stats.id}`}
        className="block p-4 sm:p-5 focus:outline-none focus:ring-2 focus:ring-bakery-400 rounded-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <div className="size-9 rounded-lg bg-bakery-500/10 text-bakery-600 grid place-items-center shrink-0">
              <MapPin className="size-4" />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold truncate">{stats.name}</h3>
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <Store className="size-3" />
                {stats.shop_count} ta do&apos;kon
              </div>
            </div>
          </div>
          <ChevronRight className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <StatCell
            label="Kutilmoqda"
            value={stats.pending}
            tone="amber"
          />
          <StatCell label="Qisman" value={stats.partial} tone="blue" />
          <StatCell
            label="Yetkazilgan"
            value={stats.delivered}
            tone="green"
          />
        </div>

        <div className="mt-3 pt-3 border-t flex items-center justify-between text-xs text-muted-foreground">
          <span>Bugungi buyurtmalar</span>
          <span className="font-semibold text-foreground tabular-nums">
            {stats.total}
          </span>
        </div>
      </Link>

      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onEdit();
        }}
        className="absolute top-3 right-3 p-1.5 rounded-md bg-background/80 border opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
        aria-label="Hududni tahrirlash"
        title="Tahrirlash"
      >
        <Pencil className="size-3.5" />
      </button>
    </div>
  );
}

function StatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "amber" | "blue" | "green";
}) {
  const toneMap = {
    amber: "bg-amber-500/10 text-amber-700",
    blue: "bg-blue-500/10 text-blue-700",
    green: "bg-emerald-500/10 text-emerald-700",
  };
  return (
    <div className={`rounded-lg py-2 ${toneMap[tone]}`}>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wide opacity-80">
        {label}
      </div>
    </div>
  );
}

function RegionModal({
  region,
  onClose,
}: {
  region?: Region;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const isEdit = !!region;
  const [name, setName] = useState(region?.name ?? "");
  const [note, setNote] = useState(region?.note ?? "");

  const save = useMutation({
    mutationFn: () => {
      const payload = { name, note };
      if (isEdit) return api.patch(`/regions/${region!.id}/`, payload);
      return api.post("/regions/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["regions"] });
      onClose();
    },
  });

  const archive = useMutation({
    mutationFn: () =>
      api.patch(`/regions/${region!.id}/`, { is_archived: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["regions"] });
      onClose();
    },
  });

  const canSave = name.trim().length > 0;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6"
      >
        <h2 className="font-semibold text-lg mb-4">
          {isEdit ? "Hududni tahrirlash" : "Yangi hudud"}
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">
              Nomi
            </label>
            <input
              autoFocus
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Masalan: Toshkent"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">
              Izoh
            </label>
            <textarea
              className="w-full min-h-[80px] px-3 py-2 rounded-lg border bg-background text-sm resize-y"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ixtiyoriy — hudud haqida qo'shimcha ma'lumot"
            />
          </div>
        </div>
        {(save.isError || archive.isError) && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            Saqlashda xatolik. Ushbu nom bilan hudud mavjud bo&apos;lishi
            mumkin.
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:items-center gap-2 sm:justify-end">
          {isEdit && (
            <button
              onClick={() => archive.mutate()}
              disabled={archive.isPending}
              className="h-10 px-4 rounded-lg border border-destructive/40 text-destructive text-sm hover:bg-destructive/10 sm:mr-auto"
            >
              Arxivlash
            </button>
          )}
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
