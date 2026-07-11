// Shared API response types (hand-maintained — swap to openapi-typescript once we stabilize).

export type Currency = "UZS" | "USD";

export interface KassaAccount {
  id: number;
  slug: string;
  name: string;
  description: string;
  balance_uzs: string;
  balance_usd: string;
}

export interface DashboardSummary {
  date?: string;
  is_today?: boolean;
  accounts: KassaAccount[];
  kirim_today: {
    uzs: string;
    usd: string;
    by_collector: {
      user_id: number | null;
      name: string;
      uzs: string;
      usd: string;
    }[];
  };
  production: {
    today: { meshok: string; units: string };
    month: { meshok: string; units: string };
    today_by_product: {
      product_id: number;
      product_name: string;
      meshok: string;
      units: string;
    }[];
  };
  urgent_orders: {
    id: number;
    shop_name: string;
    priority: string;
    delivery_time: string | null;
    order_date: string;
    status: string;
  }[];
  over_loan_limit: {
    id: number;
    name: string;
    loan_balance_uzs: string;
    loan_balance_usd: string;
    loan_limit_uzs: string;
    loan_limit_usd: string;
  }[];
  open_orders_count: number;
  orders_today: {
    total: number;
    pending: number;
    partial: number;
    delivered: number;
  };
  loans_total: {
    uzs: string;
    usd: string;
  };
  net_income_today: {
    uzs: string;
    usd: string;
    revenue_uzs: string;
    revenue_usd: string;
    expenses_uzs: string;
    expenses_usd: string;
    breakdown: {
      purchases_uzs: string;
      purchases_usd: string;
      general_expenses_uzs: string;
      general_expenses_usd: string;
      salary_uzs: string;
      salary_usd: string;
    };
  };
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Region {
  id: number;
  name: string;
  note: string;
  is_archived: boolean;
  shop_count: number;
  created_at: string;
}

export interface RegionTodayStats {
  id: number;
  name: string;
  note: string;
  shop_count: number;
  date: string;
  total: number;
  pending: number;
  partial: number;
  delivered: number;
  cancelled: number;
}

export interface Shop {
  id: number;
  name: string;
  owner_name: string;
  phone: string;
  address: string;
  region: number;
  region_name: string;
  assigned_driver: number | null;
  assigned_driver_name: string | null;
  loan_balance_uzs: string;
  loan_balance_usd: string;
  loan_limit_uzs: string;
  loan_limit_usd: string;
  limit_exceeded_uzs: boolean;
  limit_exceeded_usd: boolean;
  is_archived: boolean;
  created_at: string;
}

export interface ShopProductPrice {
  id: number;
  shop: number;
  product: number;
  product_name: string;
  currency: Currency;
  price: string;
  note: string;
  created_at: string;
}

export interface ShopDetail extends Shop {
  product_prices: ShopProductPrice[];
}

export interface Product {
  id: number;
  name: string;
  description: string;
  default_price_uzs: string;
  default_price_usd: string;
  production_salary_per_unit_uzs: string;
  cost_price_uzs: string;
  cost_price_updated_at: string | null;
  meshok_size: string;
  stock_quantity: string;
  is_archived: boolean;
  created_at: string;
}

export type OrderStatus = "pending" | "partial" | "delivered" | "cancelled";
export type OrderPriority = "low" | "normal" | "high" | "urgent";

export interface OrderItem {
  id: number;
  order: number;
  product: number;
  product_name: string;
  unit_price: string;
  quantity: number;
  delivered_quantity: number;
  returned_quantity: number;
  net_delivered: number;
  total_price: string;
  delivered_price: string;
}

export interface Order {
  id: number;
  shop: number;
  shop_name: string;
  order_date: string;
  delivery_time: string | null;
  priority: OrderPriority;
  priority_display: string;
  status: OrderStatus;
  status_display: string;
  currency: Currency;
  created_at: string;
  total_amount: string;
  delivered_amount: string;
  item_count: number;
}

export interface OrderDetail extends Order {
  items: OrderItem[];
  note: string;
  created_by: number | null;
  created_by_name: string;
}

export interface Payment {
  id: number;
  shop: number;
  shop_name: string;
  order: number | null;
  order_date: string | null;
  payment_type: "collection" | "loan_repayment" | "other";
  payment_type_display: string;
  currency: Currency;
  amount: string;
  discount: string;
  account: number;
  account_name: string;
  collected_by: number | null;
  collected_by_name: string;
  received_at: string;
  note: string;
  created_at: string;
}
