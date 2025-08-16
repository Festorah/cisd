import os

from core.models import Author, Category, SiteSettings, Tag
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Publish articles that are scheduled for publication"

    def handle(self, *args, **options):
        from core.models import Article

        scheduled_articles = Article.objects.filter(
            status="scheduled", scheduled_publish_date__lte=timezone.now()
        )

        published_count = 0
        for article in scheduled_articles:
            article.status = "published"
            article.published_date = timezone.now()
            article.save(update_fields=["status", "published_date"])

            published_count += 1
            self.stdout.write(f"Published: {article.title}")

        if published_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Published {published_count} scheduled articles")
            )
        else:
            self.stdout.write("No articles were ready for publication")
