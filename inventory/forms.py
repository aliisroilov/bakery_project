from decimal import Decimal
from django.db import transaction
from django import forms
from .models import Ingredient, Purchase, Production, DailyBakeryProduction
from django.apps import apps

class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'quantity', 'unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Ingredient name'}),
            'quantity': forms.NumberInput(attrs={'step': '0.001'}),
            'unit': forms.Select(),
        }


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['ingredient', 'quantity', 'price', 'note']
        widgets = {
            'ingredient': forms.Select(),
            'quantity': forms.NumberInput(attrs={'step': '0.001'}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'note': forms.Textarea(attrs={'rows': 2}),
        }

class ProductionForm(forms.ModelForm):
    class Meta:
        model = Production
        fields = ['product', 'meshok', 'note']
        labels = {
            'product': 'Mahsulot',
            'meshok': 'Qop soni',  # 👈 show “Qop” instead of “Meshok”
            'note': 'Izoh',
        }

    def save(self, commit=True):
        """
        Save Production and apply consumption of ingredients.
        """
        from django.db import transaction
        production = super().save(commit=False)
        if commit:
            with transaction.atomic():
                production.save()
                production.apply_consumption()
        return production

class DailyBakeryProductionForm(forms.ModelForm):
    class Meta:
        model = DailyBakeryProduction
        fields = ["product", "quantity_produced", "note"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 2}),
        }


class InventoryRevisionForm(forms.Form):
    """Form for manual inventory revision - adjusting stock quantities."""
    item_type = forms.CharField(widget=forms.HiddenInput())
    item_id = forms.IntegerField(widget=forms.HiddenInput())
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'readonly': 'readonly',
            'class': 'cursor-not-allowed bg-gray-50'
        })
    )
    current_quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        widget=forms.NumberInput(attrs={
            'readonly': 'readonly',
            'class': 'cursor-not-allowed bg-gray-50'
        })
    )
    new_quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'step': '0.001',
            'min': '0'
        })
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        help_text='Optional: Explain why the quantity is being changed'
    )

    def clean_new_quantity(self):
        """Validate new quantity is non-negative."""
        new_qty = self.cleaned_data.get('new_quantity')
        if new_qty is not None and new_qty < 0:
            raise forms.ValidationError("Miqdor manfiy bo'lishi mumkin emas!")
        return new_qty