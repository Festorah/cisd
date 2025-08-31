import uuid

from django.contrib.postgres.fields import JSONField
from django.core.validators import EmailValidator
from django.db import models
from django.utils import timezone


class PretotypeSession(models.Model):
    """
    Tracks each user's complete journey through the pretotype funnel.
    Captures more detailed data than Google Analytics can provide.
    """

    # Primary identification
    session_id = models.UUIDField(
        unique=True, db_index=True, help_text="Frontend-generated session UUID"
    )

    # Session timing and flow
    started_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When session began"
    )
    last_activity = models.DateTimeField(
        auto_now=True, help_text="Last recorded activity"
    )
    completed_funnel = models.BooleanField(
        default=False, db_index=True, help_text="Did user complete all 3 steps"
    )
    max_step_reached = models.PositiveSmallIntegerField(
        default=1, help_text="Highest step number reached (1-3)"
    )

    # Technical tracking
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="User IP for fraud detection"
    )
    user_agent = models.TextField(blank=True, help_text="Full user agent string")
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
    screen_size = models.CharField(
        max_length=20, blank=True, help_text="Screen resolution (e.g., 1920x1080)"
    )
    viewport_size = models.CharField(
        max_length=20, blank=True, help_text="Browser viewport size"
    )

    # Traffic attribution
    referrer = models.URLField(
        blank=True, max_length=500, help_text="Referring page URL"
    )
    utm_source = models.CharField(max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=100, blank=True, db_index=True)
    utm_campaign = models.CharField(max_length=200, blank=True, db_index=True)
    utm_content = models.CharField(max_length=200, blank=True)
    utm_term = models.CharField(max_length=200, blank=True)

    # Behavioral metrics
    total_time_on_site = models.PositiveIntegerField(
        default=0, help_text="Total time spent in seconds"
    )
    step_1_time = models.PositiveIntegerField(
        default=0, help_text="Time spent on landing page (seconds)"
    )
    step_2_time = models.PositiveIntegerField(
        default=0, help_text="Time spent on form (seconds)"
    )
    step_3_time = models.PositiveIntegerField(
        default=0, help_text="Time spent on thank you page (seconds)"
    )

    # Geographic (can be enhanced with IP lookup)
    country = models.CharField(
        max_length=2, blank=True, help_text="2-letter country code"
    )
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "pretotype_sessions"
        verbose_name = "Pretotype Session"
        verbose_name_plural = "Pretotype Sessions"
        indexes = [
            models.Index(fields=["started_at", "device_type"]),
            models.Index(fields=["completed_funnel", "started_at"]),
            models.Index(fields=["max_step_reached", "started_at"]),
            models.Index(fields=["utm_source", "utm_campaign"]),
        ]
        ordering = ["-started_at"]

    def __str__(self):
        return f"Session {str(self.session_id)[:8]} - Step {self.max_step_reached}"

    @property
    def conversion_rate_step_1_to_2(self):
        """Did user click CTA button"""
        return self.max_step_reached >= 2

    @property
    def conversion_rate_step_2_to_3(self):
        """Did user submit issue report"""
        return self.max_step_reached >= 3

    @property
    def provided_contact_info(self):
        """Did user provide contact details"""
        return hasattr(self, "contact") and self.contact.email


class PretotypeEvent(models.Model):
    """
    Granular event tracking - captures every meaningful interaction.
    This provides the detailed analytics Google Analytics can't give us.
    """

    EVENT_TYPES = [
        # Step 1 events
        ("page_view", "Page Loaded"),
        ("cta_hover", "CTA Button Hovered"),
        ("cta_click", "CTA Button Clicked"),
        ("scroll_behavior", "Page Scroll"),
        # Step 2 events
        ("form_displayed", "Form Displayed"),
        ("form_interaction", "Form Field Interaction"),
        ("dropdown_opened", "Issue Type Dropdown Opened"),
        ("issue_type_selected", "Issue Type Selected"),
        ("details_field_focused", "Details Field Focused"),
        ("details_typing", "User Typing in Details"),
        ("form_validation_error", "Form Validation Error"),
        ("issue_submitted", "Issue Report Submitted"),
        # Step 3 events
        ("thank_you_displayed", "Thank You Page Shown"),
        ("contact_field_focused", "Contact Field Focused"),
        ("checkbox_clicked", "Opt-in Checkbox Clicked"),
        ("contact_submitted", "Contact Details Submitted"),
        ("funnel_completed", "Full Funnel Completed"),
        # Drop-off events
        ("page_exit", "User Left Page"),
        ("form_abandoned", "Form Abandoned"),
        ("back_button", "Back Button Pressed"),
        ("tab_switch", "Switched to Another Tab"),
        # Error events
        ("javascript_error", "JavaScript Error"),
        ("network_error", "Network/API Error"),
    ]

    # Relationships
    session = models.ForeignKey(
        PretotypeSession, on_delete=models.CASCADE, related_name="events", db_index=True
    )

    # Event data
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    step = models.PositiveSmallIntegerField(help_text="Which step (1-3)")

    # Timing context
    time_from_start = models.PositiveIntegerField(
        help_text="Milliseconds since session start"
    )
    time_since_page_load = models.PositiveIntegerField(
        null=True, blank=True, help_text="Milliseconds since current page loaded"
    )

    # Event context
    page_url = models.URLField(blank=True, max_length=500)
    element_id = models.CharField(max_length=100, blank=True)
    element_text = models.CharField(max_length=200, blank=True)

    # Flexible metadata for event-specific data
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional event data in JSON format"
    )

    class Meta:
        db_table = "pretotype_events"
        verbose_name = "Pretotype Event"
        verbose_name_plural = "Pretotype Events"
        indexes = [
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["session", "step"]),
            models.Index(fields=["session", "timestamp"]),
            models.Index(fields=["step", "event_type"]),
        ]
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.get_event_type_display()} - Step {self.step}"


class PretotypeIssue(models.Model):
    """
    Stores the actual issues reported by users.
    This is the core data we're testing - will people report real issues?
    """

    ISSUE_TYPES = [
        ("light", "Light / Electricity"),
        ("roads", "Roads / Transportation"),
        ("waste", "Waste / Sanitation"),
        ("water", "Water Supply"),
        ("security", "Security"),
        ("healthcare", "Healthcare"),
        ("education", "Education"),
        ("others", "Others"),
    ]

    # Relationships
    session = models.OneToOneField(
        PretotypeSession,
        on_delete=models.CASCADE,
        related_name="issue",
        help_text="Which session reported this issue",
    )

    # Issue data
    issue_type = models.CharField(
        max_length=20,
        choices=ISSUE_TYPES,
        db_index=True,
        help_text="Type of public service issue",
    )
    issue_details = models.TextField(
        blank=True, help_text="Optional details provided by user"
    )

    # Image upload
    issue_image = models.ImageField(
        upload_to="pretotype/issues/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional photo of the issue",
    )
    image_url = models.URLField(
        blank=True, help_text="URL to uploaded image if using external storage"
    )

    # Quality metrics
    has_details = models.BooleanField(
        default=False, db_index=True, help_text="Did user provide additional details"
    )
    has_image = models.BooleanField(
        default=False, db_index=True, help_text="Did user provide a photo"
    )
    details_word_count = models.PositiveSmallIntegerField(
        default=0, help_text="Number of words in details field"
    )
    image_size = models.PositiveIntegerField(
        default=0, help_text="Image file size in bytes"
    )

    # Timing
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    time_to_submit = models.PositiveIntegerField(
        help_text="Seconds from form display to submission"
    )

    # Metadata for analysis
    is_test_data = models.BooleanField(
        default=False, db_index=True, help_text="Flag obvious test submissions"
    )

    class Meta:
        db_table = "pretotype_issues"
        verbose_name = "Pretotype Issue"
        verbose_name_plural = "Pretotype Issues"
        indexes = [
            models.Index(fields=["issue_type", "submitted_at"]),
            models.Index(fields=["has_details", "submitted_at"]),
            models.Index(fields=["has_image", "submitted_at"]),
            models.Index(fields=["is_test_data", "submitted_at"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.get_issue_type_display()} - {self.submitted_at.date()}"

    def save(self, *args, **kwargs):
        # Auto-calculate derived fields
        self.has_details = bool(self.issue_details.strip())
        if self.has_details:
            self.details_word_count = len(self.issue_details.split())

        # Check for image
        self.has_image = bool(self.issue_image or self.image_url)

        # Simple test data detection
        test_indicators = ["test", "testing", "sample", "example", "dummy"]
        issue_text = f"{self.issue_details}".lower()
        self.is_test_data = any(
            indicator in issue_text for indicator in test_indicators
        )

        super().save(*args, **kwargs)

    def get_reaction_counts(self):
        """Get reaction counts grouped by type"""
        from django.db.models import Count

        return dict(
            self.reactions.values("reaction_type")
            .annotate(count=Count("id"))
            .values_list("reaction_type", "count")
        )

    def get_user_reaction(self, session_id):
        """Get user's reaction to this issue"""
        try:
            return self.reactions.get(session__session_id=session_id).reaction_type
        except PretotypeReaction.DoesNotExist:
            return None

    def get_approved_comments_count(self):
        """Get count of approved comments"""
        return self.comments.filter(is_approved=True, parent_comment=None).count()

    def get_current_status(self):
        """Get the most recent status update"""
        latest_status = self.status_updates.first()
        return latest_status.status if latest_status else "reported"

    def get_status_display_info(self):
        """Get status with color and icon for display"""
        status = self.get_current_status()
        status_map = {
            "reported": {"color": "blue", "icon": "📋", "text": "Reported"},
            "acknowledged": {"color": "yellow", "icon": "👀", "text": "Acknowledged"},
            "investigating": {"color": "orange", "icon": "🔍", "text": "Investigating"},
            "in_progress": {"color": "purple", "icon": "🔨", "text": "In Progress"},
            "resolved": {"color": "green", "icon": "✅", "text": "Resolved"},
            "duplicate": {"color": "gray", "icon": "🔗", "text": "Duplicate"},
            "rejected": {"color": "red", "icon": "❌", "text": "Not Actionable"},
        }
        return status_map.get(status, status_map["reported"])


class PretotypeContact(models.Model):
    """
    Stores contact information from users who want updates.
    This shows genuine interest vs casual testing.
    """

    # Relationships
    session = models.OneToOneField(
        PretotypeSession,
        on_delete=models.CASCADE,
        related_name="contact",
        help_text="Which session provided contact info",
    )

    # Contact data
    email = models.EmailField(blank=True, help_text="Email address for updates")
    whatsapp = models.CharField(
        max_length=20, blank=True, help_text="WhatsApp number for updates"
    )
    opted_in = models.BooleanField(
        default=False, db_index=True, help_text="Did user check the opt-in box"
    )

    # Quality indicators
    email_domain = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Email domain for analysis (gmail.com, yahoo.com, etc)",
    )
    is_business_email = models.BooleanField(
        default=False, help_text="Appears to be business/organization email"
    )

    # Timing
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Follow-up tracking
    launch_notification_sent = models.BooleanField(
        default=False, help_text="Have we notified them about launch"
    )
    launch_notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pretotype_contacts"
        verbose_name = "Pretotype Contact"
        verbose_name_plural = "Pretotype Contacts"
        indexes = [
            models.Index(fields=["opted_in", "submitted_at"]),
            models.Index(fields=["email_domain", "submitted_at"]),
            models.Index(fields=["is_business_email", "submitted_at"]),
            models.Index(fields=["launch_notification_sent"]),
        ]
        ordering = ["-submitted_at"]

    def __str__(self):
        contact_method = self.email or self.whatsapp or "No contact info"
        return f"{contact_method} - {self.submitted_at.date()}"

    def save(self, *args, **kwargs):
        # Extract email domain for analysis
        if self.email:
            domain = self.email.split("@")[-1].lower()
            self.email_domain = domain

            # Simple business email detection
            personal_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
            self.is_business_email = domain not in personal_domains

        super().save(*args, **kwargs)


class PretotypeAnalytics(models.Model):
    """
    Daily aggregated analytics for fast dashboard queries.
    Auto-calculated from the detailed event data.
    """

    # Date identification
    date = models.DateField(unique=True, db_index=True)

    # Funnel metrics
    total_sessions = models.PositiveIntegerField(default=0)
    step_1_sessions = models.PositiveIntegerField(default=0)  # Saw landing page
    step_2_sessions = models.PositiveIntegerField(default=0)  # Clicked CTA
    step_3_sessions = models.PositiveIntegerField(default=0)  # Submitted issue
    completed_sessions = models.PositiveIntegerField(default=0)  # Provided contact

    # Issue breakdown
    issues_light = models.PositiveIntegerField(default=0)
    issues_roads = models.PositiveIntegerField(default=0)
    issues_waste = models.PositiveIntegerField(default=0)
    issues_water = models.PositiveIntegerField(default=0)
    issues_security = models.PositiveIntegerField(default=0)
    issues_healthcare = models.PositiveIntegerField(default=0)
    issues_education = models.PositiveIntegerField(default=0)
    issues_others = models.PositiveIntegerField(default=0)

    # Quality metrics
    issues_with_details = models.PositiveIntegerField(default=0)
    avg_time_to_submit = models.FloatField(null=True, blank=True)
    contacts_with_email = models.PositiveIntegerField(default=0)
    contacts_with_whatsapp = models.PositiveIntegerField(default=0)

    # Conversion rates (calculated)
    cta_click_rate = models.FloatField(null=True, blank=True)
    issue_submission_rate = models.FloatField(null=True, blank=True)
    contact_conversion_rate = models.FloatField(null=True, blank=True)
    overall_conversion_rate = models.FloatField(null=True, blank=True)

    # Device breakdown
    mobile_sessions = models.PositiveIntegerField(default=0)
    desktop_sessions = models.PositiveIntegerField(default=0)
    tablet_sessions = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pretotype_analytics"
        verbose_name = "Pretotype Daily Analytics"
        verbose_name_plural = "Pretotype Daily Analytics"
        ordering = ["-date"]

    def __str__(self):
        return f"Analytics for {self.date} - {self.completed_sessions} completed"

    def calculate_rates(self):
        """Calculate and update conversion rates"""
        if self.step_1_sessions > 0:
            self.cta_click_rate = round(
                (self.step_2_sessions / self.step_1_sessions) * 100, 2
            )
            self.overall_conversion_rate = round(
                (self.completed_sessions / self.step_1_sessions) * 100, 2
            )

        if self.step_2_sessions > 0:
            self.issue_submission_rate = round(
                (self.step_3_sessions / self.step_2_sessions) * 100, 2
            )

        if self.step_3_sessions > 0:
            self.contact_conversion_rate = round(
                (self.completed_sessions / self.step_3_sessions) * 100, 2
            )

        self.save(
            update_fields=[
                "cta_click_rate",
                "issue_submission_rate",
                "contact_conversion_rate",
                "overall_conversion_rate",
            ]
        )


class PretotypeComment(models.Model):
    """
    Comments on issue reports - allows community discussion
    """

    # Relationships
    issue = models.ForeignKey(
        PretotypeIssue,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="Issue being commented on",
    )
    session = models.ForeignKey(
        PretotypeSession,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="Session of commenter",
    )
    parent_comment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        help_text="Parent comment if this is a reply",
    )

    # Comment content
    content = models.TextField(max_length=1000, help_text="Comment text content")
    commenter_name = models.CharField(
        max_length=100, blank=True, help_text="Display name for commenter"
    )
    commenter_type = models.CharField(
        max_length=20,
        choices=[
            ("citizen", "Citizen"),
            ("government", "Government Official"),
            ("verified", "Verified Organization"),
            ("anonymous", "Anonymous"),
        ],
        default="citizen",
        help_text="Type of commenter",
    )

    # Moderation and status
    is_approved = models.BooleanField(
        default=True, help_text="Whether comment is approved for display"
    )
    is_flagged = models.BooleanField(
        default=False, help_text="Whether comment has been flagged for review"
    )
    is_government_response = models.BooleanField(
        default=False, help_text="Whether this is an official government response"
    )

    # Engagement metrics
    upvotes = models.PositiveIntegerField(default=0, help_text="Number of upvotes")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address for moderation"
    )

    class Meta:
        db_table = "pretotype_comments"
        verbose_name = "Pretotype Comment"
        verbose_name_plural = "Pretotype Comments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["issue", "-created_at"]),
            models.Index(fields=["is_approved", "-created_at"]),
            models.Index(fields=["is_government_response", "-created_at"]),
            models.Index(fields=["parent_comment"]),
        ]

    def __str__(self):
        return (
            f"Comment on {self.issue.get_issue_type_display()}: {self.content[:50]}..."
        )

    @property
    def is_reply(self):
        return self.parent_comment is not None

    @property
    def reply_count(self):
        return self.replies.filter(is_approved=True).count()


class PretotypeReaction(models.Model):
    """
    Reactions to issue reports (like, support, me_too, etc.)
    """

    REACTION_TYPES = [
        ("like", "👍 Like"),
        ("support", "🤝 Support"),
        ("me_too", "🙋 Me Too"),
        ("heart", "❤️ Care"),
        ("angry", "😠 Angry"),
        ("sad", "😢 Sad"),
    ]

    # Relationships
    issue = models.ForeignKey(
        PretotypeIssue,
        on_delete=models.CASCADE,
        related_name="reactions",
        help_text="Issue being reacted to",
    )
    session = models.ForeignKey(
        PretotypeSession,
        on_delete=models.CASCADE,
        related_name="reactions",
        help_text="Session of person reacting",
    )

    # Reaction data
    reaction_type = models.CharField(
        max_length=20, choices=REACTION_TYPES, help_text="Type of reaction"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pretotype_reactions"
        verbose_name = "Pretotype Reaction"
        verbose_name_plural = "Pretotype Reactions"
        # Ensure one reaction per session per issue
        unique_together = ["issue", "session"]
        indexes = [
            models.Index(fields=["issue", "reaction_type"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_reaction_type_display()} on {self.issue.get_issue_type_display()}"


class PretotypeIssueStatus(models.Model):
    """
    Track status updates for issues (acknowledgment, investigation, resolution)
    """

    STATUS_TYPES = [
        ("reported", "Reported"),
        ("acknowledged", "Acknowledged"),
        ("investigating", "Under Investigation"),
        ("in_progress", "Work in Progress"),
        ("resolved", "Resolved"),
        ("duplicate", "Duplicate"),
        ("rejected", "Not Actionable"),
    ]

    # Relationships
    issue = models.ForeignKey(
        PretotypeIssue,
        on_delete=models.CASCADE,
        related_name="status_updates",
        help_text="Issue being updated",
    )

    # Status data
    status = models.CharField(
        max_length=20, choices=STATUS_TYPES, help_text="New status"
    )
    message = models.TextField(
        max_length=500, blank=True, help_text="Optional status update message"
    )
    updated_by = models.CharField(
        max_length=200, help_text="Who provided this update (government dept, etc.)"
    )

    # Evidence/proof
    evidence_image_url = models.URLField(
        blank=True, help_text="Optional image showing progress/resolution"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pretotype_issue_status"
        verbose_name = "Issue Status Update"
        verbose_name_plural = "Issue Status Updates"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["issue", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.issue.get_issue_type_display()} - {self.get_status_display()}"
