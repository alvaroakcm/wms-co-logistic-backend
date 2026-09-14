import json
import logging
import ssl
from urllib import error, request

import certifi
from django.conf import settings


logger = logging.getLogger(__name__)


class SupabaseAdminError(Exception):
    """Base error for server-side Supabase Auth administration."""


class SupabaseAdminNotConfigured(SupabaseAdminError):
    pass


class SupabaseUserAlreadyExists(SupabaseAdminError):
    pass


class SupabaseAdminClient:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.secret_key = settings.SUPABASE_SECRET_KEY
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def _request(self, method, path, payload=None):
        if not self.base_url or not self.secret_key:
            raise SupabaseAdminNotConfigured(
                "La administración de Supabase Auth no está configurada."
            )

        headers = {
            "apikey": self.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "wms-co-logistic-backend/1.0",
        }
        # Legacy service_role keys are JWTs and Auth expects them as Bearer.
        if self.secret_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.secret_key}"

        body = None if payload is None else json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            f"{self.base_url}/auth/v1{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with request.urlopen(
                api_request, timeout=12, context=self.ssl_context
            ) as response:
                response_body = response.read()
                return json.loads(response_body) if response_body else {}
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(response_body)
            except json.JSONDecodeError:
                detail = {}

            error_code = str(detail.get("error_code") or detail.get("code") or "")
            message = str(detail.get("msg") or detail.get("message") or "")
            if exc.code in (400, 409, 422) and (
                "already" in message.lower()
                or "registered" in message.lower()
                or "exists" in message.lower()
                or error_code in {"email_exists", "user_already_exists"}
            ):
                raise SupabaseUserAlreadyExists(
                    "Ya existe un usuario con ese correo."
                ) from exc

            logger.warning(
                "Supabase Auth admin request failed: status=%s code=%s",
                exc.code,
                error_code or "unknown",
            )
            raise SupabaseAdminError(
                "Supabase Auth no pudo completar la operación."
            ) from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.exception("Supabase Auth admin request unavailable")
            raise SupabaseAdminError(
                "Supabase Auth no está disponible temporalmente."
            ) from exc

    def create_user(self, *, email, password, first_name, last_name):
        return self._request(
            "POST",
            "/admin/users",
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "nombre": first_name,
                    "apellido": last_name,
                },
            },
        )

    def update_user(self, user_id, *, email, first_name, last_name):
        return self._request(
            "PUT",
            f"/admin/users/{user_id}",
            {
                "email": email,
                "email_confirm": True,
                "user_metadata": {
                    "nombre": first_name,
                    "apellido": last_name,
                },
            },
        )

    def set_user_active(self, user_id, *, active):
        return self._request(
            "PUT",
            f"/admin/users/{user_id}",
            {
                # Supabase documents 876000 hours as a 100-year ban.
                "ban_duration": "none" if active else "876000h",
            },
        )

    def delete_user(self, user_id):
        return self._request("DELETE", f"/admin/users/{user_id}")
