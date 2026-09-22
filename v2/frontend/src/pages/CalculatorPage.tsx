import { useMemo, useState } from "react";
import { Calculator, Plus, Trash2, RotateCcw } from "lucide-react";
import { formatMoney } from "../lib/utils";

/**
 * "Yangi mahsulot" kalkulyatori — prototiplash uchun.
 *
 * Xomashyo ro'yxati (nom, miqdor, narx) kiritiladi va 1 dona mahsulot uchun
 * tannarx hisoblanadi — xuddi ProductsPage'dagi retsept preview'i kabi
 * (tannarx = summa(miqdor x narx)), keyin sotish narxi va kutilayotgan hajm
 * bo'yicha tushum/foyda ko'rsatiladi.
 *
 * Bu sahifa hech narsani saqlamaydi — na Mahsulot, na Retsept, na Xomashyo
 * bazasiga yozmaydi. Faqat brauzer xotirasida (state) hisoblanadi va sahifa
 * yopilganda yo'qoladi. Haqiqiy mahsulot sifatida qo'shish uchun
 * "Mahsulotlar" bo'limidagi "Yangi mahsulot" dan foydalaning.
 */

interface IngredientLine {
  key: string;
  name: string;
  quantity: string;
  price: string;
}

function newLine(): IngredientLine {
  return { key: crypto.randomUUID(), name: "", quantity: "", price: "" };
}

export function CalculatorPage() {
  const [lines, setLines] = useState<IngredientLine[]>([newLine(), newLine()]);
  const [salePrice, setSalePrice] = useState("");
  const [volume, setVolume] = useState("");

  const addLine = () => setLines((ls) => [...ls, newLine()]);
  const removeLine = (key: string) =>
    setLines((ls) => (ls.length > 1 ? ls.filter((l) => l.key !== key) : ls));
  const updateLine = (key: string, patch: Partial<IngredientLine>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const resetAll = () => {
    setLines([newLine(), newLine()]);
    setSalePrice("");
    setVolume("");
  };

  const result = useMemo(() => {
    // Tannarx (1 dona) = summa(miqdor x narx) — retsept asosidagi tannarx
    // formulasi bilan bir xil (apps/products/pricing.py: recalc_product_cost).
    const rows = lines.map((l) => {
      const qty = parseFloat(l.quantity) || 0;
      const price = parseFloat(l.price) || 0;
      return { ...l, qty, price, subtotal: qty * price };
    });
    const costPerUnit = rows.reduce((sum, r) => sum + r.subtotal, 0);

    const sale = parseFloat(salePrice) || 0;
    const vol = parseFloat(volume) || 0;

    const totalRevenue = sale * vol;
    const totalCost = costPerUnit * vol;
    const totalProfit = totalRevenue - totalCost;
    const marginPerUnit = sale - costPerUnit;
    const marginPct = sale > 0 ? (marginPerUnit / sale) * 100 : 0;

    return { rows, costPerUnit, totalRevenue, totalCost, totalProfit, marginPerUnit, marginPct, sale, vol };
  }, [lines, salePrice, volume]);

  return (
    <div className="space-y-4 sm:space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
            Kalkulyator
          </h1>
          <p className="text-muted-foreground text-sm">
            Yangi mahsulot g'oyasi uchun tannarx / foyda hisoblash — bazaga
            hech narsa saqlanmaydi
          </p>
        </div>
        <button
          onClick={resetAll}
          className="inline-flex items-center justify-center gap-1 h-10 px-3 sm:px-4 rounded-lg border text-sm hover:bg-muted self-start sm:self-auto"
        >
          <RotateCcw className="size-4" /> Tozalash
        </button>
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            <h3 className="font-semibold text-sm">Xomashyo ro'yxati (1 dona uchun)</h3>
            <p className="text-xs text-muted-foreground">
              Har bir xomashyo uchun nomi, miqdori va narxini kiriting — jami
              tannarx pastda avtomatik hisoblanadi
            </p>
          </div>
          <button
            type="button"
            onClick={addLine}
            className="shrink-0 inline-flex items-center gap-1 h-8 px-3 rounded-lg border text-xs hover:bg-muted"
          >
            <Plus className="size-3.5" /> Qo'shish
          </button>
        </div>

        {/* Desktop table */}
        <div className="hidden sm:block">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="text-left font-medium pb-2">Xomashyo nomi</th>
                <th className="text-right font-medium pb-2 w-32">Miqdor</th>
                <th className="text-right font-medium pb-2 w-40">Narx (birlik)</th>
                <th className="text-right font-medium pb-2 w-40">Summa</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {result.rows.map((l) => (
                <tr key={l.key}>
                  <td className="py-1.5 pr-2">
                    <input
                      value={l.name}
                      onChange={(e) => updateLine(l.key, { name: e.target.value })}
                      placeholder="Masalan: Un"
                      className="w-full h-10 rounded-lg border bg-background px-3 text-sm"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      value={l.quantity}
                      onChange={(e) => updateLine(l.key, { quantity: e.target.value })}
                      placeholder="0"
                      inputMode="decimal"
                      className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums text-right"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      value={l.price}
                      onChange={(e) => updateLine(l.key, { price: e.target.value })}
                      placeholder="0"
                      inputMode="decimal"
                      className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums text-right"
                    />
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">
                    {l.subtotal > 0 ? formatMoney(l.subtotal, "UZS") : "—"}
                  </td>
                  <td className="py-1.5">
                    <button
                      type="button"
                      onClick={() => removeLine(l.key)}
                      disabled={lines.length === 1}
                      className="size-9 rounded-lg border grid place-items-center text-muted-foreground hover:text-destructive disabled:opacity-30"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="sm:hidden space-y-2">
          {result.rows.map((l) => (
            <div key={l.key} className="rounded-lg border p-2.5 space-y-2">
              <div className="flex items-center gap-2">
                <input
                  value={l.name}
                  onChange={(e) => updateLine(l.key, { name: e.target.value })}
                  placeholder="Xomashyo nomi"
                  className="flex-1 h-10 rounded-lg border bg-background px-3 text-sm"
                />
                <button
                  type="button"
                  onClick={() => removeLine(l.key)}
                  disabled={lines.length === 1}
                  className="shrink-0 size-10 rounded-lg border grid place-items-center text-muted-foreground hover:text-destructive disabled:opacity-30"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={l.quantity}
                  onChange={(e) => updateLine(l.key, { quantity: e.target.value })}
                  placeholder="Miqdor"
                  inputMode="decimal"
                  className="h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                />
                <input
                  value={l.price}
                  onChange={(e) => updateLine(l.key, { price: e.target.value })}
                  placeholder="Narx"
                  inputMode="decimal"
                  className="h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
                />
              </div>
              {l.subtotal > 0 && (
                <div className="text-xs text-muted-foreground text-right">
                  {formatMoney(l.subtotal, "UZS")}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-3 pt-3 border-t flex items-center justify-between">
          <span className="text-sm font-medium">Tannarx (1 dona)</span>
          <span className="text-lg font-semibold tabular-nums">
            {formatMoney(result.costPerUnit, "UZS")}
          </span>
        </div>
      </div>

      <div className="rounded-xl border bg-card p-3 sm:p-4">
        <h3 className="font-semibold text-sm mb-3">Sotish va foyda</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">
              Sotish narxi (1 dona, so'm)
            </label>
            <input
              value={salePrice}
              onChange={(e) => setSalePrice(e.target.value)}
              placeholder="0"
              inputMode="decimal"
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">
              Kutilayotgan savdo hajmi (dona)
            </label>
            <input
              value={volume}
              onChange={(e) => setVolume(e.target.value)}
              placeholder="0"
              inputMode="decimal"
              className="w-full h-10 rounded-lg border bg-background px-3 text-sm tabular-nums"
            />
          </div>
        </div>

        <div className="mt-4 rounded-xl border bg-muted/30 p-3 sm:p-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-muted-foreground">Foyda (1 dona)</div>
              <div
                className={`text-base font-semibold tabular-nums ${
                  result.marginPerUnit < 0 ? "text-destructive" : "text-emerald-600"
                }`}
              >
                {formatMoney(result.marginPerUnit, "UZS")}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Foyda %</div>
              <div
                className={`text-base font-semibold tabular-nums ${
                  result.marginPerUnit < 0 ? "text-destructive" : "text-emerald-600"
                }`}
              >
                {result.sale > 0 ? `${result.marginPct.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Jami tushum</div>
              <div className="text-base font-semibold tabular-nums">
                {formatMoney(result.totalRevenue, "UZS")}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Jami sof foyda</div>
              <div
                className={`text-base font-semibold tabular-nums ${
                  result.totalProfit < 0 ? "text-destructive" : "text-emerald-600"
                }`}
              >
                {formatMoney(result.totalProfit, "UZS")}
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Jami tushum = sotish narxi × hajm. Jami tannarx = tannarx (1 dona) ×
            hajm ({formatMoney(result.totalCost, "UZS")}). Sof foyda = tushum − tannarx.
          </p>
        </div>

        <p className="text-xs text-muted-foreground mt-3 flex items-start gap-1.5">
          <Calculator className="size-3.5 shrink-0 mt-0.5" />
          Bu — vaqtinchalik hisob-kitob. Hech narsa saqlanmaydi va Mahsulotlar /
          Xomashyo bazasiga ta'sir qilmaydi. G'oya yoqsa, uni "Mahsulotlar"
          bo'limida haqiqiy retsept sifatida qo'shing.
        </p>
      </div>
    </div>
  );
}
