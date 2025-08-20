import uuid

from django.contrib.postgres.fields import JSONField
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.utils import timezone


class UserSession(models.Model):
    """
    Tracks a user's complete journey through the civic engagement funnel.
    Each browser session gets a unique tracking ID.
    """

    # Primary identification
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        help_text="Unique identifier for this user session",
    )

    # Technical tracking
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="User's IP address for analytics and fraud prevention",
    )
    user_agent = models.TextField(
        blank=True, help_text="Browser and device information"
    )

    # Session timing
    first_seen = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When user first arrived"
    )
    last_activity = models.DateTimeField(
        auto_now=True, db_index=True, help_text="Last recorded activity"
    )

    # Marketing attribution (UTM parameters)
    utm_source = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Traffic source (google, facebook, twitter, etc.)",
    )
    utm_medium = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Marketing medium (cpc, social, email, etc.)",
    )
    utm_campaign = models.CharField(
        max_length=200, blank=True, db_index=True, help_text="Campaign name"
    )
    utm_content = models.CharField(
        max_length=200, blank=True, help_text="Ad content or creative variant"
    )
    utm_term = models.CharField(
        max_length=200, blank=True, help_text="Keywords for paid search"
    )
    referrer = models.URLField(
        blank=True, max_length=500, help_text="Referring website URL"
    )

    # Geographic data
    country_code = models.CharField(
        max_length=2,
        blank=True,
        db_index=True,
        validators=[RegexValidator(r"^[A-Z]{2}$", "Must be 2-letter country code")],
        help_text="ISO 2-letter country code (e.g., NG)",
    )
    city = models.CharField(
        max_length=100, blank=True, db_index=True, help_text="City name"
    )
    region = models.CharField(max_length=100, blank=True, help_text="State or region")

    # Device information
    device_type = models.CharField(
        max_length=20,
        choices=[
            ("mobile", "Mobile"),
            ("tablet", "Tablet"),
            ("desktop", "Desktop"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        db_index=True,
    )
    browser = models.CharField(
        max_length=50, blank=True, help_text="Browser name (Chrome, Safari, etc.)"
    )
    os = models.CharField(max_length=50, blank=True, help_text="Operating system")

    # Session quality metrics
    page_views = models.PositiveIntegerField(
        default=0, help_text="Number of pages viewed in this session"
    )
    time_on_site = models.PositiveIntegerField(
        default=0, help_text="Total time spent on site in seconds"
    )
    is_bounce = models.BooleanField(
        default=True,
        db_index=True,
        help_text="True if user left without meaningful engagement",
    )

    class Meta:
        db_table = "user_sessions"
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"
        indexes = [
            models.Index(fields=["first_seen", "utm_source"]),
            models.Index(fields=["country_code", "city"]),
            models.Index(fields=["device_type", "first_seen"]),
            models.Index(fields=["utm_campaign", "first_seen"]),
            models.Index(fields=["is_bounce", "first_seen"]),
        ]
        ordering = ["-first_seen"]

    def __str__(self):
        return f"Session {str(self.session_id)[:8]} - {self.first_seen.date()}"

    @property
    def duration_minutes(self):
        """Calculate session duration in minutes"""
        if self.time_on_site:
            return round(self.time_on_site / 60, 1)
        return 0

    @property
    def converted(self):
        """Check if this session resulted in a signup"""
        return hasattr(self, "signup")


class FunnelEvent(models.Model):
    """
    Individual events in the user conversion funnel.
    Tracks every meaningful action users take.
    """

    EVENT_TYPES = [
        ("ad_impression", "Ad Impression"),
        ("ad_click", "Ad Click"),
        ("page_view", "Page View"),
        ("survey_start", "Survey Started"),
        ("survey_complete", "Survey Completed"),
        ("form_focus", "Form Field Focused"),
        ("form_start", "Form Started"),
        ("form_error", "Form Validation Error"),
        ("signup_attempt", "Signup Attempted"),
        ("signup_success", "Signup Successful"),
        ("page_exit", "Page Exit"),
    ]

    # Relationships
    session = models.ForeignKey(
        UserSession, on_delete=models.CASCADE, related_name="events", db_index=True
    )

    # Event data
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        db_index=True,
        help_text="Type of user action",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When this event occurred"
    )

    # Page context
    page_url = models.URLField(
        blank=True, max_length=500, help_text="URL where event occurred"
    )
    page_title = models.CharField(max_length=200, blank=True, help_text="Page title")

    # Event-specific data
    element_id = models.CharField(
        max_length=100, blank=True, help_text="DOM element ID if applicable"
    )
    element_text = models.CharField(
        max_length=200, blank=True, help_text="Text content of clicked element"
    )

    # Flexible metadata storage
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional event data in JSON format"
    )

    # Timing
    time_since_page_load = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Milliseconds since page load when event occurred",
    )

    class Meta:
        db_table = "funnel_events"
        verbose_name = "Funnel Event"
        verbose_name_plural = "Funnel Events"
        indexes = [
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["session", "event_type"]),
            models.Index(fields=["session", "timestamp"]),
            models.Index(fields=["timestamp", "event_type"]),
        ]
        ordering = ["timestamp"]

    def __str__(self):
        return (
            f"{self.get_event_type_display()} - {self.timestamp.strftime('%H:%M:%S')}"
        )


class SurveyResponse(models.Model):
    """
    Captures user preferences for civic engagement follow-up.
    This is key product-market fit data.
    """

    PREFERENCE_CHOICES = [
        ("nothing", "Nothing - Just report and move on"),
        ("notification", "Be notified when resolved"),
        ("updates", "Get progress updates throughout"),
    ]

    # Relationships
    session = models.OneToOneField(
        UserSession, on_delete=models.CASCADE, related_name="survey"
    )

    # Survey data
    preference = models.CharField(
        max_length=20,
        choices=PREFERENCE_CHOICES,
        db_index=True,
        help_text="User's preferred level of engagement",
    )

    # Timing and engagement metrics
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    time_to_select = models.PositiveIntegerField(
        null=True, blank=True, help_text="Seconds from page load to option selection"
    )
    changed_mind_count = models.PositiveSmallIntegerField(
        default=0, help_text="How many times user changed their selection"
    )

    class Meta:
        db_table = "survey_responses"
        verbose_name = "Survey Response"
        verbose_name_plural = "Survey Responses"
        indexes = [
            models.Index(fields=["preference", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_preference_display()} - {self.created_at.date()}"

    @property
    def engagement_level(self):
        """Categorize engagement preference"""
        mapping = {"nothing": "low", "notification": "medium", "updates": "high"}
        return mapping.get(self.preference, "unknown")


class EarlyAccessSignup(models.Model):
    """
    The conversion event - successful early access registration.
    This is the primary success metric.
    """

    # Relationships
    session = models.OneToOneField(
        UserSession,
        on_delete=models.SET_NULL,
        related_name="signup",
        null=True,
        blank=True,
        help_text="Associated user session (if tracked)",
    )

    # Core signup data
    name = models.CharField(max_length=200, help_text="User's full name")
    email = models.EmailField(
        unique=True,
        db_index=True,
        validators=[EmailValidator()],
        help_text="User's email address",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When signup was completed"
    )
    updated_at = models.DateTimeField(auto_now=True, help_text="Last modification time")

    # Email verification workflow
    is_verified = models.BooleanField(
        default=False, db_index=True, help_text="Has email been verified"
    )
    verification_token = models.UUIDField(
        default=uuid.uuid4, unique=True, help_text="Email verification token"
    )
    verification_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When verification email was sent"
    )
    verified_at = models.DateTimeField(
        null=True, blank=True, db_index=True, help_text="When email was verified"
    )

    # Legacy fields for backward compatibility
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address (legacy field)"
    )
    user_agent = models.TextField(blank=True, help_text="User agent (legacy field)")

    # Engagement tracking
    login_count = models.PositiveIntegerField(
        default=0, help_text="Number of times user has logged in"
    )
    last_login = models.DateTimeField(
        null=True, blank=True, help_text="Last login timestamp"
    )

    class Meta:
        db_table = "early_access_signups"
        verbose_name = "Early Access Signup"
        verbose_name_plural = "Early Access Signups"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_verified", "created_at"]),
            models.Index(fields=["verified_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} - {self.created_at.date()}"

    @property
    def has_survey_response(self):
        """Check if signup includes survey data"""
        return self.session and hasattr(self.session, "survey")

    @property
    def user_preference(self):
        """Get user's civic engagement preference"""
        if self.has_survey_response:
            return self.session.survey.preference
        return None

    @property
    def traffic_source(self):
        """Get user's traffic source"""
        if self.session:
            return self.session.utm_source or "direct"
        return "unknown"


class DailyStats(models.Model):
    """
    Pre-computed daily analytics for fast dashboard loading.
    Updated via background task or management command.
    """

    # Date identification
    date = models.DateField(
        unique=True, db_index=True, help_text="Date for these statistics"
    )

    # Funnel metrics
    ad_impressions = models.PositiveIntegerField(
        default=0, help_text="Total ad impressions"
    )
    ad_clicks = models.PositiveIntegerField(default=0, help_text="Total ad clicks")
    page_views = models.PositiveIntegerField(default=0, help_text="Total page views")
    unique_visitors = models.PositiveIntegerField(
        default=0, help_text="Unique sessions"
    )
    surveys_started = models.PositiveIntegerField(
        default=0, help_text="Users who began survey"
    )
    surveys_completed = models.PositiveIntegerField(
        default=0, help_text="Users who completed survey"
    )
    signups = models.PositiveIntegerField(default=0, help_text="Successful signups")
    verified_signups = models.PositiveIntegerField(
        default=0, help_text="Email verified signups"
    )

    # Survey preference breakdown
    prefer_nothing = models.PositiveIntegerField(
        default=0, help_text="Users preferring no follow-up"
    )
    prefer_notification = models.PositiveIntegerField(
        default=0, help_text="Users wanting resolution notification"
    )
    prefer_updates = models.PositiveIntegerField(
        default=0, help_text="Users wanting progress updates"
    )

    # Conversion rates (calculated and stored)
    click_through_rate = models.FloatField(
        null=True, blank=True, help_text="Ad clicks / impressions * 100"
    )
    page_conversion_rate = models.FloatField(
        null=True, blank=True, help_text="Signups / page views * 100"
    )
    overall_conversion_rate = models.FloatField(
        null=True, blank=True, help_text="Signups / ad impressions * 100"
    )
    survey_completion_rate = models.FloatField(
        null=True, blank=True, help_text="Survey completed / started * 100"
    )

    # Quality metrics
    avg_time_on_site = models.FloatField(
        null=True, blank=True, help_text="Average session duration in minutes"
    )
    bounce_rate = models.FloatField(
        null=True, blank=True, help_text="Percentage of single-page sessions"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "daily_stats"
        verbose_name = "Daily Statistics"
        verbose_name_plural = "Daily Statistics"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return f"Stats for {self.date} - {self.signups} signups"

    def calculate_rates(self):
        """Calculate and update conversion rates"""
        if self.ad_impressions > 0:
            self.click_through_rate = round(
                (self.ad_clicks / self.ad_impressions) * 100, 2
            )
            if self.signups > 0:
                self.overall_conversion_rate = round(
                    (self.signups / self.ad_impressions) * 100, 2
                )

        if self.page_views > 0 and self.signups > 0:
            self.page_conversion_rate = round((self.signups / self.page_views) * 100, 2)

        if self.surveys_started > 0 and self.surveys_completed > 0:
            self.survey_completion_rate = round(
                (self.surveys_completed / self.surveys_started) * 100, 2
            )

        if self.unique_visitors > 0:
            bounce_sessions = UserSession.objects.filter(
                first_seen__date=self.date, is_bounce=True
            ).count()
            self.bounce_rate = round((bounce_sessions / self.unique_visitors) * 100, 2)

        self.save(
            update_fields=[
                "click_through_rate",
                "page_conversion_rate",
                "overall_conversion_rate",
                "survey_completion_rate",
                "bounce_rate",
            ]
        )
