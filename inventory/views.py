from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import Ingredient, Purchase, Production
from .forms import IngredientForm, PurchaseForm, ProductionForm
from reports.models import Purchase as ReportPurchase
from decimal import Decimal


def inventory_dashboard(request):
    # All ingredients with their units
    ingredients = Ingredient.objects.select_related("unit").all().order_by("name")

    # Latest purchases and productions — use "date" instead of "created_at"
    recent_purchases = Purchase.objects.select_related("ingredient").order_by("-date")[:5]
    recent_productions = Production.objects.select_related("product").order_by("-date")[:5]

    # Low stock detection
    low_stock_ingredients = [
        ing for ing in ingredients
        if ing.quantity <= ing.low_stock_threshold
    ]


    context = {
        "ingredients": ingredients,
        "recent_purchases": recent_purchases,
        "recent_productions": recent_productions,
        "low_stock_ingredients": low_stock_ingredients,
    }

    return render(request, "inventory/dashboard.html", context)



# 🧂 Ingredient List + Create
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


# 🛒 Purchase Create (Fixed)
def purchase_create(request):
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save()  # just save, do NOT touch ingredient.quantity

            # 🔹 Add record to reports
            try:
                total_price = purchase.price or Decimal("0")
                ReportPurchase.objects.create(
                    item_name=f"{purchase.ingredient.name} ({purchase.quantity} {purchase.ingredient.unit.short or purchase.ingredient.unit.name})",
                    unit_price=total_price,
                    purchase_date=purchase.date.date(),
                    notes=purchase.note or "Omborga ingredient xaridi",
                )
            except Exception as e:
                print(f"[Reports Sync Error] Could not record purchase: {e}")

            messages.success(request, "✅ Xarid muvaffaqiyatli qo‘shildi!")
            return redirect("inventory:purchase_list")
    else:
        form = PurchaseForm()

    return render(request, "inventory/purchase_form.html", {"form": form})

# 🗑️ Purchase Delete
def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST__":
        with transaction.atomic():
            purchase.delete()  # ✅ Signals will automatically decrease stock & restore balance
        messages.success(request, "🛒 Xarid o‘chirildi.")
        return redirect("inventory:purchase_list")

    return render(request, "inventory/confirm_delete.html", {"object": purchase})


# 🏭 Production List
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
            
            # Apply ingredient consumption according to recipe
            production.apply_consumption()

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
