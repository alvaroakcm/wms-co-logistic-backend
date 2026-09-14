"""
Django settings for config project.

WMS CO LOGISTIC S.A.C.
Backend Django REST Framework
"""

from pathlib import Path
import environ
import os


# =====================================================
# BASE CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================================
# ENVIRONMENT VARIABLES
# =====================================================

env = environ.Env()

environ.Env.read_env(
    os.path.join(BASE_DIR, ".env")
)


# =====================================================
# SECURITY
# =====================================================

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-development-key"
)

DEBUG = env.bool(
    "DEBUG",
    default=True
)


ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)


# =====================================================
# APPLICATIONS
# =====================================================

INSTALLED_APPS = [

    # Django Core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third Party
    "rest_framework",
    "corsheaders",

    # WMS Modules
    'apps.usuarios',
    'apps.maestros',
    'apps.inventario',
    'apps.servicios',
    'apps.recepciones',
    'apps.pedidos',
    'apps.reportes',

]


# =====================================================
# MIDDLEWARE
# =====================================================

MIDDLEWARE = [

    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",

]


# =====================================================
# URL CONFIGURATION
# =====================================================

ROOT_URLCONF = "config.urls"


# =====================================================
# TEMPLATES
# =====================================================

TEMPLATES = [

    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {

            "context_processors": [

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",

            ],
        },
    },

]


WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"



# =====================================================
# DATABASE
# PostgreSQL - Supabase Ready
# =====================================================

DATABASES = {

    "default": {

        "ENGINE": "django.db.backends.postgresql",

        "NAME": env(
            "DB_NAME",
            default=""
        ),

        "USER": env(
            "DB_USER",
            default=""
        ),

        "PASSWORD": env(
            "DB_PASSWORD",
            default=""
        ),

        "HOST": env(
            "DB_HOST",
            default=""
        ),

        "PORT": env(
            "DB_PORT",
            default="5432"
        ),

        "OPTIONS": {

            "sslmode": env(
                "DB_SSLMODE",
                default="require"
            ),

        },

    }
}



# =====================================================
# PASSWORD VALIDATION
# =====================================================

AUTH_PASSWORD_VALIDATORS = [

    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator",
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator",
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator",
    },

]



# =====================================================
# INTERNATIONALIZATION
# =====================================================

LANGUAGE_CODE = "es-pe"


TIME_ZONE = "America/Lima"


USE_I18N = True


USE_TZ = True



# =====================================================
# STATIC FILES
# =====================================================

STATIC_URL = "static/"



# =====================================================
# DEFAULT PRIMARY KEY
# =====================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



# =====================================================
# DJANGO REST FRAMEWORK
# =====================================================

REST_FRAMEWORK = {

    "DEFAULT_AUTHENTICATION_CLASSES": [

        "apps.usuarios.authentication.SupabaseJWTAuthentication",

    ],

    "DEFAULT_PERMISSION_CLASSES": [

        "rest_framework.permissions.IsAuthenticated",

    ],

    "DEFAULT_RENDERER_CLASSES": [

        "rest_framework.renderers.JSONRenderer",

    ],

}


# =====================================================
# SUPABASE AUTH
# =====================================================

SUPABASE_URL = env("SUPABASE_URL", default="").rstrip("/")

SUPABASE_JWT_ISSUER = env(
    "SUPABASE_JWT_ISSUER",
    default=f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else "",
)

SUPABASE_JWT_AUDIENCE = env(
    "SUPABASE_JWT_AUDIENCE",
    default="authenticated",
)

SUPABASE_JWT_ALGORITHMS = ["RS256", "ES256"]

# Server-only key used exclusively for Supabase Auth administration. Prefer the
# new sb_secret_* key; the legacy service_role JWT is accepted during migration.
SUPABASE_SECRET_KEY = env("SUPABASE_SECRET_KEY", default="")



# =====================================================
# CORS - REACT FRONTEND
# =====================================================

FRONTEND_URL = env(
    "FRONTEND_URL",
    default="http://localhost:5173",
).rstrip("/")

CORS_ALLOWED_ORIGINS = [FRONTEND_URL]

if DEBUG and FRONTEND_URL == "http://localhost:5173":
    CORS_ALLOWED_ORIGINS.append("http://127.0.0.1:5173")


# =====================================================
# PROJECT SETTINGS
# =====================================================

APPEND_SLASH = True
