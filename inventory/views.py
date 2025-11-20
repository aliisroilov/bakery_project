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
        # Just save - the model's save() method handles stock updates automatically
        production = form.save()
        
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
    """
    Manual inventory revision - update quantities for ingredients and products.
    Creates comprehensive audit trail in InventoryRevisionReport.

    Features:
    - Displays all ingredients and bakery products
    - Allows quantity adjustments with notes
    - Creates audit trail for all changes
    - Atomic transaction ensures data consistency
    - Validates quantities are non-negative
    """
    import logging
    logger = logging.getLogger(__name__)

    # Prepare initial data for formset
    ingredients = Ingredient.objects.all().order_by('name')
    bakery_stocks = BakeryProductStock.objects.select_related('product').all().order_by('product__name')

    initial_data = []

    # Add all ingredients
    for ing in ingredients:
        initial_data.append({
            'item_type': 'ingredient',
            'item_id': ing.id,
            'name': ing.name,
            'current_quantity': ing.quantity,
            'new_quantity': ing.quantity,
        })

    # Add all bakery product stocks
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
            updated_count = 0
            errors = []

            with transaction.atomic():
                for form in formset:
                    item_type = form.cleaned_data.get('item_type')
                    item_id = form.cleaned_data.get('item_id')
                    new_qty = form.cleaned_data.get('new_quantity')
                    note = form.cleaned_data.get('note', '').strip()

                    # Skip if essential data is missing
                    if not item_type or not item_id or new_qty is None:
                        continue

                    try:
                        # Get the item with row-level lock
                        if item_type == 'ingredient':
                            item = Ingredient.objects.select_for_update().get(id=item_id)
                            item_name = item.name
                        else:  # product
                            stock = BakeryProductStock.objects.select_for_update().get(product_id=item_id)
                            item = stock
                            item_name = stock.product.name

                        # Get old quantity
                        old_qty = item.quantity

                        # Only update if quantity changed
                        if Decimal(str(new_qty)) != old_qty:
                            # Validate quantity is non-negative
                            if new_qty < 0:
                                errors.append(f"{item_name}: Miqdor manfiy bo'lishi mumkin emas")
                                continue

                            # Update quantity
                            item.quantity = Decimal(str(new_qty))
                            item.save(update_fields=['quantity'])

                            # Create audit log
                            InventoryRevisionReport.objects.create(
                                item_type=item_type,
                                ingredient=item if item_type == 'ingredient' else None,
                                product=stock.product if item_type == 'product' else None,
                                old_quantity=old_qty,
                                new_quantity=Decimal(str(new_qty)),
                                note=note or f"Qo'lda o'zgartirildi: {old_qty} → {new_qty}",
                                user=request.user
                            )
                            updated_count += 1
                            logger.info(
                                f"Inventory revised: {item_type} '{item_name}' "
                                f"{old_qty} → {new_qty} by {request.user.username}"
                            )

                    except Ingredient.DoesNotExist:
                        errors.append(f"Ingredient ID {item_id} topilmadi")
                        logger.error(f"Ingredient {item_id} not found during revision")
                        continue
                    except BakeryProductStock.DoesNotExist:
                        errors.append(f"Product stock ID {item_id} topilmadi")
                        logger.error(f"Product stock {item_id} not found during revision")
                        continue
                    except Exception as e:
                        errors.append(f"Xatolik: {str(e)}")
                        logger.exception(f"Error during inventory revision: {e}")
                        continue

            # Show appropriate messages
            if errors:
                for error in errors:
                    messages.error(request, f"❌ {error}")

            if updated_count > 0:
                messages.success(
                    request,
                    f"✅ {updated_count} ta element muvaffaqiyatli yangilandi va audit log yaratildi!"
                )
            elif not errors:
                messages.info(request, "ℹ️ Hech qanday o'zgarish kiritilmadi.")

            return redirect('inventory:inventory_revision')
        else:
            # Form validation errors
            messages.error(request, "❌ Formada xatoliklar mavjud. Iltimos, qizil rangdagi maydonlarni tekshiring.")
            # Log formset errors for debugging
            for i, form in enumerate(formset):
                if form.errors:
                    logger.error(f"Revision form {i} errors: {form.errors}")
    else:
        # GET request - create fresh formset
        formset = RevisionFormSet(initial=initial_data)

    context = {
        'formset': formset,
        'total_items': len(initial_data),
        'ingredient_count': ingredients.count(),
        'product_count': bakery_stocks.count(),
    }
    return render(request, 'inventory/inventory_revision.html', context)