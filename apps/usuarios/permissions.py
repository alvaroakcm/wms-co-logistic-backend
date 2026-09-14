from rest_framework.exceptions import PermissionDenied

from .models import Permiso, Rol, RolPermiso, UsuarioRol


def user_has_permission(principal, permission_name):
    """Return whether the active application user has an effective permission."""
    role_ids = UsuarioRol.objects.filter(id_usuario=principal.id).values_list(
        "id_rol", flat=True
    )
    active_role_ids = Rol.objects.filter(
        id_rol__in=role_ids, estado=True
    ).values_list("id_rol", flat=True)
    permission_ids = RolPermiso.objects.filter(
        id_rol__in=active_role_ids
    ).values_list("id_permiso", flat=True)
    return Permiso.objects.filter(
        id_permiso__in=permission_ids,
        nombre=permission_name,
        estado=True,
    ).exists()


def require_application_permission(principal, permission_name):
    if not user_has_permission(principal, permission_name):
        raise PermissionDenied(
            "No tienes permiso para realizar esta operación."
        )
