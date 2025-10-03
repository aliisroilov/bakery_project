from django.urls import path
from . import views
from dashboard.views import viewer_dashboard
from .views import CustomLoginView

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path('logout/', views.user_logout, name='logout'),
    path("admins/dashboard/", viewer_dashboard, name="viewer_dashboard"),
]
