import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Store, AlertTriangle, Search, Plus, Pencil, Tag, Archive, ArchiveRestore } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated, Region, Shop } from "../lib/types";
import { formatMoney } from "../lib/utils";

interface DriverOption {
  id: number;
  display_name: string;
  role: string;
}

export function ShopsPage() {
  const [search, setSearch] = useState("");
  const [onlyOverLimit, setOnlyOverLimit] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Shop | null>(null);

  const { data, isLoading } = useQuery<Paginated<Shop>>({
    queryKey: ["shops", { search, over_limit: onlyOverLimit }],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("archived", "false");
      if (search) params.set("search", search);
      if (onlyOverLimit) params.set("over_limit", "1");
      return (await api.get<Paginated<Shop>>(`/shops/?${params}`)).data;
    },
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Do'konlar</h1>
          <p className="text-muted-foreground text-sm">
            {data?.count ?? 0} ta do'kon ro'yxati
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi do'kon
        </button>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            className="w-full h-10 pl-9 pr-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-bakery-400"
            placeholder="Qidirish (nomi, telefon)…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyOverLimit}
            onChange={(e) => setOnlyOverLimit(e.target.checked)}
            className="rounded"
          />
          Faqat limitdan oshgan
        </label>
      </div>

      {/* Desktop table */}
      <div className="rounded-xl border bg-card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Nomi</th>
              <th className="text-left px-4 py-3 font-medium">Hudud</th>
              <th className="text-right px-4 py-3 font-medium">Qarz (UZS)</th>
              <th className="text-right px-4 py-3 font-medium">Qarz (USD)</th>
              <th className="text-right px-4 py-3 font-medium">Limit (UZS)</th>
              <th className="text-left px-4 py-3 font-medium">Haydovchi</th>
              <th className="text-right px-4 py-3 font-medium w-24"></th>
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
            {data?.results.map((s) => (
              <tr key={s.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link
                    to={`/shops/${s.id}`}
                    className="font-medium hover:text-bakery-600 flex items-center gap-2"
                  >
                    <Store className="size-4 text-muted-foreground" />
                    {s.name}
                    {(s.limit_exceeded_uzs || s.limit_exceeded_usd) && (
                      <AlertTriangle className="size-4 text-destructive" />
                    )}
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{s.region_name}</td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${
                    s.limit_exceeded_uzs ? "text-destructive font-medium" : ""
                  }`}
                >
                  {formatMoney(s.loan_balance_uzs, "UZS")}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${
                    s.limit_exceeded_usd ? "text-destructive font-medium" : ""
                  }`}
                >
                  {parseFloat(s.loan_balance_usd) > 0
                    ? formatMoney(s.loan_balance_usd, "USD")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {parseFloat(s.loan_limit_uzs) > 0
                    ? formatMoney(s.loan_limit_uzs, "UZS")
                    : "—"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {s.assigned_driver_name || "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setEditing(s)}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <Pencil className="size-3.5" /> Tahrir
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && data?.results.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                  Do'konlar topilmadi
                </td>
              </tr>
            )}
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
        {data?.results.map((s) => (
          <div
            key={s.id}
            className="rounded-xl border bg-card p-3 flex items-start gap-3"
          >
            <Link to={`/shops/${s.id}`} className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2 font-medium">
                <Store className="size-4 text-muted-foreground shrink-0" />
                <span className="truncate">{s.name}</span>
                {(s.limit_exceeded_uzs || s.limit_exceeded_usd) && (
                  <AlertTriangle className="size-4 text-destructive shrink-0" />
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {s.region_name}
                {s.assigned_driver_name ? ` · ${s.assigned_driver_name}` : ""}
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs tabular-nums pt-0.5">
                <span
                  className={
                    s.limit_exceeded_uzs
                      ? "text-destructive font-medium"
                      : "text-muted-foreground"
                  }
                >
                  {formatMoney(s.loan_balance_uzs, "UZS")}
                </span>
                {parseFloat(s.loan_balance_usd) > 0 && (
                  <span
                    className={
                      s.limit_exceeded_usd
                        ? "text-destructive font-medium"
                        : "text-muted-foreground"
                    }
                  >
                    {formatMoney(s.loan_balance_usd, "USD")}
                  </span>
                )}
              </div>
            </Link>
            <button
              onClick={() => setEditing(s)}
              className="shrink-0 inline-flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-muted-foreground hover:text-foreground"
            >
              <Pencil className="size-3.5" />
            </button>
          </div>
        ))}
        {!isLoading && data?.results.length === 0 && (
          <div className="rounded-xl border bg-card p-10 text-center text-muted-foreground text-sm">
            Do'konlar topilmadi
          </div>
        )}
      </div>
      {creating && <ShopModal onClose={() => setCreating(false)} />}
      {editing && <ShopModal shop={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ShopModal({ shop, onClose }: { shop?: Shop; onClose: () => void }) {
  const qc = useQueryClient();
  const isEdit = !!shop;
  const [name, setName] = useState(shop?.name ?? "");
  const [ownerName, setOwnerName] = useState(shop?.owner_name ?? "");
  const [phone, setPhone] = useState(shop?.phone ?? "");
  const [address, setAddress] = useState(shop?.address ?? "");
  const [region, setRegion] = useState<number | "">(shop?.region ?? "");
  const [driver, setDriver] = useState<number | "">(shop?.assigned_driver ?? "");
  const [loanLimitUzs, setLoanLimitUzs] = useState(shop?.loan_limit_uzs ?? "0");
  const [loanLimitUsd, setLoanLimitUsd] = useState(shop?.loan_limit_usd ?? "0");

  const { data: regions } = useQuery<Paginated<Region>>({
    queryKey: ["regions"],
    queryFn: async () => (await api.get<Paginated<Region>>("/regions/")).data,
  });

  const { data: drivers } = useQuery<Paginated<DriverOption>>({
    queryKey: ["users", "drivers"],
    queryFn: async () =>
      (await api.get<Paginated<DriverOption>>("/users/?role=driver&archived=false")).data,
  });

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        name,
        owner_name: ownerName,
        phone,
        address,
        region: region || null,
        assigned_driver: driver || null,
        loan_limit_uzs: loanLimitUzs || "0",
        loan_limit_usd: loanLimitUsd || "0",
      };
      if (isEdit) return api.patch(`/shops/${shop!.id}/`, payload);
      return api.post("/shops/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shops"] });
      onClose();
    },
  });

  const [archiveConfirm, setArchiveConfirm] = useState(false);
  const archive = useMutation({
    mutationFn: () =>
      api.patch(`/shops/${shop!.id}/`, { is_archived: !shop!.is_archived }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shops"] });
      onClose();
    },
  });

  const canSave = name.trim().length > 0 && region !== "";

  return (
    <div className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">
          {isEdit ? "Do'konni tahrirlash" : "Yangi do'kon"}
        </h2>
        <div className="space-y-3">
          <Field label="Nomi">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Masalan: Alfajr"
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Egasi">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
              />
            </Field>
            <Field label="Telefon">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+998 90 123 45 67"
              />
            </Field>
          </div>
          <Field label="Manzil">
            <input
              className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Hudud">
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="">Tanlang…</option>
                {regions?.results.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Haydovchi">
              <select
                value={driver}
                onChange={(e) => setDriver(e.target.value ? Number(e.target.value) : "")}
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm"
              >
                <option value="">— Biriktirilmagan —</option>
                {drivers?.results.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.display_name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Qarz limiti (UZS)">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm tabular-nums"
                value={loanLimitUzs}
                onChange={(e) => setLoanLimitUzs(e.target.value)}
                inputMode="decimal"
              />
            </Field>
            <Field label="Qarz limiti (USD)">
              <input
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm tabular-nums"
                value={loanLimitUsd}
                onChange={(e) => setLoanLimitUsd(e.target.value)}
                inputMode="decimal"
              />
            </Field>
          </div>
        </div>
        {save.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            Saqlashda xatolik.
          </div>
        )}
        {isEdit && shop && (
          <div className="mt-4 pt-3 border-t space-y-2">
            <Link
              to={`/shops/${shop.id}`}
              onClick={onClose}
              className="inline-flex items-center gap-1.5 text-sm text-bakery-600 hover:underline"
            >
              <Tag className="size-4" /> Mahsulot narxlarini o'rnatish
            </Link>
            <p className="text-xs text-muted-foreground">
              Do'kon sahifasida har bir mahsulot uchun maxsus narx belgilash mumkin.
            </p>
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-between gap-2">
          {isEdit && shop && (
            <div className="flex items-center gap-2">
              {!archiveConfirm ? (
                <button
                  type="button"
                  onClick={() => setArchiveConfirm(true)}
                  className="inline-flex items-center gap-1.5 h-10 px-3 rounded-lg border border-amber-300 text-amber-700 text-sm hover:bg-amber-50"
                >
                  {shop.is_archived ? (
                    <><ArchiveRestore className="size-4" /> Arxivdan chiqarish</>
                  ) : (
                    <><Archive className="size-4" /> Arxivlash</>
                  )}
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-amber-700">Ishonchingiz komilmi?</span>
                  <button
                    onClick={() => archive.mutate()}
                    disabled={archive.isPending}
                    className="h-8 px-3 rounded-lg bg-amber-600 text-white text-xs hover:bg-amber-700 disabled:opacity-50"
                  >
                    {archive.isPending ? "…" : "Ha"}
                  </button>
                  <button
                    onClick={() => setArchiveConfirm(false)}
                    className="h-8 px-3 rounded-lg border text-xs hover:bg-muted"
                  >
                    Bekor
                  </button>
                </div>
              )}
            </div>
          )}
          <div className="flex gap-2 sm:ml-auto">
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
