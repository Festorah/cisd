"""
Management command to compute daily statistics for the civic engagement platform.

Usage:
    python manage.py compute_daily_stats
    python manage.py compute_daily_stats --date 2024-01-15
    python manage.py compute_daily_stats --days 7
    python manage.py compute_daily_stats --backfill
"""

from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from tpsq.models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)


class Command(BaseCommand):
    help = "Compute daily statistics for analytics dashboard"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Specific date to compute stats for (YYYY-MM-DD format)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Number of days to compute stats for (starting from yesterday)",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Backfill all missing days since the first session",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recomputation even if stats already exist",
        )

    def handle(self, *args, **options):
        if options["backfill"]:
            self.backfill_all_stats(options["force"])
        elif options["date"]:
            try:
                target_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
                self.compute_stats_for_date(target_date, options["force"])
            except ValueError:
                raise CommandError("Invalid date format. Use YYYY-MM-DD")
        else:
            days = options["days"]
            end_date = timezone.now().date() - timedelta(days=1)  # Yesterday
            start_date = end_date - timedelta(days=days - 1)

            for i in range(days):
                target_date = start_date + timedelta(days=i)
                self.compute_stats_for_date(target_date, options["force"])

    def backfill_all_stats(self, force=False):
        """Backfill stats for all dates since the first session"""
        self.stdout.write("Starting backfill process...")

        # Find the earliest session date
        first_session = UserSession.objects.order_by("first_seen").first()
        if not first_session:
            self.stdout.write(
                self.style.WARNING("No sessions found. Nothing to backfill.")
            )
            return

        start_date = first_session.first_seen.date()
        end_date = timezone.now().date() - timedelta(days=1)  # Yesterday

        total_days = (end_date - start_date).days + 1
        self.stdout.write(
            f"Backfilling {total_days} days from {start_date} to {end_date}"
        )

        computed_count = 0
        skipped_count = 0

        current_date = start_date
        while current_date <= end_date:
            if self.compute_stats_for_date(current_date, force, quiet=True):
                computed_count += 1
            else:
                skipped_count += 1
            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete: {computed_count} computed, {skipped_count} skipped"
            )
        )

    def compute_stats_for_date(self, target_date, force=False, quiet=False):
        """Compute stats for a specific date"""

        # Check if stats already exist
        if not force and DailyStats.objects.filter(date=target_date).exists():
            if not quiet:
                self.stdout.write(
                    f"Stats for {target_date} already exist. Use --force to recompute."
                )
            return False

        if not quiet:
            self.stdout.write(f"Computing stats for {target_date}...")

        try:
            with transaction.atomic():
                stats = self.calculate_daily_metrics(target_date)

                # Create or update the daily stats record
                daily_stats, created = DailyStats.objects.update_or_create(
                    date=target_date, defaults=stats
                )

                # Calculate conversion rates
                daily_stats.calculate_rates()

                action = "Created" if created else "Updated"
                if not quiet:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'{action} stats for {target_date}: {stats["signups"]} signups'
                        )
                    )

                return True

        except Exception as e:
            if not quiet:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error computing stats for {target_date}: {str(e)}"
                    )
                )
            return False

    def calculate_daily_metrics(self, target_date):
        """Calculate all metrics for a given date"""

        # Date range for filtering
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        # Sessions for this date
        sessions = UserSession.objects.filter(first_seen__date=target_date)

        # Events for this date
        events = FunnelEvent.objects.filter(
            timestamp__range=[start_datetime, end_datetime]
        )

        # Survey responses for this date
        surveys = SurveyResponse.objects.filter(created_at__date=target_date)

        # Signups for this date
        signups = EarlyAccessSignup.objects.filter(created_at__date=target_date)

        # Count events by type
        event_counts = {}
        for event_type, _ in FunnelEvent.EVENT_TYPES:
            event_counts[event_type] = events.filter(event_type=event_type).count()

        # Survey preference breakdown
        preference_counts = surveys.values("preference").annotate(count=Count("pk"))
        preference_breakdown = {
            item["preference"]: item["count"] for item in preference_counts
        }

        # Session quality metrics
        session_metrics = sessions.aggregate(
            avg_time=Avg("time_on_site"),
            bounce_sessions=Count("id", filter=Q(is_bounce=True)),
        )

        avg_time_minutes = (session_metrics["avg_time"] or 0) / 60
        bounce_count = session_metrics["bounce_sessions"] or 0

        return {
            # Funnel metrics
            "ad_impressions": event_counts.get("ad_impression", 0),
            "ad_clicks": event_counts.get("ad_click", 0),
            "page_views": event_counts.get("page_view", 0),
            "unique_visitors": sessions.count(),
            "surveys_started": event_counts.get("survey_start", 0),
            "surveys_completed": event_counts.get("survey_complete", 0),
            "signups": signups.count(),
            "verified_signups": signups.filter(is_verified=True).count(),
            # Survey preferences
            "prefer_nothing": preference_breakdown.get("nothing", 0),
            "prefer_notification": preference_breakdown.get("notification", 0),
            "prefer_updates": preference_breakdown.get("updates", 0),
            # Quality metrics
            "avg_time_on_site": round(avg_time_minutes, 1),
        }

    def get_date_range_display(self, start_date, end_date):
        """Helper to format date range for display"""
        if start_date == end_date:
            return str(start_date)
        return f"{start_date} to {end_date}"
