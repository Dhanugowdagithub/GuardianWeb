from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import (
    LiveWatchSession, GPSPoint, EmergencyAlert, Profile,
    CompanionRequest, CompanionChatMessage,
)

class GuardianWebViewsTest(TestCase):
    def setUp(self):
        # Create standard test user
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.profile = Profile.objects.create(user=self.user, phone="1234567890", role="user")
        
        # Create standard test guardian user
        self.guardian_user = User.objects.create_user(username="guardian1", password="password123")
        self.guardian_profile = Profile.objects.create(user=self.guardian_user, phone="0987654321", role="guardian")

        # Client setup
        self.client = Client()
        self.client.login(username="testuser", password="password123")

    def test_user_dashboard_no_session(self):
        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active journey sharing")
        self.assertEqual(response.context['guardians_count'], 0)
        self.assertEqual(response.context['sharing_active'], False)

    def test_user_dashboard_with_active_session(self):
        # Create an active session
        session = LiveWatchSession.objects.create(
            user=self.user,
            title="Test Journey",
            status="active"
        )
        # Create a GPS point for this session
        GPSPoint.objects.create(
            session=session,
            latitude=12.9716,
            longitude=77.5946
        )

        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sharing_active'], True)
        self.assertEqual(response.context['session'].id, session.id)

    def test_sos_sent_creates_records(self):
        # Create an active session
        session = LiveWatchSession.objects.create(
            user=self.user,
            title="Active Journey",
            status="active"
        )
        GPSPoint.objects.create(
            session=session,
            latitude=12.9000,
            longitude=77.6000
        )

        # Trigger SOS sent view
        response = self.client.get(reverse('sos_sent'))
        self.assertEqual(response.status_code, 200)

        # Check if EmergencyAlert was created
        alerts = EmergencyAlert.objects.filter(user=self.user)
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.first().latitude, 12.9000)

        # Check if session is updated to DANGER status
        session.refresh_from_db()
        self.assertEqual(session.status, "danger")
        self.assertEqual(session.sos_triggered, True)

        # Check if DangerEvent was created
        dangers = session.danger_events.all()
        self.assertEqual(dangers.count(), 1)
        self.assertEqual(dangers.first().trigger, "sos")


class PoliceEscalationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sos_user", password="password123")
        self.client = Client()
        self.client.force_login(self.user)
        self.alert = EmergencyAlert.objects.create(
            user=self.user,
            latitude=12.9716,
            longitude=77.5946,
        )

    def test_sos_status_waits_before_escalation(self):
        check_time = self.alert.created_at + timedelta(seconds=59)
        with patch("guardianwebapp.police_views.timezone.now", return_value=check_time):
            response = self.client.get(reverse("sos_status", args=[self.alert.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"state": "waiting", "seconds_left": 1})

    def test_sos_status_escalates_after_timeout(self):
        check_time = self.alert.created_at + timedelta(seconds=60)
        with patch("guardianwebapp.police_views.timezone.now", return_value=check_time):
            response = self.client.get(reverse("sos_status", args=[self.alert.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "state": "police",
            "url": reverse("police_connected", args=[self.alert.id]),
        })

    def test_accepted_alert_does_not_show_police_page(self):
        self.alert.accepted_by_guardian = self.user
        self.alert.save(update_fields=["accepted_by_guardian"])
        check_time = self.alert.created_at + timedelta(seconds=60)

        with patch("guardianwebapp.police_views.timezone.now", return_value=check_time):
            response = self.client.get(reverse("police_connected", args=[self.alert.id]))

        self.assertRedirects(
            response,
            reverse("notifications_view"),
            fetch_redirect_response=False,
        )


class CompanionAITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ai_user", password="password123")
        self.client = Client()
        self.client.force_login(self.user)
        self.companion_request = CompanionRequest.objects.create(
            user=self.user,
            status="AI_Mode",
        )

    @patch("guardianwebapp.views.get_ai_companion_reply", return_value="I'm with you.")
    def test_ai_reply_receives_conversation_history(self, get_reply):
        CompanionChatMessage.objects.create(
            companion_request=self.companion_request,
            sender_type="user",
            text="I had a difficult day.",
        )
        CompanionChatMessage.objects.create(
            companion_request=self.companion_request,
            sender_type="ai",
            text="I'm sorry to hear that.",
        )

        response = self.client.post(reverse("companion_view"), {
            "action": "chat_message",
            "request_id": self.companion_request.id,
            "message": "Can we talk?",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_reply.call_args.kwargs["history"], [
            {"role": "user", "text": "I had a difficult day."},
            {"role": "model", "text": "I'm sorry to hear that."},
        ])
        self.assertEqual(response.json()["reply"], "I'm with you.")
        self.assertEqual(
            response.json()["id"],
            self.companion_request.messages.filter(sender_type="ai").latest("id").id,
        )

    @patch("guardianwebapp.views.genai.GenerativeModel")
    def test_ai_generation_sends_history_and_current_message(self, generative_model):
        from .views import get_ai_companion_reply

        model_instance = generative_model.return_value
        model_instance.generate_content.return_value.text = "A supportive reply."

        reply = get_ai_companion_reply("What should I do next?", history=[
            {"role": "user", "text": "I'm feeling anxious."},
            {"role": "model", "text": "What's making you anxious?"},
        ])

        self.assertEqual(reply, "A supportive reply.")
        model_instance.generate_content.assert_called_once_with([
            {"role": "user", "parts": ["I'm feeling anxious."]},
            {"role": "model", "parts": ["What's making you anxious?"]},
            {"role": "user", "parts": ["What should I do next?"]},
        ])
