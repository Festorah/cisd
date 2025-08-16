import random

from core.models import Article, Author, Category, ContentSection
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Generate sample articles for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=10, help="Number of articles to create"
        )

    def handle(self, *args, **options):
        count = options["count"]
        self.stdout.write(f"Generating {count} sample articles...")

        categories = list(Category.objects.all())
        authors = list(Author.objects.all())

        if not categories or not authors:
            self.stdout.write(self.style.ERROR("Please run setup_initial_data first"))
            return

        sample_titles = [
            "Advancing Democratic Governance in Nigeria",
            "Youth Participation in Policy Making",
            "Gender Equity in Public Service Delivery",
            "Strengthening Civil Society Organizations",
            "Digital Transformation for Government Services",
            "Community-Led Development Initiatives",
            "Tax Justice and Fiscal Transparency",
            "Electoral Reform Recommendations",
            "Healthcare Access for Marginalized Communities",
            "Education Policy Reform Strategies",
        ]

        for i in range(count):
            title = f"{random.choice(sample_titles)} - Part {i+1}"
            category = random.choice(categories)
            author = random.choice(authors)

            article = Article.objects.create(
                title=title,
                excerpt=f"This is a sample article about {title.lower()}. It discusses important aspects of governance and policy implementation.",
                category=category,
                author=author,
                status="published",
                published_date=timezone.now(),
                created_by_id=1,  # Assuming admin user exists
                last_modified_by_id=1,
            )

            # Add sample content sections
            ContentSection.objects.create(
                article=article,
                section_type="paragraph",
                content=f"<p>This is the introduction to {title}. It provides context and background information on the topic.</p>",
                order=0,
            )

            ContentSection.objects.create(
                article=article,
                section_type="paragraph",
                content=f"<p>This section discusses the main challenges and opportunities related to {title.lower()}.</p>",
                order=1,
            )

            self.stdout.write(f"Created article: {title}")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully generated {count} sample articles!")
        )
