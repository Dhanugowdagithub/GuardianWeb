from django import forms
from .models import LiveWatchSession, Checkpoint
from django import forms
from django.forms import formset_factory


class StartSessionForm(forms.ModelForm):
    class Meta:
        model  = LiveWatchSession
        fields = [
            "title", "origin_name", "destination_name",
            "origin_lat", "origin_lng",
            "destination_lat", "destination_lng",
            "expected_duration",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "e.g. Home to College",
            }),
            "origin_name": forms.TextInput(attrs={
                "placeholder": "Starting location name",
                "id": "origin_name",
            }),
            "destination_name": forms.TextInput(attrs={
                "placeholder": "Destination name",
                "id": "dest_name",
            }),
            "origin_lat":      forms.HiddenInput(attrs={"id": "origin_lat"}),
            "origin_lng":      forms.HiddenInput(attrs={"id": "origin_lng"}),
            "destination_lat": forms.HiddenInput(attrs={"id": "dest_lat"}),
            "destination_lng": forms.HiddenInput(attrs={"id": "dest_lng"}),
            "expected_duration": forms.NumberInput(attrs={
                "min": 1, "max": 720, "placeholder": "Minutes",
            }),
        }
        labels = {
            "expected_duration": "Expected journey duration (minutes)",
        }

    def clean_expected_duration(self):
        val = self.cleaned_data.get("expected_duration", 60)
        if val < 1:
            raise forms.ValidationError("Duration must be at least 1 minute.")
        if val > 720:
            raise forms.ValidationError("Duration cannot exceed 12 hours.")
        return val


class CheckpointForm(forms.Form):
    checkpoint = forms.CharField(max_length=100)

CheckpointFormSet = formset_factory(CheckpointForm, extra=1)