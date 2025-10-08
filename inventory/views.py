from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Ingredient, Purchase, Production
from .forms import IngredientForm, PurchaseForm, ProductionForm


def inventory_dashboard(request):
    ingredients = Ingredient.objects.select_related("unit").all().order_by("name")
    
    recent_purchases = Purchase.objects.select_related("ingredient").order_by("-date")[:5]
    recent_productions = Production.objects.select_related("product").order_by("-date")[:5]

    return render(request, "inventory/dashboard.html", {
        "ingredients": ingredients,
        "recent_purchases": recent_purchases,
        "recent_productions": recent_productions,
    })


# Ingredient List + Create
def ingredient_list(request):
    ingredients = Ingredient.objects.select_related("unit").all().order_by("name")

    if request.method == "POST":
        form = IngredientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "🧂 Yangi ingredient qo‘shildi!")
            return redirect("inventory:ingredient_list")
    else:
        form = IngredientForm()

    return render(request, "inventory/ingredient_list.html", {
        "ingredients": ingredients,
        "form": form,
    })


# ✏️ Ingredient Edit
def ingredient_edit(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)
    if request.method == "POST":
        form = IngredientForm(request.POST, instance=ing)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Ingredient tahrirlandi!")
            return redirect("inventory:ingredient_list")
    else:
        form = IngredientForm(instance=ing)
    return render(request, "inventory/ingredient_list.html", {
        "form": form,
        "ingredient": ing,
        "ingredients": Ingredient.objects.all()
    })


# 🗑️ Ingredient Delete
def ingredient_delete(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)
    if request.method == "POST":
        ing.delete()
        messages.success(request, "🧂 Ingredient o‘chirildi.")
        return redirect("inventory:ingredient_list")
    return render(request, "inventory/confirm_delete.html", {"object": ing})


# 🛒 Purchase List
def purchase_list(request):
    purchases = Purchase.objects.select_related("ingredient", "ingredient__unit").order_by("-date")
    return render(request, "inventory/purchase_list.html", {"purchases": purchases})


# 🛒 Purchase Create
def purchase_create(request):
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                purchase = form.save()
                # increase ingredient stock
                ing = purchase.ingredient
                ing.quantity = F("quantity") + purchase.quantity
                ing.save(update_fields=["quantity"])

            messages.success(request, "✅ Xarid muvaffaqiyatli qo‘shildi!")
            return redirect("inventory:purchase_list")
    else:
        form = PurchaseForm()

    return render(request, "inventory/purchase_form.html", {"form": form})


# 🛒 Purchase Edit



# 🗑️ Purchase Delete
def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST":
        with transaction.atomic():
            purchase.ingredient.quantity = F("quantity") - purchase.quantity
            purchase.ingredient.save(update_fields=["quantity"])
            purchase.delete()
        messages.success(request, "🛒 Xarid o‘chirildi.")
        return redirect("inventory:purchase_list")

    return render(request, "inventory/confirm_delete.html", {"object": purchase})


# 🏭 Production List (History)
def production_list(request):
    productions = Production.objects.select_related("product").order_by("-date")
    return render(request, "inventory/production_list.html", {"productions": productions})


# 🏭 Production Create
def production_create(request):
    if request.method == "POST":
        form = ProductionForm(request.POST)
        if form.is_valid():
            production = form.save(commit=False)
            production.date = timezone.now()
            production.save()

            # You can later link recipe logic here if needed
            messages.success(request, "🏭 Ishlab chiqarish muvaffaqiyatli qo‘shildi!")
            return redirect("inventory:production_history")
    else:
        form = ProductionForm()
    return render(request, "inventory/production_form.html", {"form": form})


# 🗑️ Production Delete
def production_delete(request, pk):
    prod = get_object_or_404(Production, pk=pk)
    if request.method == "POST":
        prod.delete()
        messages.success(request, "🏭 Ishlab chiqarish o‘chirildi.")
        return redirect("inventory:production_history")
    return render(request, "inventory/confirm_delete.html", {"object": prod})
