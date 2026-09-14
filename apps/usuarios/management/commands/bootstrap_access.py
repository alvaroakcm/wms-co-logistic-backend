from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.usuarios.models import Permiso, Rol, RolPermiso, Usuario, UsuarioRol


PERMISSIONS = {
    "dashboard.ver": "Acceder al panel principal del WMS.",
    "usuarios.ver": "Consultar el módulo y listado de usuarios.",
    "usuarios.crear": "Registrar usuarios en Supabase Auth y el WMS.",
    "usuarios.editar": "Actualizar la información de los usuarios.",
    "usuarios.desactivar": "Desactivar y reactivar cuentas de usuario.",
    "usuarios.asignar_roles": "Asignar roles de acceso a los usuarios.",
    "roles.ver": "Consultar roles y permisos.",
    "roles.gestionar": "Crear y actualizar roles y sus permisos.",
    "productos.ver": "Consultar y filtrar el catálogo de productos.",
    "productos.crear": "Registrar productos en el catálogo maestro.",
    "productos.editar": "Actualizar productos sin reemplazar su identidad.",
    "clientes.ver": "Consultar el catálogo de clientes.",
    "clientes.crear": "Registrar clientes en el catálogo maestro.",
    "clientes.editar": "Actualizar clientes sin reemplazar su identidad.",
    "almacenes.ver": "Consultar almacenes del WMS.",
    "almacenes.crear": "Registrar almacenes del WMS.",
    "ubicaciones.ver": "Consultar zonas, ubicaciones y su ocupación.",
    "ubicaciones.crear": "Registrar zonas y ubicaciones.",
    "ubicaciones.editar": "Actualizar o desactivar ubicaciones sin stock.",
    "importaciones.ejecutar": "Importar catálogos maestros desde plantillas.",
}


class Command(BaseCommand):
    help = "Crea el acceso base y asigna Administrador TI a un usuario existente."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", required=True)

    def handle(self, *args, **options):
        email = options["admin_email"].strip().lower()
        try:
            user = Usuario.objects.get(correo__iexact=email)
        except Usuario.DoesNotExist as exc:
            raise CommandError(
                f"No existe un perfil WMS para {email}."
            ) from exc

        with transaction.atomic():
            permission_ids = []
            for name, description in PERMISSIONS.items():
                permission, _ = Permiso.objects.update_or_create(
                    nombre=name,
                    defaults={"descripcion": description, "estado": True},
                )
                permission_ids.append(permission.id_permiso)

            role, _ = Rol.objects.update_or_create(
                nombre="Administrador TI",
                defaults={
                    "descripcion": "Administración de usuarios, roles y accesos.",
                    "estado": True,
                },
            )
            RolPermiso.objects.filter(id_rol=role.id_rol).exclude(
                id_permiso__in=permission_ids
            ).delete()
            for permission_id in permission_ids:
                RolPermiso.objects.get_or_create(
                    id_rol=role.id_rol, id_permiso=permission_id
                )
            UsuarioRol.objects.get_or_create(
                id_usuario=user.id_usuario, id_rol=role.id_rol
            )

            operations_role, _ = Rol.objects.update_or_create(
                nombre="Jefe de Operaciones",
                defaults={
                    "descripcion": "Gestión de productos y clientes maestros.",
                    "estado": True,
                },
            )
            operations_permissions = Permiso.objects.filter(
                nombre__in=[
                    "productos.ver",
                    "productos.crear",
                    "productos.editar",
                    "clientes.ver",
                    "clientes.crear",
                    "clientes.editar",
                    "almacenes.ver",
                    "almacenes.crear",
                    "ubicaciones.ver",
                    "ubicaciones.crear",
                    "ubicaciones.editar",
                ]
            )
            for permission in operations_permissions:
                RolPermiso.objects.get_or_create(
                    id_rol=operations_role.id_rol,
                    id_permiso=permission.id_permiso,
                )

            operator_role, _ = Rol.objects.update_or_create(
                nombre="Operario de almacén",
                defaults={
                    "descripcion": "Consulta operativa del catálogo de productos.",
                    "estado": True,
                },
            )
            product_view_permission = Permiso.objects.get(nombre="productos.ver")
            location_view_permission = Permiso.objects.get(
                nombre="ubicaciones.ver"
            )
            for permission in (product_view_permission, location_view_permission):
                RolPermiso.objects.get_or_create(
                    id_rol=operator_role.id_rol,
                    id_permiso=permission.id_permiso,
                )

            management_role, _ = Rol.objects.update_or_create(
                nombre="Gerencia",
                defaults={
                    "descripcion": "Consulta ejecutiva de clientes y catálogos.",
                    "estado": True,
                },
            )
            client_view_permission = Permiso.objects.get(nombre="clientes.ver")
            RolPermiso.objects.get_or_create(
                id_rol=management_role.id_rol,
                id_permiso=client_view_permission.id_permiso,
            )

            forklift_role, _ = Rol.objects.update_or_create(
                nombre="Montacarguista",
                defaults={
                    "descripcion": "Consulta operativa de ubicaciones.",
                    "estado": True,
                },
            )
            RolPermiso.objects.get_or_create(
                id_rol=forklift_role.id_rol,
                id_permiso=location_view_permission.id_permiso,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Acceso Administrador TI configurado para {user.correo}."
            )
        )
