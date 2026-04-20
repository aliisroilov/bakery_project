import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, Search, RefreshCw, ArrowUpDown, ArrowUp, ArrowDown, Copy } from "lucide-react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/utils";

type ReportType =
  | "payments"
  | "orders"
  | "production"
  | "expenses"
  | "salary"
  | "shop_debts";

interface ReportDef {
  type: ReportType;
  title: string;
  description: string;
  xlsxEndpoint: string;
  supportsDateRange: boolean;
  moneyCols?: number[];
  currencyCol?: number;
}

const REPORTS: ReportDef[] = [
  {
    type: "payments",
    title: "Kirim (kunlik)",
    description: "Har kun uchun jami kirim — kassalar va xodimlar bo'yicha.",
    xlsxEndpoint: "/reports/payments.xlsx",
    supportsDateRange: true,
    moneyCols: [4, 5],
    currencyCol: 3,
  },
  {
    type: "orders",
    title: "Buyurtmalar",
    description: "Oylik bo'yicha jami sotuv, yetkazilgan va jami summa.",
    xlsxEndpoint: "/reports/orders.xlsx",
    supportsDateRange: true,
    moneyCols: [5, 6],
    currencyCol: 4,
  },
  {
    type: "expenses",
    title: "Xarajatlar",
    description: "Xomashyo xaridlari + umumiy xarajatlar birgalikda.",
    xlsxEndpoint: "/reports/expenses.xlsx",
    supportsDateRange: true,
    moneyCols: [4],
    currencyCol: 3,
  },
  {
    type: "salary",
    title: "Oylik",
    description: "Oylik, avans, bonuslar xodim bo'yicha.",
    xlsxEndpoint: "/reports/salary.xlsx",
    supportsDateRange: true,
    moneyCols: [4],
    currencyCol: 3,
  },
  {
    type: "shop_debts",
    title: "Qarzdor do'konlar",
    description: "Limitdan oshgan do'konlar va eng katta qarzdorlar.",
    xlsxEndpoint: "/reports/shop-debts.xlsx",
    supportsDateRange: false,
    moneyCols: [2, 3, 4, 5],
  },
  {
    type: "production",
    title: "Ishlab chiqarish",
    description: "Mahsulot va nonvoylar bo'yicha ishlab chiqarish.",
    xlsxEndpoint: "/reports/production.xlsx",
    supportsDateRange: true,
  },
];

interface ReportData {
  type: ReportType;
  title: string;
  headers: string[];
  rows: (string | number)[][];
  summary: Record<string, number>;
}

export function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = new Date();
  monthStart.setDate(1);
  const [dateFrom, setDateFrom] = useState(monthStart.toISOString().slice(0, 10));
  const [dateTo, setDateTo] = useState(today);
  const [active, setActive] = useState<ReportType>("payments");
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [pinFirst, setPinFirst] = useState(true);

  const report = REPORTS.find((r) => r.type === active)!;

  const { data, isFetching, refetch } = useQuery<ReportData>({
    queryKey: ["reports", "data", active, report.supportsDateRange ? dateFrom : "", report.supportsDateRange ? dateTo : ""],
    queryFn: async () => {
      const params: Record<string, string> = { type: active };
      if (report.supportsDateRange) {
        params.date_from = dateFrom;
        params.date_to = dateTo;
      }
      return (await api.get<ReportData>("/reports/data/", { params })).data;
    },
  });

  const filteredRows = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    const base = q
      ? data.rows.filter((row) => row.some((cell) => String(cell).toLowerCase().includes(q)))
      : data.rows.slice();
    if (sortCol == null) return base;
    const isMoney = report.moneyCols?.includes(sortCol);
    return [...base].sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      let cmp = 0;
      if (isMoney || (typeof av === "number" && typeof bv === "number")) {
        cmp = Number(av) - Number(bv);
      } else {
        cmp = String(av).localeCompare(String(bv), "uz");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, search, sortCol, sortDir, report.moneyCols]);

  const columnTotals = useMemo(() => {
    if (!data || !report.moneyCols?.length) return null;
    const totals: Record<number, number> = {};
    for (const col of report.moneyCols) {
      totals[col] = filteredRows.reduce((s, r) => s + (Number(r[col]) || 0), 0);
    }
    return totals;
  }, [data, filteredRows, report.moneyCols]);

  const toggleSort = (col: number) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const copyToClipboard = async () => {
    if (!data) return;
    const tsv = [
      data.headers.join("\t"),
      ...filteredRows.map((r) => r.map((c) => String(c)).join("\t")),
    ].join("\n");
    await navigator.clipboard.writeText(tsv);
  };

  const downloadXlsx = async () => {
    const params: Record<string, string> = {};
    if (report.supportsDateRange) {
      params.date_from = dateFrom;
      params.date_to = dateTo;
    }
    const res = await api.get(report.xlsxEndpoint, {
      params,
      responseType: "blob",
    });
    const blob = new Blob([res.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const cd = (res.headers as Record<string, string>)["content-disposition"] || "";
    const match = /filename="?([^";]+)"?/.exec(cd);
    link.href = url;
    link.download = match ? match[1] : `${report.title}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart3 className="size-5 sm:size-6 text-bakery-500" /> Hisobotlar
          </h1>
          <p className="text-muted-foreground text-sm">
            Ko'rish · qidiruv · Excel yuklab olish (feature #18)
          </p>
        </div>
        <button
          onClick={downloadXlsx}
          className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-lg bg-bakery-500 hover:bg-bakery-600 text-white text-sm w-full sm:w-auto"
        >
          <Download className="size-4" /> Excel yuklab olish
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {REPORTS.map((r) => (
          <button
            key={r.type}
            onClick={() => setActive(r.type)}
            className={
              "h-9 px-4 rounded-full border text-sm transition-colors " +
              (active === r.type
                ? "bg-bakery-500 border-bakery-500 text-white"
                : "bg-card hover:bg-muted")
            }
          >
            {r.title}
          </button>
        ))}
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4 grid grid-cols-2 sm:flex sm:flex-wrap sm:items-end gap-2 sm:gap-3">
        {report.supportsDateRange && (
          <>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Sana boshi</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Sana oxiri</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
              />
            </div>
          </>
        )}
        <div className="col-span-2 sm:flex-1 sm:min-w-[220px]">
          <label className="block text-xs text-muted-foreground mb-1">Qidiruv</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Istalgan ustun bo'yicha filtr…"
              className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm"
            />
          </div>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="col-span-2 sm:col-auto h-10 px-4 rounded-lg border text-sm hover:bg-muted inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
          title="Yangilash"
        >
          <RefreshCw className={"size-4 " + (isFetching ? "animate-spin" : "")} />
          Yangilash
        </button>
      </div>

      <SummaryCards data={data} type={active} />

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-3 border-b flex items-center justify-between text-sm gap-3 flex-wrap">
          <span className="font-semibold">{report.title}</span>
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={pinFirst}
                onChange={(e) => setPinFirst(e.target.checked)}
                className="rounded"
              />
              Birinchi ustun qotirilgan
            </label>
            <button
              onClick={copyToClipboard}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              title="Clipboard ga nusxa (Excel ga yopishtiriladi)"
            >
              <Copy className="size-3.5" /> Nusxa
            </button>
            <span className="text-muted-foreground">
              {isFetching ? "Yuklanmoqda…" : `${filteredRows.length} qator`}
            </span>
          </div>
        </div>
        <div className="overflow-auto max-h-[560px] relative">
          <table className="w-full text-sm border-separate border-spacing-0">
            <thead className="bg-muted text-xs text-muted-foreground">
              <tr>
                <th className="sticky top-0 left-0 z-30 bg-muted border-b border-r px-2 py-3 font-medium text-center w-10">
                  #
                </th>
                {data?.headers.map((h, i) => {
                  const isMoney = report.moneyCols?.includes(i);
                  const isSort = sortCol === i;
                  const sticky = pinFirst && i === 0 ? "sticky left-10 z-20 bg-muted" : "";
                  return (
                    <th
                      key={i}
                      onClick={() => toggleSort(i)}
                      className={
                        "sticky top-0 z-10 bg-muted border-b px-4 py-3 font-medium cursor-pointer select-none hover:bg-muted/70 " +
                        (isMoney ? "text-right " : "text-left ") +
                        sticky
                      }
                    >
                      <span className="inline-flex items-center gap-1">
                        {h}
                        {isSort ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="size-3" />
                          ) : (
                            <ArrowDown className="size-3" />
                          )
                        ) : (
                          <ArrowUpDown className="size-3 opacity-30" />
                        )}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {!isFetching && filteredRows.length === 0 && (
                <tr>
                  <td
                    colSpan={(data?.headers.length ?? 0) + 1}
                    className="px-4 py-10 text-center text-muted-foreground border-b"
                  >
                    Ma'lumot yo'q
                  </td>
                </tr>
              )}
              {filteredRows.slice(0, 500).map((row, ri) => (
                <tr
                  key={ri}
                  className={
                    "hover:bg-bakery-50/60 " + (ri % 2 === 1 ? "bg-muted/20" : "bg-card")
                  }
                >
                  <td className="border-b border-r px-2 py-2 text-center text-xs text-muted-foreground tabular-nums sticky left-0 z-10 bg-inherit">
                    {ri + 1}
                  </td>
                  {row.map((cell, ci) => {
                    const isMoney = report.moneyCols?.includes(ci);
                    const currency = report.currencyCol != null
                      ? (row[report.currencyCol] as string)
                      : "UZS";
                    const sticky = pinFirst && ci === 0 ? "sticky left-10 z-[5] bg-inherit" : "";
                    return (
                      <td
                        key={ci}
                        className={
                          "border-b px-4 py-2 " +
                          (isMoney ? "text-right tabular-nums" : "text-left") +
                          " " + sticky
                        }
                      >
                        {isMoney
                          ? Number(cell) > 0
                            ? formatMoney(String(cell), currency as "UZS" | "USD")
                            : "—"
                          : String(cell)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
            {columnTotals && filteredRows.length > 0 && (
              <tfoot className="sticky bottom-0 z-10 bg-muted font-semibold">
                <tr>
                  <td className="sticky left-0 z-20 bg-muted border-t border-r px-2 py-2 text-center text-xs text-muted-foreground">
                    Σ
                  </td>
                  {data?.headers.map((_, ci) => {
                    const isMoney = report.moneyCols?.includes(ci);
                    const sticky = pinFirst && ci === 0 ? "sticky left-10 z-10 bg-muted" : "";
                    return (
                      <td
                        key={ci}
                        className={
                          "border-t px-4 py-2 " +
                          (isMoney ? "text-right tabular-nums" : "text-left text-muted-foreground text-xs") +
                          " " + sticky
                        }
                      >
                        {isMoney
                          ? columnTotals[ci] > 0
                            ? formatMoney(String(columnTotals[ci]), "UZS")
                            : "—"
                          : ci === 0
                            ? "Jami"
                            : ""}
                      </td>
                    );
                  })}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        {filteredRows.length > 500 && (
          <div className="px-5 py-3 border-t text-xs text-muted-foreground text-center">
            Dastlabki 500 qator ko'rsatilgan · to'liq ma'lumot uchun Excel yuklab oling
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCards({ data, type }: { data: ReportData | undefined; type: ReportType }) {
  if (!data) return null;
  const s = data.summary;
  const cards: { label: string; value: string }[] = [];
  if (s.total_uzs !== undefined) {
    cards.push({ label: "Jami (UZS)", value: formatMoney(String(s.total_uzs), "UZS") });
  }
  if (s.total_usd !== undefined && s.total_usd > 0) {
    cards.push({ label: "Jami (USD)", value: formatMoney(String(s.total_usd), "USD") });
  }
  if (type === "production") {
    cards.push({ label: "Jami qop", value: String(s.total_meshok ?? 0) });
    cards.push({ label: "Jami dona", value: String(s.total_units ?? 0) });
  }
  if (type === "shop_debts") {
    cards.push({ label: "Jami qarz (UZS)", value: formatMoney(String(s.total_uzs_debt ?? 0), "UZS") });
    if ((s.total_usd_debt ?? 0) > 0) {
      cards.push({ label: "Jami qarz (USD)", value: formatMoney(String(s.total_usd_debt ?? 0), "USD") });
    }
    cards.push({ label: "Limitdan oshgan", value: String(s.over_count ?? 0) });
  }
  cards.push({ label: "Yozuvlar", value: String(s.count ?? 0) });

  return (
    <div className="grid gap-2 sm:gap-3 grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded-xl border bg-card p-3 sm:p-4">
          <div className="text-xs text-muted-foreground truncate">{c.label}</div>
          <div className="mt-1 text-base sm:text-lg font-semibold tabular-nums truncate">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
