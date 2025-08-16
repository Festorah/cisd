from core.models import Author, Category, SiteSettings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set up initial data for CISD CMS"

    def handle(self, *args, **options):
        self.stdout.write("Setting up initial data...")

        # Create categories
        categories = [
            {"name": "analysis", "display_name": "Analysis", "color_code": "#dc2626"},
            {"name": "campaign", "display_name": "Campaign", "color_code": "#1e40af"},
            {"name": "explainer", "display_name": "Explainer", "color_code": "#059669"},
            {"name": "qna", "display_name": "Q&A", "color_code": "#7c3aed"},
            {"name": "news", "display_name": "News", "color_code": "#ea580c"},
        ]

        for cat_data in categories:
            category, created = Category.objects.get_or_create(
                name=cat_data["name"], defaults=cat_data
            )
            if created:
                self.stdout.write(f"Created category: {category.display_name}")

        # Create default authors
        authors = [
            {"name": "Folahan Johnson", "bio": "Executive Director at CISD"},
            {"name": "Michael Daramola", "bio": "Senior Policy Analyst"},
            {
                "name": "Nkenna Williams",
                "bio": "Gender and Social Inclusion Specialist",
            },
            {"name": "Kendall Verhovek", "bio": "Human-Centered Design Lead"},
        ]

        for author_data in authors:
            author, created = Author.objects.get_or_create(
                name=author_data["name"], defaults=author_data
            )
            if created:
                self.stdout.write(f"Created author: {author.name}")

        # Create site settings
        site_settings, created = SiteSettings.objects.get_or_create(
            defaults={
                "site_name": "Centre for Inclusive Social Development",
                "site_description": "Bridging the gap between policy and people through behavioral science, human-centered design, and participatory development.",
                "email": "info@cisd.org",
                "address": "3rd Floor Donatella Media\nPlot 398 Constitution Ave\nCentral Business District\nAbuja, Nigeria",
                "default_meta_title": "Centre for Inclusive Social Development",
                "default_meta_description": "Bridging the gap between policy and people through behavioral science, human-centered design, and participatory development.",
            }
        )

        if created:
            self.stdout.write("Created site settings")

        # Create superuser if it doesn't exist
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username="admin", email="admin@cisd.org", password="admin123"
            )
            self.stdout.write("Created superuser (username: admin, password: admin123)")

        self.stdout.write(self.style.SUCCESS("Initial data setup complete!"))
