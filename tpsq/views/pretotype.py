import json
import logging
from datetime import datetime, timedelta

from core.utils.cloudinary_utils import CloudinaryManager
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, F, Prefetch, Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Add these imports to your existing models import
from tpsq.models import (
    PretotypeAnalytics,
    PretotypeComment,
    PretotypeContact,
    PretotypeEvent,
    PretotypeIssue,
    PretotypeIssueStatus,
    PretotypeReaction,
    PretotypeSession,
)

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ReportView(TemplateView):
    """Serve the landing page with tracking enabled and CSRF token"""

    template_name = "tpsq/report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure CSRF token is available in template context
        context["csrf_token"] = get_token(self.request)
        return context


class ReportDashboardView(TemplateView):
    """Analytics dashboard for tracking performance"""

    template_name = "tpsq/report_dashboard.html"

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
    """Extract client IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_or_create_pretotype_session(session_id, request_data, request):
    """Get existing session or create new one with enhanced tracking"""
    try:
        session = PretotypeSession.objects.get(session_id=session_id)
        # Update last activity
        session.last_activity = timezone.now()
        session.save(update_fields=["last_activity"])
        return session
    except PretotypeSession.DoesNotExist:
        pass

    # Extract device info
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    device_type = "unknown"

    if user_agent:
        ua_lower = user_agent.lower()
        if any(mobile in ua_lower for mobile in ["mobile", "android", "iphone"]):
            device_type = "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device_type = "tablet"
        elif any(desktop in ua_lower for desktop in ["windows", "macintosh", "linux"]):
            device_type = "desktop"

    # Create new session
    session = PretotypeSession.objects.create(
        session_id=session_id,
        ip_address=get_client_ip(request),
        user_agent=user_agent,
        device_type=device_type,
        screen_size=request_data.get("screenSize", ""),
        viewport_size=request_data.get("viewport", ""),
        referrer=request_data.get("referrer", ""),
        utm_source=request_data.get("utm_source", ""),
        utm_medium=request_data.get("utm_medium", ""),
        utm_campaign=request_data.get("utm_campaign", ""),
        utm_content=request_data.get("utm_content", ""),
        utm_term=request_data.get("utm_term", ""),
    )

    logger.info(f"[PRETOTYPE] New session created: {session.session_id}")
    return session


@api_view(["POST"])
@permission_classes([AllowAny])
def pretotype_track_event(request):
    """
    API endpoint: /api/pretotype-track/
    Handles all event tracking from the frontend
    """
    try:
        data = request.data
        session_id = data.get("sessionId")
        event_type = data.get("eventType")

        if not session_id or not event_type:
            return Response(
                {"error": "sessionId and eventType are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create session
        session = get_or_create_pretotype_session(session_id, data, request)

        # Update session step tracking
        step = data.get("step", 1)
        if step > session.max_step_reached:
            session.max_step_reached = step
            session.save(update_fields=["max_step_reached"])

        # Create the event
        event = PretotypeEvent.objects.create(
            session=session,
            event_type=event_type,
            step=step,
            timestamp=timezone.now(),
            time_from_start=data.get("timeFromStart", 0),
            time_since_page_load=data.get("time_since_page_load"),
            page_url=data.get("url", ""),
            element_id=data.get("element_id", ""),
            element_text=data.get("element_text", ""),
            metadata=data.get("metadata", {}),
        )

        logger.debug(f"[PRETOTYPE-EVENT] {event_type} tracked for session {session_id}")

        return Response(
            {
                "success": True,
                "event_id": event.id,
                "session_step": session.max_step_reached,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"[PRETOTYPE-TRACK-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def pretotype_submit_issue(request):
    """
    API endpoint: /api/pretotype-issue/
    Handles issue report submissions (Step 2) with optional image
    """
    try:
        data = request.data
        session_id = data.get("sessionId")
        issue_type = data.get("issueType")

        if not session_id or not issue_type:
            return Response(
                {"error": "sessionId and issueType are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Get session
            try:
                session = PretotypeSession.objects.get(session_id=session_id)
            except PretotypeSession.DoesNotExist:
                return Response(
                    {"error": "Invalid session"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Check if issue already exists for this session
            if hasattr(session, "issue"):
                logger.warning(
                    f"[PRETOTYPE] Duplicate issue submission for session {session_id}"
                )
                return Response(
                    {"error": "Issue already submitted for this session"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Calculate time to submit
            form_start_event = session.events.filter(
                event_type="form_displayed"
            ).first()

            time_to_submit = 0
            if form_start_event:
                time_to_submit = int(
                    (timezone.now() - form_start_event.timestamp).total_seconds()
                )

            # Create issue record
            issue = PretotypeIssue.objects.create(
                session=session,
                issue_type=issue_type,
                issue_details=data.get("issueDetails", "").strip(),
                image_url=data.get("imageUrl", ""),
                time_to_submit=time_to_submit,
            )

            # If there's an image URL, extract additional metadata
            if issue.image_url:
                # You might want to validate the image URL here
                # or fetch metadata about the image
                pass

            # Update session
            session.max_step_reached = max(session.max_step_reached, 3)
            session.save(update_fields=["max_step_reached"])

            logger.info(
                f"[PRETOTYPE-ISSUE] Issue submitted: {issue.id} - {issue_type} (Image: {bool(issue.image_url)})"
            )

            return Response(
                {
                    "success": True,
                    "issue_id": issue.id,
                    "issue_type": issue.get_issue_type_display(),
                    "has_details": issue.has_details,
                    "has_image": issue.has_image,
                    "next_step": 3,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        logger.error(f"[PRETOTYPE-ISSUE-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def pretotype_submit_contact(request):
    """
    API endpoint: /api/pretotype-contact/
    Handles contact information submissions (Step 3)
    """
    try:
        data = request.data
        session_id = data.get("sessionId")

        if not session_id:
            return Response(
                {"error": "sessionId is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        email = data.get("email", "").strip()
        whatsapp = data.get("whatsapp", "").strip()
        opted_in = data.get("optIn", False)

        # Validation
        if not opted_in:
            return Response(
                {"error": "Must opt-in to receive updates"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email and not whatsapp:
            return Response(
                {"error": "Must provide either email or WhatsApp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Get session
            try:
                session = PretotypeSession.objects.get(session_id=session_id)
            except PretotypeSession.DoesNotExist:
                return Response(
                    {"error": "Invalid session"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Check if contact already exists
            if hasattr(session, "contact"):
                logger.warning(
                    f"[PRETOTYPE] Duplicate contact submission for session {session_id}"
                )
                return Response(
                    {"error": "Contact info already submitted for this session"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Create contact record
            contact = PretotypeContact.objects.create(
                session=session,
                email=email.lower() if email else "",
                whatsapp=whatsapp,
                opted_in=opted_in,
            )

            # Mark funnel as completed
            session.completed_funnel = True
            session.save(update_fields=["completed_funnel"])

            logger.info(
                f"[PRETOTYPE-CONTACT] Contact submitted: {contact.id} - {email or whatsapp}"
            )

            return Response(
                {
                    "success": True,
                    "contact_id": contact.id,
                    "email": contact.email,
                    "whatsapp": contact.whatsapp,
                    "funnel_completed": True,
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        logger.error(f"[PRETOTYPE-CONTACT-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def pretotype_analytics_dashboard(request):
    """
    API endpoint for analytics dashboard data
    Returns comprehensive funnel metrics
    """
    try:
        # Date range (default: last 7 days)
        days = int(request.GET.get("days", 7))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Session-based metrics
        sessions = PretotypeSession.objects.filter(
            started_at__date__range=[start_date, end_date]
        )

        total_sessions = sessions.count()
        step_2_sessions = sessions.filter(max_step_reached__gte=2).count()
        step_3_sessions = sessions.filter(max_step_reached__gte=3).count()
        completed_sessions = sessions.filter(completed_funnel=True).count()

        # Issue breakdown
        issues = PretotypeIssue.objects.filter(
            submitted_at__date__range=[start_date, end_date]
        )

        issue_types = {}
        for issue in issues:
            issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1

        # Contact analysis
        contacts = PretotypeContact.objects.filter(
            submitted_at__date__range=[start_date, end_date]
        )

        # Daily trends
        daily_data = []
        for i in range(days):
            date = end_date - timedelta(days=i)
            day_sessions = sessions.filter(started_at__date=date).count()
            day_issues = issues.filter(submitted_at__date=date).count()
            day_contacts = contacts.filter(submitted_at__date=date).count()

            daily_data.append(
                {
                    "date": date.isoformat(),
                    "sessions": day_sessions,
                    "issues": day_issues,
                    "contacts": day_contacts,
                    "conversion_rate": (
                        (day_contacts / day_sessions * 100) if day_sessions > 0 else 0
                    ),
                }
            )

        daily_data.reverse()  # Chronological order

        # Response data
        response_data = {
            "summary": {
                "total_sessions": total_sessions,
                "cta_clicks": step_2_sessions,
                "issues_submitted": step_3_sessions,
                "contacts_collected": completed_sessions,
                "cta_click_rate": (
                    (step_2_sessions / total_sessions * 100)
                    if total_sessions > 0
                    else 0
                ),
                "issue_submit_rate": (
                    (step_3_sessions / step_2_sessions * 100)
                    if step_2_sessions > 0
                    else 0
                ),
                "contact_rate": (
                    (completed_sessions / step_3_sessions * 100)
                    if step_3_sessions > 0
                    else 0
                ),
                "overall_conversion": (
                    (completed_sessions / total_sessions * 100)
                    if total_sessions > 0
                    else 0
                ),
            },
            "funnel_steps": {
                "step_1": total_sessions,
                "step_2": step_2_sessions,
                "step_3": step_3_sessions,
                "completed": completed_sessions,
            },
            "issue_breakdown": issue_types,
            "contact_quality": {
                "with_email": contacts.exclude(email="").count(),
                "with_whatsapp": contacts.exclude(whatsapp="").count(),
                "business_emails": contacts.filter(is_business_email=True).count(),
            },
            "device_breakdown": {
                "mobile": sessions.filter(device_type="mobile").count(),
                "desktop": sessions.filter(device_type="desktop").count(),
                "tablet": sessions.filter(device_type="tablet").count(),
            },
            "daily_trends": daily_data,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
        }

        return Response(response_data)

    except Exception as e:
        logger.error(f"[PRETOTYPE-ANALYTICS-ERROR] {str(e)}", exc_info=True)
        return Response(
            {"error": "Unable to retrieve analytics"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def pretotype_upload_image(request):
    """
    API endpoint: /api/pretotype-upload-image/
    Handles image uploads for pretotype issue reporting
    """
    try:
        # Get the uploaded file
        if "image" not in request.FILES:
            return Response(
                {"error": "No image file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_obj = request.FILES["image"]
        session_id = request.data.get("sessionId")

        if not session_id:
            return Response(
                {"error": "sessionId is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate session exists
        try:
            session = PretotypeSession.objects.get(session_id=session_id)
        except PretotypeSession.DoesNotExist:
            return Response(
                {"error": "Invalid session"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Additional file validation for pretotype
        max_size = 5 * 1024 * 1024  # 5MB limit for pretotype
        if file_obj.size > max_size:
            return Response(
                {"error": "Image must be smaller than 5MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        if file_obj.content_type not in allowed_types:
            return Response(
                {"error": "Only JPEG, PNG, and WebP images are allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Upload to Cloudinary using the existing utility
        upload_result = CloudinaryManager.upload_file(
            file_obj=file_obj,
            folder="pretotype/issues",  # Organize pretotype uploads in specific folder
            tags=["pretotype", "issue-report", session_id],  # Tag for organization
            transformation={
                "quality": "auto:good",  # Optimize quality
                "fetch_format": "auto",  # Auto-format optimization
                "width": 1200,  # Max width for issue photos
                "height": 1200,  # Max height
                "crop": "limit",  # Don't upscale smaller images
            },
            context={
                "session_id": session_id,
                "upload_type": "pretotype_issue",
                "uploaded_at": timezone.now().isoformat(),
            },
        )

        if not upload_result["success"]:
            logger.error(
                f"[PRETOTYPE-UPLOAD-ERROR] Cloudinary upload failed: {upload_result['error']}"
            )
            return Response(
                {"error": f"Upload failed: {upload_result['error']}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Track the upload event (optional)
        try:
            PretotypeEvent.objects.create(
                session=session,
                event_type="image_uploaded",
                step=2,  # Image upload happens in step 2 (form step)
                timestamp=timezone.now(),
                time_from_start=int(
                    (timezone.now() - session.started_at).total_seconds() * 1000
                ),
                page_url=request.META.get("HTTP_REFERER", ""),
                metadata={
                    "file_name": file_obj.name,
                    "file_size": file_obj.size,
                    "file_type": file_obj.content_type,
                    "cloudinary_public_id": upload_result["public_id"],
                    "upload_duration_ms": upload_result.get("upload_duration"),
                },
            )
        except Exception as event_error:
            # Don't fail the upload if event tracking fails
            logger.warning(
                f"[PRETOTYPE-UPLOAD] Failed to track upload event: {event_error}"
            )

        logger.info(
            f"[PRETOTYPE-UPLOAD] Image uploaded successfully: {upload_result['public_id']} "
            f"for session {session_id}, size: {file_obj.size} bytes"
        )

        return Response(
            {
                "success": True,
                "image_url": upload_result["url"],
                "public_id": upload_result["public_id"],
                "file_info": {
                    "original_name": file_obj.name,
                    "size": upload_result["bytes"],
                    "format": upload_result["format"],
                    "width": upload_result.get("width"),
                    "height": upload_result.get("height"),
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except ValidationError as ve:
        return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(
            f"[PRETOTYPE-UPLOAD-ERROR] Unexpected error: {str(e)}", exc_info=True
        )
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PretotypeFeedView(TemplateView):
    """Social media-style feed showing all reported issues"""

    template_name = "tpsq/community_feed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter parameters
        issue_type_filter = self.request.GET.get("type", "")
        status_filter = self.request.GET.get("status", "")
        sort_by = self.request.GET.get("sort", "recent")  # recent, popular, resolved

        # Base queryset with optimized joins
        issues = (
            PretotypeIssue.objects.select_related("session")
            .prefetch_related(
                "reactions",
                "status_updates",
                Prefetch(
                    "comments",
                    queryset=PretotypeComment.objects.filter(
                        is_approved=True, parent_comment=None
                    )
                    .select_related("session")
                    .order_by("-created_at"),
                ),
            )
            .annotate(
                reaction_count=Count("reactions"),
                comment_count=Count(
                    "comments",
                    filter=Q(comments__is_approved=True, comments__parent_comment=None),
                ),
                latest_status_date=models.Max("status_updates__created_at"),
            )
        )

        # Apply filters
        if issue_type_filter:
            issues = issues.filter(issue_type=issue_type_filter)

        if status_filter:
            # Get issues with specific current status
            if status_filter == "resolved":
                issues = issues.filter(status_updates__status="resolved")
            elif status_filter == "in_progress":
                issues = issues.filter(
                    status_updates__status__in=["investigating", "in_progress"]
                )
            elif status_filter == "new":
                # Issues with no status updates or only 'reported' status
                issues = issues.filter(
                    Q(status_updates=None) | Q(status_updates__status="reported")
                )

        # Apply sorting
        if sort_by == "popular":
            issues = issues.order_by(
                "-reaction_count", "-comment_count", "-submitted_at"
            )
        elif sort_by == "resolved":
            issues = issues.filter(status_updates__status="resolved").order_by(
                "-latest_status_date"
            )
        elif sort_by == "needs_attention":
            # High engagement but no government response
            issues = (
                issues.filter(reaction_count__gte=3)
                .exclude(comments__is_government_response=True)
                .order_by("-reaction_count", "-submitted_at")
            )
        else:  # recent
            issues = issues.order_by("-submitted_at")

        # Paginate results
        paginator = Paginator(issues, 10)
        page_number = self.request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        # Get summary stats
        stats = {
            "total_issues": PretotypeIssue.objects.count(),
            "resolved_issues": PretotypeIssue.objects.filter(
                status_updates__status="resolved"
            ).count(),
            "active_issues": PretotypeIssue.objects.exclude(
                status_updates__status__in=["resolved", "rejected"]
            ).count(),
            "total_engagement": PretotypeReaction.objects.count()
            + PretotypeComment.objects.filter(is_approved=True).count(),
        }

        # Get filter options
        issue_type_counts = (
            PretotypeIssue.objects.values("issue_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        context.update(
            {
                "page_obj": page_obj,
                "issues": page_obj.object_list,
                "stats": stats,
                "issue_type_counts": issue_type_counts,
                "current_filters": {
                    "type": issue_type_filter,
                    "status": status_filter,
                    "sort": sort_by,
                },
                "csrf_token": get_token(self.request),
            }
        )

        return context


# @ratelimit(key="ip", rate="10/m", method="POST")
@api_view(["POST"])
@permission_classes([AllowAny])
def add_comment(request):
    """Add a comment to an issue report"""
    try:
        data = request.data
        issue_id = data.get("issue_id")
        content = data.get("content", "").strip()
        session_id = data.get("session_id")
        commenter_name = data.get("commenter_name", "").strip()
        parent_comment_id = data.get("parent_comment_id")

        # Validation
        if not all([issue_id, content, session_id]):
            return Response(
                {"error": "issue_id, content, and session_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(content) > 1000:
            return Response(
                {"error": "Comment too long (max 1000 characters)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get issue and session
        try:
            issue = PretotypeIssue.objects.get(id=issue_id)
            session = PretotypeSession.objects.get(session_id=session_id)
        except (PretotypeIssue.DoesNotExist, PretotypeSession.DoesNotExist):
            return Response(
                {"error": "Invalid issue or session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get parent comment if replying
        parent_comment = None
        if parent_comment_id:
            try:
                parent_comment = PretotypeComment.objects.get(id=parent_comment_id)
            except PretotypeComment.DoesNotExist:
                return Response(
                    {"error": "Invalid parent comment"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Basic content moderation
        flagged_words = ["spam", "scam", "fake"]  # You'd have a more comprehensive list
        is_flagged = any(word.lower() in content.lower() for word in flagged_words)

        # Create comment
        comment = PretotypeComment.objects.create(
            issue=issue,
            session=session,
            parent_comment=parent_comment,
            content=content,
            commenter_name=commenter_name or f"Citizen {str(session.session_id)[:8]}",
            commenter_type="citizen",
            is_approved=not is_flagged,  # Auto-approve unless flagged
            is_flagged=is_flagged,
            ip_address=get_client_ip(request),
        )

        # Track event
        try:
            PretotypeEvent.objects.create(
                session=session,
                event_type="comment_added",
                step=4,  # Post-completion engagement
                timestamp=timezone.now(),
                time_from_start=int(
                    (timezone.now() - session.started_at).total_seconds() * 1000
                ),
                metadata={
                    "issue_id": str(issue_id),
                    "comment_id": str(comment.id),
                    "is_reply": bool(parent_comment_id),
                    "content_length": len(content),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track comment event: {e}")

        return Response(
            {
                "success": True,
                "comment": {
                    "id": comment.id,
                    "content": comment.content,
                    "commenter_name": comment.commenter_name,
                    "created_at": comment.created_at.isoformat(),
                    "is_reply": comment.is_reply,
                    "upvotes": comment.upvotes,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Error adding comment: {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# @ratelimit(key="ip", rate="30/m", method="POST")
@api_view(["POST"])
@permission_classes([AllowAny])
def add_reaction(request):
    """Add or update reaction to an issue"""
    try:
        data = request.data
        issue_id = data.get("issue_id")
        reaction_type = data.get("reaction_type")
        session_id = data.get("session_id")

        if not all([issue_id, reaction_type, session_id]):
            return Response(
                {"error": "issue_id, reaction_type, and session_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate reaction type
        valid_reactions = [choice[0] for choice in PretotypeReaction.REACTION_TYPES]
        if reaction_type not in valid_reactions:
            return Response(
                {"error": "Invalid reaction type"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get issue and session
        try:
            issue = PretotypeIssue.objects.get(id=issue_id)
            session = PretotypeSession.objects.get(session_id=session_id)
        except (PretotypeIssue.DoesNotExist, PretotypeSession.DoesNotExist):
            return Response(
                {"error": "Invalid issue or session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create or update reaction
        reaction, created = PretotypeReaction.objects.update_or_create(
            issue=issue, session=session, defaults={"reaction_type": reaction_type}
        )

        # Track event
        try:
            PretotypeEvent.objects.create(
                session=session,
                event_type="reaction_added" if created else "reaction_updated",
                step=4,
                timestamp=timezone.now(),
                time_from_start=int(
                    (timezone.now() - session.started_at).total_seconds() * 1000
                ),
                metadata={
                    "issue_id": str(issue_id),
                    "reaction_type": reaction_type,
                    "was_update": not created,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track reaction event: {e}")

        # Get updated reaction counts
        reaction_counts = issue.get_reaction_counts()

        return Response(
            {
                "success": True,
                "reaction": {"type": reaction.reaction_type, "created": created},
                "reaction_counts": reaction_counts,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error adding reaction: {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_issue_comments(request, issue_id):
    """Get comments for a specific issue"""
    try:
        # Get issue
        try:
            issue = PretotypeIssue.objects.get(id=issue_id)
        except PretotypeIssue.DoesNotExist:
            return Response(
                {"error": "Issue not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get approved comments with replies
        comments = (
            PretotypeComment.objects.filter(
                issue=issue, is_approved=True, parent_comment=None
            )
            .select_related("session")
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=PretotypeComment.objects.filter(
                        is_approved=True
                    ).select_related("session"),
                )
            )
            .order_by("-created_at")
        )

        # Serialize comments
        comments_data = []
        for comment in comments:
            comment_data = {
                "id": comment.id,
                "content": comment.content,
                "commenter_name": comment.commenter_name,
                "commenter_type": comment.commenter_type,
                "is_government_response": comment.is_government_response,
                "created_at": comment.created_at.isoformat(),
                "upvotes": comment.upvotes,
                "replies": [],
            }

            # Add replies
            for reply in comment.replies.all():
                comment_data["replies"].append(
                    {
                        "id": reply.id,
                        "content": reply.content,
                        "commenter_name": reply.commenter_name,
                        "commenter_type": reply.commenter_type,
                        "is_government_response": reply.is_government_response,
                        "created_at": reply.created_at.isoformat(),
                        "upvotes": reply.upvotes,
                    }
                )

            comments_data.append(comment_data)

        return Response(
            {
                "success": True,
                "comments": comments_data,
                "total_count": len(comments_data),
            }
        )

    except Exception as e:
        logger.error(f"Error getting comments: {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def upvote_comment(request):
    """Upvote a comment"""
    try:
        data = request.data
        comment_id = data.get("comment_id")
        session_id = data.get("session_id")

        if not all([comment_id, session_id]):
            return Response(
                {"error": "comment_id and session_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get comment and session
        try:
            comment = PretotypeComment.objects.get(id=comment_id)
            session = PretotypeSession.objects.get(session_id=session_id)
        except (PretotypeComment.DoesNotExist, PretotypeSession.DoesNotExist):
            return Response(
                {"error": "Invalid comment or session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Simple upvote (in real app, you'd track who upvoted to prevent duplicates)
        comment.upvotes = F("upvotes") + 1
        comment.save(update_fields=["upvotes"])
        comment.refresh_from_db()

        return Response({"success": True, "upvotes": comment.upvotes})

    except Exception as e:
        logger.error(f"Error upvoting comment: {str(e)}", exc_info=True)
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def get_trending_issues():
    """Get issues that are trending (high engagement recently)"""
    from datetime import timedelta

    from django.db.models import Count, Q

    recent_date = timezone.now() - timedelta(days=3)

    return (
        PretotypeIssue.objects.annotate(
            recent_engagement=Count(
                "reactions", filter=Q(reactions__created_at__gte=recent_date)
            )
            + Count(
                "comments",
                filter=Q(
                    comments__created_at__gte=recent_date, comments__is_approved=True
                ),
            )
        )
        .filter(recent_engagement__gte=3)
        .order_by("-recent_engagement", "-submitted_at")[:5]
    )


def get_government_responses():
    """Get recent government responses"""
    return (
        PretotypeComment.objects.filter(is_government_response=True, is_approved=True)
        .select_related("issue", "session")
        .order_by("-created_at")[:10]
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_csrf_token(request):
    """Get CSRF token for frontend AJAX requests"""
    return Response({"csrf_token": get_token(request)})
