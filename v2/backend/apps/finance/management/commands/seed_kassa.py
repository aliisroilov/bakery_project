"""Seed the two canonical Kassa accounts: Seyf + Rizoxon."""
from django.core.management.base import BaseCommand

from apps.finance.models import KassaAccount


class Command(BaseCommand):
    help = "Create Seyf and Rizoxon kassa accounts if they don't exist."

    DEFAULTS = [
        {
            "slug": KassaAccount.SEYF,
            "name": "Seyf",
            "description": "Asosiy pul saqlash joyi (Seyf).",
        },
        {
            "slug": KassaAccount.RIZOXON,
            "name": "Rizoxon",
            "description": "Rizoxon qo'lidagi pul.",
        },
    ]

    def handle(self, *args, **options):
        for entry in self.DEFAULTS:
            obj, created = KassaAccount.objects.get_or_create(
                slug=entry["slug"],
                defaults={
                    "name": entry["name"],
                    "description": entry["description"],
                },
            )
            verb = "Created" if created else "Exists"
            self.stdout.write(f"{verb}: {obj.name}")
