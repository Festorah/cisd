import re
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import (
    EmailValidator,
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
    URLValidator,
)
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class TimestampedModel(models.Model):
    """
    Abstract base model that provides self-updating 'created_at' and 'updated_at' fields.
    All models should inherit from this for consistent timestamp tracking.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
        help_text=_("Unique identifier for this record"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("Timestamp when this record was first created"),
        db_index=True,  # Frequently used for ordering
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("Timestamp when this record was last modified"),
        db_index=True,  # Frequently used for ordering and cache invalidation
    )

    class Meta:
        abstract = True
        get_latest_by = "created_at"


class Category(TimestampedModel):
    """
    Article categories like Analysis, Campaign, Explainer, etc.
    Used for organizing and filtering content.
    """

    CATEGORY_CHOICES = [
        ("analysis", _("Analysis")),
        ("campaign", _("Campaign")),
        ("explainer", _("Explainer")),
        ("qna", _("Q&A")),
        ("news", _("News")),
        ("research", _("Research")),
        ("report", _("Report")),
        ("opinion", _("Opinion")),
        ("interview", _("Interview")),
        ("feature", _("Feature")),
    ]

    name = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        unique=True,
        verbose_name=_("Category Name"),
        help_text=_("Internal name for the category (used in URLs and code)"),
        db_index=True,  # Frequently used for filtering
    )
    display_name = models.CharField(
        max_length=100,
        verbose_name=_("Display Name"),
        help_text=_("Human-readable name shown to users"),
        validators=[MinLengthValidator(2), MaxLengthValidator(100)],
    )
    description = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of what this category represents"),
    )
    color_code = models.CharField(
        max_length=7,
        default="#dc2626",
        verbose_name=_("Color Code"),
        help_text=_("Hex color code for category display (e.g., #dc2626)"),
        validators=[
            RegexValidator(
                regex=r"^#[0-9a-fA-F]{6}$",
                message=_("Enter a valid hex color code (e.g., #dc2626)"),
            )
        ],
    )
    icon_class = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Icon Class"),
        help_text=_("FontAwesome or other icon class for category display"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this category is available for new content"),
        db_index=True,  # Frequently filtered
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Sort Order"),
        help_text=_("Order in which categories appear in lists (lower numbers first)"),
    )

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["sort_order", "display_name"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.display_name

    def clean(self):
        if self.name and self.name not in dict(self.CATEGORY_CHOICES):
            raise ValidationError(_("Invalid category name"))


class Tag(TimestampedModel):
    """
    Tags for categorizing and cross-referencing articles.
    Many-to-many relationship with articles for flexible organization.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Tag Name"),
        help_text=_("Descriptive tag name (e.g., 'Civic Participation')"),
        validators=[MinLengthValidator(2), MaxLengthValidator(100)],
        db_index=True,  # Frequently searched
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly version of the tag name (auto-generated)"),
        db_index=True,  # Used in URLs
    )
    description = models.TextField(
        max_length=300,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of what this tag represents"),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured"),
        help_text=_("Whether this tag should be prominently displayed"),
        db_index=True,
    )
    usage_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Usage Count"),
        help_text=_("Number of articles using this tag (auto-calculated)"),
        db_index=True,  # Used for popular tags queries
    )

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")
        ordering = ["-usage_count", "name"]
        indexes = [
            models.Index(fields=["is_featured", "-usage_count"]),
            models.Index(fields=["slug"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def update_usage_count(self):
        """Update the usage count based on article relationships"""
        self.usage_count = self.articles.filter(status="published").count()
        self.save(update_fields=["usage_count"])


class Author(TimestampedModel):
    """
    Author profiles for articles and content.
    Can be linked to Django User accounts or standalone.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("User Account"),
        help_text=_("Link to Django user account (optional)"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Full Name"),
        help_text=_("Author's full name as it should appear publicly"),
        validators=[MinLengthValidator(2), MaxLengthValidator(200)],
        db_index=True,  # Frequently searched and displayed
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Professional Title"),
        help_text=_("Job title or role (e.g., 'Senior Policy Analyst')"),
    )
    bio = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name=_("Biography"),
        help_text=_("Brief professional biography (max 1000 characters)"),
    )
    profile_image_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_("Profile Image URL"),
        help_text=_("Cloudinary URL for author's profile photo"),
        validators=[URLValidator()],
    )
    profile_image_public_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Profile Image Public ID"),
        help_text=_("Cloudinary public ID for profile image management"),
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        verbose_name=_("Email Address"),
        help_text=_("Public contact email (optional)"),
        validators=[EmailValidator()],
    )

    # Social media links
    twitter_handle = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Twitter Handle"),
        help_text=_("Twitter username without @ symbol"),
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9_]{1,50}$", message=_("Enter a valid Twitter handle")
            )
        ],
    )
    linkedin_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("LinkedIn URL"),
        help_text=_("Full LinkedIn profile URL"),
        validators=[URLValidator()],
    )
    website_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("Website URL"),
        help_text=_("Personal or professional website URL"),
        validators=[URLValidator()],
    )

    # Status and metadata
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this author can be assigned to new content"),
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured"),
        help_text=_("Whether this author should be featured on the team page"),
        db_index=True,
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Sort Order"),
        help_text=_("Order in which authors appear in lists"),
    )

    class Meta:
        verbose_name = _("Author")
        verbose_name_plural = _("Authors")
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["name"]),
            models.Index(fields=["sort_order"]),
        ]

    def __str__(self):
        return self.name

    def get_initials(self):
        """Get author initials for avatar display"""
        names = self.name.split()
        return "".join(name[0].upper() for name in names[:2] if name)

    def get_article_count(self):
        """Get count of published articles by this author"""
        return self.articles.filter(status="published").count()

    def clean(self):
        if self.twitter_handle and self.twitter_handle.startswith("@"):
            self.twitter_handle = self.twitter_handle[1:]  # Remove @ if present


class CloudinaryMedia(TimestampedModel):
    """
    Media files stored on Cloudinary.
    Handles images, videos, documents, and other file types.
    """

    FILE_TYPE_CHOICES = [
        ("image", _("Image")),
        ("video", _("Video")),
        ("document", _("Document")),
        ("audio", _("Audio")),
        ("archive", _("Archive")),
        ("other", _("Other")),
    ]

    title = models.CharField(
        max_length=300,
        verbose_name=_("Title"),
        help_text=_("Descriptive title for the media file"),
        validators=[MinLengthValidator(1), MaxLengthValidator(300)],
        db_index=True,  # Frequently searched
    )

    # Cloudinary-specific fields
    cloudinary_url = models.URLField(
        max_length=500,
        verbose_name=_("Cloudinary URL"),
        help_text=_("Full Cloudinary URL for the media file"),
        validators=[URLValidator()],
        db_index=True,  # Used for serving content
    )
    cloudinary_public_id = models.CharField(
        max_length=300,
        unique=True,
        verbose_name=_("Cloudinary Public ID"),
        help_text=_("Unique Cloudinary identifier for file operations"),
        db_index=True,  # Used for Cloudinary API calls
    )

    # File metadata
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        verbose_name=_("File Type"),
        help_text=_("Type of media file"),
        db_index=True,  # Frequently filtered
    )
    file_format = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_("File Format"),
        help_text=_("File extension/format (e.g., jpg, png, pdf)"),
    )
    file_size = models.PositiveBigIntegerField(
        verbose_name=_("File Size"),
        help_text=_("File size in bytes"),
        validators=[MinValueValidator(1)],
    )

    # Image-specific metadata
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Width"),
        help_text=_("Image width in pixels (for images only)"),
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Height"),
        help_text=_("Image height in pixels (for images only)"),
    )

    # Accessibility and SEO
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Alt Text"),
        help_text=_("Alternative text for accessibility and SEO"),
    )
    caption = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name=_("Caption"),
        help_text=_("Optional caption or description for the media"),
    )

    # Organization and metadata
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("Comma-separated tags for organization"),
    )

    # User tracking
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Uploaded By"),
        help_text=_("User who uploaded this media file"),
    )

    # Usage tracking
    usage_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Usage Count"),
        help_text=_("Number of times this media is referenced"),
    )

    class Meta:
        verbose_name = _("Media File")
        verbose_name_plural = _("Media Files")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["file_type", "-created_at"]),
            models.Index(fields=["cloudinary_public_id"]),
            models.Index(fields=["title"]),
            models.Index(fields=["-usage_count"]),
            models.Index(fields=["uploaded_by", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def file_size_formatted(self):
        """Return human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"

    def get_transformed_url(self, transformations):
        """Get Cloudinary URL with transformations applied"""
        if not self.cloudinary_public_id:
            return self.cloudinary_url

        # Basic implementation - you'd expand this based on your needs
        base_url = "https://res.cloudinary.com/your-cloud-name/image/upload/"
        return f"{base_url}{transformations}/{self.cloudinary_public_id}"

    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.save(update_fields=["usage_count"])


class Article(TimestampedModel):
    """
    Main article model for news, analysis, and other content.
    Supports rich content through related ContentSection model.
    """

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("review", _("Under Review")),
        ("scheduled", _("Scheduled")),
        ("published", _("Published")),
        ("archived", _("Archived")),
    ]

    # Core content fields
    title = models.CharField(
        max_length=300,
        verbose_name=_("Title"),
        help_text=_("Article headline (max 300 characters for SEO)"),
        validators=[MinLengthValidator(5), MaxLengthValidator(300)],
        db_index=True,  # Frequently searched and displayed
    )
    slug = models.SlugField(
        max_length=300,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly version of title (auto-generated if blank)"),
        db_index=True,  # Used in URLs
    )
    excerpt = models.TextField(
        max_length=500,
        verbose_name=_("Excerpt"),
        help_text=_("Brief article summary for listings and SEO (max 500 characters)"),
        validators=[MinLengthValidator(10), MaxLengthValidator(500)],
    )

    # Relationships
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name=_("Category"),
        help_text=_("Primary category for this article"),
        db_index=True,  # Frequently filtered
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name=_("Author"),
        help_text=_("Primary author of this article"),
        db_index=True,  # Frequently filtered
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="articles",
        verbose_name=_("Tags"),
        help_text=_("Tags for categorizing and cross-referencing"),
    )

    # Media
    featured_image = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="featured_articles",
        verbose_name=_("Featured Image"),
        help_text=_("Main image for the article (recommended: 1200x800px)"),
    )

    # Publishing fields
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name=_("Status"),
        help_text=_("Current publication status"),
        db_index=True,  # Frequently filtered
    )
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Published Date"),
        help_text=_("When this article was/will be published"),
        db_index=True,  # Used for ordering and filtering
    )
    scheduled_publish_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Scheduled Publish Date"),
        help_text=_("Automatic publication date (for scheduled articles)"),
    )

    # SEO and metadata
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name=_("Meta Title"),
        help_text=_("SEO title tag (max 60 chars, uses article title if blank)"),
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name=_("Meta Description"),
        help_text=_("SEO meta description (max 160 chars, uses excerpt if blank)"),
    )
    meta_keywords = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Meta Keywords"),
        help_text=_("Comma-separated SEO keywords (optional)"),
    )

    # Social sharing
    social_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Social Media Title"),
        help_text=_("Title for social media sharing (uses title if blank)"),
    )
    social_description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Social Media Description"),
        help_text=_("Description for social media sharing"),
    )

    # Analytics and engagement
    view_count = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_("View Count"),
        help_text=_("Number of times this article has been viewed"),
        db_index=True,  # Used for popular content queries
    )
    share_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Share Count"),
        help_text=_("Number of times this article has been shared"),
    )
    comment_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Comment Count"),
        help_text=_("Number of comments on this article"),
    )

    # Content flags
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured"),
        help_text=_("Whether this article should be featured prominently"),
        db_index=True,
    )
    is_breaking = models.BooleanField(
        default=False,
        verbose_name=_("Breaking News"),
        help_text=_("Mark as breaking news for special treatment"),
    )
    allow_comments = models.BooleanField(
        default=True,
        verbose_name=_("Allow Comments"),
        help_text=_("Whether comments are enabled for this article"),
    )

    # Editorial workflow
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_articles",
        verbose_name=_("Created By"),
        help_text=_("User who created this article"),
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="modified_articles",
        verbose_name=_("Last Modified By"),
        help_text=_("User who last modified this article"),
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_articles",
        verbose_name=_("Reviewed By"),
        help_text=_("User who reviewed this article"),
    )
    reviewed_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed Date"),
        help_text=_("When this article was last reviewed"),
    )

    class Meta:
        verbose_name = _("Article")
        verbose_name_plural = _("Articles")
        ordering = ["-published_date", "-created_at"]
        indexes = [
            # Primary filtering indexes
            models.Index(fields=["status", "-published_date"]),
            models.Index(fields=["category", "status", "-published_date"]),
            models.Index(fields=["author", "status", "-published_date"]),
            # Feature and popularity indexes
            models.Index(fields=["is_featured", "-published_date"]),
            models.Index(fields=["-view_count"]),
            models.Index(fields=["is_breaking", "-published_date"]),
            # Search and URL indexes
            models.Index(fields=["slug"]),
            models.Index(fields=["title"]),
            # Workflow indexes
            models.Index(fields=["status", "created_by"]),
            models.Index(fields=["scheduled_publish_date"]),
            # Combined indexes for common queries
            models.Index(fields=["status", "is_featured", "-published_date"]),
        ]
        constraints = [
            # Ensure published articles have published_date
            models.CheckConstraint(
                check=~models.Q(status="published", published_date__isnull=True),
                name="published_articles_have_date",
            ),
            # Ensure scheduled articles have scheduled date
            models.CheckConstraint(
                check=~models.Q(
                    status="scheduled", scheduled_publish_date__isnull=True
                ),
                name="scheduled_articles_have_date",
            ),
        ]

    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            self.slug = self._generate_unique_slug()

        # Auto-populate SEO fields if not provided
        if not self.meta_title:
            self.meta_title = self.title[:60]
        if not self.meta_description:
            self.meta_description = self.excerpt[:160]

        # Set published_date when status changes to published
        if self.status == "published" and not self.published_date:
            self.published_date = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article_detail", kwargs={"slug": self.slug})

    @property
    def is_published(self):
        return self.status == "published" and self.published_date <= timezone.now()

    @property
    def reading_time(self):
        """Estimate reading time based on content sections"""
        total_words = len(self.title.split()) + len(self.excerpt.split())

        for section in self.content_sections.all():
            if section.content:
                # Strip HTML and count words
                import re

                text = re.sub(r"<[^>]+>", "", section.content)
                total_words += len(text.split())

            if section.question:
                total_words += len(section.question.split())
            if section.answer:
                total_words += len(section.answer.split())

        # Assume 200 words per minute reading speed
        return max(1, total_words // 200)

    def _generate_unique_slug(self):
        """Generate a unique slug for this article"""
        base_slug = slugify(self.title)
        slug = base_slug
        counter = 1

        while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def increment_view_count(self):
        """Increment view count atomically"""
        Article.objects.filter(pk=self.pk).update(view_count=models.F("view_count") + 1)

    def get_related_articles(self, limit=3):
        """Get related articles based on category and tags"""
        related = (
            Article.objects.filter(status="published")
            .exclude(pk=self.pk)
            .select_related("category", "author", "featured_image")
        )

        # Prioritize same category
        same_category = related.filter(category=self.category)[:limit]

        if same_category.count() < limit:
            # Fill with articles that share tags
            tag_ids = self.tags.values_list("id", flat=True)
            tag_related = (
                related.filter(tags__in=tag_ids)
                .exclude(pk__in=same_category.values_list("pk", flat=True))
                .distinct()[: limit - same_category.count()]
            )

            return list(same_category) + list(tag_related)

        return same_category


class ContentSection(TimestampedModel):
    """
    Individual content sections within articles.
    Allows for rich, structured content with different section types.
    """

    SECTION_TYPE_CHOICES = [
        ("paragraph", _("Paragraph")),
        ("heading", _("Heading")),
        ("subheading", _("Subheading")),
        ("image", _("Image")),
        ("quote", _("Quote")),
        ("interview", _("Interview")),
        ("video", _("Video")),
        ("audio", _("Audio")),
        ("code", _("Code Block")),
        ("list", _("List")),
        ("table", _("Table")),
        ("embed", _("Embed")),
        ("divider", _("Divider")),
        ("callout", _("Callout")),
    ]

    # Core relationships
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="content_sections",
        verbose_name=_("Article"),
        help_text=_("Article this section belongs to"),
        db_index=True,  # Always queried with article
    )

    # Section metadata
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_TYPE_CHOICES,
        verbose_name=_("Section Type"),
        help_text=_("Type of content section"),
        db_index=True,  # Used for filtering and rendering
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Order"),
        help_text=_("Order of this section within the article"),
        db_index=True,  # Used for ordering
    )

    # Common content fields
    content = models.TextField(
        blank=True,
        verbose_name=_("Content"),
        help_text=_("Main content for this section (HTML allowed)"),
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Section Title"),
        help_text=_("Optional title for this section"),
    )

    # Media-specific fields
    media_file = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_sections",
        verbose_name=_("Media File"),
        help_text=_("Associated media file for this section"),
    )
    caption = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Caption"),
        help_text=_("Caption for media or section description"),
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Alt Text"),
        help_text=_("Alternative text for accessibility"),
    )

    # Interview-specific fields
    question = models.TextField(
        blank=True,
        verbose_name=_("Interview Question"),
        help_text=_("Question text for interview sections"),
    )
    answer = models.TextField(
        blank=True,
        verbose_name=_("Interview Answer"),
        help_text=_("Answer text for interview sections"),
    )
    interviewer = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Interviewer"),
        help_text=_("Name of the interviewer"),
    )
    interviewee = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Interviewee"),
        help_text=_("Name of the person being interviewed"),
    )

    # Structured data fields
    list_items = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("List Items"),
        help_text=_("Array of list items for list sections"),
    )
    table_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Table Data"),
        help_text=_("Table structure and data for table sections"),
    )
    embed_code = models.TextField(
        blank=True,
        verbose_name=_("Embed Code"),
        help_text=_("HTML embed code for external content"),
    )

    # Styling and layout
    css_classes = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("CSS Classes"),
        help_text=_("Additional CSS classes for custom styling"),
    )
    background_color = models.CharField(
        max_length=7,
        blank=True,
        verbose_name=_("Background Color"),
        help_text=_("Hex color code for section background"),
        validators=[
            RegexValidator(
                regex=r"^#[0-9a-fA-F]{6}$", message=_("Enter a valid hex color code")
            )
        ],
    )

    # Visibility and behavior
    is_visible = models.BooleanField(
        default=True,
        verbose_name=_("Is Visible"),
        help_text=_("Whether this section should be displayed"),
    )
    is_expandable = models.BooleanField(
        default=False,
        verbose_name=_("Is Expandable"),
        help_text=_("Whether this section can be collapsed/expanded"),
    )

    class Meta:
        verbose_name = _("Content Section")
        verbose_name_plural = _("Content Sections")
        ordering = ["article", "order"]
        indexes = [
            models.Index(fields=["article", "order"]),
            models.Index(fields=["article", "section_type"]),
            models.Index(fields=["section_type"]),
        ]
        constraints = [
            # Ensure unique ordering within article
            models.UniqueConstraint(
                fields=["article", "order"], name="unique_section_order_per_article"
            ),
        ]

    def __str__(self):
        return f"{self.article.title} - {self.get_section_type_display()} {self.order}"

    def clean(self):
        """Validate section data based on type"""
        if self.section_type == "interview":
            if not self.question or not self.answer:
                raise ValidationError(
                    _("Interview sections must have both question and answer")
                )

        elif self.section_type in ["image", "video", "audio"]:
            if not self.media_file:
                raise ValidationError(
                    _(f"{self.section_type.title()} sections must have a media file")
                )

        elif self.section_type in ["paragraph", "heading", "subheading"]:
            if not self.content:
                raise ValidationError(
                    _(f"{self.section_type.title()} sections must have content")
                )

        elif self.section_type == "list":
            if not self.list_items:
                raise ValidationError(_("List sections must have list items"))

        elif self.section_type == "table":
            if not self.table_data:
                raise ValidationError(_("Table sections must have table data"))

        elif self.section_type == "embed":
            if not self.embed_code:
                raise ValidationError(_("Embed sections must have embed code"))


class Event(TimestampedModel):
    """
    Events and community dialogues organized by CISD.
    Supports both virtual and in-person events.
    """

    EVENT_TYPE_CHOICES = [
        ("virtual", _("Virtual Event")),
        ("in_person", _("In-Person Event")),
        ("hybrid", _("Hybrid Event")),
        ("webinar", _("Webinar")),
        ("workshop", _("Workshop")),
        ("conference", _("Conference")),
        ("dialogue", _("Community Dialogue")),
        ("training", _("Training Session")),
    ]

    STATUS_CHOICES = [
        ("upcoming", _("Upcoming")),
        ("ongoing", _("Ongoing")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
        ("postponed", _("Postponed")),
    ]

    # Basic information
    title = models.CharField(
        max_length=300,
        verbose_name=_("Event Title"),
        help_text=_("Clear, descriptive title for the event"),
        validators=[MinLengthValidator(5), MaxLengthValidator(300)],
        db_index=True,
    )
    slug = models.SlugField(
        max_length=300,
        unique=True,
        blank=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly version of title"),
        db_index=True,
    )
    description = models.TextField(
        max_length=2000,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the event"),
        validators=[MinLengthValidator(20)],
    )
    short_description = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Short Description"),
        help_text=_("Brief description for listings"),
    )

    # Event categorization
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        verbose_name=_("Event Type"),
        help_text=_("Format/type of the event"),
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("Category"),
        help_text=_("Event category (optional)"),
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="events",
        verbose_name=_("Tags"),
        help_text=_("Tags for categorizing the event"),
    )

    # Date and time
    start_datetime = models.DateTimeField(
        verbose_name=_("Start Date & Time"),
        help_text=_("When the event begins"),
        db_index=True,
    )
    end_datetime = models.DateTimeField(
        verbose_name=_("End Date & Time"),
        help_text=_("When the event ends"),
        db_index=True,
    )
    timezone = models.CharField(
        max_length=50,
        default="Africa/Lagos",
        verbose_name=_("Timezone"),
        help_text=_("Event timezone"),
    )

    # Location information
    venue_name = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_("Venue Name"),
        help_text=_("Name of the venue (for in-person events)"),
    )
    venue_address = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_("Venue Address"),
        help_text=_("Full address of the venue"),
    )
    online_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_("Online URL"),
        help_text=_("Link for virtual participation"),
        validators=[URLValidator()],
    )

    # Media and content
    featured_image = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="featured_events",
        verbose_name=_("Featured Image"),
        help_text=_("Main image for the event"),
    )
    agenda = models.TextField(
        blank=True, verbose_name=_("Agenda"), help_text=_("Detailed agenda or schedule")
    )

    # People
    speakers = models.ManyToManyField(
        Author,
        blank=True,
        related_name="speaking_events",
        verbose_name=_("Speakers"),
        help_text=_("Event speakers and facilitators"),
    )
    organizer = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
        verbose_name=_("Organizer"),
        help_text=_("Primary event organizer"),
    )

    # Registration and capacity
    registration_required = models.BooleanField(
        default=False,
        verbose_name=_("Registration Required"),
        help_text=_("Whether attendees must register"),
    )
    registration_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_("Registration URL"),
        help_text=_("External registration link"),
        validators=[URLValidator()],
    )
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Registration Deadline"),
        help_text=_("Last date for registration"),
    )
    max_attendees = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Maximum Attendees"),
        help_text=_("Maximum number of attendees (if limited)"),
    )
    current_attendees = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Current Attendees"),
        help_text=_("Number of registered attendees"),
    )

    # Status and visibility
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="upcoming",
        verbose_name=_("Status"),
        help_text=_("Current status of the event"),
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured"),
        help_text=_("Whether this event should be featured"),
        db_index=True,
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_("Is Public"),
        help_text=_("Whether this event is publicly visible"),
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_events",
        verbose_name=_("Created By"),
    )

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["status", "start_datetime"]),
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["is_featured", "start_datetime"]),
            models.Index(fields=["is_public", "status", "start_datetime"]),
            models.Index(fields=["slug"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_datetime__gt=models.F("start_datetime")),
                name="event_end_after_start",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()

        if not self.short_description:
            self.short_description = self.description[:500]

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def _generate_unique_slug(self):
        """Generate unique slug for the event"""
        base_slug = slugify(self.title)
        slug = base_slug
        counter = 1

        while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @property
    def is_upcoming(self):
        return self.start_datetime > timezone.now()

    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime

    @property
    def is_past(self):
        return self.end_datetime < timezone.now()

    @property
    def registration_open(self):
        if not self.registration_required:
            return False
        if self.registration_deadline and timezone.now() > self.registration_deadline:
            return False
        if self.max_attendees and self.current_attendees >= self.max_attendees:
            return False
        return self.status == "upcoming"


class Newsletter(TimestampedModel):
    """
    Newsletter campaigns sent to subscribers.
    Tracks engagement metrics and delivery status.
    """

    title = models.CharField(
        max_length=300,
        verbose_name=_("Newsletter Title"),
        help_text=_("Internal title for the newsletter"),
        validators=[MinLengthValidator(5), MaxLengthValidator(300)],
    )
    subject = models.CharField(
        max_length=200,
        verbose_name=_("Email Subject"),
        help_text=_("Subject line for the email"),
        validators=[MinLengthValidator(5), MaxLengthValidator(200)],
    )
    content = models.TextField(
        verbose_name=_("Content"), help_text=_("Newsletter content (HTML allowed)")
    )

    # Sending status
    is_sent = models.BooleanField(
        default=False,
        verbose_name=_("Is Sent"),
        help_text=_("Whether this newsletter has been sent"),
        db_index=True,
    )
    sent_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent Date"),
        help_text=_("When this newsletter was sent"),
        db_index=True,
    )
    scheduled_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Scheduled Date"),
        help_text=_("When this newsletter is scheduled to be sent"),
    )

    # Analytics
    total_sent = models.PositiveIntegerField(
        default=0, verbose_name=_("Total Sent"), help_text=_("Number of emails sent")
    )
    open_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Open Count"), help_text=_("Number of opens tracked")
    )
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Click Count"),
        help_text=_("Number of clicks tracked"),
    )
    bounce_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Bounce Count"),
        help_text=_("Number of bounced emails"),
    )
    unsubscribe_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Unsubscribe Count"),
        help_text=_("Number of unsubscribes from this newsletter"),
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_newsletters",
        verbose_name=_("Created By"),
    )

    class Meta:
        verbose_name = _("Newsletter")
        verbose_name_plural = _("Newsletters")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_sent", "-sent_date"]),
            models.Index(fields=["scheduled_date"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def open_rate(self):
        if self.total_sent > 0:
            return round((self.open_count / self.total_sent) * 100, 2)
        return 0

    @property
    def click_rate(self):
        if self.total_sent > 0:
            return round((self.click_count / self.total_sent) * 100, 2)
        return 0

    @property
    def bounce_rate(self):
        if self.total_sent > 0:
            return round((self.bounce_count / self.total_sent) * 100, 2)
        return 0


class Subscriber(TimestampedModel):
    """
    Newsletter subscribers with preference management.
    Supports GDPR compliance and subscription management.
    """

    email = models.EmailField(
        max_length=254,
        unique=True,
        verbose_name=_("Email Address"),
        help_text=_("Subscriber's email address"),
        validators=[EmailValidator()],
        db_index=True,  # Primary lookup field
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("First Name"),
        help_text=_("Subscriber's first name"),
        validators=[MaxLengthValidator(100)],
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Last Name"),
        help_text=_("Subscriber's last name"),
        validators=[MaxLengthValidator(100)],
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Location"),
        help_text=_("Subscriber's location (city, state, country)"),
    )
    zip_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Zip Code"),
        help_text=_("Subscriber's postal/zip code"),
    )

    # Subscription preferences
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="subscribers",
        verbose_name=_("Interested Categories"),
        help_text=_("Content categories of interest"),
    )
    frequency = models.CharField(
        max_length=20,
        choices=[
            ("weekly", _("Weekly")),
            ("monthly", _("Monthly")),
            ("breaking", _("Breaking News Only")),
        ],
        default="weekly",
        verbose_name=_("Email Frequency"),
        help_text=_("How often to receive newsletters"),
    )

    # Status and compliance
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether subscription is active"),
        db_index=True,
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Confirmed At"),
        help_text=_("When email was confirmed (double opt-in)"),
        db_index=True,
    )
    unsubscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Unsubscribed At"),
        help_text=_("When subscriber opted out"),
        db_index=True,
    )

    # Tracking
    source = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Source"),
        help_text=_("How the subscriber was acquired"),
    )
    last_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Sent"),
        help_text=_("When last newsletter was sent to this subscriber"),
    )

    class Meta:
        verbose_name = _("Newsletter Subscriber")
        verbose_name_plural = _("Newsletter Subscribers")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "confirmed_at"]),
            models.Index(fields=["email"]),
            models.Index(fields=["location"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["frequency", "is_active"]),
        ]

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name} ({self.email})"
        return self.email

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.email.split("@")[0]  # Fallback to email username

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None

    @property
    def is_unsubscribed(self):
        return self.unsubscribed_at is not None


class SiteSettings(TimestampedModel):
    """
    Global site settings and configuration.
    Singleton model - only one instance should exist.
    """

    # Basic site information
    site_name = models.CharField(
        max_length=200,
        default="Centre for Inclusive Social Development",
        verbose_name=_("Site Name"),
        help_text=_("Name of the organization/site"),
    )
    site_tagline = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_("Site Tagline"),
        help_text=_("Brief tagline or motto"),
    )
    site_description = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name=_("Site Description"),
        help_text=_("Description of the organization and its mission"),
    )

    # Visual branding
    logo = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_logos",
        verbose_name=_("Logo"),
        help_text=_("Main site logo"),
    )
    favicon = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_favicons",
        verbose_name=_("Favicon"),
        help_text=_("Site favicon (32x32px)"),
    )

    # Contact information
    email = models.EmailField(
        max_length=254,
        blank=True,
        verbose_name=_("Contact Email"),
        help_text=_("Main contact email address"),
        validators=[EmailValidator()],
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Phone Number"),
        help_text=_("Main contact phone number"),
    )
    address = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_("Address"),
        help_text=_("Physical address"),
    )

    # Social media links
    facebook_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("Facebook URL"),
        validators=[URLValidator()],
    )
    twitter_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("Twitter URL"),
        validators=[URLValidator()],
    )
    linkedin_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("LinkedIn URL"),
        validators=[URLValidator()],
    )
    youtube_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("YouTube URL"),
        validators=[URLValidator()],
    )
    instagram_url = models.URLField(
        max_length=300,
        blank=True,
        verbose_name=_("Instagram URL"),
        validators=[URLValidator()],
    )

    # SEO defaults
    default_meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name=_("Default Meta Title"),
        help_text=_("Default title for SEO (max 60 characters)"),
    )
    default_meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name=_("Default Meta Description"),
        help_text=_("Default description for SEO (max 160 characters)"),
    )
    default_og_image = models.ForeignKey(
        CloudinaryMedia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_og_images",
        verbose_name=_("Default Social Media Image"),
        help_text=_("Default image for social media sharing (1200x630px)"),
    )

    # Analytics and tracking
    google_analytics_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Google Analytics ID"),
        help_text=_("Google Analytics measurement ID (e.g., G-XXXXXXXXXX)"),
    )
    google_tag_manager_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Google Tag Manager ID"),
        help_text=_("Google Tag Manager container ID"),
    )

    # Feature flags
    enable_comments = models.BooleanField(
        default=True,
        verbose_name=_("Enable Comments"),
        help_text=_("Whether comments are enabled site-wide"),
    )
    enable_newsletter = models.BooleanField(
        default=True,
        verbose_name=_("Enable Newsletter"),
        help_text=_("Whether newsletter signup is enabled"),
    )
    maintenance_mode = models.BooleanField(
        default=False,
        verbose_name=_("Maintenance Mode"),
        help_text=_("Put site in maintenance mode"),
    )

    class Meta:
        verbose_name = _("Site Settings")
        verbose_name_plural = _("Site Settings")

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SiteSettings.objects.exists():
            raise ValidationError(_("Only one SiteSettings instance is allowed"))

        # Auto-populate meta fields if empty
        if not self.default_meta_title and self.site_name:
            self.default_meta_title = self.site_name[:60]

        if not self.default_meta_description and self.site_description:
            self.default_meta_description = self.site_description[:160]

        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get the site settings instance (create if doesn't exist)"""
        settings, created = cls.objects.get_or_create(
            defaults={"site_name": "Centre for Inclusive Social Development"}
        )
        return settings
