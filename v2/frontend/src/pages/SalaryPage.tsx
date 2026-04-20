import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Banknote,
  Factory,
  History,
  Pencil,
  Plus,
  Receipt,
  Settings2,
  Users,
  Wallet,
} from "lucide-react";
import { api } from "../lib/api";
import type { KassaAccount, Paginated } from "../lib/types";
import { formatMoney } from "../lib/utils";

type Kind = "salary" | "advance" | "bonus" | "deduction";
type RateType = "per_unit" | "per_meshok" | "per_week" | "fixed_monthly" | "per_product";

interface Payment {
  id: number;
  user: number;
  user_display: string;
  kind: Kind;
  kind_display: string;
  currency: "UZS" | "USD";
  amount: string;
  account: number;
  account_name: string;
  occurred_at: string;
  note: string;
  period_start: string | null;
  period_end: string | null;
}

interface EmployeeRate {
  id: number;
  rate_type: RateType;
  rate_type_display: string;
  rate: string;
  currency: "UZS" | "USD";
  initial_balance: string;
  note: string;
}

interface EmployeeSummary {
  user_id: number;
  display_name: string;
  username: string;
  role: string;
  produced_product_name: string | null;
  rate: EmployeeRate | null;
  earned: string;
  initial_balance: string;
  paid_salary: string;
  paid_advance: string;
  paid_bonus: string;
  paid_deduction: string;
  remaining: string;
  last_payment: {
    amount: string;
    currency: "UZS" | "USD";
    kind: Kind;
    kind_display: string;
    occurred_at: string;
  } | null;
}

const ROLE_LABEL: Record<string, string> = {
  nonvoy: "Nonvoy",
  driver: "Haydovchi",
  manager: "Menejer",
  accountant: "Buxgalter",
};

const ROLE_COLORS: Record<string, string> = {
  nonvoy: "bg-bakery-500/15 text-bakery-700",
  driver: "bg-amber-500/15 text-amber-700",
  manager: "bg-blue-500/15 text-blue-700",
  accountant: "bg-emerald-500/15 text-emerald-700",
};

const KIND_BADGE: Record<Kind, string> = {
  salary: "bg-emerald-500/15 text-emerald-700",
  advance: "bg-amber-500/15 text-amber-700",
  bonus: "bg-bakery-500/15 text-bakery-700",
  deduction: "bg-destructive/15 text-destructive",
};

const RATE_TYPE_LABEL: Record<RateType, string> = {
  per_unit: "Dona boshi",
  per_meshok: "Meshok boshi",
  per_week: "Haftalik",
  fixed_monthly: "Oylik qat'iy",
  per_product: "Mahsulot bo'yicha",
};

export function SalaryPage() {
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [payingFor, setPayingFor] = useState<EmployeeSummary | null>(null);
  const [editingRate, setEditingRate] = useState<EmployeeSummary | null>(null);
  const [historyFor, setHistoryFor] = useState<EmployeeSummary | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);

  const { data: summary, isLoading } = useQuery<{
    results: EmployeeSummary[];
    count: number;
  }>({
    queryKey: ["salary", "employees", roleFilter],
    queryFn: async () => {
      const params = roleFilter ? `?role=${roleFilter}` : "";
      return (await api.get(`/salary/employees/${params}`)).data;
    },
  });

  const { data: payments } = useQuery<Paginated<Payment>>({
    queryKey: ["salary", "payments"],
    queryFn: async () =>
      (await api.get<Paginated<Payment>>("/salary/payments/")).data,
  });

  const totals = useMemo(() => {
    const rows = summary?.results ?? [];
    const totalRemaining = rows.reduce((a, r) => a + parseFloat(r.remaining || "0"), 0);
    const totalPaid = rows.reduce(
      (a, r) =>
        a +
        parseFloat(r.paid_salary || "0") +
        parseFloat(r.paid_advance || "0") +
        parseFloat(r.paid_bonus || "0"),
      0,
    );
    const totalEarned = rows.reduce((a, r) => a + parseFloat(r.earned || "0"), 0);
    return { totalRemaining, totalPaid, totalEarned };
  }, [summary]);

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Wallet className="size-5 sm:size-6 text-bakery-500" /> Oylik
          </h1>
          <p className="text-muted-foreground text-sm">
            Xodimlar oyligi · tarif · avans / bonus / ushlab qolish (feature #4)
          </p>
        </div>
        <button
          onClick={() => setQuickOpen(true)}
          className="inline-flex items-center justify-center gap-1 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Plus className="size-4" /> Yangi to'lov
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Hisoblangan jami"
          value={formatMoney(totals.totalEarned, "UZS")}
          tone="info"
          icon={<Receipt className="size-4" />}
        />
        <StatCard
          label="To'langan jami"
          value={formatMoney(totals.totalPaid, "UZS")}
          tone="success"
          icon={<Banknote className="size-4" />}
        />
        <StatCard
          label="Qoldiq (qarzdormiz)"
          value={formatMoney(totals.totalRemaining, "UZS")}
          tone={totals.totalRemaining > 0 ? "warning" : "success"}
          icon={<Wallet className="size-4" />}
        />
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4 flex items-center gap-2 sm:gap-3">
        <Users className="size-4 text-muted-foreground shrink-0" />
        <label className="text-xs text-muted-foreground hidden sm:inline">Rol:</label>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="h-9 rounded-lg border bg-background px-2 sm:px-3 text-sm flex-1 sm:flex-initial"
        >
          <option value="">Barcha rollar</option>
          {Object.entries(ROLE_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-muted-foreground whitespace-nowrap">
          {summary?.count ?? 0} ta xodim
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {isLoading && (
          <div className="col-span-full rounded-xl border bg-card p-6 text-sm text-muted-foreground text-center">
            Yuklanmoqda…
          </div>
        )}
        {!isLoading && summary?.results.length === 0 && (
          <div className="col-span-full rounded-xl border bg-card p-6 text-sm text-muted-foreground text-center">
            Xodim topilmadi
          </div>
        )}
        {summary?.results.map((e) => (
          <EmployeeCard
            key={e.user_id}
            employee={e}
            onPay={() => setPayingFor(e)}
            onEditRate={() => setEditingRate(e)}
            onHistory={() => setHistoryFor(e)}
          />
        ))}
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-3 border-b flex items-center justify-between text-sm">
          <span className="font-semibold flex items-center gap-2">
            <History className="size-4" /> Oxirgi to'lovlar
          </span>
          <span className="text-muted-foreground">
            {payments?.results.length ?? 0} qator
          </span>
        </div>

        {/* Desktop table */}
        <div className="overflow-auto max-h-[400px] hidden md:block">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground sticky top-0">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Sana</th>
                <th className="text-left px-4 py-3 font-medium">Xodim</th>
                <th className="text-left px-4 py-3 font-medium">Tur</th>
                <th className="text-right px-4 py-3 font-medium">Miqdor</th>
                <th className="text-left px-4 py-3 font-medium">Kassa</th>
                <th className="text-left px-4 py-3 font-medium">Izoh</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {payments?.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                    Oylik to'lovlari hali yo'q
                  </td>
                </tr>
              )}
              {payments?.results.slice(0, 50).map((p) => (
                <tr key={p.id} className="hover:bg-muted/30">
                  <td className="px-4 py-2 text-muted-foreground tabular-nums whitespace-nowrap">
                    {p.occurred_at.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2 font-medium">{p.user_display}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${KIND_BADGE[p.kind]}`}
                    >
                      {p.kind_display}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums font-medium">
                    {formatMoney(p.amount, p.currency)}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{p.account_name}</td>
                  <td className="px-4 py-2 text-muted-foreground truncate max-w-xs">
                    {p.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="md:hidden divide-y max-h-[400px] overflow-auto">
          {payments?.results.length === 0 && (
            <div className="px-4 py-10 text-center text-muted-foreground text-sm">
              Oylik to'lovlari hali yo'q
            </div>
          )}
          {payments?.results.slice(0, 50).map((p) => (
            <div key={p.id} className="p-3 space-y-1">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium truncate">{p.user_display}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.occurred_at.slice(0, 10)} · {p.account_name}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-semibold tabular-nums">
                    {formatMoney(p.amount, p.currency)}
                  </div>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${KIND_BADGE[p.kind]}`}
                  >
                    {p.kind_display}
                  </span>
                </div>
              </div>
              {p.note && (
                <div className="text-xs text-muted-foreground italic truncate">
                  {p.note}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {quickOpen && (
        <PaymentModal onClose={() => setQuickOpen(false)} preselectUser={null} />
      )}
      {payingFor && (
        <PaymentModal
          onClose={() => setPayingFor(null)}
          preselectUser={payingFor}
        />
      )}
      {editingRate && (
        <RateModal
          onClose={() => setEditingRate(null)}
          employee={editingRate}
        />
      )}
      {historyFor && (
        <HistoryDrawer
          employee={historyFor}
          onClose={() => setHistoryFor(null)}
        />
      )}
    </div>
  );
}

function EmployeeCard({
  employee,
  onPay,
  onEditRate,
  onHistory,
}: {
  employee: EmployeeSummary;
  onPay: () => void;
  onEditRate: () => void;
  onHistory: () => void;
}) {
  const remaining = parseFloat(employee.remaining);
  const earned = parseFloat(employee.earned);
  const paid =
    parseFloat(employee.paid_salary) +
    parseFloat(employee.paid_advance) +
    parseFloat(employee.paid_bonus);

  return (
    <div className="rounded-xl border bg-card p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-semibold">{employee.display_name}</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                ROLE_COLORS[employee.role] ?? "bg-muted"
              }`}
            >
              {ROLE_LABEL[employee.role] ?? employee.role}
            </span>
            {employee.produced_product_name && (
              <span className="text-xs text-muted-foreground">
                · {employee.produced_product_name}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onEditRate}
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          title="Tarifni tahrirlash"
        >
          <Settings2 className="size-3.5" />
          <span className="hidden sm:inline">Tarif</span>
        </button>
      </div>

      <div className="text-xs text-muted-foreground">
        {employee.rate ? (
          <>
            Tarif: <span className="text-foreground font-medium">{employee.rate.rate_type_display}</span>
            {" · "}
            <span className="text-foreground">
              {formatMoney(employee.rate.rate, employee.rate.currency)}
            </span>
          </>
        ) : (
          <span className="italic">Tarif belgilanmagan</span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-lg bg-muted/40 p-2">
          <div className="text-muted-foreground">Hisoblangan</div>
          <div className="font-semibold tabular-nums mt-0.5">
            {formatMoney(earned, "UZS")}
          </div>
        </div>
        <div className="rounded-lg bg-muted/40 p-2">
          <div className="text-muted-foreground">To'langan</div>
          <div className="font-semibold tabular-nums mt-0.5">
            {formatMoney(paid, "UZS")}
          </div>
        </div>
        <div
          className={`rounded-lg p-2 ${
            remaining > 0
              ? "bg-amber-500/10 text-amber-800"
              : remaining < 0
                ? "bg-destructive/10 text-destructive"
                : "bg-emerald-500/10 text-emerald-800"
          }`}
        >
          <div className="opacity-80">Qoldiq</div>
          <div className="font-semibold tabular-nums mt-0.5">
            {formatMoney(remaining, "UZS")}
          </div>
        </div>
      </div>

      {employee.last_payment && (
        <div className="text-xs text-muted-foreground">
          Oxirgi: {employee.last_payment.kind_display} ·{" "}
          <span className="font-medium text-foreground">
            {formatMoney(employee.last_payment.amount, employee.last_payment.currency)}
          </span>{" "}
          ({employee.last_payment.occurred_at.slice(0, 10)})
        </div>
      )}

      <div className="mt-auto flex gap-2 pt-1">
        <button
          onClick={onPay}
          className="flex-1 h-9 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-xs font-medium inline-flex items-center justify-center gap-1"
        >
          <Plus className="size-3.5" /> To'lash
        </button>
        <button
          onClick={onHistory}
          className="h-9 px-3 rounded-lg border text-xs hover:bg-muted inline-flex items-center gap-1"
        >
          <History className="size-3.5" /> Tarix
        </button>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone?: "info" | "success" | "warning" | "danger";
  icon?: React.ReactNode;
}) {
  const toneCls =
    tone === "warning"
      ? "text-amber-700"
      : tone === "danger"
        ? "text-destructive"
        : tone === "success"
          ? "text-emerald-700"
          : tone === "info"
            ? "text-bakery-600"
            : "";
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-xs text-muted-foreground flex items-center gap-1.5">
        {icon} {label}
      </div>
      <div className={"mt-1 text-xl font-semibold tabular-nums " + toneCls}>{value}</div>
    </div>
  );
}

interface StaffUser {
  id: number;
  display_name: string;
  role: string;
}

function PaymentModal({
  onClose,
  preselectUser,
}: {
  onClose: () => void;
  preselectUser: EmployeeSummary | null;
}) {
  const qc = useQueryClient();
  const [userId, setUserId] = useState<number | "">(
    preselectUser?.user_id ?? "",
  );
  const [kind, setKind] = useState<Kind>("salary");
  const [currency, setCurrency] = useState<"UZS" | "USD">("UZS");
  const [amount, setAmount] = useState(
    preselectUser && parseFloat(preselectUser.remaining) > 0
      ? preselectUser.remaining
      : "",
  );
  const [accountId, setAccountId] = useState<number | "">("");
  const [occurredAt, setOccurredAt] = useState(() =>
    new Date().toISOString().slice(0, 16),
  );
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [note, setNote] = useState("");

  const { data: accounts } = useQuery<Paginated<KassaAccount>>({
    queryKey: ["kassa", "accounts"],
    queryFn: async () =>
      (await api.get<Paginated<KassaAccount>>("/finance/accounts/")).data,
  });

  const { data: users } = useQuery<Paginated<StaffUser>>({
    queryKey: ["users", { staff: true }],
    queryFn: async () =>
      (await api.get<Paginated<StaffUser>>("/users/?archived=false")).data,
    enabled: !preselectUser,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/salary/payments/", {
        user: userId,
        kind,
        currency,
        amount,
        account: accountId,
        occurred_at: new Date(occurredAt).toISOString(),
        period_start: periodStart || null,
        period_end: periodEnd || null,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["salary"] });
      qc.invalidateQueries({ queryKey: ["kassa"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      onClose();
    },
  });

  const canSave = userId && accountId && parseFloat(amount) > 0;
  const title = preselectUser
    ? `${preselectUser.display_name} uchun to'lov`
    : "Yangi to'lov";

  return (
    <div
      className="fixed inset-0 grid place-items-center bg-black/30 p-3 sm:p-4 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-card rounded-2xl shadow-xl border p-4 sm:p-6 max-h-[90vh] overflow-y-auto"
      >
        <h2 className="font-semibold text-lg mb-4">{title}</h2>
        <div className="space-y-3">
          {!preselectUser && (
            <Field label="Xodim">
              <select
                value={userId}
                onChange={(e) =>
                  setUserId(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="">Tanlang…</option>
                {users?.results.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.display_name} ({u.role})
                  </option>
                ))}
              </select>
            </Field>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tur">
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as Kind)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              >
                <option value="salary">Oylik</option>
                <option value="advance">Avans</option>
                <option value="bonus">Bonus</option>
                <option value="deduction">Ushlab qolish</option>
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
            <Field label="Miqdor">
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                inputMode="decimal"
              />
            </Field>
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
          </div>
          <Field label="To'lov vaqti">
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            />
          </Field>
          {kind === "salary" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Davr boshi">
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                />
              </Field>
              <Field label="Davr oxiri">
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                />
              </Field>
            </div>
          )}
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
            {create.isPending ? "Saqlanmoqda…" : "Saqlash"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RateModal({
  onClose,
  employee,
}: {
  onClose: () => void;
  employee: EmployeeSummary;
}) {
  const qc = useQueryClient();
  const existing = employee.rate;
  const [rateType, setRateType] = useState<RateType>(existing?.rate_type ?? "fixed_monthly");
  const [rate, setRate] = useState(existing?.rate ?? "0");
  const [currency, setCurrency] = useState<"UZS" | "USD">(
    existing?.currency ?? "UZS",
  );
  const [initialBalance, setInitialBalance] = useState(
    existing?.initial_balance ?? "0",
  );
  const [note, setNote] = useState(existing?.note ?? "");

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        user: employee.user_id,
        rate_type: rateType,
        rate,
        currency,
        initial_balance: initialBalance,
        note,
      };
      if (existing) {
        return api.patch(`/salary/rates/${existing.id}/`, payload);
      }
      return api.post("/salary/rates/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["salary"] });
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
        <h2 className="font-semibold text-lg mb-1">
          Tarif — {employee.display_name}
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          Hisoblash qoidasi va boshlang'ich qarz/kredit.
        </p>
        <div className="space-y-3">
          <Field label="Hisoblash turi">
            <select
              value={rateType}
              onChange={(e) => setRateType(e.target.value as RateType)}
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
            >
              {Object.entries(RATE_TYPE_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={rateType === "per_product" ? "Tarif (ishlatilmaydi)" : "Tarif (miqdor)"}>
              <input
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                inputMode="decimal"
                disabled={rateType === "per_product"}
              />
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
          <Field label="Boshlang'ich qarz (biz unga qarzmiz = musbat)">
            <input
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
              value={initialBalance}
              onChange={(e) => setInitialBalance(e.target.value)}
              inputMode="decimal"
            />
          </Field>
          {rateType === "per_product" && (
            <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-2">
              Bu turda har bir mahsulot uchun tarif mahsulot sahifasidan
              (production_salary_per_unit_uzs) olinadi.
            </div>
          )}
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
            disabled={save.isPending}
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

interface ProductionDay {
  date: string;
  total_meshok: string;
  total_units: string;
  products: {
    product_id: number;
    product_name: string;
    meshok: string;
    units: string;
    salary_per_unit: string;
  }[];
}

function HistoryDrawer({
  employee,
  onClose,
}: {
  employee: EmployeeSummary;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"payments" | "production">("payments");
  const { data, isLoading } = useQuery<Paginated<Payment>>({
    queryKey: ["salary", "history", employee.user_id],
    queryFn: async () =>
      (
        await api.get<Paginated<Payment>>(
          `/salary/payments/?user=${employee.user_id}`,
        )
      ).data,
  });

  const showProductionTab =
    employee.role === "nonvoy" &&
    (employee.rate?.rate_type === "per_meshok" ||
      employee.rate?.rate_type === "per_unit" ||
      employee.rate?.rate_type === "per_product");

  const { data: production, isLoading: prodLoading } = useQuery<{
    results: ProductionDay[];
    count: number;
  }>({
    queryKey: ["salary", "production-breakdown", employee.user_id],
    queryFn: async () =>
      (
        await api.get<{ results: ProductionDay[]; count: number }>(
          `/salary/production-breakdown/?user=${employee.user_id}`,
        )
      ).data,
    enabled: showProductionTab && tab === "production",
  });

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex justify-end"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl bg-card shadow-xl border-l h-full overflow-y-auto"
      >
        <div className="p-4 sm:p-5 border-b flex items-center justify-between gap-2 sticky top-0 bg-card z-10">
          <div className="min-w-0">
            <h2 className="font-semibold text-base sm:text-lg truncate">
              {employee.display_name} — to'lovlar
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {ROLE_LABEL[employee.role] ?? employee.role} · Qoldiq:{" "}
              <span className="font-medium">
                {formatMoney(employee.remaining, "UZS")}
              </span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 h-9 px-3 rounded-lg border text-sm hover:bg-muted"
          >
            Yopish
          </button>
        </div>
        {showProductionTab && (
          <div className="px-4 sm:px-5 pt-4 flex gap-1 border-b">
            <button
              onClick={() => setTab("payments")}
              className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === "payments"
                  ? "border-bakery-500 text-bakery-700"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              To'lovlar
            </button>
            <button
              onClick={() => setTab("production")}
              className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px flex items-center gap-1.5 ${
                tab === "production"
                  ? "border-bakery-500 text-bakery-700"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Factory className="size-3.5" />
              Ishlab chiqarish (kunlik)
            </button>
          </div>
        )}
        <div className="p-4 sm:p-5">
          {tab === "payments" && (
            <>
              {isLoading && (
                <div className="text-sm text-muted-foreground">Yuklanmoqda…</div>
              )}
              {!isLoading && (data?.results.length ?? 0) === 0 && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  To'lovlar tarixi bo'sh
                </div>
              )}
              <div className="divide-y">
                {data?.results.map((p) => (
                  <div key={p.id} className="py-3 flex items-start gap-3">
                    <Pencil className="size-3.5 mt-1 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full ${KIND_BADGE[p.kind]}`}
                        >
                          {p.kind_display}
                        </span>
                        <span className="text-sm font-semibold tabular-nums">
                          {formatMoney(p.amount, p.currency)}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {p.occurred_at.slice(0, 16).replace("T", " ")} ·{" "}
                        {p.account_name}
                      </div>
                      {p.note && (
                        <div className="text-xs text-muted-foreground mt-1 italic">
                          {p.note}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          {tab === "production" && showProductionTab && (
            <>
              {prodLoading && (
                <div className="text-sm text-muted-foreground">Yuklanmoqda…</div>
              )}
              {!prodLoading && (production?.results.length ?? 0) === 0 && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  Ishlab chiqarish tarixi bo'sh
                </div>
              )}
              <div className="space-y-4">
                {production?.results.map((day) => (
                  <div
                    key={day.date}
                    className="rounded-lg border bg-muted/20 p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium text-sm">{day.date}</div>
                      <div className="text-sm tabular-nums">
                        <span className="font-semibold">{day.total_meshok}</span>{" "}
                        <span className="text-muted-foreground">qop ·</span>{" "}
                        <span className="font-semibold">{day.total_units}</span>{" "}
                        <span className="text-muted-foreground">dona</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      {day.products.map((p) => (
                        <div
                          key={p.product_id}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-muted-foreground truncate pr-2">
                            {p.product_name}
                          </span>
                          <span className="tabular-nums">
                            {p.meshok} qop · {p.units} dona
                            {employee.rate?.rate_type === "per_product" &&
                              parseFloat(p.salary_per_unit) > 0 && (
                                <span className="ml-2 text-bakery-600">
                                  ≈{" "}
                                  {formatMoney(
                                    String(
                                      parseFloat(p.units) *
                                        parseFloat(p.salary_per_unit),
                                    ),
                                    "UZS",
                                  )}
                                </span>
                              )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      {children}
    </div>
  );
}
