from django import forms
from .models import Category, Purchase

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]

class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['category', 'item_name', 'unit_price', 'purchase_date', 'notes']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'w-full border rounded px-4 py-2 focus:ring-2 focus:ring-orange-300 focus:outline-none'
            }),
            'item_name': forms.TextInput(attrs={
                'class': 'w-full border rounded px-4 py-2 focus:ring-2 focus:ring-orange-300 focus:outline-none'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'w-full border rounded px-4 py-2 focus:ring-2 focus:ring-orange-300 focus:outline-none'
            }),
            'purchase_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full border rounded px-4 py-2 focus:ring-2 focus:ring-orange-300 focus:outline-none'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full border rounded px-4 py-2 focus:ring-2 focus:ring-orange-300 focus:outline-none',
                'rows': 3,
                'placeholder': 'Optional notes'
            }),
        }
