"""
URL configuration for guardianwebproj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from guardianwebapp import views
from django.conf import settings
from django.conf.urls.static import static  
from django.contrib import admin
from django.urls import path, include
from guardianwebapp import police_views



urlpatterns = [
    path('', views.welcome, name='home'),
    path('admin/', admin.site.urls),
    path('welcome_page/',views.welcome,name='welcome_page'),
    path('register/', views.registration_view, name='register'),
    path('registration_page/',views.registration_view,name='registration_view'),
    path('login/', views.login_view, name='login'),
    path('login_page/',views.login_view,name='login_page'),
    path('user_dashboard/',views.user_dashboard,name='user_dashboard'),
    path('guardian_dashboard/',views.guardian_dashboard,name='guardian_dashboard'),
    path('volunteer_dashboard/',views.volunteer_dashboard,name='volunteer_dashboard'),
    path('verify_otp/',views.verify_otp,name='verify_otp'),
    path("track/<int:session_id>/", views.track_view, name="track"),
    path('start_session/',views.start_session,name='start_session'),
    path("view-location/", views.view_location, name="view_location"),
    path("get-live-location/", views.get_live_location, name="get_live_location"),
    path("update-location/", views.update_location, name="update_location"),
    path("save-location/", views.save_location, name="save_location"),
    #path("profile/", views.profile, name="profile"),
    path("logout/", views.logout_view, name="logout"),
    path("sos_sent/", views.sos_sent, name="sos_sent"),
    path('share_location/', views.share_location, name='share_location'),
    path('add_guardian/<int:session_id>/', views.add_guardian, name='add_guardian'),
    path('remove_guardian/<int:guardian_id>/', views.remove_guardian, name='remove_guardian'),
    path('companion_mode/',views.companion_view,name="companion_view"),
    path('emergency_alert/',views.emergency_alert_view,name="emergency_alert"),
    path('travel_monitoring/',views.travel_view,name="travel_monitoring"),  
    path('volunteer/toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('volunteer/emergency-requests/', views.emergency_alert_view, name='emergency_alert_view'),
path('volunteer/emergency-requests/<int:request_id>/accept/', views.accept_emergency_request, name='accept_emergency_request'),
path('accept-nearby-alert/<int:alert_id>/', views.accept_nearby_alert, name='accept_nearby_alert'),
path('join-companion-session/<int:request_id>/', views.join_companion_session, name='join_companion_session'),
path('volunteer/accepted-requests/', views.volunteer_accepted_requests, name='volunteer_accepted_requests'),
path('volunteer_dashboard/', views.volunteer_dashboard, name='volunteer_dashboard'),
path('volunteer/pending-requests/', views.volunteer_pending_requests, name='volunteer_pending_requests'),
path('volunteer/nearby-alerts/', views.volunteer_nearby_alerts, name='volunteer_nearby_alerts'),
path('volunteer/companion-sessions/', views.volunteer_companion_sessions, name='volunteer_companion_sessions'),
path('update-volunteer-location/', views.update_volunteer_location, name='update_volunteer_location'),
path('accept-nearby-alert/<int:alert_id>/', views.accept_nearby_alert, name='accept_nearby_alert'),
  path('companion/', views.companion_view, name='companion_view'),
path('companion/waiting/<int:request_id>/', views.companion_waiting, name='companion_waiting'),
path('companion/status/<int:request_id>/', views.companion_status_check, name='companion_status_check'),
path('companion/timeout/<int:request_id>/', views.companion_timeout, name='companion_timeout'),
path('companion/<int:request_id>/accept/', views.accept_companion_request, name='accept_companion_request'),
path('companion/chat/<int:request_id>/', views.companion_chat, name='companion_chat'),
path('stop-sharing/<int:session_id>/', views.stop_sharing, name='stop_sharing'),
path('end-session/<int:session_id>/', views.end_session, name='end_session'),
path('update-expected-duration/<int:session_id>/', views.update_expected_duration, name='update_expected_duration'),
path('notifications/', views.notifications_view, name='notifications_view'),
path('profile/', views.profile_settings, name='profile_settings'),
path('forgot-password/', views.forgot_password, name='forgot_password'),
path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
path('reset-password/', views.reset_password, name='reset_password'),
 path('sos-alerts/', views.sos_alerts_list, name='sos_alerts_list'),
path('sos-alerts/<int:alert_id>/accept/', views.accept_sos_alert, name='accept_sos_alert'),
path('guardian/emergency-alerts/', views.guardian_emergency_alerts, name='guardian_emergency_alerts'),
path('guardian/mark-resolved/<int:alert_id>/', views.mark_alert_resolved, name='mark_alert_resolved'),
path('guardian/accept-alert/<int:alert_id>/', views.guardian_accept_alert, name='guardian_accept_alert'), 
path('watch/<str:share_code>/', views.watch_by_code, name='watch_by_code'),
path('guardian/travel-monitoring/', views.travel_monitoring, name='travel_monitoring'),
path('companion/end/<int:request_id>/', views.end_companion_session, name='end_companion_session'),
path('sos-history/', views.sos_history_view, name='sos_history'),
path('sos/<int:alert_id>/attach-voice/', views.attach_voice_note, name='attach_voice_note'),
path('volunteer/track-alert/<int:alert_id>/', views.volunteer_track_alert, name='volunteer_track_alert'),
path('companion/messages/<int:request_id>/', views.companion_messages_fetch, name='companion_messages_fetch'),
path('sos/<int:alert_id>/status/', police_views.sos_status, name='sos_status'),
path('sos/<int:alert_id>/police/', police_views.police_connected, name='police_connected'),



   ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    