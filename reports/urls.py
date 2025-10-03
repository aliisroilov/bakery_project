from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path("", views.reports_home, name='reports_home'),
    path('sales/', views.sales_report, name='sales_report'),
    path('all/', views.all_reports, name='all_reports'),

    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_update"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    # Purchase CRUD
    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/add/", views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/edit/", views.purchase_update, name="purchase_update"),
    path("purchases/<int:pk>/delete/", views.purchase_delete, name="purchase_delete"),

    # Purchases Report
    path("purchases/report/", views.purchase_list, name="purchase_list"),
    path("contragents/", views.contragents_report, name="contragents_report"),
    
]
