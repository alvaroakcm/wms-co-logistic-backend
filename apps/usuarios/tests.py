from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import jwt
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .authentication import (
    SupabaseJWTAuthentication,
    SupabasePrincipal,
    verify_supabase_token,
)
from .views import CurrentUserView, UserStatusView
from .permissions import require_application_permission
from .services import (
    IdentityServiceUnavailable,
    create_application_user,
    set_application_user_status,
)


class SupabaseJWTAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.authentication = SupabaseJWTAuthentication()

    def test_request_without_bearer_token_is_not_authenticated(self):
        request = self.factory.get("/api/auth/me/")

        self.assertIsNone(self.authentication.authenticate(request))

    @patch("apps.usuarios.authentication.Usuario.objects.filter")
    @patch("apps.usuarios.authentication.verify_supabase_token")
    def test_active_application_user_is_authenticated(self, verify, user_filter):
        verify.return_value = {
            "sub": "3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            "email": "operador@empresa.com",
        }
        profile = SimpleNamespace(
            id_usuario="3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            correo="operador@empresa.com",
            estado=True,
        )
        user_filter.return_value.first.return_value = profile
        request = self.factory.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION="Bearer valid-token",
        )

        principal, token = self.authentication.authenticate(request)

        self.assertTrue(principal.is_authenticated)
        self.assertEqual(principal.email, "operador@empresa.com")
        self.assertEqual(token, "valid-token")

    @patch("apps.usuarios.authentication.Usuario.objects.filter")
    @patch("apps.usuarios.authentication.verify_supabase_token")
    def test_inactive_application_user_is_rejected(self, verify, user_filter):
        verify.return_value = {
            "sub": "3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            "email": "inactivo@empresa.com",
        }
        user_filter.return_value.first.return_value = SimpleNamespace(
            id_usuario="3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            correo="inactivo@empresa.com",
            estado=False,
        )
        request = self.factory.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION="Bearer valid-token",
        )

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(request)

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_JWT_ISSUER="https://example.supabase.co/auth/v1",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHMS=["RS256", "ES256"],
    )
    def test_symmetric_or_unexpected_algorithm_is_rejected(self):
        token = jwt.encode(
            {"sub": "user", "aud": "authenticated"},
            "unsafe-test-secret-with-32-characters",
            algorithm="HS256",
        )

        with self.assertRaises(AuthenticationFailed):
            verify_supabase_token(token)


class CurrentUserViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.profile = SimpleNamespace(
            nombre="Ana",
            apellido="Torres",
            correo="ana@empresa.com",
            estado=True,
        )
        self.principal = SupabasePrincipal(
            id="3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            email="ana@empresa.com",
            claims={},
            profile=self.profile,
        )

    @patch("apps.usuarios.views.build_user_access")
    def test_me_returns_current_user_access(self, build_user_access):
        payload = {
            "id": self.principal.id,
            "correo": self.principal.email,
            "nombre": "Ana",
            "apellido": "Torres",
            "roles": [{"id_rol": 1, "nombre": "Operador"}],
            "permisos": ["inventario.ver"],
        }
        build_user_access.return_value = payload
        request = self.factory.get("/api/auth/me/")
        force_authenticate(request, user=self.principal, token="valid-token")

        response = CurrentUserView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, payload)

    def test_me_rejects_anonymous_request(self):
        request = self.factory.get("/api/auth/me/")

        response = CurrentUserView.as_view()(request)

        self.assertEqual(response.status_code, 401)


class ApplicationAuthorizationTests(SimpleTestCase):
    @patch("apps.usuarios.permissions.user_has_permission", return_value=True)
    def test_required_application_permission_allows_authorized_user(self, has_permission):
        principal = SimpleNamespace(id="user-id")

        require_application_permission(principal, "usuarios.ver")

        has_permission.assert_called_once_with(principal, "usuarios.ver")

    @patch("apps.usuarios.permissions.user_has_permission", return_value=False)
    def test_required_application_permission_rejects_unauthorized_user(self, _):
        with self.assertRaises(PermissionDenied):
            require_application_permission(SimpleNamespace(id="user-id"), "roles.ver")


class UserRegistrationServiceTests(SimpleTestCase):
    payload = {
        "nombre": "Ana",
        "apellido": "Torres",
        "correo": "ana@empresa.com",
        "password": "temporary-password",
        "role_ids": [1],
    }

    @patch("apps.usuarios.services.UsuarioRol.objects.bulk_create")
    @patch("apps.usuarios.services.Usuario.objects.create")
    @patch("apps.usuarios.services.SupabaseAdminClient")
    @patch("apps.usuarios.services.transaction.atomic", side_effect=nullcontext)
    def test_registration_creates_auth_identity_before_profile(
        self, _, client_class, create_profile, bulk_create
    ):
        client_class.return_value.create_user.return_value = {"id": "auth-user-id"}
        create_profile.return_value = SimpleNamespace(id_usuario="auth-user-id")

        user = create_application_user(self.payload)

        self.assertEqual(user.id_usuario, "auth-user-id")
        client_class.return_value.create_user.assert_called_once()
        create_profile.assert_called_once()
        bulk_create.assert_called_once()

    @patch("apps.usuarios.services.Usuario.objects.create")
    @patch("apps.usuarios.services.SupabaseAdminClient")
    @patch("apps.usuarios.services.transaction.atomic", side_effect=nullcontext)
    def test_registration_removes_auth_identity_if_profile_fails(
        self, _, client_class, create_profile
    ):
        from django.db import IntegrityError

        client_class.return_value.create_user.return_value = {"id": "auth-user-id"}
        create_profile.side_effect = IntegrityError("duplicate")

        with self.assertRaises(ValidationError):
            create_application_user(self.payload)

        client_class.return_value.delete_user.assert_called_once_with("auth-user-id")


class UserStatusServiceTests(SimpleTestCase):
    @patch("apps.usuarios.services.SupabaseAdminClient")
    @patch("apps.usuarios.services.transaction.atomic", side_effect=nullcontext)
    def test_deactivation_bans_identity_and_marks_profile_inactive(
        self, _, client_class
    ):
        user = SimpleNamespace(
            id_usuario="auth-user-id",
            estado=True,
            fecha_actualizacion=None,
            save=Mock(),
        )

        result = set_application_user_status(user, False)

        self.assertFalse(result.estado)
        client_class.return_value.set_user_active.assert_called_once_with(
            "auth-user-id", active=False
        )
        user.save.assert_called_once_with(
            update_fields=["estado", "fecha_actualizacion"]
        )

    @patch("apps.usuarios.services.SupabaseAdminClient")
    @patch("apps.usuarios.services.transaction.atomic", side_effect=nullcontext)
    def test_status_change_restores_auth_when_database_fails(
        self, _, client_class
    ):
        from django.db import DatabaseError

        user = SimpleNamespace(
            id_usuario="auth-user-id",
            estado=True,
            fecha_actualizacion=None,
            save=Mock(side_effect=DatabaseError("unavailable")),
        )

        with self.assertRaises(IdentityServiceUnavailable):
            set_application_user_status(user, False)

        self.assertTrue(user.estado)
        self.assertEqual(
            client_class.return_value.set_user_active.call_args_list,
            [call("auth-user-id", active=False), call("auth-user-id", active=True)],
        )


class UserStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.principal = SimpleNamespace(
            id="3f09a7b9-e9fd-48dc-b134-20a4f909e629",
            is_authenticated=True,
        )

    @patch("apps.usuarios.views.set_application_user_status")
    @patch("apps.usuarios.views.require_application_permission")
    @patch("apps.usuarios.views.get_object_or_404")
    def test_administrator_cannot_deactivate_own_account(
        self, get_user, _, set_status
    ):
        get_user.return_value = SimpleNamespace(
            id_usuario=self.principal.id, estado=True
        )
        request = self.factory.patch(
            f"/api/users/{self.principal.id}/status/",
            {"estado": False},
            format="json",
        )
        force_authenticate(request, user=self.principal, token="valid-token")

        response = UserStatusView.as_view()(request, user_id=self.principal.id)

        self.assertEqual(response.status_code, 400)
        set_status.assert_not_called()

# Create your tests here.
