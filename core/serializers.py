from django.contrib.auth.models import User
from rest_framework import serializers

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


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for article categories"""

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "display_name",
            "description",
            "color_code",
            "icon_class",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]


class TagSerializer(serializers.ModelSerializer):
    """Serializer for article tags"""

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_featured",
            "usage_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "usage_count"]


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for article authors"""

    initials = serializers.CharField(source="get_initials", read_only=True)
    article_count = serializers.IntegerField(source="get_article_count", read_only=True)

    class Meta:
        model = Author
        fields = [
            "id",
            "name",
            "title",
            "bio",
            "profile_image_url",
            "profile_image_public_id",
            "email",
            "twitter_handle",
            "linkedin_url",
            "website_url",
            "is_active",
            "is_featured",
            "sort_order",
            "initials",
            "article_count",
            "created_at",
            "updated_at",
        ]


class CloudinaryMediaSerializer(serializers.ModelSerializer):
    """Serializer for Cloudinary media files"""

    file_size_formatted = serializers.CharField(
        source="file_size_formatted", read_only=True
    )
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.username", read_only=True
    )
    transformed_urls = serializers.SerializerMethodField()

    class Meta:
        model = CloudinaryMedia
        fields = [
            "id",
            "title",
            "cloudinary_url",
            "cloudinary_public_id",
            "file_type",
            "file_format",
            "file_size",
            "file_size_formatted",
            "width",
            "height",
            "alt_text",
            "caption",
            "tags",
            "uploaded_by_name",
            "usage_count",
            "transformed_urls",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["file_size", "uploaded_by", "usage_count"]

    def get_transformed_urls(self, obj):
        """Get common transformation URLs"""
        if obj.file_type != "image":
            return {}

        from .utils.cloudinary_utils import CloudinaryManager

        return {
            "thumbnail": CloudinaryManager.get_optimized_image_url(
                obj.cloudinary_public_id, width=300, height=200
            ),
            "medium": CloudinaryManager.get_optimized_image_url(
                obj.cloudinary_public_id, width=600, height=400
            ),
            "large": CloudinaryManager.get_optimized_image_url(
                obj.cloudinary_public_id, width=1200, height=800
            ),
        }


class ContentSectionSerializer(serializers.ModelSerializer):
    """Serializer for article content sections"""

    media_file = CloudinaryMediaSerializer(read_only=True)
    media_file_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = ContentSection
        fields = [
            "id",
            "section_type",
            "order",
            "content",
            "title",
            "media_file",
            "media_file_id",
            "caption",
            "alt_text",
            "question",
            "answer",
            "interviewer",
            "interviewee",
            "list_items",
            "table_data",
            "embed_code",
            "css_classes",
            "background_color",
            "is_visible",
            "is_expandable",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Handle media file assignment during creation"""
        media_file_id = validated_data.pop("media_file_id", None)
        section = ContentSection.objects.create(**validated_data)

        if media_file_id:
            try:
                media_file = CloudinaryMedia.objects.get(id=media_file_id)
                section.media_file = media_file
                section.save()
            except CloudinaryMedia.DoesNotExist:
                pass

        return section

    def update(self, instance, validated_data):
        """Handle media file assignment during update"""
        media_file_id = validated_data.pop("media_file_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if media_file_id:
            try:
                media_file = CloudinaryMedia.objects.get(id=media_file_id)
                instance.media_file = media_file
            except CloudinaryMedia.DoesNotExist:
                instance.media_file = None
        elif media_file_id is None:
            instance.media_file = None

        instance.save()
        return instance


class ArticleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual articles"""

    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)

    author = AuthorSerializer(read_only=True)
    author_id = serializers.UUIDField(write_only=True)

    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    content_sections = ContentSectionSerializer(many=True, read_only=True)
    featured_image = CloudinaryMediaSerializer(read_only=True)
    featured_image_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    reading_time = serializers.IntegerField(source="reading_time", read_only=True)
    is_published = serializers.BooleanField(source="is_published", read_only=True)

    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )
    last_modified_by_name = serializers.CharField(
        source="last_modified_by.username", read_only=True
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.username", read_only=True
    )

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "category_id",
            "author",
            "author_id",
            "tags",
            "tag_ids",
            "content_sections",
            "featured_image",
            "featured_image_id",
            "status",
            "published_date",
            "scheduled_publish_date",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "social_title",
            "social_description",
            "view_count",
            "share_count",
            "comment_count",
            "is_featured",
            "is_breaking",
            "allow_comments",
            "reading_time",
            "is_published",
            "created_at",
            "updated_at",
            "created_by_name",
            "last_modified_by_name",
            "reviewed_by_name",
            "reviewed_date",
        ]
        read_only_fields = [
            "slug",
            "view_count",
            "share_count",
            "comment_count",
            "created_at",
            "updated_at",
            "created_by_name",
            "last_modified_by_name",
            "reviewed_by_name",
        ]

    def create(self, validated_data):
        """Handle nested relationships during creation"""
        tag_ids = validated_data.pop("tag_ids", [])
        featured_image_id = validated_data.pop("featured_image_id", None)

        article = Article.objects.create(**validated_data)

        # Handle tags
        if tag_ids:
            tags = Tag.objects.filter(id__in=tag_ids)
            article.tags.set(tags)

        # Handle featured image
        if featured_image_id:
            try:
                featured_image = CloudinaryMedia.objects.get(id=featured_image_id)
                article.featured_image = featured_image
                article.save()
            except CloudinaryMedia.DoesNotExist:
                pass

        return article

    def update(self, instance, validated_data):
        """Handle nested relationships during update"""
        tag_ids = validated_data.pop("tag_ids", None)
        featured_image_id = validated_data.pop("featured_image_id", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle tags
        if tag_ids is not None:
            tags = Tag.objects.filter(id__in=tag_ids)
            instance.tags.set(tags)

        # Handle featured image
        if featured_image_id:
            try:
                featured_image = CloudinaryMedia.objects.get(id=featured_image_id)
                instance.featured_image = featured_image
            except CloudinaryMedia.DoesNotExist:
                instance.featured_image = None
        elif featured_image_id is None:
            instance.featured_image = None

        instance.save()
        return instance


class ArticleSerializer(serializers.ModelSerializer):
    """Basic serializer for article lists"""

    category = CategorySerializer(read_only=True)
    author = AuthorSerializer(read_only=True)
    featured_image = CloudinaryMediaSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    reading_time = serializers.IntegerField(source="reading_time", read_only=True)
    is_published = serializers.BooleanField(source="is_published", read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "author",
            "featured_image",
            "tags",
            "status",
            "published_date",
            "view_count",
            "share_count",
            "is_featured",
            "is_breaking",
            "reading_time",
            "is_published",
            "created_at",
            "updated_at",
        ]


class EventSerializer(serializers.ModelSerializer):
    """Serializer for events"""

    speakers = AuthorSerializer(many=True, read_only=True)
    speaker_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    organizer = AuthorSerializer(read_only=True)
    organizer_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    featured_image = CloudinaryMediaSerializer(read_only=True)
    featured_image_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    is_upcoming = serializers.BooleanField(source="is_upcoming", read_only=True)
    is_ongoing = serializers.BooleanField(source="is_ongoing", read_only=True)
    is_past = serializers.BooleanField(source="is_past", read_only=True)
    registration_open = serializers.BooleanField(
        source="registration_open", read_only=True
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "short_description",
            "event_type",
            "category",
            "category_id",
            "tags",
            "tag_ids",
            "start_datetime",
            "end_datetime",
            "timezone",
            "venue_name",
            "venue_address",
            "online_url",
            "featured_image",
            "featured_image_id",
            "agenda",
            "speakers",
            "speaker_ids",
            "organizer",
            "organizer_id",
            "registration_required",
            "registration_url",
            "registration_deadline",
            "max_attendees",
            "current_attendees",
            "status",
            "is_featured",
            "is_public",
            "is_upcoming",
            "is_ongoing",
            "is_past",
            "registration_open",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]

    def create(self, validated_data):
        """Handle relationships during creation"""
        speaker_ids = validated_data.pop("speaker_ids", [])
        tag_ids = validated_data.pop("tag_ids", [])
        featured_image_id = validated_data.pop("featured_image_id", None)
        organizer_id = validated_data.pop("organizer_id", None)
        category_id = validated_data.pop("category_id", None)

        event = Event.objects.create(**validated_data)

        # Handle relationships
        if speaker_ids:
            speakers = Author.objects.filter(id__in=speaker_ids)
            event.speakers.set(speakers)

        if tag_ids:
            tags = Tag.objects.filter(id__in=tag_ids)
            event.tags.set(tags)

        if featured_image_id:
            try:
                featured_image = CloudinaryMedia.objects.get(id=featured_image_id)
                event.featured_image = featured_image
                event.save()
            except CloudinaryMedia.DoesNotExist:
                pass

        return event


class NewsletterSerializer(serializers.ModelSerializer):
    """Serializer for newsletters"""

    open_rate = serializers.FloatField(source="open_rate", read_only=True)
    click_rate = serializers.FloatField(source="click_rate", read_only=True)
    bounce_rate = serializers.FloatField(source="bounce_rate", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Newsletter
        fields = [
            "id",
            "title",
            "subject",
            "content",
            "is_sent",
            "sent_date",
            "scheduled_date",
            "total_sent",
            "open_count",
            "click_count",
            "bounce_count",
            "unsubscribe_count",
            "open_rate",
            "click_rate",
            "bounce_rate",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "is_sent",
            "sent_date",
            "total_sent",
            "open_count",
            "click_count",
            "bounce_count",
            "unsubscribe_count",
            "created_at",
            "updated_at",
        ]


class SubscriberSerializer(serializers.ModelSerializer):
    """Serializer for newsletter subscribers"""

    full_name = serializers.CharField(source="full_name", read_only=True)
    is_confirmed = serializers.BooleanField(source="is_confirmed", read_only=True)
    is_unsubscribed = serializers.BooleanField(source="is_unsubscribed", read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model = Subscriber
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "location",
            "zip_code",
            "categories",
            "category_ids",
            "frequency",
            "is_active",
            "is_confirmed",
            "is_unsubscribed",
            "confirmed_at",
            "unsubscribed_at",
            "source",
            "last_sent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "confirmed_at",
            "unsubscribed_at",
            "last_sent",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Handle category relationships during creation"""
        category_ids = validated_data.pop("category_ids", [])
        subscriber = Subscriber.objects.create(**validated_data)

        if category_ids:
            categories = Category.objects.filter(id__in=category_ids)
            subscriber.categories.set(categories)

        return subscriber


class SiteSettingsSerializer(serializers.ModelSerializer):
    """Serializer for site settings"""

    logo = CloudinaryMediaSerializer(read_only=True)
    logo_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    favicon = CloudinaryMediaSerializer(read_only=True)
    favicon_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    default_og_image = CloudinaryMediaSerializer(read_only=True)
    default_og_image_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = SiteSettings
        fields = [
            "id",
            "site_name",
            "site_tagline",
            "site_description",
            "logo",
            "logo_id",
            "favicon",
            "favicon_id",
            "email",
            "phone",
            "address",
            "facebook_url",
            "twitter_url",
            "linkedin_url",
            "youtube_url",
            "instagram_url",
            "default_meta_title",
            "default_meta_description",
            "default_og_image",
            "default_og_image_id",
            "google_analytics_id",
            "google_tag_manager_id",
            "enable_comments",
            "enable_newsletter",
            "maintenance_mode",
            "created_at",
            "updated_at",
        ]


# Specialized serializers for specific use cases
class ArticleSummarySerializer(serializers.ModelSerializer):
    """Minimal serializer for article summaries"""

    category_name = serializers.CharField(source="category.display_name")
    author_name = serializers.CharField(source="author.name")
    featured_image_url = serializers.CharField(
        source="featured_image.cloudinary_url", allow_null=True
    )

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category_name",
            "author_name",
            "published_date",
            "view_count",
            "featured_image_url",
        ]


class RelatedArticleSerializer(serializers.ModelSerializer):
    """Serializer for related articles"""

    category = CategorySerializer(read_only=True)
    author_name = serializers.CharField(source="author.name")
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "author_name",
            "published_date",
            "featured_image_url",
        ]

    def get_featured_image_url(self, obj):
        if obj.featured_image and obj.featured_image.cloudinary_url:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.featured_image.cloudinary_url)
            return obj.featured_image.cloudinary_url
        return None


# Utility serializers for forms and dropdowns
class CategoryChoiceSerializer(serializers.ModelSerializer):
    """Simple serializer for category choices"""

    class Meta:
        model = Category
        fields = ["id", "name", "display_name", "color_code"]


class AuthorChoiceSerializer(serializers.ModelSerializer):
    """Simple serializer for author choices"""

    class Meta:
        model = Author
        fields = ["id", "name", "title"]


class TagChoiceSerializer(serializers.ModelSerializer):
    """Simple serializer for tag choices"""

    class Meta:
        model = Tag
        fields = ["id", "name", "usage_count"]


class MediaUploadSerializer(serializers.Serializer):
    """Serializer for handling file uploads to Cloudinary"""

    file = serializers.FileField()
    title = serializers.CharField(max_length=300, required=False)
    alt_text = serializers.CharField(max_length=255, required=False)
    caption = serializers.CharField(max_length=1000, required=False)
    tags = serializers.CharField(max_length=500, required=False)
    folder = serializers.CharField(max_length=100, required=False)

    def create(self, validated_data):
        """Handle file upload to Cloudinary and create media record"""
        from .utils.cloudinary_utils import CloudinaryManager

        file_obj = validated_data["file"]
        title = validated_data.get("title", file_obj.name)

        # Upload to Cloudinary
        upload_result = CloudinaryManager.upload_file(
            file_obj=file_obj,
            folder=validated_data.get("folder"),
            tags=(
                validated_data.get("tags", "").split(",")
                if validated_data.get("tags")
                else None
            ),
        )

        if not upload_result["success"]:
            raise serializers.ValidationError(
                f"Upload failed: {upload_result['error']}"
            )

        # Create CloudinaryMedia record
        file_type, file_format = CloudinaryManager.determine_file_type(file_obj)

        media = CloudinaryMedia.objects.create(
            title=title,
            cloudinary_url=upload_result["url"],
            cloudinary_public_id=upload_result["public_id"],
            file_type=file_type,
            file_format=file_format,
            file_size=upload_result["bytes"],
            width=upload_result.get("width"),
            height=upload_result.get("height"),
            alt_text=validated_data.get("alt_text", ""),
            caption=validated_data.get("caption", ""),
            tags=validated_data.get("tags", ""),
            uploaded_by=self.context["request"].user,
        )

        return media


# Bulk operation serializers
class BulkArticleUpdateSerializer(serializers.Serializer):
    """Serializer for bulk article operations"""

    article_ids = serializers.ListField(child=serializers.UUIDField())
    action = serializers.ChoiceField(
        choices=["publish", "unpublish", "archive", "delete"]
    )

    def validate_article_ids(self, value):
        """Validate that all article IDs exist"""
        existing_ids = set(
            Article.objects.filter(id__in=value).values_list("id", flat=True)
        )
        provided_ids = set(value)

        if not provided_ids.issubset(existing_ids):
            missing_ids = provided_ids - existing_ids
            raise serializers.ValidationError(
                f"Articles with IDs {list(missing_ids)} do not exist"
            )

        return value


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""

    total_articles = serializers.IntegerField()
    published_articles = serializers.IntegerField()
    draft_articles = serializers.IntegerField()
    archived_articles = serializers.IntegerField()
    total_subscribers = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
    total_page_views = serializers.IntegerField()
    total_media_files = serializers.IntegerField()
    recent_articles = ArticleSummarySerializer(many=True)
    popular_tags = TagChoiceSerializer(many=True)
