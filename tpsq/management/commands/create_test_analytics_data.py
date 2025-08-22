"""
Django management command to create test data for analytics with mixed preferences.

Usage: python manage.py create_test_analytics_data [--days=7] [--sessions=200] [--clear]

This creates realistic test data with:
- Few old preferences (nothing, notification, updates)
- Majority new preferences (yes_would_use, no_wouldnt_use, not_sure)
- Realistic conversion funnel with drop-offs
- Multiple traffic sources and device types
- Various time patterns over specified days
"""

import random
import uuid
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from tpsq.models import (
    DailyStats,
    EarlyAccessSignup,
    FunnelEvent,
    SurveyResponse,
    UserSession,
)


class Command(BaseCommand):
    help = "Create test analytics data with mixed old and new preferences"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to generate data for (default: 7)",
        )
        parser.add_argument(
            "--sessions",
            type=int,
            default=200,
            help="Total number of sessions to create (default: 200)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing test data before creating new data",
        )

    def handle(self, *args, **options):
        days = options["days"]
        total_sessions = options["sessions"]
        clear_data = options["clear"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Creating test analytics data: {total_sessions} sessions over {days} days"
            )
        )

        if clear_data:
            self.clear_test_data()

        with transaction.atomic():
            self.create_test_data(days, total_sessions)

        self.stdout.write(self.style.SUCCESS("✅ Test data created successfully!"))
        self.show_summary()

    def clear_test_data(self):
        """Clear existing test data"""
        self.stdout.write("🗑️  Clearing existing test data...")

        # Delete in order to respect foreign key constraints
        EarlyAccessSignup.objects.filter(email__contains="testuser").delete()
        FunnelEvent.objects.filter(session__utm_campaign__contains="test").delete()
        SurveyResponse.objects.filter(session__utm_campaign__contains="test").delete()
        UserSession.objects.filter(utm_campaign__contains="test").delete()
        DailyStats.objects.filter(
            date__gte=timezone.now().date() - timedelta(days=30)
        ).delete()

        self.stdout.write(self.style.WARNING("Cleared existing test data"))

    def create_test_data(self, days, total_sessions):
        """Create comprehensive test data"""

        # Traffic source configurations
        traffic_sources = [
            {
                "utm_source": "google",
                "utm_medium": "cpc",
                "weight": 40,
                "conversion_rate": 0.12,
            },
            {
                "utm_source": "facebook",
                "utm_medium": "social",
                "weight": 25,
                "conversion_rate": 0.08,
            },
            {
                "utm_source": "twitter",
                "utm_medium": "social",
                "weight": 15,
                "conversion_rate": 0.06,
            },
            {
                "utm_source": "",
                "utm_medium": "",
                "weight": 15,
                "conversion_rate": 0.15,
            },  # Direct
            {
                "utm_source": "linkedin",
                "utm_medium": "social",
                "weight": 5,
                "conversion_rate": 0.10,
            },
        ]

        # Device type distribution
        device_types = [
            {"type": "mobile", "weight": 60},
            {"type": "desktop", "weight": 35},
            {"type": "tablet", "weight": 5},
        ]

        # Preference distribution (new preferences dominate)
        preference_distribution = [
            # Old preferences (20% of total)
            {"preference": "nothing", "weight": 5},
            {"preference": "notification", "weight": 10},
            {"preference": "updates", "weight": 5},
            # New preferences (80% of total)
            {"preference": "yes_would_use", "weight": 45},
            {"preference": "not_sure", "weight": 25},
            {"preference": "no_wouldnt_use", "weight": 10},
        ]

        # Generate sessions distributed over days
        sessions_per_day = self.distribute_sessions_over_days(total_sessions, days)

        total_created = 0
        for day_offset in range(days):
            day_sessions = sessions_per_day[day_offset]
            base_date = timezone.now() - timedelta(days=days - day_offset - 1)

            self.stdout.write(
                f"📅 Day {day_offset + 1}: Creating {day_sessions} sessions..."
            )

            day_signups = 0
            day_surveys = 0

            for _ in range(day_sessions):
                # Create session with realistic timing throughout the day
                session_time = self.random_time_in_day(base_date)
                session = self.create_session(
                    session_time, traffic_sources, device_types
                )

                # Create funnel events with realistic progression
                events = self.create_funnel_events(session, session_time)

                # Determine if user completes survey (70% completion rate)
                if random.random() < 0.70:
                    preference = self.weighted_choice(preference_distribution)
                    survey = self.create_survey_response(
                        session, preference, session_time
                    )
                    day_surveys += 1

                    # Determine if user converts (varies by traffic source)
                    source_config = next(
                        (
                            s
                            for s in traffic_sources
                            if s["utm_source"] == session.utm_source
                        ),
                        traffic_sources[-1],
                    )

                    if random.random() < source_config["conversion_rate"]:
                        signup = self.create_signup(session, session_time)
                        day_signups += 1

                total_created += 1

                if total_created % 50 == 0:
                    self.stdout.write(
                        f"   Created {total_created}/{total_sessions} sessions..."
                    )

            # Create daily stats for this day
            self.create_daily_stats(
                base_date.date(), day_sessions, day_surveys, day_signups
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Created {total_created} sessions with realistic funnel progression"
            )
        )

    def distribute_sessions_over_days(self, total_sessions, days):
        """Distribute sessions over days with realistic patterns"""
        # Higher traffic on recent days, lower on weekends
        base_distribution = []

        for day_offset in range(days):
            # Recent days get more traffic
            recency_multiplier = 0.7 + (day_offset / days) * 0.6

            # Weekend effect (assuming day 0 is most recent)
            day_of_week = (
                timezone.now() - timedelta(days=days - day_offset - 1)
            ).weekday()
            weekend_multiplier = 0.6 if day_of_week >= 5 else 1.0

            weight = recency_multiplier * weekend_multiplier
            base_distribution.append(weight)

        # Normalize to total sessions
        total_weight = sum(base_distribution)
        sessions_per_day = [
            int((weight / total_weight) * total_sessions)
            for weight in base_distribution
        ]

        # Adjust for rounding
        difference = total_sessions - sum(sessions_per_day)
        for i in range(abs(difference)):
            if difference > 0:
                sessions_per_day[i % len(sessions_per_day)] += 1
            else:
                sessions_per_day[i % len(sessions_per_day)] -= 1

        return sessions_per_day

    def random_time_in_day(self, base_date):
        """Generate random time within a day with realistic distribution"""
        # Peak hours: 9-11 AM, 2-4 PM, 7-9 PM
        hour_weights = [
            1,
            1,
            1,
            1,
            1,
            2,
            3,
            4,
            5,
            8,
            7,
            6,
            4,
            5,
            8,
            7,
            5,
            4,
            6,
            8,
            6,
            4,
            2,
            1,
        ]
        hour = self.weighted_choice(
            [{"preference": i, "weight": w} for i, w in enumerate(hour_weights)]
        )

        minute = random.randint(0, 59)
        second = random.randint(0, 59)

        return base_date.replace(hour=hour, minute=minute, second=second)

    def create_session(self, session_time, traffic_sources, device_types):
        """Create a realistic user session"""
        # Select traffic source and device
        source_config = self.weighted_choice(traffic_sources)
        device_config = self.weighted_choice(device_types)

        # Generate realistic session data
        session = UserSession.objects.create(
            session_id=uuid.uuid4(),
            first_seen=session_time,
            last_activity=session_time + timedelta(minutes=random.randint(1, 15)),
            ip_address=self.random_ip(),
            user_agent=self.random_user_agent(device_config["type"]),
            utm_source=source_config["utm_source"],
            utm_medium=source_config["utm_medium"],
            utm_campaign="test_civic_engagement_2024",
            utm_content=random.choice(["banner_a", "banner_b", "text_ad", ""]),
            utm_term=random.choice(
                ["civic reporting", "community issues", "city problems", ""]
            ),
            referrer=self.random_referrer(source_config["utm_source"]),
            country_code=random.choice(["NG", "GH", "KE", "ZA", "US"]),
            city=random.choice(
                ["Lagos", "Abuja", "Kano", "Accra", "Nairobi", "Cape Town"]
            ),
            region=random.choice(["Lagos State", "FCT", "Kano State", "Greater Accra"]),
            device_type=device_config["type"],
            browser=self.random_browser(),
            os=self.random_os(device_config["type"]),
            page_views=random.randint(1, 5),
            time_on_site=random.randint(30, 600),  # 30 seconds to 10 minutes
            is_bounce=random.random() < 0.4,  # 40% bounce rate
        )

        return session

    def create_funnel_events(self, session, session_time):
        """Create realistic funnel events for a session"""
        events = []
        current_time = session_time

        # Always start with page view
        events.append(
            FunnelEvent.objects.create(
                session=session,
                event_type="page_view",
                timestamp=current_time,
                page_url="https://tpsq.com/intervention/",
                page_title="Your Voice, Your Choice | tpsq",
                time_since_page_load=random.randint(100, 1000),
                metadata={"referrer": session.referrer, "viewport": "1920x1080"},
            )
        )

        current_time += timedelta(seconds=random.randint(5, 30))

        # 70% start survey
        if random.random() < 0.70:
            events.append(
                FunnelEvent.objects.create(
                    session=session,
                    event_type="survey_start",
                    timestamp=current_time,
                    page_url="https://tpsq.com/intervention/",
                    time_since_page_load=random.randint(5000, 30000),
                    metadata={"interaction_time": random.randint(5, 30)},
                )
            )

            current_time += timedelta(seconds=random.randint(10, 60))

            # 85% complete survey if they started
            if random.random() < 0.85:
                events.append(
                    FunnelEvent.objects.create(
                        session=session,
                        event_type="survey_complete",
                        timestamp=current_time,
                        time_since_page_load=random.randint(15000, 90000),
                        metadata={
                            "time_to_select": random.randint(10, 120),
                            "changes_made": random.randint(0, 3),
                        },
                    )
                )

                current_time += timedelta(seconds=random.randint(5, 20))

                # 60% proceed to form if they completed survey
                if random.random() < 0.60:
                    events.append(
                        FunnelEvent.objects.create(
                            session=session,
                            event_type="form_start",
                            timestamp=current_time,
                            element_id="signupForm",
                            time_since_page_load=random.randint(20000, 120000),
                        )
                    )

                    current_time += timedelta(seconds=random.randint(30, 180))

                    # 80% complete signup if they started form
                    if random.random() < 0.80:
                        events.append(
                            FunnelEvent.objects.create(
                                session=session,
                                event_type="signup_attempt",
                                timestamp=current_time,
                                element_id="submitBtn",
                                time_since_page_load=random.randint(60000, 300000),
                            )
                        )

                        current_time += timedelta(seconds=random.randint(2, 10))

                        # 90% succeed if they attempted
                        if random.random() < 0.90:
                            events.append(
                                FunnelEvent.objects.create(
                                    session=session,
                                    event_type="signup_success",
                                    timestamp=current_time,
                                    time_since_page_load=random.randint(62000, 310000),
                                    metadata={"conversion": True},
                                )
                            )

        # Always add page exit
        exit_time = current_time + timedelta(seconds=random.randint(1, 30))
        events.append(
            FunnelEvent.objects.create(
                session=session,
                event_type="page_exit",
                timestamp=exit_time,
                time_since_page_load=random.randint(30000, 600000),
                metadata={"time_on_page": random.randint(30000, 600000)},
            )
        )

        return events

    def create_survey_response(self, session, preference, session_time):
        """Create survey response with realistic timing"""
        return SurveyResponse.objects.create(
            session=session,
            preference=preference,
            created_at=session_time + timedelta(seconds=random.randint(10, 90)),
            time_to_select=random.randint(5, 120),
            changed_mind_count=random.randint(0, 3),
        )

    def create_signup(self, session, session_time):
        """Create early access signup"""
        user_number = random.randint(1000, 9999)
        names = [
            "John Doe",
            "Jane Smith",
            "Ahmed Hassan",
            "Fatima Yusuf",
            "Kemi Adebayo",
            "Chidi Okafor",
            "Aisha Ibrahim",
            "Tunde Williams",
            "Grace Ogundimu",
            "Ibrahim Musa",
        ]

        name = random.choice(names)
        email = f"testuser{user_number}@example.com"

        return EarlyAccessSignup.objects.create(
            session=session,
            name=name,
            email=email,
            created_at=session_time + timedelta(minutes=random.randint(1, 10)),
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            is_verified=random.random() < 0.75,  # 75% verify email
            verified_at=(
                session_time + timedelta(hours=random.randint(1, 48))
                if random.random() < 0.75
                else None
            ),
        )

    def create_daily_stats(self, date, sessions, surveys, signups):
        """Create or update daily stats for a date"""
        events_for_day = FunnelEvent.objects.filter(timestamp__date=date)

        stats, created = DailyStats.objects.get_or_create(
            date=date,
            defaults={
                "unique_visitors": sessions,
                "page_views": events_for_day.filter(event_type="page_view").count(),
                "surveys_started": events_for_day.filter(
                    event_type="survey_start"
                ).count(),
                "surveys_completed": events_for_day.filter(
                    event_type="survey_complete"
                ).count(),
                "signups": signups,
                "verified_signups": int(signups * 0.75),
            },
        )

        if not created:
            # Update existing stats
            stats.unique_visitors += sessions
            stats.page_views = events_for_day.filter(event_type="page_view").count()
            stats.surveys_started = events_for_day.filter(
                event_type="survey_start"
            ).count()
            stats.surveys_completed = events_for_day.filter(
                event_type="survey_complete"
            ).count()
            stats.signups += signups
            stats.verified_signups = int(stats.signups * 0.75)

        stats.calculate_rates()

    # Helper methods for realistic data generation
    def weighted_choice(self, choices):
        """Select item based on weights"""
        total_weight = sum(choice["weight"] for choice in choices)
        r = random.uniform(0, total_weight)

        current_weight = 0
        for choice in choices:
            current_weight += choice["weight"]
            if r <= current_weight:
                return choice["preference"] if "preference" in choice else choice

        return choices[-1]["preference"] if "preference" in choices[-1] else choices[-1]

    def random_ip(self):
        """Generate random IP address"""
        return f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"

    def random_user_agent(self, device_type):
        """Generate realistic user agent"""
        if device_type == "mobile":
            return random.choice(
                [
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
                    "Mozilla/5.0 (Android 11; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0",
                    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36",
                ]
            )
        elif device_type == "tablet":
            return "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
        else:
            return random.choice(
                [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                ]
            )

    def random_referrer(self, utm_source):
        """Generate realistic referrer URL"""
        referrers = {
            "google": "https://www.google.com/",
            "facebook": "https://www.facebook.com/",
            "twitter": "https://twitter.com/",
            "linkedin": "https://www.linkedin.com/",
            "": "",  # Direct traffic
        }
        return referrers.get(utm_source, "")

    def random_browser(self):
        """Generate random browser"""
        return random.choice(["Chrome", "Safari", "Firefox", "Edge", "Opera"])

    def random_os(self, device_type):
        """Generate random OS based on device type"""
        if device_type == "mobile":
            return random.choice(["iOS", "Android"])
        elif device_type == "tablet":
            return random.choice(["iOS", "Android", "iPadOS"])
        else:
            return random.choice(["Windows", "macOS", "Linux"])

    def show_summary(self):
        """Show summary of created data"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("📊 TEST DATA SUMMARY"))
        self.stdout.write("=" * 50)

        # Session summary
        sessions = UserSession.objects.filter(utm_campaign__contains="test")
        self.stdout.write(f"👥 Total Sessions: {sessions.count()}")

        # Traffic sources
        sources = (
            sessions.values("utm_source").annotate(count=Count("id")).order_by("-count")
        )
        self.stdout.write("\n🚦 Traffic Sources:")
        for source in sources:
            source_name = source["utm_source"] or "Direct"
            self.stdout.write(f'   {source_name}: {source["count"]} sessions')

        # Device breakdown
        devices = sessions.values("device_type").annotate(count=Count("id"))
        self.stdout.write("\n📱 Device Types:")
        for device in devices:
            self.stdout.write(
                f'   {device["device_type"].title()}: {device["count"]} sessions'
            )

        # Survey responses
        surveys = SurveyResponse.objects.filter(session__utm_campaign__contains="test")
        self.stdout.write(f"\n📝 Survey Responses: {surveys.count()}")

        # Preference breakdown
        preferences = (
            surveys.values("preference").annotate(count=Count("id")).order_by("-count")
        )
        self.stdout.write("\n🎯 Preference Distribution:")

        old_prefs = ["nothing", "notification", "updates"]
        new_prefs = ["yes_would_use", "no_wouldnt_use", "not_sure"]

        old_total = sum(p["count"] for p in preferences if p["preference"] in old_prefs)
        new_total = sum(p["count"] for p in preferences if p["preference"] in new_prefs)

        self.stdout.write(
            f"   📈 Old Preferences (Follow-up): {old_total} ({old_total/surveys.count()*100:.1f}%)"
        )
        for pref in preferences:
            if pref["preference"] in old_prefs:
                self.stdout.write(f'      {pref["preference"]}: {pref["count"]}')

        self.stdout.write(
            f"   🆕 New Preferences (App Intent): {new_total} ({new_total/surveys.count()*100:.1f}%)"
        )
        for pref in preferences:
            if pref["preference"] in new_prefs:
                self.stdout.write(f'      {pref["preference"]}: {pref["count"]}')

        # Signup summary
        signups = EarlyAccessSignup.objects.filter(email__contains="testuser")
        self.stdout.write(f"\n✅ Signups: {signups.count()}")
        self.stdout.write(f"   Verified: {signups.filter(is_verified=True).count()}")

        # Conversion rates
        if sessions.count() > 0:
            conversion_rate = (signups.count() / sessions.count()) * 100
            self.stdout.write(f"\n📈 Overall Conversion Rate: {conversion_rate:.1f}%")

        # Daily stats
        daily_stats = DailyStats.objects.filter(
            date__gte=timezone.now().date() - timedelta(days=7)
        )
        self.stdout.write(f"\n📅 Daily Stats Records: {daily_stats.count()}")

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("🎉 Ready to test analytics dashboard!"))
        self.stdout.write("=" * 50)
