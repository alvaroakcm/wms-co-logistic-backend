import logging
import ssl
from dataclasses import dataclass
from functools import lru_cache

import certifi
import jwt
from django.conf import settings
from django.db import DatabaseError
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import APIException, AuthenticationFailed

from .models import Usuario


logger = logging.getLogger(__name__)


class AuthenticationServiceUnavailable(APIException):
    status_code = 503
    default_detail = "No fue posible validar la sesión. Inténtalo nuevamente."
    default_code = "authentication_unavailable"


@dataclass(frozen=True)
class SupabasePrincipal:
    id: str
    email: str
    claims: dict
    profile: Usuario

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


@lru_cache(maxsize=4)
def _get_jwks_client(jwks_url):
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return jwt.PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=600,
        ssl_context=ssl_context,
    )


def verify_supabase_token(token):
    """Verify signature and mandatory claims of a Supabase access token."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_JWT_ISSUER:
        logger.error("Supabase Auth is not configured")
        raise AuthenticationServiceUnavailable()

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")

        if algorithm not in settings.SUPABASE_JWT_ALGORITHMS:
            raise AuthenticationFailed("La sesión no es válida o ha expirado.")

        jwks_url = (
            f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        )
        signing_key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=settings.SUPABASE_JWT_ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except AuthenticationFailed:
        raise
    except (jwt.PyJWTError, ValueError) as exc:
        logger.info("Supabase JWT rejected: %s", exc.__class__.__name__)
        raise AuthenticationFailed(
            "La sesión no es válida o ha expirado."
        ) from exc
    except Exception as exc:
        logger.exception("Supabase JWKS validation failed")
        raise AuthenticationServiceUnavailable() from exc


class SupabaseJWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        authorization = get_authorization_header(request).split()

        if not authorization:
            return None

        if authorization[0].decode("ascii", errors="ignore").lower() != "bearer":
            return None

        if len(authorization) != 2:
            raise AuthenticationFailed("Encabezado de autorización inválido.")

        try:
            token = authorization[1].decode("utf-8")
        except UnicodeError as exc:
            raise AuthenticationFailed(
                "Encabezado de autorización inválido."
            ) from exc

        claims = verify_supabase_token(token)
        user_id = claims.get("sub")

        if not user_id:
            raise AuthenticationFailed("La sesión no es válida o ha expirado.")

        try:
            profile = Usuario.objects.filter(id_usuario=user_id).first()
        except (DatabaseError, ValueError) as exc:
            logger.exception("Application user lookup failed")
            raise AuthenticationServiceUnavailable() from exc

        if profile is None or not profile.estado:
            raise AuthenticationFailed(
                "La cuenta no está habilitada para acceder al sistema."
            )

        principal = SupabasePrincipal(
            id=str(profile.id_usuario),
            email=claims.get("email") or profile.correo,
            claims=claims,
            profile=profile,
        )
        return principal, token

    def authenticate_header(self, request):
        return self.keyword
