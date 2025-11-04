from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import Ingredient, Purchase, Production, DailyBakeryProduction, BakeryProductStock, InventoryRevisionReport
from .forms import IngredientForm, PurchaseForm, ProductionForm, DailyBakeryProductionForm, InventoryRevisionForm
from reports.models import Purchase as ReportPurchase
from django.forms import formset_factory
from decimal import Decimal


# 🏠 Inventory Dashboard
def inventory_dashboard(request):
    ingredients = Ingredient.objects.select_related("unit").all().order_by("name")
    bakery_products = BakeryProductStock.objects.select_related("product").all().order_by("-pinned", "product__name")
    recent_purchases = Purchase.objects.select_related("ingredient").order_by("-date")[:5]
    recent_productions = Production.objects.select_related("product").order_by("-date")[:5]

    low_stock_ingredients = [ing for ing in ingredients if ing.quantity <= ing.low_stock_threshold]

    context = {
        "ingredients": ingredients,
        "bakery_stocks": bakery_products,
        "recent_purchases": recent_purchases,
        "recent_bakery_productions": recent_productions,
        "low_stock_ingredients": low_stock_ingredients,
    }
    return render(request, "inventory/dashboard.html", context)


# 🧂 Ingredient List + Create
def ingredient_list(request):
    ingredients = Ingredient.objects.select_related("unit").all().order_by("name")
    form = IngredientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "🧂 Yangi ingredient qo‘shildi!")
        return redirect("inventory:ingredient_list")
    return render(request, "inventory/ingredient_list.html", {"ingredients": ingredients, "form": form})


# ✏️ Ingredient Edit
def ingredient_edit(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)
    form = IngredientForm(request.POST or None, instance=ing)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "✅ Ingredient tahrirlandi!")
        return redirect("inventory:ingredient_list")
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
    form = PurchaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        purchase = form.save()  # don't touch stock directly

        # Sync with reports
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
    return render(request, "inventory/purchase_form.html", {"form": form})


# 🗑️ Purchase Delete
def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST":
        with transaction.atomic():
            purchase.delete()
        messages.success(request, "🛒 Xarid o‘chirildi.")
        return redirect("inventory:purchase_list")
    return render(request, "inventory/confirm_delete.html", {"object": purchase})


# 🏭 Production List
def production_list(request):
    productions = Production.objects.select_related("product").order_by("-date")
    return render(request, "inventory/production_list.html", {"productions": productions})


# 🏭 Production Create (updated: deduct ingredients + add to bakery stock)
def production_create(request):
    form = ProductionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        production = form.save(commit=False)
        production.date = timezone.now()
        production.save()

        # Deduct ingredients according to recipe
        production.apply_consumption()

        # Add to bakery stock (meshok = finished product quantity)
        stock, _ = BakeryProductStock.objects.get_or_create(
            product=production.product,
            defaults={"quantity": Decimal("0.000"), "pinned": True}
        )
        stock.quantity += production.meshok
        stock.save(update_fields=["quantity"])

        messages.success(request, "🏭 Ishlab chiqarish muvaffaqiyatli qo‘shildi!")
        return redirect("inventory:production_history")

    return render(request, "inventory/production_form.html", {"form": form})


# 🏭 Daily Bakery Production (manager-entered finished products)
def daily_production_entry(request):
    form = DailyBakeryProductionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        production = form.save(commit=False)
        production.save()

        # Update bakery stock
        stock, _ = BakeryProductStock.objects.get_or_create(
            product=production.product,
            defaults={"quantity": Decimal("0.000"), "pinned": True}
        )
        stock.quantity += production.quantity_produced
        stock.save(update_fields=["quantity"])

        messages.success(request, "✅ Bugungi mahsulot miqdori muvaffaqiyatli kiritildi.")
        return redirect("inventory:inventory_dashboard")

    recent_entries = DailyBakeryProduction.objects.select_related("product").order_by("-date")[:10]
    stocks = BakeryProductStock.objects.select_related("product").order_by("-pinned", "product__name")
    return render(request, "inventory/daily_production_entry.html", {"form": form, "recent_entries": recent_entries, "stocks": stocks})


# 🗑️ Production Delete
def production_delete(request, pk):
    prod = get_object_or_404(Production, pk=pk)
    if request.method == "POST":
        prod.delete()
        messages.success(request, "🏭 Ishlab chiqarish o‘chirildi.")
        return redirect("inventory:production_history")
    return render(request, "inventory/confirm_delete.html", {"object": prod})



def inventory_revision(request):
    # Prepare initial data for formset
    ingredients = Ingredient.objects.all()
    bakery_stocks = BakeryProductStock.objects.select_related('product').all()

    initial_data = []

    for ing in ingredients:
        initial_data.append({
            'item_type': 'ingredient',
            'item_id': ing.id,
            'name': ing.name,
            'current_quantity': ing.quantity,
            'new_quantity': ing.quantity,
        })

    for stock in bakery_stocks:
        initial_data.append({
            'item_type': 'product',
            'item_id': stock.product.id,
            'name': stock.product.name,
            'current_quantity': stock.quantity,
            'new_quantity': stock.quantity,
        })

    RevisionFormSet = formset_factory(InventoryRevisionForm, extra=0)
    if request.method == 'POST':
        formset = RevisionFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                item_type = form.cleaned_data['item_type']
                item_id = form.cleaned_data['item_id']
                new_qty = form.cleaned_data['new_quantity']
                note = form.cleaned_data.get('note', '')

                if item_type == 'ingredient':
                    item = Ingredient.objects.get(id=item_id)
                else:
                    item = BakeryProductStock.objects.get(product_id=item_id)

                old_qty = item.quantity
                if Decimal(new_qty) != old_qty:
                    item.quantity = Decimal(new_qty)
                    item.save(update_fields=['quantity'])
                    InventoryRevisionReport.objects.create(
                        item_type=item_type,
                        ingredient=item if item_type == 'ingredient' else None,
                        product=item.product if item_type == 'product' else None,
                        old_quantity=old_qty,
                        new_quantity=Decimal(new_qty),
                        note=note,
                        user=request.user
                    )
            return redirect('inventory:inventory_revision')
    else:
        formset = RevisionFormSet(initial=initial_data)

    return render(request, 'inventory/inventory_revision.html', {'formset': formset})
