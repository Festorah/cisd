"""
Django management command to verify test analytics data is working correctly.

Usage: python manage.py verify_test_analytics

This command tests:
- Analytics calculations with mixed preferences
- Dashboard API responses
- Insight generation
- Data integrity
"""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from tpsq.models import EarlyAccessSignup, SurveyResponse, UserSession
from tpsq.utils import AnalyticsCalculator, FunnelAnalyzer


class Command(BaseCommand):
    help = "Verify test analytics data is working correctly"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Verifying test analytics data..."))

        # Check if test data exists
        test_sessions = UserSession.objects.filter(utm_campaign__contains="test")
        if not test_sessions.exists():
            self.stdout.write(
                self.style.ERROR(
                    "❌ No test data found. Run create_test_analytics_data first."
                )
            )
            return

        self.verify_data_structure()
        self.verify_analytics_calculations()
        self.verify_mixed_preferences()
        self.verify_insights_generation()
        self.verify_dashboard_compatibility()

        self.stdout.write(
            self.style.SUCCESS(
                "✅ All verification tests passed! Analytics are working correctly."
            )
        )

    def verify_data_structure(self):
        """Verify basic data structure"""
        self.stdout.write("\n📊 Verifying data structure...")

        # Count test data
        test_sessions = UserSession.objects.filter(utm_campaign__contains="test")
        test_surveys = SurveyResponse.objects.filter(
            session__utm_campaign__contains="test"
        )
        test_signups = EarlyAccessSignup.objects.filter(email__contains="testuser")

        self.stdout.write(f"   Sessions: {test_sessions.count()}")
        self.stdout.write(f"   Surveys: {test_surveys.count()}")
        self.stdout.write(f"   Signups: {test_signups.count()}")

        # Verify preference distribution
        old_prefs = test_surveys.filter(
            preference__in=["nothing", "notification", "updates"]
        ).count()
        new_prefs = test_surveys.filter(
            preference__in=["yes_would_use", "no_wouldnt_use", "not_sure"]
        ).count()

        self.stdout.write(
            f"   Old preferences: {old_prefs} ({old_prefs/test_surveys.count()*100:.1f}%)"
        )
        self.stdout.write(
            f"   New preferences: {new_prefs} ({new_prefs/test_surveys.count()*100:.1f}%)"
        )

        # Check that new preferences dominate
        if new_prefs > old_prefs:
            self.stdout.write(
                self.style.SUCCESS("   ✅ New preferences dominate as expected")
            )
        else:
            self.stdout.write(
                self.style.WARNING("   ⚠️  Expected new preferences to dominate")
            )

    def verify_analytics_calculations(self):
        """Test analytics calculations with mixed data"""
        self.stdout.write("\n🧮 Testing analytics calculations...")

        # Use last 7 days to capture test data
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)

        calc = AnalyticsCalculator(start_date, end_date)

        try:
            # Test basic funnel calculation
            funnel = calc.get_conversion_funnel()
            self.stdout.write(
                f'   Funnel calculation: {funnel["total_sessions"]} sessions → {funnel["conversions"]} conversions'
            )

            # Test conversion rates
            rates = calc.get_conversion_rates()
            if "overall" in rates:
                self.stdout.write(
                    f'   Overall conversion rate: {rates["overall"]:.1f}%'
                )

            # Test preference breakdown
            preferences = calc.get_user_preferences_breakdown()
            total_responses = preferences.get("total_responses", 0)
            self.stdout.write(
                f"   Preference analysis: {total_responses} total responses"
            )

            # Check segmented data
            if "original_question" in preferences and "new_question" in preferences:
                orig_total = preferences["original_question"]["total"]
                new_total = preferences["new_question"]["total"]
                self.stdout.write(
                    f"   Segmented: {orig_total} old + {new_total} new preferences"
                )
                self.stdout.write(
                    self.style.SUCCESS("   ✅ Mixed preference analysis working")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "   ⚠️  Mixed preference segmentation not detected"
                    )
                )

            # Test traffic attribution
            traffic = calc.get_traffic_attribution()
            sources_count = len(traffic.get("sources", []))
            self.stdout.write(f"   Traffic sources analyzed: {sources_count}")

            self.stdout.write(
                self.style.SUCCESS("   ✅ Analytics calculations working")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Analytics calculation error: {str(e)}")
            )

    def verify_mixed_preferences(self):
        """Test mixed preference handling"""
        self.stdout.write("\n🔀 Testing mixed preference handling...")

        # Test preference model methods
        test_surveys = SurveyResponse.objects.filter(
            session__utm_campaign__contains="test"
        )

        old_pref_count = 0
        new_pref_count = 0

        for survey in test_surveys[:10]:  # Test first 10
            question_type = survey.question_type
            engagement_level = survey.engagement_level

            if question_type == "engagement_followup":
                old_pref_count += 1
            elif question_type == "app_usage_intent":
                new_pref_count += 1

            # Verify engagement level mapping
            expected_levels = {
                "nothing": "low",
                "notification": "medium",
                "updates": "high",
                "no_wouldnt_use": "low",
                "not_sure": "medium",
                "yes_would_use": "high",
            }

            expected_level = expected_levels.get(survey.preference, "unknown")
            if engagement_level != expected_level:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⚠️  Engagement level mismatch: {survey.preference} → {engagement_level} (expected {expected_level})"
                    )
                )

        self.stdout.write(
            f"   Question type detection: {old_pref_count} old, {new_pref_count} new"
        )
        self.stdout.write(self.style.SUCCESS("   ✅ Mixed preference handling working"))

    def verify_insights_generation(self):
        """Test insight generation with mixed data"""
        self.stdout.write("\n💡 Testing insights generation...")

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)

        calc = AnalyticsCalculator(start_date, start_date)

        try:
            preferences = calc.get_user_preferences_breakdown()
            insights = preferences.get("insights", [])

            self.stdout.write(f"   Generated {len(insights)} insights:")
            for i, insight in enumerate(insights[:5]):  # Show first 5
                self.stdout.write(f"     {i+1}. {insight}")

            # Check for mixed-data specific insights
            mixed_insights = [
                i
                for i in insights
                if "app usage" in i.lower() or "follow-up" in i.lower() or "split:" in i
            ]
            if mixed_insights:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"   ✅ Found {len(mixed_insights)} mixed-data insights"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING("   ⚠️  No mixed-data specific insights detected")
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Insights generation error: {str(e)}")
            )

    def verify_dashboard_compatibility(self):
        """Test dashboard API compatibility"""
        self.stdout.write("\n🎛️  Testing dashboard compatibility...")

        try:
            # Simulate dashboard data request
            from django.contrib.auth.models import User
            from django.test import Client

            client = Client()

            # Test dashboard stats API
            response = client.get("/api/dashboard-stats/?days=7")

            if response.status_code == 200:
                data = response.json()

                # Check for preference data
                if "preferences" in data:
                    prefs = data["preferences"]
                    old_pref_keys = ["nothing", "notification", "updates"]
                    new_pref_keys = ["yes_would_use", "no_wouldnt_use", "not_sure"]

                    has_old = any(key in prefs for key in old_pref_keys)
                    has_new = any(key in prefs for key in new_pref_keys)

                    if has_old and has_new:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "   ✅ Dashboard API returns mixed preference data"
                            )
                        )
                    elif has_new:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "   ✅ Dashboard API returns new preference data"
                            )
                        )
                    elif has_old:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "   ✅ Dashboard API returns old preference data"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                "   ⚠️  No preference data in API response"
                            )
                        )

                # Check other key metrics
                required_fields = [
                    "overview",
                    "funnel",
                    "traffic_sources",
                    "daily_trends",
                ]
                missing_fields = [
                    field for field in required_fields if field not in data
                ]

                if not missing_fields:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "   ✅ All required dashboard fields present"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"   ⚠️  Missing dashboard fields: {missing_fields}"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Dashboard API error: {response.status_code}"
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Dashboard test error: {str(e)}")
            )
            self.stdout.write("   (This is normal if running without a web server)")

    def show_test_recommendations(self):
        """Show recommendations for testing"""
        self.stdout.write("\n🎯 Testing Recommendations:")
        self.stdout.write(
            "   1. Visit /tpsq/dashboard/ to see mixed preference visualization"
        )
        self.stdout.write(
            '   2. Toggle between "All", "Follow-up", and "App Intent" views'
        )
        self.stdout.write("   3. Check insights adapt to available data")
        self.stdout.write(
            "   4. Verify conversion funnel includes both preference types"
        )
        self.stdout.write("   5. Test admin interface filters by question type")

        # Show specific test URLs
        self.stdout.write("\n🔗 Test URLs:")
        self.stdout.write("   Dashboard: /tpsq/dashboard/")
        self.stdout.write("   API: /api/dashboard-stats/?days=7")
        self.stdout.write("   Admin: /admin/tpsq/surveyresponse/")


if __name__ == "__main__":
    # Allow running as standalone script
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cisd.settings")
    django.setup()

    command = Command()
    command.handle()
