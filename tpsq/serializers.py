from django.core.validators import EmailValidator
from rest_framework import serializers
from tpsq.models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for UserSession model"""

    class Meta:
        model = UserSession
        fields = [
            "session_id",
            "ip_address",
            "user_agent",
            "first_seen",
            "last_activity",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "referrer",
            "country_code",
            "city",
            "region",
            "device_type",
            "browser",
            "os",
            "page_views",
            "time_on_site",
            "is_bounce",
        ]
        read_only_fields = ["first_seen", "last_activity"]

    def validate_country_code(self, value):
        """Validate and normalize country code format"""
        if value:
            # Normalize to uppercase
            value = value.upper().strip()

            # Validate length
            if len(value) != 2:
                raise serializers.ValidationError(
                    "Country code must be 2 characters long"
                )

            # Validate format (letters only)
            if not value.isalpha():
                raise serializers.ValidationError(
                    "Country code must contain only letters"
                )

        return value


class FunnelEventSerializer(serializers.ModelSerializer):
    """Serializer for FunnelEvent model"""

    class Meta:
        model = FunnelEvent
        fields = [
            "id",
            "session",
            "event_type",
            "timestamp",
            "page_url",
            "page_title",
            "element_id",
            "element_text",
            "time_since_page_load",
            "metadata",
        ]
        read_only_fields = ["id", "timestamp"]

    def validate_event_type(self, value):
        """Validate event type is in allowed choices"""
        valid_events = [choice[0] for choice in FunnelEvent.EVENT_TYPES]
        if value not in valid_events:
            raise serializers.ValidationError(
                f"Invalid event type. Must be one of: {valid_events}"
            )
        return value

    def validate_time_since_page_load(self, value):
        """Validate timing data"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Time since page load cannot be negative")
        return value


class SurveyResponseSerializer(serializers.ModelSerializer):
    """Serializer for SurveyResponse model"""

    class Meta:
        model = SurveyResponse
        fields = [
            "session",
            "preference",
            "created_at",
            "time_to_select",
            "changed_mind_count",
        ]
        read_only_fields = ["created_at"]

    def validate_preference(self, value):
        """Validate preference choice"""
        valid_preferences = [choice[0] for choice in SurveyResponse.PREFERENCE_CHOICES]
        if value not in valid_preferences:
            raise serializers.ValidationError(
                f"Invalid preference. Must be one of: {valid_preferences}"
            )
        return value

    def validate_time_to_select(self, value):
        """Validate timing data"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Time to select cannot be negative")
        if value is not None and value > 3600:  # More than 1 hour seems unrealistic
            raise serializers.ValidationError("Time to select seems too large")
        return value

    def validate_changed_mind_count(self, value):
        """Validate change count"""
        if value < 0:
            raise serializers.ValidationError("Changed mind count cannot be negative")
        if value > 100:  # Sanity check
            raise serializers.ValidationError("Changed mind count seems unrealistic")
        return value


class EarlyAccessSignupSerializer(serializers.ModelSerializer):
    """Serializer for EarlyAccessSignup model"""

    # Additional fields for the signup process
    session_id = serializers.UUIDField(write_only=True, required=False)
    preference = serializers.CharField(write_only=True, required=False)
    time_to_select = serializers.IntegerField(write_only=True, required=False)
    changes_made = serializers.IntegerField(write_only=True, required=False)

    # UTM parameters (write-only for tracking)
    utm_source = serializers.CharField(write_only=True, required=False)
    utm_medium = serializers.CharField(write_only=True, required=False)
    utm_campaign = serializers.CharField(write_only=True, required=False)
    utm_content = serializers.CharField(write_only=True, required=False)
    utm_term = serializers.CharField(write_only=True, required=False)

    # Device info (write-only)
    device_type = serializers.CharField(write_only=True, required=False)
    browser = serializers.CharField(write_only=True, required=False)
    os = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = EarlyAccessSignup
        fields = [
            "id",
            "name",
            "email",
            "created_at",
            "updated_at",
            "is_verified",
            "verified_at",
            "login_count",
            "last_login",
            # Write-only fields for signup process
            "session_id",
            "preference",
            "time_to_select",
            "changes_made",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "device_type",
            "browser",
            "os",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "verification_token",
            "verification_sent_at",
            "verified_at",
            "login_count",
            "last_login",
        ]

    def validate_email(self, value):
        """Validate email format and uniqueness"""
        if not value:
            raise serializers.ValidationError("Email is required")

        # Normalize email
        value = value.lower().strip()

        # Validate format
        email_validator = EmailValidator()
        email_validator(value)

        # Check for duplicates (exclude current instance if updating)
        queryset = EarlyAccessSignup.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "An account with this email already exists"
            )

        return value

    def validate_name(self, value):
        """Validate name field"""
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required")

        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters long")

        if len(value) > 200:
            raise serializers.ValidationError("Name is too long")

        return value


class DailyStatsSerializer(serializers.ModelSerializer):
    """Serializer for DailyStats model"""

    class Meta:
        model = DailyStats
        fields = [
            "date",
            "ad_impressions",
            "ad_clicks",
            "page_views",
            "unique_visitors",
            "surveys_started",
            "surveys_completed",
            "signups",
            "verified_signups",
            "prefer_nothing",
            "prefer_notification",
            "prefer_updates",
            "click_through_rate",
            "page_conversion_rate",
            "overall_conversion_rate",
            "survey_completion_rate",
            "avg_time_on_site",
            "bounce_rate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class EventTrackingSerializer(serializers.Serializer):
    """Serializer for frontend event tracking payload"""

    # Required fields
    session_id = serializers.UUIDField(required=True)
    event_type = serializers.CharField(required=True)
    timestamp = serializers.DateTimeField(required=False)

    # Page context
    page_url = serializers.URLField(required=False, allow_blank=True)
    page_title = serializers.CharField(required=False, allow_blank=True)
    referrer = serializers.URLField(required=False, allow_blank=True)

    # UTM parameters
    utm_source = serializers.CharField(required=False, allow_blank=True)
    utm_medium = serializers.CharField(required=False, allow_blank=True)
    utm_campaign = serializers.CharField(required=False, allow_blank=True)
    utm_content = serializers.CharField(required=False, allow_blank=True)
    utm_term = serializers.CharField(required=False, allow_blank=True)

    # Device and browser info
    device_type = serializers.CharField(required=False, allow_blank=True)
    browser = serializers.CharField(required=False, allow_blank=True)
    os = serializers.CharField(required=False, allow_blank=True)

    # Event-specific data
    element_id = serializers.CharField(required=False, allow_blank=True)
    element_text = serializers.CharField(required=False, allow_blank=True)
    time_since_page_load = serializers.IntegerField(required=False, min_value=0)
    metadata = serializers.JSONField(required=False)

    # Screen and viewport info
    screen_resolution = serializers.CharField(required=False, allow_blank=True)
    viewport = serializers.CharField(required=False, allow_blank=True)

    def validate_event_type(self, value):
        """Validate event type"""
        valid_events = [choice[0] for choice in FunnelEvent.EVENT_TYPES]
        if value not in valid_events:
            raise serializers.ValidationError(f"Invalid event type: {value}")
        return value

    def validate_session_id(self, value):
        """Validate session ID format"""
        if not value:
            raise serializers.ValidationError("Session ID is required")
        return value


class SignupRequestSerializer(serializers.Serializer):
    """Serializer for complete signup request with tracking data"""

    # Core signup fields
    name = serializers.CharField(required=True, max_length=200)
    email = serializers.EmailField(required=True)

    # Tracking fields
    session_id = serializers.UUIDField(required=True)
    preference = serializers.CharField(required=False, allow_blank=True)
    time_to_select = serializers.IntegerField(required=False, min_value=0)
    changes_made = serializers.IntegerField(required=False, min_value=0, default=0)

    # UTM and device tracking
    utm_source = serializers.CharField(required=False, allow_blank=True)
    utm_medium = serializers.CharField(required=False, allow_blank=True)
    utm_campaign = serializers.CharField(required=False, allow_blank=True)
    utm_content = serializers.CharField(required=False, allow_blank=True)
    utm_term = serializers.CharField(required=False, allow_blank=True)
    device_type = serializers.CharField(required=False, allow_blank=True)
    browser = serializers.CharField(required=False, allow_blank=True)
    os = serializers.CharField(required=False, allow_blank=True)

    def validate_name(self, value):
        """Validate name"""
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters")
        return value

    def validate_email(self, value):
        """Validate and normalize email"""
        value = value.lower().strip()

        # Check for existing signup
        if EarlyAccessSignup.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered")

        return value

    def validate_preference(self, value):
        """Validate preference choice"""
        if value:
            valid_preferences = [
                choice[0] for choice in SurveyResponse.PREFERENCE_CHOICES
            ]
            if value not in valid_preferences:
                raise serializers.ValidationError(f"Invalid preference: {value}")
        return value
