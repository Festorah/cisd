from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Article,
    Author,
    Category,
    CloudinaryMedia,
    ContentSection,
    Event,
    Newsletter,
    SiteSettings,
    Subscriber,
    Tag,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "name",
        "color_preview",
        "icon_class",
        "sort_order",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "display_name", "description"]
    list_editable = ["sort_order", "is_active"]
    ordering = ["sort_order", "display_name"]

    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px; border: 1px solid #ccc;"></div>',
            obj.color_code,
        )

    color_preview.short_description = "Color"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "usage_count", "is_featured", "created_at"]
    list_filter = ["is_featured", "created_at"]
    search_fields = ["name", "description"]
    list_editable = ["is_featured"]
    ordering = ["-usage_count", "name"]
    readonly_fields = ["usage_count", "slug"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "title",
        "email",
        "is_active",
        "is_featured",
        "sort_order",
        "created_at",
    ]
    list_filter = ["is_active", "is_featured", "created_at"]
    search_fields = ["name", "title", "email", "bio"]
    list_editable = ["is_active", "is_featured", "sort_order"]
    ordering = ["sort_order", "name"]


class ContentSectionInline(admin.StackedInline):
    model = ContentSection
    extra = 0
    fields = [
        "section_type",
        "order",
        "title",
        "content",
        "media_file",
        "caption",
        "alt_text",
        "question",
        "answer",
        "is_visible",
    ]
    ordering = ["order"]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "author",
        "status",
        "is_featured",
        "is_breaking",
        "published_date",
        "view_count",
        "created_at",
    ]
    list_filter = [
        "status",
        "category",
        "author",
        "is_featured",
        "is_breaking",
        "created_at",
        "published_date",
    ]
    search_fields = ["title", "excerpt", "meta_title"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_date"
    inlines = [ContentSectionInline]
    list_editable = ["status", "is_featured", "is_breaking"]

    fieldsets = (
        (
            "Content",
            {"fields": ("title", "slug", "excerpt", "category", "author", "tags")},
        ),
        ("Media", {"fields": ("featured_image",)}),
        (
            "Publishing",
            {"fields": ("status", "published_date", "scheduled_publish_date")},
        ),
        (
            "Features",
            {
                "fields": ("is_featured", "is_breaking", "allow_comments"),
                "classes": ("collapse",),
            },
        ),
        (
            "SEO",
            {
                "fields": ("meta_title", "meta_description", "meta_keywords"),
                "classes": ("collapse",),
            },
        ),
        (
            "Social Media",
            {
                "fields": ("social_title", "social_description"),
                "classes": ("collapse",),
            },
        ),
        (
            "Analytics",
            {
                "fields": ("view_count", "share_count", "comment_count"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = [
        "view_count",
        "share_count",
        "comment_count",
        "created_at",
        "updated_at",
    ]

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CloudinaryMedia)
class CloudinaryMediaAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "file_type",
        "file_size_formatted",
        "width",
        "height",
        "usage_count",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["file_type", "created_at", "uploaded_by"]
    search_fields = ["title", "caption", "tags", "cloudinary_public_id"]
    readonly_fields = [
        "cloudinary_public_id",
        # "file_size",
        "width",
        "height",
        "usage_count",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("uploaded_by")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "event_type",
        "start_datetime",
        "status",
        "is_featured",
        "is_public",
        "created_at",
    ]
    list_filter = [
        "event_type",
        "status",
        "is_featured",
        "is_public",
        "start_datetime",
        "created_at",
    ]
    search_fields = ["title", "description", "venue_name"]
    date_hierarchy = "start_datetime"
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["speakers", "tags"]
    list_editable = ["status", "is_featured", "is_public"]


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "subject",
        "is_sent",
        "sent_date",
        "total_sent",
        "open_rate",
        "click_rate",
        "created_at",
    ]
    list_filter = ["is_sent", "sent_date", "created_at"]
    search_fields = ["title", "subject"]
    readonly_fields = [
        "is_sent",
        "sent_date",
        "total_sent",
        "open_count",
        "click_count",
        "bounce_count",
        "unsubscribe_count",
        "open_rate",
        "click_rate",
        "bounce_rate",
    ]


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "full_name",
        "location",
        "frequency",
        "is_active",
        "is_confirmed",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "frequency",
        "confirmed_at",
        "unsubscribed_at",
        "created_at",
    ]
    search_fields = ["email", "first_name", "last_name", "location"]
    readonly_fields = ["confirmed_at", "unsubscribed_at", "last_sent"]
    filter_horizontal = ["categories"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("site_name", "site_tagline", "site_description")},
        ),
        ("Visual Branding", {"fields": ("logo", "favicon")}),
        ("Contact Information", {"fields": ("email", "phone", "address")}),
        (
            "Social Media",
            {
                "fields": (
                    "facebook_url",
                    "twitter_url",
                    "linkedin_url",
                    "youtube_url",
                    "instagram_url",
                )
            },
        ),
        (
            "SEO Defaults",
            {
                "fields": (
                    "default_meta_title",
                    "default_meta_description",
                    "default_og_image",
                )
            },
        ),
        (
            "Analytics & Tracking",
            {"fields": ("google_analytics_id", "google_tag_manager_id")},
        ),
        (
            "Feature Flags",
            {"fields": ("enable_comments", "enable_newsletter", "maintenance_mode")},
        ),
    )

    def has_add_permission(self, request):
        # Prevent adding more than one instance
        return not SiteSettings.objects.exists()


# Customize admin site
admin.site.site_header = "CISD Content Management System"
admin.site.site_title = "CISD CMS"
admin.site.index_title = "Welcome to CISD Content Management"
