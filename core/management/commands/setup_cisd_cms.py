import os

from core.models import Author, Category, SiteSettings, Tag
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Set up initial data for CISD CMS with comprehensive configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-superuser",
            action="store_true",
            help="Skip creating superuser if one already exists",
        )
        parser.add_argument(
            "--sample-data",
            action="store_true",
            help="Create sample articles and content",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Setting up CISD CMS..."))

        # Create categories
        self.create_categories()

        # Create tags
        self.create_tags()

        # Create default authors
        self.create_authors()

        # Create site settings
        self.create_site_settings()

        # Create superuser
        if not options["skip_superuser"]:
            self.create_superuser()

        # Create sample data if requested
        if options["sample_data"]:
            self.create_sample_data()

        self.stdout.write(self.style.SUCCESS("✅ CISD CMS setup complete!"))
        self.stdout.write("🌐 Visit /admin/dashboard/ to start managing content")

    def create_categories(self):
        """Create default categories with proper ordering and colors"""
        categories = [
            {
                "name": "analysis",
                "display_name": "Analysis",
                "description": "In-depth analysis of policy issues and governance",
                "color_code": "#dc2626",
                "icon_class": "fas fa-chart-line",
                "sort_order": 1,
            },
            {
                "name": "campaign",
                "display_name": "Campaign",
                "description": "Advocacy campaigns and civic engagement initiatives",
                "color_code": "#1e40af",
                "icon_class": "fas fa-bullhorn",
                "sort_order": 2,
            },
            {
                "name": "explainer",
                "display_name": "Explainer",
                "description": "Clear explanations of complex policy issues",
                "color_code": "#059669",
                "icon_class": "fas fa-lightbulb",
                "sort_order": 3,
            },
            {
                "name": "qna",
                "display_name": "Q&A",
                "description": "Questions and answers on governance topics",
                "color_code": "#7c3aed",
                "icon_class": "fas fa-question-circle",
                "sort_order": 4,
            },
            {
                "name": "news",
                "display_name": "News",
                "description": "Latest news and updates from CISD",
                "color_code": "#ea580c",
                "icon_class": "fas fa-newspaper",
                "sort_order": 5,
            },
            {
                "name": "research",
                "display_name": "Research",
                "description": "Research reports and findings",
                "color_code": "#0891b2",
                "icon_class": "fas fa-microscope",
                "sort_order": 6,
            },
        ]

        for cat_data in categories:
            category, created = Category.objects.get_or_create(
                name=cat_data["name"], defaults=cat_data
            )
            if created:
                self.stdout.write(f"  ✓ Created category: {category.display_name}")
            else:
                self.stdout.write(f"  → Category exists: {category.display_name}")

    def create_tags(self):
        """Create essential tags for content organization"""
        tags = [
            {
                "name": "Governance",
                "description": "Democratic governance and institutions",
                "is_featured": True,
            },
            {
                "name": "Civic Participation",
                "description": "Citizen engagement in democracy",
                "is_featured": True,
            },
            {
                "name": "Electoral Reform",
                "description": "Election and voting system improvements",
                "is_featured": True,
            },
            {
                "name": "Tax Justice",
                "description": "Fair taxation and fiscal policy",
                "is_featured": True,
            },
            {
                "name": "Gender Inclusion",
                "description": "Gender equality and women empowerment",
                "is_featured": True,
            },
            {
                "name": "Human-Centered Design",
                "description": "HCD approach to policy development",
            },
            {
                "name": "Behavioral Science",
                "description": "Behavioral insights in governance",
            },
            {
                "name": "Community Development",
                "description": "Local community initiatives",
            },
            {"name": "Policy Reform", "description": "Government policy improvements"},
            {
                "name": "Digital Governance",
                "description": "Technology in government services",
            },
            {"name": "Youth Engagement", "description": "Young people in democracy"},
            {
                "name": "Transparency",
                "description": "Government transparency and openness",
            },
            {
                "name": "Accountability",
                "description": "Government accountability mechanisms",
            },
            {
                "name": "Social Justice",
                "description": "Equity and social justice issues",
            },
            {
                "name": "Economic Justice",
                "description": "Fair economic policies and practices",
            },
        ]

        for tag_data in tags:
            tag, created = Tag.objects.get_or_create(
                name=tag_data["name"], defaults=tag_data
            )
            if created:
                self.stdout.write(f"  ✓ Created tag: {tag.name}")

    def create_authors(self):
        """Create default author profiles"""
        authors = [
            {
                "name": "Folahan Johnson",
                "title": "Executive Director",
                "bio": "Executive Director at Centre for Inclusive Social Development with expertise in governance and policy reform.",
                "email": "folahan@cisd.org",
                "is_featured": True,
                "sort_order": 1,
            },
            {
                "name": "Michael Daramola",
                "title": "Senior Policy Analyst",
                "bio": "Senior Policy Analyst specializing in behavioral science applications in governance and public policy.",
                "email": "michael@cisd.org",
                "is_featured": True,
                "sort_order": 2,
            },
            {
                "name": "Nkenna Williams",
                "title": "Gender & Social Inclusion Specialist",
                "bio": "Expert in gender equality, social inclusion, and human rights with focus on policy implementation.",
                "email": "nkenna@cisd.org",
                "is_featured": True,
                "sort_order": 3,
            },
            {
                "name": "Kendall Verhovek",
                "title": "Human-Centered Design Lead",
                "bio": "Leading human-centered design initiatives for community-driven policy development and implementation.",
                "email": "kendall@cisd.org",
                "is_featured": True,
                "sort_order": 4,
            },
            {
                "name": "George Kacuna",
                "title": "Community Engagement Coordinator",
                "bio": "Coordinating community dialogue and participatory development initiatives across Nigeria.",
                "is_featured": False,
                "sort_order": 5,
            },
            {
                "name": "Chinoso Asuma",
                "title": "Research Associate",
                "bio": "Research associate focusing on electoral reforms and democratic participation.",
                "is_featured": False,
                "sort_order": 6,
            },
        ]

        for author_data in authors:
            author, created = Author.objects.get_or_create(
                name=author_data["name"], defaults=author_data
            )
            if created:
                self.stdout.write(f"  ✓ Created author: {author.name}")

    def create_site_settings(self):
        """Create comprehensive site settings"""
        settings_data = {
            "site_name": "Centre for Inclusive Social Development",
            "site_tagline": "Bridging Policy and People",
            "site_description": "Bridging the gap between policy and people through behavioral science, human-centered design, and participatory development.",
            "email": "info@cisd.org",
            "phone": "+234 123 456 7890",
            "address": "3rd Floor Donatella Media\nPlot 398 Constitution Ave\nCentral Business District\nAbuja, Nigeria",
            "default_meta_title": "Centre for Inclusive Social Development",
            "default_meta_description": "Bridging the gap between policy and people through behavioral science, human-centered design, and participatory development.",
            "enable_comments": True,
            "enable_newsletter": True,
            "maintenance_mode": False,
        }

        site_settings, created = SiteSettings.objects.get_or_create(
            defaults=settings_data
        )

        if created:
            self.stdout.write("  ✓ Created site settings")
        else:
            self.stdout.write("  → Site settings already exist")

    def create_superuser(self):
        """Create superuser if none exists"""
        if not User.objects.filter(is_superuser=True).exists():
            username = "admin"
            email = "admin@cisd.org"
            password = "cisd2025!"  # Should be changed immediately

            User.objects.create_superuser(
                username=username, email=email, password=password
            )
            self.stdout.write(f"  ✓ Created superuser: {username}")
            self.stdout.write(self.style.WARNING(f"  ⚠️  Default password: {password}"))
            self.stdout.write(
                self.style.WARNING("  ⚠️  Please change the password immediately!")
            )
        else:
            self.stdout.write("  → Superuser already exists")

    def create_sample_data(self):
        """Create sample articles and content"""
        from core.models import Article, ContentSection

        # Sample articles
        sample_articles = [
            {
                "title": "Advancing Democratic Governance Through Human-Centered Design",
                "excerpt": "How CISD is using human-centered design principles to create more inclusive and effective governance systems in Nigeria.",
                "category": "analysis",
                "author": "Folahan Johnson",
                "status": "published",
                "is_featured": True,
                "content_sections": [
                    {
                        "type": "paragraph",
                        "content": "<p>Democratic governance in Nigeria faces unique challenges that require innovative approaches. At CISD, we believe that human-centered design (HCD) provides a powerful framework for creating policies and systems that truly serve the people.</p>",
                    },
                    {"type": "heading", "content": "The HCD Approach to Policy"},
                    {
                        "type": "paragraph",
                        "content": "<p>Human-centered design puts people at the center of the design process. This means understanding their needs, challenges, and aspirations before developing solutions. In the context of governance, this translates to policies that are not only effective but also accessible and acceptable to the communities they serve.</p>",
                    },
                ],
            },
            {
                "title": "Youth Engagement Beyond the Ballot Box: A New Campaign",
                "excerpt": "Introducing our comprehensive campaign to equip young Nigerians with tools for continuous civic participation.",
                "category": "campaign",
                "author": "Michael Daramola",
                "status": "published",
                "is_featured": True,
                "content_sections": [
                    {
                        "type": "paragraph",
                        "content": "<p>Democracy doesn't end at the ballot box. Our new youth engagement campaign recognizes that meaningful participation requires ongoing involvement in governance processes.</p>",
                    },
                    {
                        "type": "quote",
                        "content": "True democratic participation means having a voice in decisions that affect your daily life, not just once every four years.",
                    },
                ],
            },
        ]

        for article_data in sample_articles:
            try:
                category = Category.objects.get(name=article_data["category"])
                author = Author.objects.get(name=article_data["author"])

                article, created = Article.objects.get_or_create(
                    title=article_data["title"],
                    defaults={
                        "excerpt": article_data["excerpt"],
                        "category": category,
                        "author": author,
                        "status": article_data["status"],
                        "is_featured": article_data["is_featured"],
                        "published_date": timezone.now(),
                        "created_by": User.objects.filter(is_superuser=True).first(),
                        "last_modified_by": User.objects.filter(
                            is_superuser=True
                        ).first(),
                    },
                )

                if created:
                    # Create content sections
                    for i, section_data in enumerate(article_data["content_sections"]):
                        ContentSection.objects.create(
                            article=article,
                            section_type=section_data["type"],
                            content=section_data["content"],
                            order=i,
                        )

                    self.stdout.write(f"  ✓ Created sample article: {article.title}")

            except (Category.DoesNotExist, Author.DoesNotExist) as e:
                self.stdout.write(f"  ✗ Failed to create article: {e}")
