from datetime import timedelta

from django.contrib import admin
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [
        "session_display",
        "first_seen",
        "device_type",
        "browser",
        "utm_source",
        "page_views",
        "time_on_site_display",
        "is_bounce",
        "has_signup",
    ]
    list_filter = [
        "device_type",
        "browser",
        "utm_source",
        "utm_medium",
        "is_bounce",
        "first_seen",
        "country_code",
    ]
    search_fields = ["session_id", "ip_address", "utm_campaign", "city"]
    readonly_fields = [
        "session_id",
        "first_seen",
        "last_activity",
        "duration_minutes",
        "converted",
    ]
    date_hierarchy = "first_seen"
    ordering = ["-first_seen"]

    fieldsets = (
        (
            "Session Info",
            {
                "fields": (
                    "session_id",
                    "first_seen",
                    "last_activity",
                    "ip_address",
                    "user_agent",
                )
            },
        ),
        (
            "Marketing Attribution",
            {
                "fields": (
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                    "utm_content",
                    "utm_term",
                    "referrer",
                ),
                "classes": ["collapse"],
            },
        ),
        (
            "Location & Device",
            {
                "fields": (
                    "country_code",
                    "city",
                    "region",
                    "device_type",
                    "browser",
                    "os",
                )
            },
        ),
        (
            "Engagement Metrics",
            {"fields": ("page_views", "time_on_site", "is_bounce", "converted")},
        ),
    )

    def session_display(self, obj):
        """Display short session ID"""
        return f"{str(obj.session_id)[:8]}..."

    session_display.short_description = "Session"

    def time_on_site_display(self, obj):
        """Display time on site in minutes"""
        if obj.time_on_site:
            return f"{obj.duration_minutes}m"
        return "-"

    time_on_site_display.short_description = "Time on Site"

    def has_signup(self, obj):
        """Show if session resulted in signup"""
        return hasattr(obj, "signup")

    has_signup.short_description = "Converted"
    has_signup.boolean = True


@admin.register(FunnelEvent)
class FunnelEventAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "session_short",
        "event_type",
        "page_title_short",
        "time_since_load",
        "element_id",
    ]
    list_filter = ["event_type", "timestamp"]
    search_fields = ["session__session_id", "page_url", "page_title", "element_id"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    fieldsets = (
        ("Event Info", {"fields": ("session", "event_type", "timestamp")}),
        (
            "Page Context",
            {"fields": ("page_url", "page_title", "element_id", "element_text")},
        ),
        (
            "Timing & Data",
            {"fields": ("time_since_page_load", "metadata"), "classes": ["collapse"]},
        ),
    )

    def session_short(self, obj):
        """Display short session ID with link"""
        session_id = str(obj.session.session_id)[:8]
        url = reverse("admin:tpsq_usersession_change", args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, session_id)

    session_short.short_description = "Session"

    def page_title_short(self, obj):
        """Display truncated page title"""
        if obj.page_title:
            return obj.page_title[:50] + ("..." if len(obj.page_title) > 50 else "")
        return "-"

    page_title_short.short_description = "Page"

    def time_since_load(self, obj):
        """Display time since page load in seconds"""
        if obj.time_since_page_load:
            return f"{obj.time_since_page_load/1000:.1f}s"
        return "-"

    time_since_load.short_description = "Load Time"


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "session_short",
        "preference",
        "question_type_display",
        "engagement_level",
        "time_to_select",
        "changed_mind_count",
    ]
    list_filter = [
        "preference",
        "created_at",
        (
            "preference",
            admin.ChoicesFieldListFilter,
        ),  # Better filtering for preferences
    ]
    search_fields = ["session__session_id"]
    readonly_fields = ["created_at", "engagement_level", "question_type"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    def session_short(self, obj):
        """Display short session ID with link"""
        session_id = str(obj.session.session_id)[:8]
        url = reverse("admin:tpsq_usersession_change", args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', url, session_id)

    session_short.short_description = "Session"

    def question_type_display(self, obj):
        """Show which question type this response belongs to"""
        question_type = obj.question_type
        colors = {
            "engagement_followup": "blue",
            "app_usage_intent": "green",
            "unknown": "gray",
        }
        labels = {
            "engagement_followup": "Follow-up",
            "app_usage_intent": "App Intent",
            "unknown": "Unknown",
        }

        color = colors.get(question_type, "gray")
        label = labels.get(question_type, "Unknown")

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, label
        )

    question_type_display.short_description = "Question Type"

    # Add custom list filter for question types
    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request))
        list_filter.append(QuestionTypeFilter)
        return list_filter


# Custom admin filter for question types
class QuestionTypeFilter(admin.SimpleListFilter):
    title = "Question Type"
    parameter_name = "question_type"

    def lookups(self, request, model_admin):
        return [
            ("engagement_followup", "Follow-up Engagement"),
            ("app_usage_intent", "App Usage Intent"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "engagement_followup":
            return queryset.filter(
                preference__in=["nothing", "notification", "updates"]
            )
        elif self.value() == "app_usage_intent":
            return queryset.filter(
                preference__in=["yes_would_use", "no_wouldnt_use", "not_sure"]
            )
        return queryset


class PreferenceTypeFilter(admin.SimpleListFilter):
    title = "Preference Type"
    parameter_name = "preference_type"

    def lookups(self, request, model_admin):
        return [
            ("engagement_followup", "Follow-up Engagement"),
            ("app_usage_intent", "App Usage Intent"),
            ("no_survey", "No Survey Response"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "engagement_followup":
            return queryset.filter(
                session__survey__preference__in=["nothing", "notification", "updates"]
            )
        elif self.value() == "app_usage_intent":
            return queryset.filter(
                session__survey__preference__in=[
                    "yes_would_use",
                    "no_wouldnt_use",
                    "not_sure",
                ]
            )
        elif self.value() == "no_survey":
            return queryset.filter(session__survey__isnull=True)
        return queryset


@admin.register(EarlyAccessSignup)
class EarlyAccessSignupAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "name",
        "created_at",
        "is_verified",
        "traffic_source",
        "user_preference",
        "login_count",
    ]
    list_filter = [
        "is_verified",
        "created_at",
        "session__utm_source",
        "session__device_type",
        "session__survey__preference",
        PreferenceTypeFilter,
    ]
    search_fields = ["email", "name", "session__session_id"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "verification_token",
        "has_survey_response",
        "user_preference",
        "traffic_source",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        ("Signup Info", {"fields": ("name", "email", "created_at", "updated_at")}),
        (
            "Verification",
            {
                "fields": (
                    "is_verified",
                    "verification_token",
                    "verification_sent_at",
                    "verified_at",
                )
            },
        ),
        (
            "Tracking Data",
            {
                "fields": (
                    "session",
                    "has_survey_response",
                    "user_preference",
                    "traffic_source",
                ),
                "classes": ["collapse"],
            },
        ),
        (
            "Engagement",
            {"fields": ("login_count", "last_login"), "classes": ["collapse"]},
        ),
        (
            "Legacy Fields",
            {"fields": ("ip_address", "user_agent"), "classes": ["collapse"]},
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return (
            super().get_queryset(request).select_related("session", "session__survey")
        )

    def preference_type_display(self, obj):
        """Show which type of preference question the user answered"""
        if obj.has_survey_response:
            question_type = obj.session.survey.question_type
            if question_type == "engagement_followup":
                return format_html('<span style="color: blue;">Follow-up</span>')
            elif question_type == "app_usage_intent":
                return format_html('<span style="color: green;">App Intent</span>')
        return "-"

    preference_type_display.short_description = "Preference Type"


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "unique_visitors",
        "page_views",
        "signups",
        "conversion_rate_display",
        "bounce_rate_display",
        "updated_at",
    ]
    list_filter = ["date"]
    search_fields = ["date"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-date"]

    fieldsets = (
        ("Date", {"fields": ("date",)}),
        (
            "Funnel Metrics",
            {
                "fields": (
                    "ad_impressions",
                    "ad_clicks",
                    "page_views",
                    "unique_visitors",
                    "surveys_started",
                    "surveys_completed",
                    "signups",
                    "verified_signups",
                )
            },
        ),
        (
            "User Preferences",
            {"fields": ("prefer_nothing", "prefer_notification", "prefer_updates")},
        ),
        (
            "Conversion Rates",
            {
                "fields": (
                    "click_through_rate",
                    "page_conversion_rate",
                    "overall_conversion_rate",
                    "survey_completion_rate",
                ),
                "classes": ["collapse"],
            },
        ),
        (
            "Quality Metrics",
            {"fields": ("avg_time_on_site", "bounce_rate"), "classes": ["collapse"]},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ["collapse"]},
        ),
    )

    def conversion_rate_display(self, obj):
        """Display conversion rate with color coding"""
        if obj.page_conversion_rate is not None:
            rate = obj.page_conversion_rate
            color = "green" if rate >= 5 else "orange" if rate >= 2 else "red"
            return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
        return "-"

    conversion_rate_display.short_description = "Conversion Rate"

    def bounce_rate_display(self, obj):
        """Display bounce rate with color coding"""
        if obj.bounce_rate is not None:
            rate = obj.bounce_rate
            color = "green" if rate <= 40 else "orange" if rate <= 60 else "red"
            return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
        return "-"

    bounce_rate_display.short_description = "Bounce Rate"

    actions = ["recalculate_rates"]

    def recalculate_rates(self, request, queryset):
        """Admin action to recalculate conversion rates"""
        count = 0
        for stats in queryset:
            stats.calculate_rates()
            count += 1

        self.message_user(
            request, f"Recalculated rates for {count} daily stats records."
        )

    recalculate_rates.short_description = "Recalculate conversion rates"


# Custom admin site configuration
admin.site.site_header = "CISD Analytics Administration"
admin.site.site_title = "CISD Analytics"
admin.site.index_title = "Welcome to CISD Analytics Administration"


# Additional admin customizations
class AnalyticsAdminMixin:
    """Mixin to add analytics context to admin pages"""

    def changelist_view(self, request, extra_context=None):
        # Add summary stats to changelist pages
        extra_context = extra_context or {}

        if hasattr(self.model, "objects"):
            # Recent activity (last 7 days)
            week_ago = timezone.now() - timedelta(days=7)

            if hasattr(self.model, "created_at"):
                recent_count = self.model.objects.filter(
                    created_at__gte=week_ago
                ).count()
                extra_context["recent_count"] = recent_count
            elif hasattr(self.model, "first_seen"):
                recent_count = self.model.objects.filter(
                    first_seen__gte=week_ago
                ).count()
                extra_context["recent_count"] = recent_count

        return super().changelist_view(request, extra_context=extra_context)


# Apply analytics mixin to relevant admin classes
UserSessionAdmin.__bases__ = (AnalyticsAdminMixin,) + UserSessionAdmin.__bases__
EarlyAccessSignupAdmin.__bases__ = (
    AnalyticsAdminMixin,
) + EarlyAccessSignupAdmin.__bases__
