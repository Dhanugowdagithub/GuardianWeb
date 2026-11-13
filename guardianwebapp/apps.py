from django.apps import AppConfig


class GuardianwebappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'guardianwebapp'

class LivewatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name  = "livewatch"
    label = "livewatch"
    verbose_name = "Live Watch"