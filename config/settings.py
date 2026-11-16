"""
Réglages du projet Révisions Étudiants.

Un seul fichier de réglages, piloté par les variables d'environnement :
- en local : fichier .env (jamais versionné) ;
- en production : variables définies sur Render.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG vaut False si la variable est absente : on est en sécurité par défaut.
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")  # en production il n'y a pas de .env, c'est normal


# --- Sécurité de base -------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")  # pas de valeur par défaut : on veut une erreur si elle manque
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = []

# Render fournit automatiquement le nom de domaine du service (xxx.onrender.com).
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")


# --- Applications ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
        # Apps du projet
    "core",
    "accounts",
    "courses",
    "quizzes",
    "reviews",
    "planning"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sert les fichiers statiques en production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # nos templates communs (base.html...)
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


# --- Base de données -----------------------------------------------------------
# Sans DATABASE_URL → SQLite en local. Avec → PostgreSQL (Neon) en production.

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = 60          # réutilise la connexion 60 s
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # vérifie qu'elle est vivante (Neon se met en veille)


# --- Utilisateurs ----------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"  # défini AVANT la première migration

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Où aller selon la situation (noms d'URL, pas de chemins en dur)
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "courses:list"       # deviendra le tableau de bord plus tard   # deviendra le tableau de bord plus tard
LOGOUT_REDIRECT_URL = "core:home"


# --- Langue et heure -------------------------------------------------------------

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Kinshasa"
USE_I18N = True
USE_TZ = True


# --- Fichiers statiques ----------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"     # où collectstatic rassemble tout (production)
STATICFILES_DIRS = [BASE_DIR / "static"]   # nos fichiers à nous (CSS, JS)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Manifest WhiteNoise seulement en production : en local et dans les tests,
        # il exigerait d'avoir lancé collectstatic et ferait planter les pages.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# --- Fichiers envoyés par les étudiants (PDF, .txt) -------------------------------

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"   # en local uniquement (le disque de Render est effacé à chaque déploiement)

# En production : stockage objet Supabase (protocole S3). Sans STORAGE_BUCKET → disque local.
STORAGE_BUCKET = env("STORAGE_BUCKET", default="")
if STORAGE_BUCKET:
    from botocore.config import Config

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": STORAGE_BUCKET,
            "endpoint_url": env("STORAGE_ENDPOINT"),
            "region_name": env("STORAGE_REGION"),
            "access_key": env("STORAGE_ACCESS_KEY"),
            "secret_key": env("STORAGE_SECRET_KEY"),
            "default_acl": None,          # bucket privé : aucune permission publique
            "querystring_auth": True,     # liens de téléchargement signés...
            "querystring_expire": 600,    # ...valables 10 minutes
            "file_overwrite": False,
            "client_config": Config(
                s3={"addressing_style": "path"},             # format d'adresse exigé par Supabase
                signature_version="s3v4",
                request_checksum_calculation="when_required",  # compatibilité avec Supabase
                response_checksum_validation="when_required",
            ),
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Durcissement en production --------------------------------------------------

if not DEBUG:
    # Render termine le HTTPS devant l'app et transmet l'info dans cet en-tête.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True          # redirige tout le HTTP vers HTTPS
    SESSION_COOKIE_SECURE = True        # cookie de session envoyé uniquement en HTTPS
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600          # 1 h pour commencer ; on augmentera plus tard
    SECURE_REFERRER_POLICY = "same-origin"
    

# --- Intelligence artificielle (génération de quiz) -------------------------------

AI_PROVIDER = env("AI_PROVIDER", default="gemini")       # "gemini" ou "fake" (démo, sans réseau)
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")      # jamais dans le code : .env / Render
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-flash-latest")
AI_TIMEOUT = env.int("AI_TIMEOUT", default=90)  
# Tests uniquement : hachage rapide des mots de passe (jamais utilisé en production)
import sys

if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]         # secondes (gunicorn est réglé à 120)