"""
Utility functions for analytics and reporting
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from tpsq.models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)


class AnalyticsCalculator:
    """
    Main class for calculating analytics metrics.
    Like a data analyst for your civic engagement platform.
    """

    def __init__(self, start_date: date = None, end_date: date = None):
        """Initialize with date range"""
        self.end_date = end_date or timezone.now().date()
        self.start_date = start_date or (self.end_date - timedelta(days=30))

    def get_conversion_funnel(self) -> Dict[str, int]:
        """
        Calculate the main conversion funnel metrics.
        Returns step-by-step counts through the user journey.
        """
        cache_key = f"funnel_{self.start_date}_{self.end_date}"
        cached_result = cache.get(cache_key)

        if cached_result:
            return cached_result

        # Get sessions in date range
        sessions = UserSession.objects.filter(
            first_seen__date__range=[self.start_date, self.end_date]
        )

        # Get events in date range
        events = FunnelEvent.objects.filter(
            timestamp__date__range=[self.start_date, self.end_date]
        )

        # Count events by type
        event_counts = dict(
            events.values("event_type")
            .annotate(count=Count("id"))
            .values_list("event_type", "count")
        )

        # Calculate funnel
        funnel = {
            "total_sessions": sessions.count(),
            "page_views": event_counts.get("page_view", 0),
            "surveys_started": event_counts.get("survey_start", 0),
            "surveys_completed": event_counts.get("survey_complete", 0),
            "forms_started": event_counts.get("form_start", 0),
            "signup_attempts": event_counts.get("signup_attempt", 0),
            "successful_signups": event_counts.get("signup_success", 0),
            "conversions": sessions.filter(signup__isnull=False).count(),
        }

        # Cache for 5 minutes
        cache.set(cache_key, funnel, 300)
        return funnel

    def get_conversion_rates(self) -> Dict[str, float]:
        """Calculate conversion rates between funnel steps"""
        funnel = self.get_conversion_funnel()

        rates = {}

        # Page view to survey rate
        if funnel["page_views"] > 0:
            rates["page_to_survey"] = (
                funnel["surveys_started"] / funnel["page_views"]
            ) * 100

        # Survey completion rate
        if funnel["surveys_started"] > 0:
            rates["survey_completion"] = (
                funnel["surveys_completed"] / funnel["surveys_started"]
            ) * 100

        # Form conversion rate
        if funnel["surveys_completed"] > 0:
            rates["survey_to_form"] = (
                funnel["forms_started"] / funnel["surveys_completed"]
            ) * 100

        # Signup success rate
        if funnel["signup_attempts"] > 0:
            rates["signup_success"] = (
                funnel["successful_signups"] / funnel["signup_attempts"]
            ) * 100

        # Overall conversion rate
        if funnel["page_views"] > 0:
            rates["overall"] = (funnel["conversions"] / funnel["page_views"]) * 100

        return {k: round(v, 2) for k, v in rates.items()}

    def get_user_preferences_breakdown(self) -> Dict[str, Any]:
        """Analyze user engagement preferences with support for multiple question types"""
        surveys = SurveyResponse.objects.filter(
            created_at__date__range=[self.start_date, self.end_date]
        )

        # Count by preference
        preference_counts = dict(
            surveys.values("preference")
            .annotate(count=Count("pk"))
            .values_list("preference", "count")
        )

        total_responses = sum(preference_counts.values())

        # Separate old and new preferences
        original_prefs = ["nothing", "notification", "updates"]
        new_prefs = ["yes_would_use", "no_wouldnt_use", "not_sure"]

        original_counts = {
            k: v for k, v in preference_counts.items() if k in original_prefs
        }
        new_counts = {k: v for k, v in preference_counts.items() if k in new_prefs}

        original_total = sum(original_counts.values())
        new_total = sum(new_counts.values())

        # Calculate engagement scores
        original_score = self._calculate_engagement_score(original_counts, "original")
        new_score = self._calculate_engagement_score(new_counts, "new")
        overall_score = self._calculate_engagement_score(preference_counts, "combined")

        # Calculate percentages
        breakdown = {
            "total_responses": total_responses,
            "counts": preference_counts,
            "percentages": {},
            "engagement_score": overall_score,
            "insights": [],
            # Segmented data
            "original_question": {
                "total": original_total,
                "counts": original_counts,
                "percentages": {},
                "engagement_score": original_score,
            },
            "new_question": {
                "total": new_total,
                "counts": new_counts,
                "percentages": {},
                "engagement_score": new_score,
            },
        }

        # Calculate overall percentages
        if total_responses > 0:
            for pref, count in preference_counts.items():
                breakdown["percentages"][pref] = round(
                    (count / total_responses) * 100, 1
                )

        # Calculate segmented percentages
        if original_total > 0:
            for pref, count in original_counts.items():
                breakdown["original_question"]["percentages"][pref] = round(
                    (count / original_total) * 100, 1
                )

        if new_total > 0:
            for pref, count in new_counts.items():
                breakdown["new_question"]["percentages"][pref] = round(
                    (count / new_total) * 100, 1
                )

        # Generate insights
        breakdown["insights"] = self._generate_preference_insights(breakdown)

        return breakdown

    def _calculate_engagement_score(
        self, preference_counts: Dict, question_type: str
    ) -> float:
        """Calculate engagement score based on preference weights"""

        # Define engagement weights for different question types
        engagement_weights = {
            # Original engagement follow-up preferences
            "nothing": 0,
            "notification": 1,
            "updates": 2,
            # New app usage intent preferences
            "yes_would_use": 2,
            "not_sure": 1,
            "no_wouldnt_use": 0,
        }

        total_responses = sum(preference_counts.values())
        if total_responses == 0:
            return 0

        weighted_sum = sum(
            preference_counts.get(pref, 0) * weight
            for pref, weight in engagement_weights.items()
            if pref in preference_counts
        )

        return round((weighted_sum / total_responses), 2)

    def _generate_preference_insights(self, breakdown: Dict) -> List[str]:
        """Generate insights based on preference data from both question types"""
        insights = []

        # Overall insights
        total_responses = breakdown["total_responses"]
        if total_responses == 0:
            return ["No survey data available yet"]

        overall_score = breakdown["engagement_score"]

        # Insights about question mix
        original_total = breakdown["original_question"]["total"]
        new_total = breakdown["new_question"]["total"]

        if original_total > 0 and new_total > 0:
            insights.append(
                f"Responses split: {original_total} engagement preferences, {new_total} app usage intent"
            )

        # Original question insights (engagement follow-up)
        if original_total > 0:
            original_percentages = breakdown["original_question"]["percentages"]
            original_score = breakdown["original_question"]["engagement_score"]

            updates_pct = original_percentages.get("updates", 0)
            notification_pct = original_percentages.get("notification", 0)
            nothing_pct = original_percentages.get("nothing", 0)

            if updates_pct > 50:
                insights.append(
                    "Follow-up engagement: Users strongly prefer active progress updates"
                )
            elif notification_pct > 40:
                insights.append(
                    "Follow-up engagement: Users prefer simple resolution notifications"
                )
            elif nothing_pct > 60:
                insights.append(
                    "Follow-up engagement: High percentage prefer no follow-up - consider value proposition"
                )

            if original_score > 1.5:
                insights.append(
                    "High engagement level - users want to stay involved after reporting"
                )
            elif original_score < 0.5:
                insights.append(
                    "Low engagement level - users prefer fire-and-forget reporting"
                )

        # New question insights (app usage intent)
        if new_total > 0:
            new_percentages = breakdown["new_question"]["percentages"]
            new_score = breakdown["new_question"]["engagement_score"]

            yes_pct = new_percentages.get("yes_would_use", 0)
            no_pct = new_percentages.get("no_wouldnt_use", 0)
            unsure_pct = new_percentages.get("not_sure", 0)

            if yes_pct > 70:
                insights.append(
                    "Strong app adoption intent - high market demand signal"
                )
            elif yes_pct > 50:
                insights.append("Positive app adoption intent - good market validation")
            elif no_pct > 50:
                insights.append(
                    "Low app adoption intent - may need to refine value proposition"
                )
            elif unsure_pct > 40:
                insights.append(
                    "High uncertainty about app usage - need clearer benefit communication"
                )

            if new_score > 1.5:
                insights.append("High willingness to use reporting app")
            elif new_score < 0.8:
                insights.append(
                    "Low willingness to use app - consider addressing barriers"
                )

        # Combined insights
        if original_total > 0 and new_total > 0:
            # Compare engagement patterns
            original_score = breakdown["original_question"]["engagement_score"]
            new_score = breakdown["new_question"]["engagement_score"]

            if abs(original_score - new_score) < 0.3:
                insights.append(
                    "Consistent engagement levels across both question types"
                )
            elif new_score > original_score + 0.5:
                insights.append(
                    "Higher app usage intent than follow-up engagement preference"
                )
            elif original_score > new_score + 0.5:
                insights.append("Higher follow-up engagement than app usage intent")

        # Overall engagement insight
        if overall_score > 1.5:
            insights.append("Overall: High civic engagement and platform interest")
        elif overall_score > 1.0:
            insights.append("Overall: Moderate civic engagement and platform interest")
        elif overall_score < 0.7:
            insights.append(
                "Overall: Low engagement - focus on value proposition and barriers"
            )

        return insights

    def get_traffic_attribution(self) -> Dict[str, Any]:
        """Analyze traffic sources and their conversion performance"""
        sessions = UserSession.objects.filter(
            first_seen__date__range=[self.start_date, self.end_date]
        )

        # Group by UTM source
        source_data = (
            sessions.values("utm_source")
            .annotate(
                total_sessions=Count("id"),
                conversions=Count("signup", filter=Q(signup__isnull=False)),
                avg_time_on_site=Avg("time_on_site"),
                bounce_rate=Count("id", filter=Q(is_bounce=True)),
            )
            .order_by("-total_sessions")
        )

        # Calculate conversion rates and format data
        attribution_data = []
        for item in source_data:
            source = item["utm_source"] or "Direct"
            total = item["total_sessions"]
            conversions = item["conversions"]

            attribution_data.append(
                {
                    "source": source,
                    "sessions": total,
                    "conversions": conversions,
                    "conversion_rate": (
                        round((conversions / total) * 100, 2) if total > 0 else 0
                    ),
                    "avg_time_minutes": round((item["avg_time_on_site"] or 0) / 60, 1),
                    "bounce_rate": (
                        round((item["bounce_rate"] / total) * 100, 1)
                        if total > 0
                        else 0
                    ),
                }
            )

        return {
            "sources": attribution_data,
            "total_sources": len(attribution_data),
            "top_converting_source": (
                max(attribution_data, key=lambda x: x["conversion_rate"])
                if attribution_data
                else None
            ),
        }

    def get_time_based_trends(self, granularity: str = "daily") -> List[Dict]:
        """Get trends over time with specified granularity"""
        if granularity == "daily":
            return self._get_daily_trends()
        elif granularity == "hourly":
            return self._get_hourly_trends()
        else:
            raise ValueError("Granularity must be 'daily' or 'hourly'")

    def _get_daily_trends(self) -> List[Dict]:
        """Get daily trends data"""
        trends = []
        current_date = self.start_date

        while current_date <= self.end_date:
            # Try to get from DailyStats first for performance
            daily_stat = DailyStats.objects.filter(date=current_date).first()

            if daily_stat:
                trends.append(
                    {
                        "date": current_date.isoformat(),
                        "sessions": daily_stat.unique_visitors,
                        "signups": daily_stat.signups,
                        "conversion_rate": daily_stat.page_conversion_rate or 0,
                    }
                )
            else:
                # Calculate on the fly if no daily stat exists
                day_sessions = UserSession.objects.filter(
                    first_seen__date=current_date
                ).count()
                day_signups = EarlyAccessSignup.objects.filter(
                    created_at__date=current_date
                ).count()
                conversion_rate = (
                    (day_signups / day_sessions * 100) if day_sessions > 0 else 0
                )

                trends.append(
                    {
                        "date": current_date.isoformat(),
                        "sessions": day_sessions,
                        "signups": day_signups,
                        "conversion_rate": round(conversion_rate, 2),
                    }
                )

            current_date += timedelta(days=1)

        return trends

    def _get_hourly_trends(self) -> List[Dict]:
        """Get hourly trends for the last 24 hours"""
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=24)

        trends = []
        current_hour = start_time.replace(minute=0, second=0, microsecond=0)

        while current_hour <= end_time:
            next_hour = current_hour + timedelta(hours=1)

            hour_sessions = UserSession.objects.filter(
                first_seen__range=[current_hour, next_hour]
            ).count()

            hour_signups = EarlyAccessSignup.objects.filter(
                created_at__range=[current_hour, next_hour]
            ).count()

            trends.append(
                {
                    "hour": current_hour.strftime("%Y-%m-%d %H:00"),
                    "sessions": hour_sessions,
                    "signups": hour_signups,
                }
            )

            current_hour = next_hour

        return trends


class FunnelAnalyzer:
    """
    Specialized class for analyzing the conversion funnel.
    Think of it as a conversion optimization consultant.
    """

    @staticmethod
    def identify_drop_off_points(
        start_date: date = None, end_date: date = None
    ) -> Dict[str, Any]:
        """Identify where users are dropping off in the funnel"""
        calc = AnalyticsCalculator(start_date, end_date)
        funnel = calc.get_conversion_funnel()
        rates = calc.get_conversion_rates()

        # Define expected minimum rates (industry benchmarks)
        benchmarks = {
            "page_to_survey": 25.0,  # 25% should start survey
            "survey_completion": 70.0,  # 70% should complete survey
            "survey_to_form": 60.0,  # 60% should start form
            "signup_success": 90.0,  # 90% should complete signup
        }

        issues = []
        recommendations = []

        for step, actual_rate in rates.items():
            if step in benchmarks:
                benchmark = benchmarks[step]
                if actual_rate < benchmark:
                    issues.append(
                        {
                            "step": step,
                            "actual_rate": actual_rate,
                            "benchmark": benchmark,
                            "gap": round(benchmark - actual_rate, 2),
                        }
                    )

        # Generate recommendations based on issues
        for issue in issues:
            step = issue["step"]
            if step == "page_to_survey":
                recommendations.append(
                    "Consider making the survey more prominent or compelling"
                )
            elif step == "survey_completion":
                recommendations.append(
                    "Simplify survey options or reduce cognitive load"
                )
            elif step == "survey_to_form":
                recommendations.append(
                    "Improve value proposition for early access signup"
                )
            elif step == "signup_success":
                recommendations.append("Fix form validation or technical issues")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "overall_health": "good" if len(issues) <= 1 else "needs_attention",
        }

    @staticmethod
    def get_user_journey_patterns() -> Dict[str, Any]:
        """Analyze common user journey patterns"""
        # Get sessions with events
        sessions_with_events = (
            UserSession.objects.filter(events__isnull=False)
            .prefetch_related("events")
            .distinct()
        )

        journey_patterns = {}

        for session in sessions_with_events[:1000]:  # Limit for performance
            # Get event sequence
            events = session.events.order_by("timestamp").values_list(
                "event_type", flat=True
            )
            journey_key = " -> ".join(events)

            if journey_key in journey_patterns:
                journey_patterns[journey_key] += 1
            else:
                journey_patterns[journey_key] = 1

        # Sort by frequency
        sorted_patterns = sorted(
            journey_patterns.items(), key=lambda x: x[1], reverse=True
        )[
            :10
        ]  # Top 10 patterns

        return {
            "top_patterns": [
                {"pattern": pattern, "count": count}
                for pattern, count in sorted_patterns
            ],
            "total_unique_patterns": len(journey_patterns),
        }


def generate_weekly_report() -> Dict[str, Any]:
    """Generate a comprehensive weekly analytics report"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=7)

    calc = AnalyticsCalculator(start_date, end_date)

    report = {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": 7,
        },
        "funnel": calc.get_conversion_funnel(),
        "conversion_rates": calc.get_conversion_rates(),
        "preferences": calc.get_user_preferences_breakdown(),
        "traffic": calc.get_traffic_attribution(),
        "trends": calc.get_time_based_trends("daily"),
        "funnel_analysis": FunnelAnalyzer.identify_drop_off_points(
            start_date, end_date
        ),
        "generated_at": timezone.now().isoformat(),
    }

    return report


def get_real_time_stats() -> Dict[str, Any]:
    """Get real-time statistics for dashboard"""
    now = timezone.now()
    today = now.date()
    hour_ago = now - timedelta(hours=1)

    return {
        "sessions_today": UserSession.objects.filter(first_seen__date=today).count(),
        "signups_today": EarlyAccessSignup.objects.filter(
            created_at__date=today
        ).count(),
        "sessions_last_hour": UserSession.objects.filter(
            first_seen__gte=hour_ago
        ).count(),
        "active_sessions": UserSession.objects.filter(
            last_activity__gte=now - timedelta(minutes=30)
        ).count(),
        "total_signups": EarlyAccessSignup.objects.count(),
        "last_signup": EarlyAccessSignup.objects.order_by("-created_at").first(),
        "timestamp": now.isoformat(),
    }
