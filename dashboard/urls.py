from django.urls import path
from . import views
from .views import loan_repayment_view
from dashboard.views import db_check 

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('districts/', views.districts_view, name='districts'),
    path('districts/<int:district_id>/', views.district_detail_view, name='district_detail'),
    path('loan-repayment/', views.loan_repayment_view, name='loan_repayment'),
    path("admins/", views.viewer_dashboard, name="viewer_dashboard"),
    path("db-check/", db_check),
]