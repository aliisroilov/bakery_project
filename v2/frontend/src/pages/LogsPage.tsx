import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import type { Paginated } from "../lib/types";

interface ApiUser {
  id: number;
  display_name: string;
  username: string;
}

interface ActivityLog {
  id: number;
  user: number;
  user_display: string;
  path: string;
  method: string;
  status_code: number | null;
  ip: string | null;
  timestamp: string;
  action: string;
}

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-slate-500/15 text-slate-700",
  POST: "bg-emerald-500/15 text-emerald-700",
  PATCH: "bg-amber-500/15 text-amber-700",
  PUT: "bg-amber-500/15 text-amber-700",
  DELETE: "bg-destructive/15 text-destructive",
};

export function LogsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString().slice(0, 10);

  const [userId, setUserId] = useState("");
  const [method, setMethod] = useState("");
  const [dateFrom, setDateFrom] = useState(weekAgo);
  const [dateTo, setDateTo] = useState(today);
  const [pathQuery, setPathQuery] = useState("");

  const { data: users } = useQuery<Paginated<ApiUser>>({
    queryKey: ["logs", "users"],
    queryFn: async () =>
      (await api.get<Paginated<ApiUser>>("/users/?archived=false")).data,
  });

  const { data: logs, isFetching, refetch } = useQuery<Paginated<ActivityLog>>({
    queryKey: ["logs", userId, method, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (userId) params.user = userId;
      if (method) params.method = method;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      return (await api.get<Paginated<ActivityLog>>("/users/activity/", { params })).data;
    },
  });

  const filteredResults = (logs?.results ?? []).filter((l) => {
    if (pathQuery.trim() && !l.path.toLowerCase().includes(pathQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  const errorCount = filteredResults.filter((l) => (l.status_code ?? 0) >= 400).length;
  const writesCount = filteredResults.filter((l) =>
    ["POST", "PATCH", "PUT", "DELETE"].includes(l.method),
  ).length;

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Activity className="size-5 sm:size-6 text-bakery-500" /> Loglar
          </h1>
          <p className="text-muted-foreground text-sm">
            Xodimlar faoliyati · audit · filtrlar (feature #15)
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-lg border text-sm hover:bg-muted disabled:opacity-50 w-full sm:w-auto"
        >
          <RefreshCw className={"size-4 " + (isFetching ? "animate-spin" : "")} /> Yangilash
        </button>
      </div>

      <div className="grid gap-3 grid-cols-3">
        <StatCard label="Jami" value={filteredResults.length} />
        <StatCard label="Yozuvlar" value={writesCount} tone="info" />
        <StatCard label="Xatolik" value={errorCount} tone="danger" />
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4 grid gap-3 grid-cols-2 md:grid-cols-5">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Xodim</label>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          >
            <option value="">Barchasi</option>
            {users?.results.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Amal</label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          >
            <option value="">Barchasi</option>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PATCH">PATCH</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Sana boshi</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Sana oxiri</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          />
        </div>
        <div className="col-span-2 md:col-span-1">
          <label className="block text-xs text-muted-foreground mb-1">Yo'l (URL)</label>
          <input
            value={pathQuery}
            onChange={(e) => setPathQuery(e.target.value)}
            placeholder="/orders /shops …"
            className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
          />
        </div>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 sm:px-5 py-3 border-b flex items-center justify-between text-sm">
          <span className="font-semibold">So'rovlar jurnali</span>
          <span className="text-muted-foreground">
            {isFetching ? "Yuklanmoqda…" : `${filteredResults.length} qator`}
          </span>
        </div>

        {/* Desktop table */}
        <div className="overflow-auto max-h-[640px] hidden md:block">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground sticky top-0">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Vaqt</th>
                <th className="text-left px-4 py-3 font-medium">Xodim</th>
                <th className="text-left px-4 py-3 font-medium">Amal</th>
                <th className="text-left px-4 py-3 font-medium">Tavsif</th>
                <th className="text-left px-4 py-3 font-medium">Yo'l (URL)</th>
                <th className="text-right px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {!isFetching && filteredResults.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                    Log topilmadi
                  </td>
                </tr>
              )}
              {filteredResults.slice(0, 500).map((l) => {
                const errored = (l.status_code ?? 0) >= 400;
                return (
                  <tr key={l.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2 text-muted-foreground tabular-nums text-xs whitespace-nowrap">
                      {l.timestamp.slice(0, 19).replace("T", " ")}
                    </td>
                    <td className="px-4 py-2 font-medium">{l.user_display}</td>
                    <td className="px-4 py-2">
                      <span
                        className={
                          "inline-flex px-2 py-0.5 rounded text-[10px] font-mono font-semibold " +
                          (METHOD_COLORS[l.method] ?? "bg-muted")
                        }
                      >
                        {l.method}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">{l.action}</td>
                    <td className="px-4 py-2 text-xs font-mono text-muted-foreground truncate max-w-[300px]" title={l.path}>
                      {l.path}
                    </td>
                    <td
                      className={
                        "px-4 py-2 text-right tabular-nums text-xs " +
                        (errored ? "text-destructive font-medium" : "text-muted-foreground")
                      }
                    >
                      {l.status_code ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-muted-foreground">
                      {l.ip ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="md:hidden divide-y max-h-[640px] overflow-auto">
          {!isFetching && filteredResults.length === 0 && (
            <div className="px-4 py-10 text-center text-muted-foreground text-sm">
              Log topilmadi
            </div>
          )}
          {filteredResults.slice(0, 300).map((l) => {
            const errored = (l.status_code ?? 0) >= 400;
            return (
              <div key={l.id} className="p-3 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span
                      className={
                        "inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold shrink-0 " +
                        (METHOD_COLORS[l.method] ?? "bg-muted")
                      }
                    >
                      {l.method}
                    </span>
                    <span className="text-sm truncate">{l.action}</span>
                  </div>
                  <span
                    className={
                      "text-xs tabular-nums shrink-0 " +
                      (errored ? "text-destructive font-medium" : "text-muted-foreground")
                    }
                  >
                    {l.status_code ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground flex items-center justify-between gap-2">
                  <span className="truncate">{l.user_display}</span>
                  <span className="tabular-nums shrink-0">
                    {l.timestamp.slice(0, 16).replace("T", " ")}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-muted-foreground truncate">
                  {l.path}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "info" | "danger";
}) {
  const toneCls =
    tone === "danger"
      ? "text-destructive"
      : tone === "info"
        ? "text-bakery-600"
        : "";
  return (
    <div className="rounded-xl border bg-card p-3 sm:p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={"mt-1 text-xl sm:text-2xl font-semibold tabular-nums " + toneCls}>{value}</div>
    </div>
  );
}
