"""
Django settings for public_interface project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

import django.conf.global_settings as DEFAULT_SETTINGS  # http://stackoverflow.com/a/15446953/1763984

from django.utils.crypto import get_random_string # http://stackoverflow.com/a/16630719/1763984

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

THUMBNAIL_URL = os.getenv('UCLDC_THUMBNAIL_URL', 'http://localhost:8888/')  # `python thumbnail.py`
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY',
                       get_random_string(50,
                                         'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
                       )
             )

STATIC_URL = os.getenv('UCLDC_STATIC_URL', 'http://localhost:9000/')  # `grunt serve`

SOLR_URL = os.getenv('UCLDC_SOLR_URL', 'http://localhost:8983/solr')
SOLR_API_KEY = os.getenv('UCLDC_SOLR_API_KEY', '')
UCLDC_IMAGES = os.getenv('UCLDC_IMAGES', '')
UCLDC_MEDIA = os.getenv('UCLDC_MEDIA', '')

GA_SITE_CODE = os.getenv('UCLDC_GA_SITE_CODE', False)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get('UCLDC_DEBUG'))

UCLDC_DEVEL = TEMPLATE_DEBUG = bool(os.environ.get('UCLDC_DEVEL'))

TEMPLATE_CONTEXT_PROCESSORS = DEFAULT_SETTINGS.TEMPLATE_CONTEXT_PROCESSORS  + (
    'django.core.context_processors.request',
    'public_interface.context_processors.settings',
)

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'easy_pjax',
    'calisphere',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'public_interface.urls'

WSGI_APPLICATION = 'public_interface.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATICFILES_STORAGE = 'whitenoise.django.GzipManifestStaticFilesStorage'

STATIC_ROOT = os.path.join(BASE_DIR, "static_root")

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "dist"),
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
        },
    },
}
