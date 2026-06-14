import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Wallet,
  ArrowDownCircle,
  ArrowUpCircle,
  Plus,
  Truck,
  HandCoins,
  TrendingDown,
  TrendingUp,
  ArrowRight,
  ArrowLeftRight,
  Pencil,
  X,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { C, TICK, mkTooltip } from "../lib/chart";
import { api } from "../lib/api";
import type { KassaAccount, Paginated, Shop } from "../lib/types";
import { formatMoney, fmtDate, fmtDateTime, nowTashkentStr, tashkentToISO } from "../lib/utils";
import { useAuth } from "../lib/auth";

function getApiError(err: unknown): string {
  const e = err as { response?: { data?: unknown }; message?: string };
  const d = e?.response?.data;
  if (d && typeof d === "object")
    return Object.entries(d as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
      .join(" · ");
  return typeof d === "string" ? d : e?.message ?? "Saqlashda xatolik.";
}

interface ExpenseCategory {
  id: number;
  name: string;
  is_archived: boolean;
}

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
  reference_model: string;
  reference_id: number | null;
}

// All kinds backed by an editable source record.
// "adjustment" has no reference_id so it stays read-only.
const EDITABLE_KINDS = new Set([
  "payment_in", "loan_repayment",
  "general_expense",
  "salary", "advance", "bonus",
  "inventory_purchase",
  "cash_handover",
  "transfer",
]);

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

function DriverHandoverChart({ data }: { data: DriverHandoverRow[] }) {
  const chartData = useMemo(
    () =>
      data
        .filter((r) => parseFloat(r.collected_uzs) > 0)
        .map((r) => ({
          name: r.driver_name.split(" ")[0],
          "Yig'ildi": Math.round((parseFloat(r.collected_uzs) / 1_000_000) * 10) / 10,
          Topshirildi: Math.round((parseFloat(r.handed_uzs) / 1_000_000) * 10) / 10,
          Qoldiq: Math.round((parseFloat(r.pending_uzs) / 1_000_000) * 10) / 10,
        })),
    [data],
  );

  if (chartData.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="size-4 text-bakery-500" />
        <h3 className="font-semibold text-sm">Haydovchilar · yig'im vs topshiruv (mln UZS)</h3>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
          <XAxis dataKey="name" tick={TICK} axisLine={false} tickLine={false} />
          <YAxis tick={TICK} axisLine={false} tickLine={false} unit="M" />
          <Tooltip content={mkTooltip((v) => `${v} mln`)} />
          <Legend wrapperStyle={{ fontSize: 11, color: "hsl(var(--muted-foreground))" }} />
          <Bar dataKey="Yig'ildi" fill={C.blue} radius={[3, 3, 0, 0]} />
          <Bar dataKey="Topshirildi" fill={C.green} radius={[3, 3, 0, 0]} />
          <Bar dataKey="Qoldiq" fill={C.amber} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function KassaPage() {
  const user = useAuth((s) => s.user);
  if (user?.role === "driver") return <DriverKassaPage />;

  const [kirimOpen, setKirimOpen] = useState(false);
  const [chiqimOpen, setChiqimOpen] = useState(false);
  const [handoverOpen, setHandoverOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [editTx, setEditTx] = useState<KassaTransaction | null>(null);
  const today = nowTashkentStr().slice(0, 10);
  const [reportFrom, setReportFrom] = useState<string>(today);
  const [reportTo, setReportTo] = useState<string>(today);
  const [txFrom, setTxFrom] = useState<string>("");
  const [txTo, setTxTo] = useState<string>("");

  const { data: accounts } = useQuery<Paginated<KassaAccount>>({
    queryKey: ["kassa", "accounts"],
    queryFn: async () =>
      (await api.get<Paginated<KassaAccount>>("/finance/accounts/")).data,
  });

  const { data: txs } = useQuery<Paginated<KassaTransaction>>({
    queryKey: ["kassa", "transactions", txFrom, txTo],
    queryFn: async () => {
      const p = new URLSearchParams({ page_size: "1000", ordering: "-occurred_at" });
      if (txFrom) p.set("date_from", txFrom);
      if (txTo) p.set("date_to", txTo);
      return (await api.get<Paginated<KassaTransaction>>(`/finance/transactions/?${p}`)).data;
    },
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
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setHandoverOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border text-sm hover:bg-muted"
          >
            <HandCoins className="size-4" /> <span className="hidden sm:inline">Pul topshirish</span><span className="sm:hidden">Topshirish</span>
          </button>
          <button
            onClick={() => setTransferOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border border-sky-400 text-sky-700 hover:bg-sky-50 text-sm"
          >
            <ArrowLeftRight className="size-4" /> <span className="hidden sm:inline">O'tkazma</span><span className="sm:hidden">O'tkazma</span>
          </button>
          <button
            onClick={() => setChiqimOpen(true)}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border border-destructive text-destructive hover:bg-destructive/10 text-sm"
          >
            <TrendingDown className="size-4" /> <span className="hidden sm:inline">Chiqim (xarajat)</span><span className="sm:hidden">Chiqim</span>
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

      <DriverHandoverChart data={handoverReport?.results ?? []} />

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
                <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
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
                  <td className={`px-4 py-3 text-right tabular-nums font-semibold ${hasPending ? "text-amber-700" : "text-muted-foreground"}`}>
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
                  {formatMoney(String(parseFloat(handoverReport.totals.collected_uzs) - parseFloat(handoverReport.totals.handed_uzs)), "UZS")}
                </td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>

        {/* Mobile cards */}
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
                    <div className="font-semibold tabular-nums mt-0.5">{formatMoney(r.collected_uzs, "UZS")}</div>
                  </div>
                  <div className="rounded-md bg-emerald-500/10 p-2 text-emerald-700">
                    <div className="opacity-80">Topshirildi</div>
                    <div className="font-semibold tabular-nums mt-0.5">{formatMoney(r.handed_uzs, "UZS")}</div>
                  </div>
                  <div className={`rounded-md p-2 ${hasPending ? "bg-amber-500/10 text-amber-700" : "bg-muted/40 text-muted-foreground"}`}>
                    <div className="opacity-80">Qoldiq</div>
                    <div className="font-semibold tabular-nums mt-0.5">{formatMoney(r.pending_uzs, "UZS")}</div>
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

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="font-semibold">Barcha harakatlar</h2>
            <p className="text-xs text-muted-foreground">
              Kirim, xarajat, oylik, pul topshirish · {txs?.count ?? 0} ta yozuv
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <input
              type="date"
              value={txFrom}
              onChange={(e) => setTxFrom(e.target.value)}
              className="h-9 rounded-lg border bg-background px-2 text-sm"
              placeholder="Dan"
            />
            <span className="text-muted-foreground">—</span>
            <input
              type="date"
              value={txTo}
              onChange={(e) => setTxTo(e.target.value)}
              className="h-9 rounded-lg border bg-background px-2 text-sm"
              placeholder="Gacha"
            />
            {(txFrom || txTo) && (
              <button
                onClick={() => { setTxFrom(""); setTxTo(""); }}
                className="h-9 px-3 rounded-lg border text-xs hover:bg-muted"
              >
                Tozalash
              </button>
            )}
          </div>
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
              <th className="w-8 px-2 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {txs?.results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                  Harakatlar hali yo'q
                </td>
              </tr>
            )}
            {txs?.results.map((tx) => {
              const inbound = parseFloat(tx.amount) >= 0;
              const canEdit = EDITABLE_KINDS.has(tx.kind) && !!tx.reference_id;
              return (
                <tr key={tx.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">
                    {fmtDateTime(tx.occurred_at)}
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
                  <td className="px-2 py-3 text-right">
                    {canEdit && (
                      <button
                        onClick={() => setEditTx(tx)}
                        className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
                        title="Tahrirlash"
                      >
                        <Pencil className="size-3.5" />
                      </button>
                    )}
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
            const canEdit = EDITABLE_KINDS.has(tx.kind) && !!tx.reference_id;
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
                  <div className="flex items-center gap-1.5 shrink-0">
                    <div
                      className={`text-sm font-semibold tabular-nums ${
                        inbound ? "text-emerald-700" : "text-destructive"
                      }`}
                    >
                      {inbound ? "+" : ""}
                      {formatMoney(tx.amount, tx.currency)}
                    </div>
                    {canEdit && (
                      <button
                        onClick={() => setEditTx(tx)}
                        className="p-1.5 rounded-md hover:bg-muted text-muted-foreground"
                        title="Tahrirlash"
                      >
                        <Pencil className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>
                <div className="text-xs text-muted-foreground flex justify-between gap-2">
                  <span className="truncate">{tx.account_name}</span>
                  <span className="tabular-nums shrink-0">
                    {fmtDateTime(tx.occurred_at)}
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
      {kirimOpen && (
        <KirimModal
          accounts={accounts?.results ?? []}
          onClose={() => setKirimOpen(false)}
        />
      )}
      {chiqimOpen && (
        <ChiqimModal
          accounts={accounts?.results ?? []}
          onClose={() => setChiqimOpen(false)}
        />
      )}
      {handoverOpen && (
        <HandoverModal
          accounts={accounts?.results ?? []}
          onClose={() => setHandoverOpen(false)}
        />
      )}
      {transferOpen && (
        <TransferModal
          accounts={accounts?.results ?? []}
          onClose={() => setTransferOpen(false)}
        />
      )}
      {editTx && (
        <EditTransactionModal
          tx={editTx}
          accounts={accounts?.results ?? []}
          onClose={() => setEditTx(null)}
        />
      )}
    </div>
  );
}

// ─── Driver-only Kassa view ───────────────────────────────────────────────────

interface HandoverRow {
  id: number;
  currency: "UZS" | "USD";
  amount: string;
  occurred_at: string;
  note: string;
  to_account_name?: string;
}

function DriverKassaPage() {
  const user = useAuth((s) => s.user);
  const today = nowTashkentStr().slice(0, 10);
  const [handoverOpen, setHandoverOpen] = useState(false);

  const { data: accounts } = useQuery<KassaAccount[]>({
    queryKey: ["kassa-accounts"],
    queryFn: async () => (await api.get<KassaAccount[]>("/finance/accounts/")).data,
  });

  const { data: myPayments, refetch: refetchPayments } = useQuery<Paginated<{ currency: string; amount: string }>>({
    queryKey: ["payments", "mine", today],
    queryFn: async () =>
      (await api.get(`/finance/payments/?collected_by=${user!.id}&date_from=${today}&date_to=${today}&page_size=500`)).data,
    enabled: !!user?.id,
    refetchInterval: 30_000,
  });

  const { data: myHandovers, refetch: refetchHandovers } = useQuery<Paginated<HandoverRow>>({
    queryKey: ["handovers", "mine-all", user?.id],
    queryFn: async () =>
      (await api.get<Paginated<HandoverRow>>(`/finance/handovers/?driver=${user!.id}&page_size=100`)).data,
    enabled: !!user?.id,
    refetchInterval: 30_000,
  });

  const { data: todayHandovers } = useQuery<Paginated<{ currency: string; amount: string }>>({
    queryKey: ["handovers", "mine-today", today],
    queryFn: async () =>
      (await api.get(`/finance/handovers/?driver=${user!.id}&date_from=${today}&date_to=${today}&page_size=500`)).data,
    enabled: !!user?.id,
    refetchInterval: 30_000,
  });

  const sum = (rows: Array<{ currency: string; amount: string }> | undefined, cur: string) =>
    (rows ?? []).filter((r) => r.currency === cur).reduce((s, r) => s + parseFloat(r.amount), 0);

  const colUzs = sum(myPayments?.results, "UZS");
  const colUsd = sum(myPayments?.results, "USD");
  const handUzs = sum(todayHandovers?.results, "UZS");
  const handUsd = sum(todayHandovers?.results, "USD");
  const pendUzs = colUzs - handUzs;
  const pendUsd = colUsd - handUsd;
  const hasPending = pendUzs > 0 || pendUsd > 0;

  const accountsList = Array.isArray(accounts)
    ? accounts
    : (accounts as unknown as { results: KassaAccount[] })?.results ?? [];

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <HandCoins className="size-5 text-bakery-500" />
            Mening Kassa
          </h1>
          <p className="text-muted-foreground text-sm">Bugungi yig'im va topshiruv holati.</p>
        </div>
        <button
          onClick={() => setHandoverOpen(true)}
          className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm"
        >
          <HandCoins className="size-4" /> Pul topshirish
        </button>
      </div>

      {/* Cash summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border bg-card p-3 sm:p-4">
          <div className="text-xs text-muted-foreground mb-1">Yig'ildi (bugun)</div>
          <div className="font-semibold tabular-nums">{formatMoney(String(colUzs), "UZS")}</div>
          {colUsd > 0 && (
            <div className="text-xs text-muted-foreground tabular-nums">{formatMoney(String(colUsd), "USD")}</div>
          )}
        </div>
        <div className="rounded-xl border bg-emerald-500/10 p-3 sm:p-4 text-emerald-700">
          <div className="text-xs opacity-80 mb-1">Topshirildi (bugun)</div>
          <div className="font-semibold tabular-nums">{formatMoney(String(handUzs), "UZS")}</div>
          {handUsd > 0 && (
            <div className="text-xs opacity-70 tabular-nums">{formatMoney(String(handUsd), "USD")}</div>
          )}
        </div>
        <div className={`rounded-xl border p-3 sm:p-4 ${hasPending ? "bg-amber-500/10 border-amber-200 text-amber-700" : "bg-card"}`}>
          <div className="text-xs opacity-80 mb-1">Qoldiq</div>
          <div className="font-semibold tabular-nums">{formatMoney(String(pendUzs), "UZS")}</div>
          {pendUsd !== 0 && (
            <div className="text-xs opacity-70 tabular-nums">{formatMoney(String(pendUsd), "USD")}</div>
          )}
        </div>
      </div>

      {hasPending && (
        <button
          onClick={() => setHandoverOpen(true)}
          className="w-full flex items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 hover:bg-amber-500/20 transition-colors"
        >
          <span className="flex items-center gap-2">
            <Truck className="size-4" />
            {formatMoney(String(pendUzs), "UZS")} qoldiq bor — hozir topshiring
          </span>
          <ArrowRight className="size-4 shrink-0" />
        </button>
      )}

      {/* Handover history */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b">
          <h2 className="font-semibold">Mening topshiruvlarim</h2>
          <p className="text-xs text-muted-foreground">Barcha pul topshiruv tarixi</p>
        </div>
        <div className="divide-y">
          {(myHandovers?.results.length ?? 0) === 0 && (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">
              Hali topshiruv yo'q
            </div>
          )}
          {myHandovers?.results.map((h) => (
            <div key={h.id} className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3">
              <div className="min-w-0">
                <div className="text-sm font-medium tabular-nums text-emerald-700">
                  +{formatMoney(h.amount, h.currency)}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {fmtDateTime(h.occurred_at)}
                  {h.note ? ` · ${h.note}` : ""}
                </div>
              </div>
              <HandCoins className="size-4 text-emerald-600 shrink-0" />
            </div>
          ))}
        </div>
      </div>

      {handoverOpen && (
        <DriverSelfHandoverModal
          driverId={user!.id}
          accounts={accountsList}
          onClose={() => {
            setHandoverOpen(false);
            void refetchPayments();
            void refetchHandovers();
          }}
        />
      )}
    </div>
  );
}

function DriverSelfHandoverModal({
  driverId,
  accounts,
  onClose,
}: {
  driverId: number;
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [accountId, setAccountId] = useState<number | "">(accounts[0]?.id ?? "");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post("/finance/handovers/", {
        driver: driverId,
        to_account: accountId,
        currency,
        amount,
        occurred_at: new Date().toISOString(),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["handovers"] });
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["kassa"] });
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
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6"
      >
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <HandCoins className="size-5 text-bakery-500" /> Pul topshirish
        </h2>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Qaysi kassaga">
              <select
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
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
          <Field label="Summa">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputMode="decimal"
              placeholder="0"
            />
          </Field>
          <Field label="Izoh (ixtiyoriy)">
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[60px]"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
        </div>
        {create.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {getApiError(create.error)}
          </div>
        )}
        <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button onClick={onClose} className="h-10 px-4 rounded-lg border text-sm hover:bg-muted">
            Bekor qilish
          </button>
          <button
            disabled={!amount || !accountId || create.isPending}
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

// ─────────────────────────────────────────────────────────────────────────────

function TransferModal({
  accounts,
  onClose,
}: {
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const defaultFrom = accounts[0]?.id ?? "";
  const defaultTo = accounts[1]?.id ?? accounts[0]?.id ?? "";

  const [fromId, setFromId] = useState<number | "">(defaultFrom);
  const [toId, setToId] = useState<number | "">(defaultTo);
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const fromAccount = accounts.find((a) => a.id === fromId);
  const toAccount = accounts.find((a) => a.id === toId);

  const fromBalance = fromAccount
    ? currency === "UZS"
      ? parseFloat(fromAccount.balance_uzs)
      : parseFloat(fromAccount.balance_usd)
    : null;

  const amountNum = parseFloat(amount) || 0;
  const insufficient = fromBalance !== null && amountNum > fromBalance;
  const sameAccount = fromId !== "" && fromId === toId;

  const swap = () => {
    setFromId(toId);
    setToId(fromId);
  };

  const create = useMutation({
    mutationFn: () =>
      api.post("/finance/transfers/", {
        from_account: fromId,
        to_account: toId,
        currency,
        amount,
        occurred_at: new Date().toISOString(),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      onClose();
    },
  });

  const canSave =
    !!fromId && !!toId && !sameAccount && amountNum > 0 && !insufficient && !create.isPending;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6"
      >
        <h2 className="font-semibold text-lg mb-1 flex items-center gap-2">
          <ArrowLeftRight className="size-5 text-sky-600" />
          Kassalar o'rtasida o'tkazma
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          Bir kassadan ikkinchisiga pul o'tkazish
        </p>

        {/* From / swap / To row */}
        <div className="flex items-end gap-2 mb-3">
          <div className="flex-1">
            <label className="block text-xs text-muted-foreground mb-1">Kimdan</label>
            <select
              value={fromId}
              onChange={(e) => setFromId(Number(e.target.value))}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={swap}
            title="Almashtirish"
            className="h-10 w-10 shrink-0 flex items-center justify-center rounded-lg border hover:bg-muted transition-colors"
          >
            <ArrowLeftRight className="size-4 text-muted-foreground" />
          </button>
          <div className="flex-1">
            <label className="block text-xs text-muted-foreground mb-1">Kimga</label>
            <select
              value={toId}
              onChange={(e) => setToId(Number(e.target.value))}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
        </div>

        {sameAccount && (
          <p className="text-xs text-destructive mb-2">
            Kimdan va kimga bir xil bo'lishi mumkin emas.
          </p>
        )}

        {/* Balance preview */}
        {fromAccount && toAccount && !sameAccount && (
          <div className="rounded-xl bg-muted/40 px-4 py-3 mb-3 flex items-center justify-between text-sm">
            <div className="text-center">
              <div className="text-xs text-muted-foreground">{fromAccount.name}</div>
              <div className="font-semibold tabular-nums">
                {currency === "UZS"
                  ? formatMoney(fromAccount.balance_uzs, "UZS")
                  : formatMoney(fromAccount.balance_usd, "USD")}
              </div>
            </div>
            <ArrowRight className="size-4 text-muted-foreground" />
            <div className="text-center">
              <div className="text-xs text-muted-foreground">{toAccount.name}</div>
              <div className="font-semibold tabular-nums">
                {currency === "UZS"
                  ? formatMoney(toAccount.balance_uzs, "UZS")
                  : formatMoney(toAccount.balance_usd, "USD")}
              </div>
            </div>
          </div>
        )}

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
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
            <Field label="Summa">
              <input
                className={`w-full h-10 rounded-lg border px-3 text-sm tabular-nums ${
                  insufficient ? "border-destructive bg-destructive/5" : "bg-background"
                }`}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                inputMode="decimal"
                placeholder="0"
              />
            </Field>
          </div>
          {insufficient && (
            <p className="text-xs text-destructive -mt-1">
              {fromAccount?.name} kassasida yetarli mablag' yo'q
              ({currency === "UZS"
                ? formatMoney(fromAccount!.balance_uzs, "UZS")
                : formatMoney(fromAccount!.balance_usd, "USD")}).
            </p>
          )}
          <Field label="Izoh (ixtiyoriy)">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Masalan: oylik mablag' Seyfga"
            />
          </Field>
        </div>

        {create.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {getApiError(create.error)}
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
            disabled={!canSave}
            onClick={() => create.mutate()}
            className="h-10 px-4 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {create.isPending ? "O'tkazilmoqda…" : "O'tkazish"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ChiqimModal({
  accounts,
  onClose,
}: {
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [title, setTitle] = useState("");
  const [accountId, setAccountId] = useState<number | "">(accounts[0]?.id ?? "");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState("");
  const [occurredAt, setOccurredAt] = useState(() => nowTashkentStr().slice(0, 10));
  const [note, setNote] = useState("");

  const { data: categories } = useQuery<Paginated<ExpenseCategory>>({
    queryKey: ["finance", "expense-categories"],
    queryFn: async () =>
      (await api.get<Paginated<ExpenseCategory>>("/finance/expense-categories/")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/finance/expenses/", {
        category: categoryId || null,
        title: title || "Xarajat",
        account: accountId,
        currency,
        amount,
        occurred_at: tashkentToISO(occurredAt + "T00:00"),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      onClose();
    },
  });

  const canSave = !!accountId && parseFloat(amount) > 0;

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
          <TrendingDown className="size-5 text-destructive" />
          Chiqim / Xarajat
        </h2>
        <div className="space-y-3">
          <Field label="Sarlavha">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Masalan: Yoqilg'i, Kommunal, Maosh..."
            />
          </Field>
          <Field label="Kategoriya (ixtiyoriy)">
            <select
              value={categoryId}
              onChange={(e) =>
                setCategoryId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              <option value="">— Kategoriyasiz —</option>
              {categories?.results
                .filter((c) => !c.is_archived)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Qaysi kassadan">
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
          <Field label="Summa">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputMode="decimal"
              placeholder="0"
            />
          </Field>
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
            {getApiError(create.error)}
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
            className="h-10 px-4 rounded-lg bg-destructive hover:bg-destructive/90 text-white text-sm disabled:opacity-50"
          >
            {create.isPending ? "Saqlanmoqda…" : "Chiqim yozish"}
          </button>
        </div>
      </div>
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
            {getApiError(create.error)}
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
    () => nowTashkentStr().slice(0, 10),
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
        // Record the kirim on the chosen date (with the current wall-clock time
        // in Tashkent) instead of always using today.
        received_at: tashkentToISO(`${orderDate}T${nowTashkentStr().slice(11, 16)}`),
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
          <Field label="Sana (kirim shu kunga yoziladi)">
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
            {getApiError(create.error)}
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

// ─── Edit Transaction Modal ───────────────────────────────────────────────────

interface PaymentDetail {
  id: number; shop: number; shop_name: string;
  amount: string; discount: string; currency: "UZS" | "USD";
  account: number; note: string; received_at: string; payment_type: string;
}
interface ExpenseDetail {
  id: number; title: string; amount: string; currency: "UZS" | "USD";
  account: number; occurred_at: string; note: string; category: number | null;
}
interface SalaryPaymentDetail {
  id: number; user: number; user_display: string;
  kind: string; kind_display: string;
  amount: string; currency: "UZS" | "USD";
  account: number; occurred_at: string; note: string;
}
interface PurchaseDetail {
  id: number; ingredient: number; ingredient_name: string;
  quantity: string; total_price: string; currency: "UZS" | "USD";
  account: number; occurred_at: string; note: string;
}
interface HandoverDetail {
  id: number; driver: number; driver_name: string;
  to_account: number; amount: string; currency: "UZS" | "USD";
  occurred_at: string; note: string;
}
interface TransferDetail {
  id: number; from_account: number; from_account_name: string;
  to_account: number; to_account_name: string;
  amount: string; currency: "UZS" | "USD";
  occurred_at: string; note: string;
}

function EditTransactionModal({
  tx,
  accounts,
  onClose,
}: {
  tx: KassaTransaction;
  accounts: KassaAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const isPayment  = tx.kind === "payment_in" || tx.kind === "loan_repayment";
  const isExpense  = tx.kind === "general_expense";
  const isSalary   = tx.kind === "salary" || tx.kind === "advance" || tx.kind === "bonus";
  const isPurchase = tx.kind === "inventory_purchase";
  const isHandover = tx.kind === "cash_handover";
  const isTransfer = tx.kind === "transfer";

  // ── Fetch source record ──────────────────────────────────────────
  const { data: paymentData,  isLoading: l1 } = useQuery<PaymentDetail>({
    queryKey: ["finance", "payment", tx.reference_id],
    queryFn: async () => (await api.get<PaymentDetail>(`/finance/payments/${tx.reference_id}/`)).data,
    enabled: isPayment && !!tx.reference_id,
  });
  const { data: expenseData,  isLoading: l2 } = useQuery<ExpenseDetail>({
    queryKey: ["finance", "expense", tx.reference_id],
    queryFn: async () => (await api.get<ExpenseDetail>(`/finance/expenses/${tx.reference_id}/`)).data,
    enabled: isExpense && !!tx.reference_id,
  });
  const { data: salaryData,   isLoading: l3 } = useQuery<SalaryPaymentDetail>({
    queryKey: ["salary", "payment", tx.reference_id],
    queryFn: async () => (await api.get<SalaryPaymentDetail>(`/salary/payments/${tx.reference_id}/`)).data,
    enabled: isSalary && !!tx.reference_id,
  });
  const { data: purchaseData, isLoading: l4 } = useQuery<PurchaseDetail>({
    queryKey: ["inventory", "purchase", tx.reference_id],
    queryFn: async () => (await api.get<PurchaseDetail>(`/inventory/purchases/${tx.reference_id}/`)).data,
    enabled: isPurchase && !!tx.reference_id,
  });
  const { data: handoverData, isLoading: l5 } = useQuery<HandoverDetail>({
    queryKey: ["finance", "handover", tx.reference_id],
    queryFn: async () => (await api.get<HandoverDetail>(`/finance/handovers/${tx.reference_id}/`)).data,
    enabled: isHandover && !!tx.reference_id,
  });
  const { data: transferData, isLoading: l6 } = useQuery<TransferDetail>({
    queryKey: ["finance", "transfer", tx.reference_id],
    queryFn: async () => (await api.get<TransferDetail>(`/finance/transfers/${tx.reference_id}/`)).data,
    enabled: isTransfer && !!tx.reference_id,
  });

  const isLoading = l1 || l2 || l3 || l4 || l5 || l6;

  // ── Form state ───────────────────────────────────────────────────
  const [amount,      setAmount]      = useState("");
  const [note,        setNote]        = useState("");
  const [occurredAt,  setOccurredAt]  = useState("");
  const [accountId,   setAccountId]   = useState<number | "">("");
  const [fromAccount, setFromAccount] = useState<number | "">("");  // transfer only
  const [toAccount,   setToAccount]   = useState<number | "">("");  // transfer only
  const [title,       setTitle]       = useState("");               // expense only
  const [salaryKind,  setSalaryKind]  = useState("");               // salary payment only
  const [quantity,    setQuantity]    = useState("");               // purchase only

  // Populate from whichever source record loaded
  useEffect(() => {
    if (paymentData) {
      setAmount(paymentData.amount);
      setNote(paymentData.note ?? "");
      setOccurredAt(paymentData.received_at ? fmtDate(paymentData.received_at) : "");
      setAccountId(paymentData.account);
    }
  }, [paymentData]);

  useEffect(() => {
    if (expenseData) {
      setTitle(expenseData.title);
      setAmount(expenseData.amount);
      setNote(expenseData.note ?? "");
      setOccurredAt(expenseData.occurred_at ? fmtDate(expenseData.occurred_at) : "");
      setAccountId(expenseData.account);
    }
  }, [expenseData]);

  useEffect(() => {
    if (salaryData) {
      setSalaryKind(salaryData.kind);
      setAmount(salaryData.amount);
      setNote(salaryData.note ?? "");
      setOccurredAt(salaryData.occurred_at ? fmtDate(salaryData.occurred_at) : "");
      setAccountId(salaryData.account);
    }
  }, [salaryData]);

  useEffect(() => {
    if (purchaseData) {
      setQuantity(purchaseData.quantity);
      setAmount(purchaseData.total_price);
      setNote(purchaseData.note ?? "");
      setOccurredAt(purchaseData.occurred_at ? fmtDate(purchaseData.occurred_at) : "");
      setAccountId(purchaseData.account);
    }
  }, [purchaseData]);

  useEffect(() => {
    if (handoverData) {
      setAmount(handoverData.amount);
      setNote(handoverData.note ?? "");
      setOccurredAt(handoverData.occurred_at ? fmtDate(handoverData.occurred_at) : "");
      setAccountId(handoverData.to_account);
    }
  }, [handoverData]);

  useEffect(() => {
    if (transferData) {
      setAmount(transferData.amount);
      setNote(transferData.note ?? "");
      setOccurredAt(transferData.occurred_at ? fmtDate(transferData.occurred_at) : "");
      setFromAccount(transferData.from_account);
      setToAccount(transferData.to_account);
    }
  }, [transferData]);

  // ── Save mutation ────────────────────────────────────────────────
  const save = useMutation({
    mutationFn: () => {
      const dateIso = tashkentToISO(occurredAt + "T00:00");
      const id = tx.reference_id!;
      if (isPayment) {
        return api.patch(`/finance/payments/${id}/`, {
          amount, note, received_at: dateIso, account: accountId,
        });
      }
      if (isExpense) {
        return api.patch(`/finance/expenses/${id}/`, {
          title: title || "Xarajat", amount, note, occurred_at: dateIso, account: accountId,
        });
      }
      if (isSalary) {
        return api.patch(`/salary/payments/${id}/`, {
          kind: salaryKind, amount, note, occurred_at: dateIso, account: accountId,
        });
      }
      if (isPurchase) {
        return api.patch(`/inventory/purchases/${id}/`, {
          quantity, total_price: amount, note, occurred_at: dateIso, account: accountId,
        });
      }
      if (isHandover) {
        return api.patch(`/finance/handovers/${id}/`, {
          amount, note, occurred_at: dateIso, to_account: accountId,
        });
      }
      // transfer
      return api.patch(`/finance/transfers/${id}/`, {
        amount, note, occurred_at: dateIso,
        from_account: fromAccount, to_account: toAccount,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      qc.invalidateQueries({ queryKey: ["salary"] });
      qc.invalidateQueries({ queryKey: ["inventory"] });
      onClose();
    },
  });

  const canSave = !!occurredAt && parseFloat(amount || "0") > 0 && !save.isPending &&
    (isTransfer ? !!fromAccount && !!toAccount : !!accountId);

  // ── Info label shown at top of form ─────────────────────────────
  const infoLabel = isHandover
    ? `Haydovchi: ${handoverData?.driver_name ?? "…"}`
    : isPurchase
    ? `Xomashyo: ${purchaseData?.ingredient_name ?? "…"}`
    : isSalary
    ? salaryData?.user_display ?? "…"
    : tx.note;

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/40 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg flex items-center gap-2">
            <Pencil className="size-5 text-bakery-500" />
            Yozuvni tahrirlash
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="size-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-muted-foreground text-sm">Yuklanmoqda…</div>
        ) : (
          <div className="space-y-3">
            {/* Info banner */}
            <div className="rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium">{tx.kind_display}</span>
              {infoLabel ? <> · {infoLabel}</> : null}
            </div>

            {/* Expense: title */}
            {isExpense && (
              <Field label="Sarlavha">
                <input className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                  value={title} onChange={(e) => setTitle(e.target.value)}
                  placeholder="Xarajat sarlavhasi" />
              </Field>
            )}

            {/* Salary: kind */}
            {isSalary && (
              <Field label="To'lov turi">
                <select value={salaryKind} onChange={(e) => setSalaryKind(e.target.value)}
                  className="w-full h-10 rounded-lg border bg-background px-3 text-sm">
                  <option value="salary">Oylik</option>
                  <option value="advance">Avans</option>
                  <option value="bonus">Bonus</option>
                </select>
              </Field>
            )}

            {/* Purchase: quantity */}
            {isPurchase && (
              <Field label="Miqdor">
                <input className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                  value={quantity} onChange={(e) => setQuantity(e.target.value)}
                  inputMode="decimal" placeholder="0" />
              </Field>
            )}

            {/* Transfer: from / to accounts */}
            {isTransfer ? (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Kimdan">
                  <select value={fromAccount} onChange={(e) => setFromAccount(Number(e.target.value))}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm">
                    {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </Field>
                <Field label="Kimga">
                  <select value={toAccount} onChange={(e) => setToAccount(Number(e.target.value))}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm">
                    {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </Field>
              </div>
            ) : (
              /* All non-transfer: amount + account side by side */
              <div className="grid grid-cols-2 gap-3">
                <Field label={isPurchase ? "Jami narx" : "Summa"}>
                  <input className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                    value={amount} onChange={(e) => setAmount(e.target.value)}
                    inputMode="decimal" placeholder="0" />
                </Field>
                <Field label="Kassa">
                  <select value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}
                    className="w-full h-10 rounded-lg border bg-background px-3 text-sm">
                    {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </Field>
              </div>
            )}

            {/* Transfer: amount on its own row */}
            {isTransfer && (
              <Field label="Summa">
                <input className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                  value={amount} onChange={(e) => setAmount(e.target.value)}
                  inputMode="decimal" placeholder="0" />
              </Field>
            )}

            <Field label="Sana">
              <input type="date" value={occurredAt}
                onChange={(e) => setOccurredAt(e.target.value)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm" />
            </Field>

            <Field label="Izoh">
              <textarea className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[60px]"
                value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </div>
        )}

        {save.isError && (
          <div className="mt-3 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
            {getApiError(save.error)}
          </div>
        )}

        {!isLoading && (
          <div className="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button onClick={onClose}
              className="h-10 px-4 rounded-lg border text-sm hover:bg-muted">
              Bekor qilish
            </button>
            <button disabled={!canSave} onClick={() => save.mutate()}
              className="h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm disabled:opacity-50">
              {save.isPending ? "Saqlanmoqda…" : "Saqlash"}
            </button>
          </div>
        )}
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
