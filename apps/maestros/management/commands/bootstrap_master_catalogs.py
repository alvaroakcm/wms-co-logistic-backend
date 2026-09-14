from django.core.management.base import BaseCommand
from django.db import transaction

from apps.maestros.models import CategoriaProducto, UnidadMedida


UNITS = {
    "UND": "Unidad",
    "CJ": "Caja",
    "KG": "Kilogramo",
    "PLT": "Pallet",
}


class Command(BaseCommand):
    help = "Crea las unidades y categoría inicial requeridas por Productos."

    def handle(self, *args, **options):
        with transaction.atomic():
            CategoriaProducto.objects.update_or_create(
                nombre="General",
                defaults={
                    "descripcion": "Productos sin una categoría especializada.",
                    "estado": True,
                },
            )
            for code, name in UNITS.items():
                UnidadMedida.objects.update_or_create(
                    codigo=code,
                    defaults={"nombre": name, "estado": True},
                )
        self.stdout.write(self.style.SUCCESS("Catálogos maestros inicializados."))
