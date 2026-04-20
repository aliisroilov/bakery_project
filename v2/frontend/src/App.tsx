import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ShopsPage } from "./pages/ShopsPage";
import { ShopDetailPage } from "./pages/ShopDetailPage";
import { ProductsPage } from "./pages/ProductsPage";
import { OrdersPage } from "./pages/OrdersPage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { KassaPage } from "./pages/KassaPage";
import { InventoryPage } from "./pages/InventoryPage";
import { ProductionPage } from "./pages/ProductionPage";
import { SalaryPage } from "./pages/SalaryPage";
import { UsersPage } from "./pages/UsersPage";
import { ArchivePage } from "./pages/ArchivePage";
import { ReportsPage } from "./pages/ReportsPage";
import { LogsPage } from "./pages/LogsPage";

function Protected({ children }: { children: React.ReactNode }) {
  const user = useAuth((s) => s.user);
  const loading = useAuth((s) => s.loading);
  const location = useLocation();
  if (loading) {
    return (
      <div className="h-screen grid place-items-center text-muted-foreground">
        Yuklanmoqda…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  const loadMe = useAuth((s) => s.loadMe);
  useEffect(() => {
    loadMe();
  }, [loadMe]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/orders" element={<Protected><OrdersPage /></Protected>} />
      <Route path="/orders/:id" element={<Protected><OrderDetailPage /></Protected>} />
      <Route path="/shops" element={<Protected><ShopsPage /></Protected>} />
      <Route path="/shops/:id" element={<Protected><ShopDetailPage /></Protected>} />
      <Route path="/products" element={<Protected><ProductsPage /></Protected>} />
      <Route path="/finance" element={<Protected><KassaPage /></Protected>} />
      <Route path="/inventory" element={<Protected><InventoryPage /></Protected>} />
      <Route path="/production" element={<Protected><ProductionPage /></Protected>} />
      <Route path="/salary" element={<Protected><SalaryPage /></Protected>} />
      <Route path="/users" element={<Protected><UsersPage /></Protected>} />
      <Route path="/archive" element={<Protected><ArchivePage /></Protected>} />
      <Route path="/reports" element={<Protected><ReportsPage /></Protected>} />
      <Route path="/logs" element={<Protected><LogsPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
