from django.urls import path
from . import views

urlpatterns = [
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/confirm/", views.confirm_delivery, name="confirm_delivery"),
    path('<int:order_id>/mark_fully_delivered/', views.mark_fully_delivered, name='mark_fully_delivered'),
]
