from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("data/", views.ReportsDataView.as_view(), name="data"),
    path("payments.xlsx", views.PaymentsExportView.as_view(), name="payments-export"),
    path("orders.xlsx", views.OrdersExportView.as_view(), name="orders-export"),
    path("production.xlsx", views.ProductionExportView.as_view(), name="production-export"),
    path("expenses.xlsx", views.ExpensesExportView.as_view(), name="expenses-export"),
    path("salary.xlsx", views.SalaryExportView.as_view(), name="salary-export"),
    path("shop-debts.xlsx", views.ShopDebtsExportView.as_view(), name="shop-debts-export"),
    path("pnl-daily.xlsx", views.PnlDailyExportView.as_view(), name="pnl-daily-export"),
    path("gross-overall.xlsx", views.GrossOverallExportView.as_view(), name="gross-overall-export"),
    path("gross-daily/", views.GrossDailyView.as_view(), name="gross-daily"),
    path("cos/", views.CosBreakdownView.as_view(), name="cos"),
    path("sofp/", views.SofpView.as_view(), name="sofp"),
]
