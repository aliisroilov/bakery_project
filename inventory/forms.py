from decimal import Decimal
from django.db import transaction
from django import forms
from .models import Ingredient, Purchase, Production
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
