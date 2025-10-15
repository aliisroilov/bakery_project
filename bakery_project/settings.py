"""
Django settings for bakery_project project (Heroku-ready).
"""

from pathlib import Path
import os
from decouple import config  # pip install python-decouple
import dj_database_url        # pip install dj-database-url

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'bakery_db'),
        'USER': os.environ.get('POSTGRES_USER', 'bakuser'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', '0270'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', ''),
    }
}

# =========================
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# =========================
# Core Settings
# =========================
SECRET_KEY = config('SECRET_KEY', default='unsafe-secret-key-for-testing')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['sutli-non.uz', 'www.sutli-non.uz', '217.76.51.229']

# =========================
# Applications
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Local apps
    'users',
    'products',
    'shops',
    'orders',
    'dashboard',
    'reports',
    'widget_tweaks',
    'inventory',
    'salary',
]

AUTH_USER_MODEL = "users.User"

# =========================
# Tailwind Config
# =========================
TAILWIND_APP_NAME = 'theme'  # the app you created for Tailwind
INTERNAL_IPS = ["127.0.0.1"]  # required for Tailwind dev server

# =========================
# Middleware
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # added for static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.ActivityLogMiddleware',
]

# =========================
# URL / WSGI
# =========================
ROOT_URLCONF = 'bakery_project.urls'
WSGI_APPLICATION = 'bakery_project.wsgi.application'

# =========================
# Templates
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# =========================
# Database (SQLite for testing)
# =========================


# =========================
# Authentication
# =========================
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGOUT_REDIRECT_URL = 'login'

# =========================
# Password Validation
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 4},  # testing only
    },
]

# =========================
# Internationalization
# =========================
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# =========================
# Static & Media
# =========================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []  # leave empty, since you only use staticfiles folder

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

# =========================
# Default Primary Key
# =========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
