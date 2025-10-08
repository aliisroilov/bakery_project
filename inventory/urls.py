from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.inventory_dashboard, name="inventory_dashboard"),  # 👈 matches your template
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/<int:pk>/edit/", views.ingredient_edit, name="ingredient_edit"),
    path("ingredients/<int:pk>/delete/", views.ingredient_delete, name="ingredient_delete"),

    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/add/", views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/delete/", views.purchase_delete, name="purchase_delete"),

    path("productions/", views.production_list, name="production_history"),
    path("productions/add/", views.production_create, name="production_create"),
    path("productions/<int:pk>/delete/", views.production_delete, name="production_delete"),
]
