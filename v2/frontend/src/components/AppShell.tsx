import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  ShoppingCart,
  Store,
  MapPin,
  Wheat,
  Factory,
  Wallet,
  BarChart3,
  Users,
  LogOut,
  Bell,
  Archive,
  Package,
  DollarSign,
  AlertTriangle,
  Activity,
  Menu,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn, formatMoney } from "../lib/utils";

const NAV = [
  { to: "/", label: "Bosh sahifa", icon: LayoutDashboard },
  { to: "/orders", label: "Buyurtmalar", icon: ShoppingCart },
  { to: "/regions", label: "Hududlar", icon: MapPin },
  { to: "/shops", label: "Do'konlar", icon: Store },
  { to: "/products", label: "Mahsulotlar", icon: Package },
  { to: "/inventory", label: "Xomashyo", icon: Wheat },
  { to: "/production", label: "Ishlab chiqarish", icon: Factory },
  { to: "/salary", label: "Oylik", icon: DollarSign },
  { to: "/finance", label: "Kassa / Moliya", icon: Wallet },
  { to: "/reports", label: "Hisobotlar", icon: BarChart3 },
  { to: "/users", label: "Xodimlar", icon: Users },
  { to: "/logs", label: "Loglar", icon: Activity },
  { to: "/archive", label: "Arxiv", icon: Archive },
];

interface LowStockNotification {
  id: number;
  kind: "low_stock";
  ingredient_id: number;
  name: string;
  quantity: string;
  threshold: string;
  unit: string;
}

interface LoanLimitNotification {
  id: number;
  kind: "loan_limit";
  shop_id: number;
  name: string;
  loan_balance_uzs: string;
  loan_limit_uzs: string;
  loan_balance_usd: string;
  loan_limit_usd: string;
  uzs_over: boolean;
  usd_over: boolean;
}

interface NotificationsResponse {
  count: number;
  low_stock: LowStockNotification[];
  loan_limit: LoanLimitNotification[];
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const [bellOpen, setBellOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Auto-close mobile sidebar on route change.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const { data: notifications } = useQuery<NotificationsResponse>({
    queryKey: ["notifications"],
    queryFn: async () =>
      (await api.get<NotificationsResponse>("/notifications/")).data,
    refetchInterval: 30_000,
  });

  const count = notifications?.count ?? 0;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr] lg:grid-cols-[260px_1fr] bg-muted/30">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-50 w-[260px] md:w-auto",
          "border-r bg-card flex flex-col",
          "transform transition-transform md:transform-none",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="h-16 flex items-center justify-between gap-2 px-5 border-b">
          <div className="flex items-center gap-2">
            <div className="size-9 rounded-xl bg-bakery-500 text-white grid place-items-center font-bold">
              S
            </div>
            <div>
              <div className="font-semibold tracking-tight">Sutli-non</div>
              <div className="text-[11px] text-muted-foreground">Boshqaruv v2</div>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-2 rounded-md hover:bg-muted text-muted-foreground"
            aria-label="Menyuni yopish"
          >
            <X className="size-5" />
          </button>
        </div>
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-bakery-500 text-white"
                    : "text-foreground/80 hover:bg-muted",
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t p-3 flex items-center gap-3">
          <div className="size-9 rounded-full bg-bakery-100 text-bakery-700 grid place-items-center font-semibold">
            {user?.display_name?.charAt(0) ?? "?"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">
              {user?.display_name}
            </div>
            <div className="text-[11px] text-muted-foreground capitalize">
              {user?.role}
            </div>
          </div>
          <button
            onClick={logout}
            className="p-2 rounded-md hover:bg-muted text-muted-foreground"
            title="Chiqish"
            aria-label="Chiqish"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>

      <div className="flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 border-b bg-card flex items-center gap-2 px-4 sm:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-2 -ml-2 rounded-md hover:bg-muted text-muted-foreground"
            aria-label="Menyuni ochish"
          >
            <Menu className="size-5" />
          </button>
          <div className="md:hidden flex items-center gap-2">
            <div className="size-8 rounded-lg bg-bakery-500 text-white grid place-items-center font-bold text-sm">
              S
            </div>
            <div className="font-semibold tracking-tight text-sm">Sutli-non</div>
          </div>
          <div className="flex-1" />
          <div className="relative">
            <button
              onClick={() => setBellOpen((v) => !v)}
              className="p-2 rounded-md hover:bg-muted text-muted-foreground relative"
              aria-label="Bildirishnomalar"
            >
              <Bell className="size-5" />
              {count > 0 && (
                <span className="absolute top-0.5 right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-destructive text-white text-[10px] font-semibold grid place-items-center">
                  {count}
                </span>
              )}
            </button>
            {bellOpen && (
              <NotificationsDropdown
                data={notifications}
                onClose={() => setBellOpen(false)}
              />
            )}
          </div>
        </header>
        <main className="p-4 sm:p-5 md:p-6 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

function NotificationsDropdown({
  data,
  onClose,
}: {
  data: NotificationsResponse | undefined;
  onClose: () => void;
}) {
  const hasAny = (data?.count ?? 0) > 0;
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="absolute top-12 right-0 w-[340px] max-w-[calc(100vw-2rem)] bg-card border rounded-xl shadow-lg z-50 overflow-hidden">
        <div className="px-4 py-3 border-b">
          <h3 className="font-semibold text-sm">Bildirishnomalar</h3>
          <p className="text-xs text-muted-foreground">
            Zaxira tugayapti · qarz limitidan oshgan
          </p>
        </div>
        <div className="max-h-[420px] overflow-auto">
          {!hasAny && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Hozir bildirishnoma yo'q 👍
            </div>
          )}
          {data?.low_stock.map((n) => (
            <Link
              key={`ls-${n.id}`}
              to="/inventory"
              onClick={onClose}
              className="flex items-start gap-3 px-4 py-3 border-b hover:bg-muted/30 transition-colors"
            >
              <div className="mt-0.5 size-8 rounded-lg bg-amber-500/15 text-amber-700 grid place-items-center shrink-0">
                <AlertTriangle className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{n.name}</div>
                <div className="text-xs text-muted-foreground">
                  Zaxira: {parseFloat(n.quantity).toFixed(2)} {n.unit} · Minimum:{" "}
                  {parseFloat(n.threshold).toFixed(2)} {n.unit}
                </div>
              </div>
            </Link>
          ))}
          {data?.loan_limit.map((n) => (
            <Link
              key={`ll-${n.id}`}
              to={`/shops/${n.shop_id}`}
              onClick={onClose}
              className="flex items-start gap-3 px-4 py-3 border-b hover:bg-muted/30 transition-colors"
            >
              <div className="mt-0.5 size-8 rounded-lg bg-destructive/15 text-destructive grid place-items-center shrink-0">
                <AlertTriangle className="size-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{n.name}</div>
                <div className="text-xs text-muted-foreground">
                  {n.uzs_over && (
                    <span>
                      UZS: {formatMoney(n.loan_balance_uzs, "UZS")} /{" "}
                      {formatMoney(n.loan_limit_uzs, "UZS")}
                    </span>
                  )}
                  {n.usd_over && (
                    <span className={n.uzs_over ? "ml-2" : ""}>
                      USD: {formatMoney(n.loan_balance_usd, "USD")} /{" "}
                      {formatMoney(n.loan_limit_usd, "USD")}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}
