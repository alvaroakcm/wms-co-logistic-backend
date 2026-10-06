from django.core.management.base import BaseCommand

from apps.servicios.technical import run_scheduled_backup


class Command(BaseCommand):
    help = "Ejecuta el respaldo programado de EP-08 si alcanzó su fecha prevista."

    def handle(self, *args, **options):
        backup = run_scheduled_backup()
        if backup is None:
            self.stdout.write("No existe un respaldo programado pendiente.")
            return
        if backup.valido:
            self.stdout.write(self.style.SUCCESS(f"Respaldo {backup.id_respaldo} generado."))
        else:
            self.stdout.write(self.style.ERROR(f"Respaldo {backup.id_respaldo} falló: {backup.resultado}"))
