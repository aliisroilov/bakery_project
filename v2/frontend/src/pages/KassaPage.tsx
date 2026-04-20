import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Wallet,
  ArrowDownCircle,
  ArrowUpCircle,
  Plus,
  Truck,
  HandCoins,
} from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, Paginated, Shop } from "../lib/types";
import { formatMoney } from "../lib/utils";

interface KassaTransaction {
  id: number;
  account: number;
  account_name: string;
  kind: string;
  kind_display: string;
  currency: "UZS" | "USD";
  amount: string;
  note: string;
  occurred_at: string;
}

interface DriverHandoverRow {
  driver_id: number;
  driver_name: string;
  username: string;
  collected_uzs: string;
  collected_usd: string;
  handed_uzs: string;
  handed_usd: string;
  pending_uzs: string;
  pending_usd: string;
  payment_count: number;
  handover_count: number;
}

interface DriverHandoverReport {
  date_from: string;
  date_to: string;
  results: DriverHandoverRow[];
  count: number;
  totals: {
    collected_uzs: string;
    collected_usd: string;
    handed_uzs: string;
    handed_usd: string;
  };
}

interface DriverUser {
  id: number;
  display_name: string;
  username: string;
  role: string;
}

export function KassaPage() {
  const [kirimOpen, setKirimOpen] = useState(false);
  const [handoverOpen, setHandoverOpen] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [reportFrom, setReportFrom] = useState<string>(today);
  const [reportTo, setReportTo] = useState<string>(today);

  const { data: accounts } = useQuery<Paginated<KassaAccount>>({
    queryKey: ["kassa", "accounts"],
    queryFn: async () =>
      (await api.get<Paginated<KassaAccount>>("/finance/accounts/")).data,
  });

  const { data: txs } = useQuery<Paginated<KassaTransaction>>({
    queryKey: ["kassa", "transactions"],
    queryFn: async () =>
      (await api.get<Paginated<KassaTransaction>>("/finance/transactions/")).data,
    refetchInterval: 30_000,
  });

  const { data: handoverReport } = useQuery<DriverHandoverReport>({
    queryKey: ["kassa", "handover-report", reportFrom, reportTo],
    queryFn: async () =>
      (
        await api.get<DriverHandoverReport>(
          `/finance/driver-handover-report/?date_from=${reportFrom}&date_to=${reportTo}`,
        )
      ).data,
  });

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Kassa / Moliya</h1>
          <p className="text-muted-foreground text-sm">
            Seyf va Rizoxon kassalari · har ikki valyuta alohida
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setHandoverOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border text-sm hover:bg-muted"
          >
            <HandCoins className="size-4" /> <span className="hidden sm:inline">Pul topshirish</span><span className="sm:hidden">Topshirish</span>
          </button>
          <button
            onClick={() => setKirimOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm"
          >
            <Plus className="size-4" /> <span className="hidden sm:inline">Yangi kirim</span><span className="sm:hidden">Kirim</span>
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:gap-4 md:grid-cols-2">
        {accounts?.results.map((a) => (
          <div key={a.id} className="rounded-xl border bg-card p-4 sm:p-5">
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Wallet className="size-5 text-bakery-500" />
              <span className="font-semibold text-foreground">{a.name}</span>
            </div>
            <div className="mt-3 flex gap-6">
              <div>
                <div className="text-xs text-muted-foreground">UZS</div>
                <div className="text-xl font-semibold tabular-nums">
                  {formatMoney(a.balance_uzs, "UZS")}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">USD</div>
                <div className="text-xl font-semibold tabular-nums">
                  {formatMoney(a.balance_usd, "USD")}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b">
          <h2 className="font-semibold">Oxirgi harakatlar</h2>
          <p className="text-xs text-muted-foreground">
            Kirim, xarajat, oylik, pul topshirish
          </p>
        </div>

        {/* Desktop table */}
        <table className="w-full text-sm hidden md:table">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Sana</th>
              <th className="text-left px-4 py-3 font-medium">Kassa</th>
              <th className="text-left px-4 py-3 font-medium">Tur</th>
              <th className="text-left px-4 py-3 font-medium">Izoh</th>
              <th className="text-right px-4 py-3 font-medium">Miqdor</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {txs?.results.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                  Harakatlar hali yo'q
                </td>
              </tr>
            )}
            {txs?.results.map((tx) => {
              const inbound = parseFloat(tx.amount) >= 0;
              return (
                <tr key={tx.id}>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">
                    {tx.occurred_at.slice(0, 16).replace("T", " ")}
                  </td>
                  <td className="px-4 py-3">{tx.account_name}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1">
                      {inbound ? (
                        <ArrowDownCircle className="size-4 text-emerald-600" />
                      ) : (
                        <ArrowUpCircle className="size-4 text-destructive" />
                      )}
                      {tx.kind_display}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground truncate max-w-xs">
                    {tx.note}
                  </td>
                  <td
                    className={`px-4 py-3 text-right tabular-nums font-medium ${
                      inbound ? "text-emerald-700" : "text-destructive"
                    }`}
                  >
                    {inbound ? "+" : ""}
                    {formatMoney(tx.amount, tx.currency)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Mobile cards */}
        <div className="md:hidden divide-y">
          {txs?.results.length === 0 && (
            <div className="px-4 py-10 text-center text-muted-foreground text-sm">
              Harakatlar hali yo'q
            </div>
          )}
          {txs?.results.map((tx) => {
            const inbound = parseFloat(tx.amount) >= 0;
            return (
              <div key={tx.id} className="p-3 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex items-center gap-1.5">
                    {inbound ? (
                      <ArrowDownCircle className="size-4 text-emerald-600 shrink-0" />
                    ) : (
                      <ArrowUpCircle className="size-4 text-destructive shrink-0" />
                    )}
                    <span className="truncate text-sm">{tx.kind_display}</span>
                  </div>
                  <div
                    className={`text-sm font-semibold tabular-nums shrink-0 ${
                      inbound ? "text-emerald-700" : "text-destructive"
                    }`}
                  >
                    {inbound ? "+" : ""}
                    {formatMoney(tx.amount, tx.currency)}
                  </div>
                </div>
                <div className="text-xs text-muted-foreground flex justify-between gap-2">
                  <span className="truncate">{tx.account_name}</span>
                  <span className="tabular-nums shrink-0">
                    {tx.occurred_at.slice(0, 16).replace("T", " ")}
                  </span>
                </div>
                {tx.note && (
                  <div className="text-xs text-muted-foreground italic truncate">
                    {tx.note}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="font-semibold flex items-center gap-2">
              <Truck className="size-4 text-bakery-500" />
              <span className="hidden sm:inline">Haydovchilar pul topshirish hisoboti</span>
              <span className="sm:hidden">Haydovchilar topshirishi</span>
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Yig'ilgan vs topshirilgan · qoldiq haydovchi qo'lida
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <input
              type="date"
              value={reportFrom}
              onChange={(e) => setReportFrom(e.target.value)}
              className="h-9 flex-1 rounded-lg border bg-background px-2 sm:px-3 text-sm"
            />
            <span className="text-muted-foreground">—</span>
            <input
              type="date"
              value={reportTo}
              onChange={(e) => setReportTo(e.target.value)}
              className="h-9 flex-1 rounded-lg border bg-background px-2 sm:px-3 text-sm"
            />
          </div>
        </div>

        {/* Desktop table */}
        <table className="w-full text-sm hidden md:table">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Haydovchi</th>
              <th className="text-right px-4 py-3 font-medium">Yig'ildi</th>
              <th className="text-right px-4 py-3 font-medium">Topshirildi</th>
              <th className="text-right px-4 py-3 font-medium">Qoldiq</th>
              <th className="text-right px-4 py-3 font-medium">To'lovlar</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(handoverReport?.results.length ?? 0) === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-10 text-center text-muted-foreground"
                >
                  Haydovchilar topilmadi
                </td>
              </tr>
            )}
            {handoverReport?.results.map((r) => {
              const pendingUzs = parseFloat(r.pending_uzs);
              const pendingUsd = parseFloat(r.pending_usd);
              const hasPending = pendingUzs > 0 || pendingUsd > 0;
              return (
                <tr key={r.driver_id}>
                  <td className="px-4 py-3 font-medium">{r.driver_name}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatMoney(r.collected_uzs, "UZS")}
                    {parseFloat(r.collected_usd) > 0 && (
                      <div className="text-xs text-muted-foreground">
                        {formatMoney(r.collected_usd, "USD")}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-emerald-700">
                    {formatMoney(r.handed_uzs, "UZS")}
                    {parseFloat(r.handed_usd) > 0 && (
                      <div className="text-xs">
                        {formatMoney(r.handed_usd, "USD")}
                      </div>
                    )}
                  </td>
                  <td
                    className={`px-4 py-3 text-right tabular-nums font-semibold ${
                      hasPending ? "text-amber-700" : "text-muted-foreground"
                    }`}
                  >
                    {formatMoney(r.pending_uzs, "UZS")}
                    {pendingUsd !== 0 && (
                      <div className="text-xs">
                        {formatMoney(r.pending_usd, "USD")}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {r.payment_count} / {r.handover_count}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {handoverReport && handoverReport.results.length > 0 && (
            <tfoot className="border-t bg-muted/30 text-sm font-semibold">
              <tr>
                <td className="px-4 py-3">Jami</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {formatMoney(handoverReport.totals.collected_uzs, "UZS")}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {formatMoney(handoverReport.totals.handed_uzs, "UZS")}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {formatMoney(
                    String(
                      parseFloat(handoverReport.totals.collected_uzs) -
                        parseFloat(handoverReport.totals.handed_uzs),
                    ),
                    "UZS",
                  )}
                </td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>

        {/* Mobile cards for handover report */}
        <div className="md:hidden divide-y">
          {(handoverReport?.results.length ?? 0) === 0 && (
            <div className="px-4 py-10 text-center text-muted-foreground text-sm">
              Haydovchilar topilmadi
            </div>
          )}
          {handoverReport?.results.map((r) => {
            const pendingUzs = parseFloat(r.pending_uzs);
            const pendingUsd = parseFloat(r.pending_usd);
            const hasPending = pendingUzs > 0 || pendingUsd > 0;
            return (
              <div key={r.driver_id} className="p-3 space-y-2">
                <div className="font-medium">{r.driver_name}</div>
                <div className="grid grid-cols-3 gap-1.5 text-xs">
                  <div className="rounded-md bg-muted/40 p-2">
                    <div className="text-muted-foreground">Yig'ildi</div>
                    <div className="font-semibold tabular-nums mt-0.5">
                      {formatMoney(r.collected_uzs, "UZS")}
                    </div>
                  </div>
                  <div className="rounded-md bg-emerald-500/10 p-2 text-emerald-700">
                    <div className="opacity-80">Topshirildi</div>
                    <div className="font-semibold tabular-nums mt-0.5">
                      {formatMoney(r.handed_uzs, "UZS")}
                    </div>
                  </div>
                  <div
                    className={`rounded-md p-2 ${
                      hasPending ? "bg-amber-500/10 text-amber-700" : "bg-muted/40 text-muted-foreground"
                    }`}
                  >
                    <div className="opacity-80">Qoldiq</div>
                    <div className="font-semibold tabular-nums mt-0.5">
                      {formatMoney(r.pending_uzs, "UZS")}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-muted-foreground">
                  {r.payment_count} to'lov · {r.handover_count} topshiruv
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {kirimOpen && (
        <KirimModal
          accounts={accounts?.results ?? []}
          onClose={() => setKirimOpen(false)}
        />
      )}
      {handoverOpen && (
        <HandoverModal
          accounts={accounts?.results ?? []}
          onClose={() => setHandoverOpen(false)}
        />
      )}
    </div>
  );
}

function HandoverModal({
  accounts,
  onClose,
}: {
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [driverId, setDriverId] = useState<number | "">("");
  const [accountId, setAccountId] = useState<number | "">(accounts[0]?.id ?? "");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const { data: drivers } = useQuery<Paginated<DriverUser>>({
    queryKey: ["users", "drivers"],
    queryFn: async () =>
      (await api.get<Paginated<DriverUser>>("/users/?role=driver&archived=false"))
        .data,
  });

  // received_by = current user; backend needs the PK
  const { data: me } = useQuery<{ id: number }>({
    queryKey: ["me"],
    queryFn: async () => (await api.get<{ id: number }>("/users/me/")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/finance/handovers/", {
        driver: driverId,
        received_by: me?.id,
        to_account: accountId,
        currency,
        amount,
        occurred_at: new Date().toISOString(),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
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
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <HandCoins className="size-5 text-bakery-500" />
          Pul topshirish
        </h2>
        <div className="space-y-3">
          <Field label="Haydovchi">
            <select
              value={driverId}
              onChange={(e) =>
                setDriverId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">Tanlang…</option>
              {drivers?.results.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.display_name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Qaysi kassaga">
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Valyuta">
              <select
                value={currency}
                onChange={(e) =>
                  setCurrency(e.target.value as "UZS" | "USD")
                }
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
              </select>
            </Field>
          </div>
          <Field label="Summa">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputMode="decimal"
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
            disabled={!driverId || !amount || !me || create.isPending}
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

function KirimModal({
  accounts,
  onClose,
}: {
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [shopId, setShopId] = useState<number | "">("");
  const [accountId, setAccountId] = useState<number | "">(accounts[0]?.id ?? "");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState("");
  const [discount, setDiscount] = useState("0");
  const [orderDate, setOrderDate] = useState<string>(
    () => new Date().toISOString().slice(0, 10),
  );
  const [note, setNote] = useState("");

  const { data: shops } = useQuery<Paginated<Shop>>({
    queryKey: ["shops", { archived: false }],
    queryFn: async () =>
      (await api.get<Paginated<Shop>>("/shops/?archived=false")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/finance/payments/", {
        shop: shopId,
        account: accountId,
        currency,
        amount,
        discount,
        order_date: orderDate,
        note,
        received_at: new Date().toISOString(),
        payment_type: "collection",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      qc.invalidateQueries({ queryKey: ["shops"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="font-semibold text-lg mb-4">Yangi kirim</h2>
        <div className="space-y-3">
          <Field label="Do'kon">
            <select
              value={shopId}
              onChange={(e) => setShopId(e.target.value ? Number(e.target.value) : "")}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">Tanlang…</option>
              {shops?.results.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Kassa">
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                {accounts.map((a) => (
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
          <div className="grid grid-cols-2 gap-3">
            <Field label="Summa">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                inputMode="decimal"
              />
            </Field>
            <Field label="Skidka / bonus">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={discount}
                onChange={(e) => setDiscount(e.target.value)}
                inputMode="decimal"
              />
            </Field>
          </div>
          <Field label="Qaysi kungi buyurtma uchun (feature #1)">
            <input
              type="date"
              value={orderDate}
              onChange={(e) => setOrderDate(e.target.value)}
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
          <button onClick={onClose} className="h-10 px-4 rounded-lg border text-sm hover:bg-muted">
            Bekor qilish
          </button>
          <button
            disabled={!shopId || !amount || create.isPending}
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
