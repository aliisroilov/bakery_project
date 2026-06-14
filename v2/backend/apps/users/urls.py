from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ActivityLogViewSet, EmployeeGroupViewSet, MeView, UserViewSet

app_name = "users"

router = DefaultRouter()
router.register(r"activity", ActivityLogViewSet, basename="activity")
router.register(r"groups", EmployeeGroupViewSet, basename="employeegroup")
router.register(r"", UserViewSet, basename="user")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
] + router.urls
