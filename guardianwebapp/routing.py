from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/guardianwebapp/track/(?P<session_id>\w+)/$', consumers.UserTrackingConsumer.as_asgi()),
    re_path(r'ws/guardianwebapp/watch/(?P<session_id>\w+)/$', consumers.GuardianWatchConsumer.as_asgi()),
    re_path(r'ws/guardianwebapp/watch/code/(?P<share_code>\w+)/$', consumers.GuardianWatchConsumer.as_asgi()),
]