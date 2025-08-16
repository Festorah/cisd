import os

from core.models import Author, Category, SiteSettings, Tag
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Update usage counts for all tags"

    def handle(self, *args, **options):
        from core.models import Tag

        tags = Tag.objects.all()
        updated_count = 0

        for tag in tags:
            old_count = tag.usage_count
            tag.update_usage_count()

            if tag.usage_count != old_count:
                updated_count += 1
                self.stdout.write(
                    f"Updated {tag.name}: {old_count} → {tag.usage_count}"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Updated usage counts for {updated_count} tags")
        )
