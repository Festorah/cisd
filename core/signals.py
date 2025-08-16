from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Article, CloudinaryMedia, ContentSection, Tag


@receiver(post_save, sender=Article)
def update_article_slug_and_dates(sender, instance, created, **kwargs):
    """Handle article slug generation and date updates"""
    if created and not instance.slug:
        instance.slug = instance._generate_unique_slug()
        instance.save(update_fields=["slug"])

    # Update published_date when status changes to published
    if instance.status == "published" and not instance.published_date:
        instance.published_date = timezone.now()
        instance.save(update_fields=["published_date"])


@receiver(m2m_changed, sender=Article.tags.through)
def update_tag_usage_count(sender, instance, action, pk_set, **kwargs):
    """Update tag usage counts when articles are tagged/untagged"""
    if action in ["post_add", "post_remove", "post_clear"]:
        # Update usage count for affected tags
        if pk_set:
            tags = Tag.objects.filter(pk__in=pk_set)
            for tag in tags:
                tag.update_usage_count()


@receiver(post_save, sender=ContentSection)
def increment_media_usage(sender, instance, created, **kwargs):
    """Increment media usage count when referenced in content"""
    if created and instance.media_file:
        instance.media_file.increment_usage()


@receiver(post_delete, sender=ContentSection)
def decrement_media_usage(sender, instance, **kwargs):
    """Decrement media usage count when content section is deleted"""
    if instance.media_file:
        instance.media_file.usage_count = max(0, instance.media_file.usage_count - 1)
        instance.media_file.save(update_fields=["usage_count"])


@receiver(post_save, sender=CloudinaryMedia)
def set_media_dimensions(sender, instance, created, **kwargs):
    """Set image dimensions for image files if not already set"""
    if created and instance.file_type == "image" and not instance.width:
        # You would implement dimension extraction from Cloudinary here
        # This is a placeholder for the actual implementation
        pass
