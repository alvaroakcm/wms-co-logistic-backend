from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Permiso, Rol, Usuario
from .permissions import require_application_permission
from .serializers import (
    RoleAssignmentSerializer,
    RoleWriteSerializer,
    UserCreateSerializer,
    UserStatusSerializer,
    UserUpdateSerializer,
)
from .services import (
    build_user_access,
    create_application_user,
    replace_user_roles,
    save_role,
    serialize_role,
    serialize_user,
    set_application_user_status,
    update_application_user,
)


class CurrentUserView(APIView):
    """Return the application profile and effective access for the session."""

    def get(self, request):
        return Response(build_user_access(request.user))


class UserListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "usuarios.ver")
        query = Usuario.objects.all().order_by("nombre", "apellido")
        search = request.query_params.get("search", "").strip()
        if search:
            query = query.filter(
                Q(nombre__icontains=search)
                | Q(apellido__icontains=search)
                | Q(correo__icontains=search)
            )
        return Response([serialize_user(user) for user in query[:200]])

    def post(self, request):
        require_application_permission(request.user, "usuarios.crear")
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["role_ids"]:
            require_application_permission(
                request.user, "usuarios.asignar_roles"
            )
        user = create_application_user(serializer.validated_data)
        return Response(serialize_user(user), status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    def patch(self, request, user_id):
        require_application_permission(request.user, "usuarios.editar")
        user = get_object_or_404(Usuario, id_usuario=user_id)
        serializer = UserUpdateSerializer(
            data=request.data,
            context={"user_id": user.id_usuario},
        )
        serializer.is_valid(raise_exception=True)
        user = update_application_user(user, serializer.validated_data)
        return Response(serialize_user(user))


class UserRoleAssignmentView(APIView):
    def put(self, request, user_id):
        require_application_permission(request.user, "usuarios.asignar_roles")
        user = get_object_or_404(Usuario, id_usuario=user_id)
        serializer = RoleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = replace_user_roles(user, serializer.validated_data["role_ids"])
        return Response(serialize_user(user))


class UserStatusView(APIView):
    def patch(self, request, user_id):
        require_application_permission(request.user, "usuarios.desactivar")
        user = get_object_or_404(Usuario, id_usuario=user_id)
        serializer = UserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        active = serializer.validated_data["estado"]
        if str(user.id_usuario) == str(request.user.id) and not active:
            raise ValidationError(
                {"estado": ["No puedes desactivar tu propia cuenta."]}
            )
        user = set_application_user_status(user, active)
        return Response(serialize_user(user))


class RoleListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "roles.ver")
        roles = Rol.objects.all().order_by("nombre")
        return Response([serialize_role(role) for role in roles])

    def post(self, request):
        require_application_permission(request.user, "roles.gestionar")
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = save_role(serializer.validated_data)
        return Response(serialize_role(role), status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    def patch(self, request, role_id):
        require_application_permission(request.user, "roles.gestionar")
        role = get_object_or_404(Rol, id_rol=role_id)
        serializer = RoleWriteSerializer(
            data=request.data, context={"role_id": role.id_rol}
        )
        serializer.is_valid(raise_exception=True)
        role = save_role(serializer.validated_data, role=role)
        return Response(serialize_role(role))


class PermissionListView(APIView):
    def get(self, request):
        require_application_permission(request.user, "roles.ver")
        permissions = Permiso.objects.filter(estado=True).order_by("nombre")
        return Response(
            list(
                permissions.values(
                    "id_permiso", "nombre", "descripcion", "estado"
                )
            )
        )
