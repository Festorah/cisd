from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

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
from .utils.cloudinary_utils import CloudinaryManager


class ArticleForm(forms.ModelForm):
    """Form for creating and editing articles"""

    class Meta:
        model = Article
        fields = [
            "title",
            "excerpt",
            "category",
            "author",
            "tags",
            "featured_image",
            "status",
            "published_date",
            "scheduled_publish_date",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "social_title",
            "social_description",
            "is_featured",
            "is_breaking",
            "allow_comments",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Enter article title",
                    "maxlength": 300,
                }
            ),
            "excerpt": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 3,
                    "placeholder": "Brief description of the article (max 500 characters)",
                    "maxlength": 500,
                }
            ),
            "category": forms.Select(attrs={"class": "form-select-custom"}),
            "author": forms.Select(attrs={"class": "form-select-custom"}),
            "tags": forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
            "featured_image": forms.Select(attrs={"class": "form-select-custom"}),
            "status": forms.Select(attrs={"class": "form-select-custom"}),
            "published_date": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
            "scheduled_publish_date": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
            "meta_title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "SEO title (max 60 characters)",
                    "maxlength": 60,
                }
            ),
            "meta_description": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "SEO description (max 160 characters)",
                    "maxlength": 160,
                }
            ),
            "meta_keywords": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Comma-separated keywords",
                }
            ),
            "social_title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Social media title (max 100 characters)",
                    "maxlength": 100,
                }
            ),
            "social_description": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Social media description (max 200 characters)",
                    "maxlength": 200,
                }
            ),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_breaking": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "allow_comments": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter active categories and authors
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True
        ).order_by("sort_order")
        self.fields["author"].queryset = Author.objects.filter(is_active=True).order_by(
            "name"
        )
        self.fields["featured_image"].queryset = CloudinaryMedia.objects.filter(
            file_type="image"
        ).order_by("-created_at")
        self.fields["tags"].queryset = Tag.objects.all().order_by("name")

        # Make fields optional
        self.fields["published_date"].required = False
        self.fields["scheduled_publish_date"].required = False
        self.fields["featured_image"].required = False

        # Add empty option for featured image
        self.fields["featured_image"].empty_label = "No featured image"

        # Add help text
        self.fields["meta_title"].help_text = "Leave blank to use article title"
        self.fields["meta_description"].help_text = "Leave blank to use excerpt"
        self.fields["social_title"].help_text = "Leave blank to use article title"
        self.fields["social_description"].help_text = "Leave blank to use excerpt"
        self.fields["scheduled_publish_date"].help_text = (
            "Set future date for automatic publishing"
        )

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        published_date = cleaned_data.get("published_date")
        scheduled_publish_date = cleaned_data.get("scheduled_publish_date")

        # Validation for published articles
        if status == "published" and not published_date:
            from django.utils import timezone

            cleaned_data["published_date"] = timezone.now()

        # Validation for scheduled articles
        if status == "scheduled":
            if not scheduled_publish_date:
                raise ValidationError(
                    _("Scheduled articles must have a scheduled publish date")
                )

            from django.utils import timezone

            if scheduled_publish_date <= timezone.now():
                raise ValidationError(_("Scheduled publish date must be in the future"))

        return cleaned_data


class ContentSectionForm(forms.ModelForm):
    """Form for individual content sections"""

    class Meta:
        model = ContentSection
        fields = [
            "section_type",
            "title",
            "content",
            "media_file",
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
        ]
        widgets = {
            "section_type": forms.Select(
                attrs={
                    "class": "form-select-custom",
                    "onchange": "toggleSectionFields(this)",
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Section title (optional)",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control-custom rich-editor",
                    "rows": 4,
                    "placeholder": "Section content",
                }
            ),
            "media_file": forms.Select(attrs={"class": "form-select-custom"}),
            "caption": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Media caption",
                    "maxlength": 500,
                }
            ),
            "alt_text": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Alt text for accessibility",
                    "maxlength": 255,
                }
            ),
            "question": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Interview question",
                }
            ),
            "answer": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 3,
                    "placeholder": "Interview answer",
                }
            ),
            "interviewer": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Interviewer name",
                }
            ),
            "interviewee": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Interviewee name",
                }
            ),
            "embed_code": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 3,
                    "placeholder": "HTML embed code",
                }
            ),
            "css_classes": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "CSS classes (optional)",
                }
            ),
            "background_color": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "#ffffff",
                    "type": "color",
                }
            ),
            "is_visible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_expandable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["media_file"].queryset = CloudinaryMedia.objects.all().order_by(
            "-created_at"
        )
        self.fields["media_file"].required = False
        self.fields["media_file"].empty_label = "No media file"


# Create formset for content sections
ContentSectionFormSet = inlineformset_factory(
    Article,
    ContentSection,
    form=ContentSectionForm,
    extra=1,
    can_delete=True,
    can_order=True,
)


class EventForm(forms.ModelForm):
    """Form for creating and editing events"""

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "short_description",
            "event_type",
            "category",
            "tags",
            "start_datetime",
            "end_datetime",
            "timezone",
            "venue_name",
            "venue_address",
            "online_url",
            "featured_image",
            "agenda",
            "speakers",
            "organizer",
            "registration_required",
            "registration_url",
            "registration_deadline",
            "max_attendees",
            "status",
            "is_featured",
            "is_public",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Event title",
                    "maxlength": 300,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 4,
                    "placeholder": "Detailed event description",
                }
            ),
            "short_description": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 2,
                    "placeholder": "Brief description for listings",
                    "maxlength": 500,
                }
            ),
            "event_type": forms.Select(attrs={"class": "form-select-custom"}),
            "category": forms.Select(attrs={"class": "form-select-custom"}),
            "tags": forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
            "start_datetime": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
            "end_datetime": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
            "timezone": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "Africa/Lagos"}
            ),
            "venue_name": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "Venue name"}
            ),
            "venue_address": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 2,
                    "placeholder": "Venue address",
                }
            ),
            "online_url": forms.URLInput(
                attrs={"class": "form-control-custom", "placeholder": "https://..."}
            ),
            "featured_image": forms.Select(attrs={"class": "form-select-custom"}),
            "agenda": forms.Textarea(
                attrs={
                    "class": "form-control-custom rich-editor",
                    "rows": 6,
                    "placeholder": "Event agenda or schedule",
                }
            ),
            "speakers": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
            "organizer": forms.Select(attrs={"class": "form-select-custom"}),
            "registration_url": forms.URLInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Registration URL",
                }
            ),
            "registration_deadline": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
            "max_attendees": forms.NumberInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Maximum attendees",
                    "min": 1,
                }
            ),
            "status": forms.Select(attrs={"class": "form-select-custom"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set querysets
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["featured_image"].queryset = CloudinaryMedia.objects.filter(
            file_type="image"
        )
        self.fields["speakers"].queryset = Author.objects.filter(is_active=True)
        self.fields["organizer"].queryset = Author.objects.filter(is_active=True)
        self.fields["tags"].queryset = Tag.objects.all()

        # Make fields optional
        self.fields["category"].required = False
        self.fields["short_description"].required = False
        self.fields["venue_name"].required = False
        self.fields["venue_address"].required = False
        self.fields["online_url"].required = False
        self.fields["featured_image"].required = False
        self.fields["organizer"].required = False
        self.fields["registration_url"].required = False
        self.fields["registration_deadline"].required = False
        self.fields["max_attendees"].required = False

        # Add empty labels
        self.fields["category"].empty_label = "No category"
        self.fields["featured_image"].empty_label = "No featured image"
        self.fields["organizer"].empty_label = "No organizer"

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get("start_datetime")
        end_datetime = cleaned_data.get("end_datetime")
        event_type = cleaned_data.get("event_type")
        venue_name = cleaned_data.get("venue_name")
        online_url = cleaned_data.get("online_url")
        registration_required = cleaned_data.get("registration_required")
        registration_deadline = cleaned_data.get("registration_deadline")

        # Validate date range
        if start_datetime and end_datetime:
            if end_datetime <= start_datetime:
                raise ValidationError(_("End date must be after start date"))

        # Validate location requirements
        if event_type == "in_person" and not venue_name:
            raise ValidationError(_("In-person events must have a venue name"))

        if event_type in ["virtual", "hybrid"] and not online_url:
            raise ValidationError(
                _("Virtual and hybrid events must have an online URL")
            )

        # Validate registration deadline
        if registration_required and registration_deadline:
            if start_datetime and registration_deadline >= start_datetime:
                raise ValidationError(
                    _("Registration deadline must be before event start")
                )

        return cleaned_data


class NewsletterForm(forms.ModelForm):
    """Form for creating newsletters"""

    class Meta:
        model = Newsletter
        fields = ["title", "subject", "content", "scheduled_date"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Newsletter title",
                    "maxlength": 300,
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Email subject line",
                    "maxlength": 200,
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control-custom rich-editor",
                    "rows": 10,
                    "placeholder": "Newsletter content",
                }
            ),
            "scheduled_date": forms.DateTimeInput(
                attrs={"class": "form-control-custom", "type": "datetime-local"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_date"].required = False
        self.fields["scheduled_date"].help_text = "Leave blank to send immediately"


class SubscriberForm(forms.ModelForm):
    """Form for newsletter subscription"""

    class Meta:
        model = Subscriber
        fields = [
            "email",
            "first_name",
            "last_name",
            "location",
            "zip_code",
            "categories",
            "frequency",
        ]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Email address",
                    "required": True,
                }
            ),
            "first_name": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "First name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "Last name"}
            ),
            "location": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "Location"}
            ),
            "zip_code": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "Zip code"}
            ),
            "categories": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
            "frequency": forms.Select(attrs={"class": "form-select-custom"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categories"].queryset = Category.objects.filter(is_active=True)
        self.fields["categories"].required = False


class CloudinaryMediaUploadForm(forms.ModelForm):
    """Form for uploading media files to Cloudinary"""

    file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                "class": "form-control-custom",
                "accept": "image/*,video/*,audio/*,.pdf,.doc,.docx",
            }
        ),
        help_text="Select a file to upload to Cloudinary",
    )
    folder = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control-custom",
                "placeholder": "Upload folder (optional)",
            }
        ),
        help_text="Cloudinary folder path (e.g., cisd/articles)",
    )

    class Meta:
        model = CloudinaryMedia
        fields = ["title", "alt_text", "caption", "tags"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control-custom", "placeholder": "File title"}
            ),
            "alt_text": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Alt text for accessibility",
                }
            ),
            "caption": forms.Textarea(
                attrs={
                    "class": "form-control-custom",
                    "rows": 2,
                    "placeholder": "File caption",
                }
            ),
            "tags": forms.TextInput(
                attrs={
                    "class": "form-control-custom",
                    "placeholder": "Comma-separated tags",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False  # Will be auto-generated from filename

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            # Validate using CloudinaryManager
            CloudinaryManager.validate_file(file)
        return file

    def save(self, commit=True, user=None):
        """Handle file upload to Cloudinary and create media record"""
        file_obj = self.cleaned_data["file"]
        title = self.cleaned_data.get("title") or file_obj.name
        folder = self.cleaned_data.get("folder")
        tags = self.cleaned_data.get("tags")

        # Upload to Cloudinary
        upload_result = CloudinaryManager.upload_file(
            file_obj=file_obj, folder=folder, tags=tags.split(",") if tags else None
        )

        if not upload_result["success"]:
            raise ValidationError(f"Upload failed: {upload_result['error']}")

        # Create CloudinaryMedia instance
        file_type, file_format = CloudinaryManager.determine_file_type(file_obj)

        instance = CloudinaryMedia(
            title=title,
            cloudinary_url=upload_result["url"],
            cloudinary_public_id=upload_result["public_id"],
            file_type=file_type,
            file_format=file_format,
            file_size=upload_result["bytes"],
            width=upload_result.get("width"),
            height=upload_result.get("height"),
            alt_text=self.cleaned_data.get("alt_text", ""),
            caption=self.cleaned_data.get("caption", ""),
            tags=tags or "",
            uploaded_by=user,
        )

        if commit:
            instance.save()

        return instance


# Quick edit and utility forms
class QuickEditForm(forms.Form):
    """Form for quick inline editing"""

    field_name = forms.CharField(max_length=50)
    field_value = forms.CharField(widget=forms.Textarea(attrs={"rows": 1}))
    article_id = forms.UUIDField()

    def clean_field_name(self):
        field_name = self.cleaned_data["field_name"]
        allowed_fields = ["title", "excerpt", "status", "is_featured", "is_breaking"]
        if field_name not in allowed_fields:
            raise ValidationError("Field not allowed for quick edit")
        return field_name


class BulkActionForm(forms.Form):
    """Form for bulk actions on articles"""

    ACTION_CHOICES = [
        ("publish", "Publish"),
        ("unpublish", "Unpublish"),
        ("archive", "Archive"),
        ("delete", "Delete"),
    ]

    articles = forms.ModelMultipleChoiceField(
        queryset=Article.objects.all(), widget=forms.CheckboxSelectMultiple
    )
    action = forms.ChoiceField(choices=ACTION_CHOICES)

    def clean(self):
        cleaned_data = super().clean()
        articles = cleaned_data.get("articles")
        action = cleaned_data.get("action")

        if not articles:
            raise ValidationError("Please select at least one article")

        # Additional validation based on action
        if action == "delete":
            # Prevent deletion of published articles without confirmation
            published_articles = articles.filter(status="published")
            if published_articles.exists():
                raise ValidationError(
                    "Cannot delete published articles. Please unpublish them first."
                )

        return cleaned_data


# Search and filter forms
class ArticleSearchForm(forms.Form):
    """Form for searching and filtering articles"""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control-custom", "placeholder": "Search articles..."}
        ),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={"class": "form-select-custom"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Status")] + Article.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select-custom"}),
    )
    author = forms.ModelChoiceField(
        queryset=Author.objects.filter(is_active=True),
        required=False,
        empty_label="All Authors",
        widget=forms.Select(attrs={"class": "form-select-custom"}),
    )
    tag = forms.ModelChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        empty_label="All Tags",
        widget=forms.Select(attrs={"class": "form-select-custom"}),
    )


class SiteSettingsForm(forms.ModelForm):
    """Form for site settings"""

    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "site_tagline",
            "site_description",
            "logo",
            "favicon",
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
            "google_analytics_id",
            "google_tag_manager_id",
            "enable_comments",
            "enable_newsletter",
            "maintenance_mode",
        ]
        widgets = {
            "site_name": forms.TextInput(
                attrs={"class": "form-control-custom", "maxlength": 200}
            ),
            "site_tagline": forms.TextInput(
                attrs={"class": "form-control-custom", "maxlength": 300}
            ),
            "site_description": forms.Textarea(
                attrs={"class": "form-control-custom", "rows": 3, "maxlength": 1000}
            ),
            "logo": forms.Select(attrs={"class": "form-select-custom"}),
            "favicon": forms.Select(attrs={"class": "form-select-custom"}),
            "email": forms.EmailInput(attrs={"class": "form-control-custom"}),
            "phone": forms.TextInput(attrs={"class": "form-control-custom"}),
            "address": forms.Textarea(
                attrs={"class": "form-control-custom", "rows": 3}
            ),
            "facebook_url": forms.URLInput(attrs={"class": "form-control-custom"}),
            "twitter_url": forms.URLInput(attrs={"class": "form-control-custom"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control-custom"}),
            "youtube_url": forms.URLInput(attrs={"class": "form-control-custom"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control-custom"}),
            "default_meta_title": forms.TextInput(
                attrs={"class": "form-control-custom", "maxlength": 60}
            ),
            "default_meta_description": forms.TextInput(
                attrs={"class": "form-control-custom", "maxlength": 160}
            ),
            "default_og_image": forms.Select(attrs={"class": "form-select-custom"}),
            "google_analytics_id": forms.TextInput(
                attrs={"class": "form-control-custom"}
            ),
            "google_tag_manager_id": forms.TextInput(
                attrs={"class": "form-control-custom"}
            ),
            "enable_comments": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "enable_newsletter": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "maintenance_mode": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter media files
        self.fields["logo"].queryset = CloudinaryMedia.objects.filter(file_type="image")
        self.fields["favicon"].queryset = CloudinaryMedia.objects.filter(
            file_type="image"
        )
        self.fields["default_og_image"].queryset = CloudinaryMedia.objects.filter(
            file_type="image"
        )

        # Make fields optional
        self.fields["logo"].required = False
        self.fields["favicon"].required = False
        self.fields["default_og_image"].required = False

        # Add empty labels
        self.fields["logo"].empty_label = "No logo"
        self.fields["favicon"].empty_label = "No favicon"
        self.fields["default_og_image"].empty_label = "No default image"
