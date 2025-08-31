import json
import logging
import uuid
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from tpsq.models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)
from user_agents import parse

# Set up logging
logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LandingPageView(TemplateView):
    """Serve the landing page with tracking enabled and CSRF token"""

    template_name = "tpsq/intervention.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure CSRF token is available in template context
        context["csrf_token"] = get_token(self.request)
        return context


class DashboardView(TemplateView):
    """Analytics dashboard for tracking performance"""

    template_name = "tpsq/analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range (last 30 days by default)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

        context.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "csrf_token": get_token(self.request),
            }
        )

        return context


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def parse_user_agent(user_agent_string):
    """Parse user agent string to extract device info"""
    if not user_agent_string:
        return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}

    user_agent = parse(user_agent_string)

    # Determine device type
    if user_agent.is_mobile:
        device_type = "mobile"
    elif user_agent.is_tablet:
        device_type = "tablet"
    elif user_agent.is_pc:
        device_type = "desktop"
    else:
        device_type = "unknown"

    return {
        "device_type": device_type,
        "browser": user_agent.browser.family or "unknown",
        "os": user_agent.os.family or "unknown",
    }


def get_or_create_session(session_id, request_data, request):
    """Get existing session or create new one"""
    try:
        # Validate UUID format
        try:
            uuid.UUID(session_id)  # This will raise ValueError if invalid
        except (ValueError, TypeError):
            # If session_id is not a valid UUID, generate a new one
            session_id = str(uuid.uuid4())
            logger.warning(
                f"[SESSION] Invalid UUID provided, generated new one: {session_id}"
            )

        try:
            session = UserSession.objects.get(session_id=session_id)
            # Update last activity
            session.last_activity = timezone.now()
            session.save(update_fields=["last_activity"])
            return session
        except UserSession.DoesNotExist:
            pass  # Will create new session below

    except Exception as e:
        logger.error(f"[SESSION-ERROR] Error validating session: {str(e)}")
        session_id = str(uuid.uuid4())

    # Create new session
    client_ip = get_client_ip(request)
    user_agent_string = request.META.get("HTTP_USER_AGENT", "")
    device_info = parse_user_agent(user_agent_string)

    session = UserSession.objects.create(
        session_id=session_id,
        ip_address=client_ip,
        user_agent=user_agent_string,
        utm_source=request_data.get("utm_source", ""),
        utm_medium=request_data.get("utm_medium", ""),
        utm_campaign=request_data.get("utm_campaign", ""),
        utm_content=request_data.get("utm_content", ""),
        utm_term=request_data.get("utm_term", ""),
        referrer=request_data.get("referrer", ""),
        device_type=device_info["device_type"],
        browser=device_info["browser"],
        os=device_info["os"],
    )

    logger.info(f"[SESSION-CREATED] New session: {session.session_id}")
    return session


@api_view(["POST"])
@permission_classes([AllowAny])
def track_event(request):
    """Handle event tracking from frontend with CSRF protection"""
    try:
        data = request.data

        # Ensure data is a dictionary (DRF should handle this, but double-check)
        if isinstance(data, str):
            data = json.loads(data)

        session_id = data.get("session_id")
        event_type = data.get("event_type")

        if not session_id or not event_type:
            return Response(
                {"error": "session_id and event_type are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create session
        session = get_or_create_session(session_id, data, request)

        # Create the event
        event = FunnelEvent.objects.create(
            session=session,
            event_type=event_type,
            page_url=data.get("page_url", ""),
            page_title=data.get("page_title", ""),
            element_id=data.get("element_id", ""),
            element_text=data.get("element_text", ""),
            time_since_page_load=data.get("time_since_page_load"),
            metadata=data.get("metadata", {}),
        )

        # Update session metrics based on event type
        if event_type == "page_view":
            session.page_views += 1
            session.is_bounce = False

        elif event_type == "survey_start":
            session.is_bounce = False

        elif event_type == "page_exit":
            # Safe metadata access
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                time_on_page = metadata.get("time_on_page", 0)
                if time_on_page:
                    session.time_on_site = max(
                        session.time_on_site, time_on_page // 1000
                    )

        session.save()
        logger.debug(f"[EVENT-TRACKED] {event_type} for session {session_id}")
        return Response({"success": True}, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"[TRACKING-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def submit_early_access(request):
    """Handle early access form submissions with full tracking and CSRF protection"""

    try:
        data = request.data
        session_id = data.get("session_id")
        email = data.get("email", "").lower().strip()
        name = data.get("name", "").strip()
        preference = data.get("preference")

        logger.info(f"[EARLY-ACCESS] Submission from session: {session_id}")

        # Validate required fields
        if not all([session_id, email, name]):
            return Response(
                {
                    "success": False,
                    "error": "Name, email, and session are required.",
                    "errors": {
                        "email": ["Email is required."] if not email else [],
                        "name": ["Name is required."] if not name else [],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create session first to check for existing registration
        session = get_or_create_session(session_id, data, request)

        # Check for duplicate registration by session (same session already registered)
        existing_session_signup = EarlyAccessSignup.objects.filter(
            session=session
        ).first()
        if existing_session_signup:
            logger.warning(
                f"[DUPLICATE-SESSION] Session {session_id} already registered with email: {existing_session_signup.email}"
            )
            return Response(
                {
                    "success": False,
                    "duplicate": True,
                    "duplicate_type": "session",
                    "error": "You have already registered for early access in this session.",
                    "existing_email": existing_session_signup.email,
                    "existing_name": existing_session_signup.name,
                    "registration_date": existing_session_signup.created_at.strftime(
                        "%B %d, %Y at %I:%M %p"
                    ),
                    "errors": {
                        "general": [
                            "You have already registered for early access. Check your email for confirmation."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate email (different session, same email)
        existing_email_signup = EarlyAccessSignup.objects.filter(
            email__iexact=email
        ).first()
        if existing_email_signup:
            logger.warning(
                f"[DUPLICATE-EMAIL] {email} already registered from session: {existing_email_signup.session.session_id if existing_email_signup.session else 'unknown'}"
            )
            return Response(
                {
                    "success": False,
                    "duplicate": True,
                    "duplicate_type": "email",
                    "error": f"The email '{email}' is already registered for early access.",
                    "registration_date": existing_email_signup.created_at.strftime(
                        "%B %d, %Y at %I:%M %p"
                    ),
                    "errors": {
                        "email": [
                            f"The email '{email}' is already registered. Check your email for confirmation."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use database transaction for consistency
        with transaction.atomic():
            # Session already retrieved above for duplicate checking

            # Create survey response if preference provided
            if preference:
                survey, created = SurveyResponse.objects.get_or_create(
                    session=session,
                    defaults={
                        "preference": preference,
                        "time_to_select": data.get("time_to_select"),
                        "changed_mind_count": data.get("changes_made", 0),
                    },
                )

                if not created:
                    # Update existing survey response
                    survey.preference = preference
                    survey.time_to_select = data.get("time_to_select")
                    survey.changed_mind_count = data.get("changes_made", 0)
                    survey.save()

            # Create early access signup
            signup = EarlyAccessSignup.objects.create(
                session=session,
                name=name,
                email=email,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            # Mark session as converted
            session.is_bounce = False
            session.save()

            logger.info(f"[SUCCESS] Signup created: {signup.id} for {email}")

            return Response(
                {
                    "success": True,
                    "message": "Registration successful!",
                    "id": signup.id,
                    "email": signup.email,
                    "name": signup.name,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        logger.error(f"[SIGNUP-ERROR] {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "error": "An unexpected error occurred. Please try again.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token(request):
    """API endpoint to get CSRF token"""
    return Response({"csrf_token": get_token(request)})


@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard_stats(request):
    """API endpoint for dashboard statistics"""

    try:
        # Get date range from query parameters
        days = int(request.GET.get("days", 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Session-based metrics
        sessions = UserSession.objects.filter(
            first_seen__date__range=[start_date, end_date]
        )

        total_sessions = sessions.count()
        converted_sessions = sessions.filter(signup__isnull=False).count()

        # Event-based metrics
        events_queryset = FunnelEvent.objects.filter(
            timestamp__date__range=[start_date, end_date]
        )

        event_counts = dict(
            events_queryset.values("event_type")
            .annotate(count=Count("id"))
            .values_list("event_type", "count")
        )

        # Survey preferences
        survey_stats = (
            SurveyResponse.objects.filter(
                created_at__date__range=[start_date, end_date]
            )
            .values("preference")
            .annotate(count=Count("pk"))
        )

        preference_breakdown = {
            item["preference"]: item["count"] for item in survey_stats
        }

        # Conversion rates
        page_views = event_counts.get("page_view", 0)
        signups = EarlyAccessSignup.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).count()

        conversion_rate = (signups / page_views * 100) if page_views > 0 else 0
        session_conversion_rate = (
            (converted_sessions / total_sessions * 100) if total_sessions > 0 else 0
        )

        # Traffic sources
        traffic_sources = (
            sessions.exclude(utm_source="")
            .values("utm_source")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

        # Device breakdown
        device_breakdown = sessions.values("device_type").annotate(count=Count("id"))

        # Daily trends (last 7 days)
        daily_trends = []
        for i in range(7):
            date = end_date - timedelta(days=i)
            day_sessions = sessions.filter(first_seen__date=date).count()
            day_signups = EarlyAccessSignup.objects.filter(
                created_at__date=date
            ).count()

            daily_trends.append(
                {
                    "date": date.isoformat(),
                    "sessions": day_sessions,
                    "signups": day_signups,
                    "conversion_rate": (
                        (day_signups / day_sessions * 100) if day_sessions > 0 else 0
                    ),
                }
            )

        daily_trends.reverse()  # Chronological order

        response_data = {
            "overview": {
                "total_sessions": total_sessions,
                "total_signups": signups,
                "conversion_rate": round(conversion_rate, 2),
                "session_conversion_rate": round(session_conversion_rate, 2),
                "page_views": page_views,
                "avg_time_on_site": round(
                    sessions.aggregate(avg_time=Avg("time_on_site"))["avg_time"]
                    or 0 / 60,
                    1,
                ),  # Convert to minutes
                "bounce_rate": (
                    round(
                        sessions.filter(is_bounce=True).count() / total_sessions * 100,
                        1,
                    )
                    if total_sessions > 0
                    else 0
                ),
            },
            "funnel": {
                "page_views": event_counts.get("page_view", 0),
                "surveys_started": event_counts.get("survey_start", 0),
                "surveys_completed": event_counts.get("survey_complete", 0),
                "forms_started": event_counts.get("form_start", 0),
                "signup_attempts": event_counts.get("signup_attempt", 0),
                "successful_signups": event_counts.get("signup_success", 0),
            },
            "preferences": preference_breakdown,
            "traffic_sources": [
                {"source": item["utm_source"], "count": item["count"]}
                for item in traffic_sources
            ],
            "devices": [
                {"type": item["device_type"], "count": item["count"]}
                for item in device_breakdown
            ],
            "daily_trends": daily_trends,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
        }

        return Response(response_data)

    except Exception as e:
        logger.error(f"[DASHBOARD-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Unable to retrieve dashboard stats"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def check_email_exists(request):
    """Check if email is already registered"""

    email = request.data.get("email", "").lower().strip()
    if not email:
        return Response({"exists": False})

    exists = EarlyAccessSignup.objects.filter(email__iexact=email).exists()
    return Response({"exists": exists, "email": email})


@api_view(["GET"])
@permission_classes([AllowAny])
def stats_summary(request):
    """Simple stats endpoint for monitoring"""

    try:
        early_access_count = EarlyAccessSignup.objects.count()
        survey_count = SurveyResponse.objects.count()
        session_count = UserSession.objects.count()

        # Last 24 hours activity
        yesterday = timezone.now() - timedelta(hours=24)
        recent_signups = EarlyAccessSignup.objects.filter(
            created_at__gte=yesterday
        ).count()
        recent_sessions = UserSession.objects.filter(first_seen__gte=yesterday).count()

        return Response(
            {
                "early_access_signups": early_access_count,
                "survey_responses": survey_count,
                "total_sessions": session_count,
                "signups_24h": recent_signups,
                "sessions_24h": recent_sessions,
            }
        )

    except Exception as e:
        logger.error(f"[STATS-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Unable to retrieve stats"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
