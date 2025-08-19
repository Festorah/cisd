import json
import logging

from core.forms import ArticleForm, ContentSectionFormSet

# Import from core app
from core.models import (
    Article,
    Author,
    Category,
    CloudinaryMedia,
    ContentSection,
    Event,
    Newsletter,
    Subscriber,
    Tag,
)
from core.serializers import MediaUploadSerializer
from core.utils.cloudinary_utils import CloudinaryManager
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView

# Import dashboard utilities
from .managers import ArticleManager, DashboardStatsManager
from .utils.file_processors import ContentGenerator, FileProcessor
from .utils.media_optimizer import MediaOptimizer

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """Check if user has admin privileges"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to require admin access"""

    def test_func(self):
        return is_admin_user(self.request.user)


class DashboardHomeView(AdminRequiredMixin, ListView):
    """Dashboard homepage with real statistics"""

    template_name = "dashboard/home.html"
    context_object_name = "recent_articles"
    paginate_by = 10

    def get_queryset(self):
        return ArticleManager.get_optimized_articles_list()[:10]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get real dashboard statistics
        stats = DashboardStatsManager.get_overview_stats()
        recent_activity = DashboardStatsManager.get_recent_activity()
        popular_content = DashboardStatsManager.get_popular_content()

        context.update(
            {
                "stats": stats,
                "recent_activity": recent_activity,
                "popular_content": popular_content,
                "pending_reviews": Article.objects.filter(status="review")[:5],
                "scheduled_posts": Article.objects.filter(status="scheduled").order_by(
                    "scheduled_publish_date"
                )[:5],
            }
        )

        return context


class ArticleCreateView(AdminRequiredMixin, CreateView):
    """Create new article with enhanced functionality"""

    model = Article
    form_class = ArticleForm
    template_name = "dashboard/article_create.html"
    success_url = reverse_lazy("dashboard:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "formset": (
                    ContentSectionFormSet() if self.request.method == "GET" else None
                ),
                "categories": Category.objects.filter(is_active=True),
                "authors": Author.objects.filter(is_active=True),
                "tags": Tag.objects.all().order_by("name"),
                "recent_media": CloudinaryMedia.objects.order_by("-created_at")[:20],
                "default_structure": ContentGenerator.get_default_structure(),
            }
        )

        return context

    def form_valid(self, form):
        """Handle form submission with content sections"""
        formset = ContentSectionFormSet(self.request.POST, instance=form.instance)

        if formset.is_valid():
            with transaction.atomic():
                form.instance.created_by = self.request.user
                form.instance.last_modified_by = self.request.user
                article = form.save()

                formset.instance = article
                formset.save()

                messages.success(
                    self.request, f'Article "{article.title}" created successfully!'
                )

            return redirect(self.success_url)
        else:
            return self.form_invalid(form)


@login_required
@user_passes_test(is_admin_user)
def article_editor_view(request, article_id=None):
    """Enhanced article editor with real-time functionality"""

    article = None
    if article_id:
        article = get_object_or_404(Article, id=article_id)

    context = {
        "article": article,
        "categories": Category.objects.filter(is_active=True),
        "authors": Author.objects.filter(is_active=True),
        "tags": Tag.objects.all().order_by("name"),
        "recent_media": CloudinaryMedia.objects.order_by("-created_at")[:50],
        "default_structure": ContentGenerator.get_default_structure(),
    }

    return render(request, "dashboard/article_editor.html", context)


@csrf_exempt
@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def save_article_ajax(request):
    """Save article via AJAX with proper validation"""

    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ["title", "excerpt", "category_id", "author_id"]
        for field in required_fields:
            if not data.get(field):
                return JsonResponse(
                    {
                        "success": False,
                        "error": f'{field.replace("_", " ").title()} is required',
                    },
                    status=400,
                )

        # Clean and validate data
        article_data = {
            "title": data["title"].strip()[:300],
            "excerpt": data["excerpt"].strip()[:500],
            "category_id": data["category_id"],
            "author_id": data["author_id"],
            "featured_image_id": data.get("featured_image_id"),
            "status": data.get("status", "draft"),
            "meta_title": data.get("meta_title", "")[:60],
            "meta_description": data.get("meta_description", "")[:160],
            "tag_ids": data.get("tag_ids", []),
        }

        sections_data = data.get("content_sections", [])

        # Create or update article
        article_id = data.get("article_id")
        if article_id:
            article = get_object_or_404(Article, id=article_id)
            # Update existing article
            for key, value in article_data.items():
                if key != "tag_ids":
                    setattr(article, key, value)
            article.last_modified_by = request.user
            article.save()

            if article_data["tag_ids"]:
                article.tags.set(article_data["tag_ids"])
        else:
            # Create new article
            article = ArticleManager.create_article_with_sections(
                article_data, sections_data, request.user
            )

        return JsonResponse(
            {
                "success": True,
                "article_id": str(article.id),
                "message": "Article saved successfully",
                "url": f"/dashboard/article/{article.id}/edit/",
            }
        )

    except Exception as e:
        logger.error(f"Error saving article: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while saving the article"},
            status=500,
        )


@csrf_exempt
@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def upload_file_ajax(request):
    """Handle file upload and processing"""

    try:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return JsonResponse(
                {"success": False, "error": "No file uploaded"}, status=400
            )

        # Process file based on type
        file_extension = uploaded_file.name.split(".")[-1].lower()

        if file_extension in ["pdf", "doc", "docx", "txt"]:
            # Process document and extract content
            processed_file = FileProcessor.process_file(uploaded_file)

            if processed_file["success"]:
                # Generate article structure
                article_data = ContentGenerator.generate_article_from_file(
                    processed_file
                )

                return JsonResponse(
                    {
                        "success": True,
                        "file_type": "document",
                        "article_data": article_data,
                        "message": "File processed successfully",
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "error": processed_file["error"]}, status=400
                )

        else:
            # Handle media file upload
            media = MediaOptimizer.upload_and_optimize(uploaded_file, request.user)

            return JsonResponse(
                {
                    "success": True,
                    "file_type": "media",
                    "media": {
                        "id": str(media.id),
                        "title": media.title,
                        "url": media.cloudinary_url,
                        "file_type": media.file_type,
                        "file_size": media.file_size_formatted,
                    },
                    "message": "Media uploaded successfully",
                }
            )

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@user_passes_test(is_admin_user)
def media_library_view(request):
    """Media library with pagination and search"""

    media_list = CloudinaryMedia.objects.select_related("uploaded_by").order_by(
        "-created_at"
    )

    # Apply filters
    file_type = request.GET.get("type")
    if file_type:
        media_list = media_list.filter(file_type=file_type)

    search = request.GET.get("search")
    if search:
        media_list = media_list.filter(title__icontains=search)

    paginator = Paginator(media_list, 24)  # 24 items per page
    page_number = request.GET.get("page")
    media_page = paginator.get_page(page_number)

    context = {
        "media_page": media_page,
        "file_types": CloudinaryMedia.objects.values_list(
            "file_type", flat=True
        ).distinct(),
        "current_filters": {
            "type": file_type,
            "search": search,
        },
    }

    return render(request, "dashboard/media_library.html", context)


@csrf_exempt
@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["DELETE"])
def delete_media_ajax(request, media_id):
    """Delete media file"""

    try:
        media = get_object_or_404(CloudinaryMedia, id=media_id)

        # Delete from Cloudinary
        from core.utils.cloudinary_utils import CloudinaryManager

        delete_result = CloudinaryManager.delete_file(
            media.cloudinary_public_id,
            resource_type="image" if media.file_type == "image" else "raw",
        )

        if delete_result["success"]:
            media.delete()
            return JsonResponse(
                {"success": True, "message": "Media deleted successfully"}
            )
        else:
            return JsonResponse(
                {"success": False, "error": "Failed to delete from Cloudinary"},
                status=500,
            )

    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# API endpoints for real-time features
@csrf_exempt
@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["GET"])
def get_dashboard_stats_ajax(request):
    """Get dashboard statistics via AJAX"""

    try:
        stats = DashboardStatsManager.get_overview_stats()
        return JsonResponse({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def upload_file_view(request):
    try:
        # Validate file upload
        if "file" not in request.FILES:
            return JsonResponse(
                {"success": False, "error": "No file provided"}, status=400
            )

        file_obj = request.FILES["file"]
        title = request.POST.get("title", file_obj.name.split(".")[0])

        # Use the serializer for validation and processing
        serializer = MediaUploadSerializer(
            data={
                "file": file_obj,
                "title": title,
                "alt_text": request.POST.get("alt_text", ""),
                "caption": request.POST.get("caption", ""),
                "tags": request.POST.get("tags", ""),
                "folder": request.POST.get("folder", "cisd/uploads"),
            },
            context={"request": request},
        )

        if serializer.is_valid():
            media = serializer.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "File uploaded successfully",
                    "media_id": str(media.id),
                    "cloudinary_url": media.cloudinary_url,
                    "file_type": media.file_type,
                    "file_size": media.file_size_formatted,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Validation failed",
                    "details": serializer.errors,
                },
                status=400,
            )

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Upload failed: {str(e)}"}, status=500
        )


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_media_view(request, media_id):
    try:
        media = CloudinaryMedia.objects.get(id=media_id)

        # Check permissions (optional)
        if request.user != media.uploaded_by and not request.user.is_staff:
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        # Delete from Cloudinary
        delete_result = CloudinaryManager.delete_file(
            media.cloudinary_public_id,
            "raw" if media.file_type == "document" else media.file_type,
        )

        # Delete from database
        media.delete()

        return JsonResponse(
            {"success": True, "message": "Media file deleted successfully"}
        )

    except CloudinaryMedia.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Media file not found"}, status=404
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Delete failed: {str(e)}"}, status=500
        )


@login_required
def articles_list_view(request):
    """Display all articles with filtering and pagination"""
    articles = Article.objects.select_related(
        "category", "author", "featured_image"
    ).order_by("-updated_at")

    # Apply filters
    search = request.GET.get("search")
    if search:
        articles = articles.filter(
            Q(title__icontains=search)
            | Q(excerpt__icontains=search)
            | Q(author__name__icontains=search)
        )

    status = request.GET.get("status")
    if status:
        articles = articles.filter(status=status)

    category = request.GET.get("category")
    if category:
        articles = articles.filter(category_id=category)

    author = request.GET.get("author")
    if author:
        articles = articles.filter(author_id=author)

    # Pagination
    paginator = Paginator(articles, 20)  # 20 articles per page
    page_number = request.GET.get("page")
    articles_page = paginator.get_page(page_number)

    # Get filter options
    categories = Category.objects.filter(is_active=True).order_by(
        "sort_order", "display_name"
    )
    authors = Author.objects.filter(is_active=True).order_by("name")

    context = {
        "articles": articles_page,
        "categories": categories,
        "authors": authors,
    }

    return render(request, "dashboard/articles_list.html", context)


@login_required
def article_edit_view(request, article_id):
    """Edit an existing article with properly loaded content"""
    article = get_object_or_404(Article, id=article_id)

    # Get content sections ordered properly
    content_sections = article.content_sections.all().order_by("order")

    # Serialize content sections for JavaScript with proper handling of None values
    sections_data = []
    for section in content_sections:
        section_data = {
            "id": str(section.id) if section.id else "",
            "type": section.section_type or "paragraph",
            "content": section.content or "",
            "title": section.title or "",
            "order": section.order if section.order is not None else 0,
            "media_file_id": str(section.media_file.id) if section.media_file else "",
            "caption": section.caption or "",
            "alt_text": section.alt_text or "",
            "question": section.question or "",
            "answer": section.answer or "",
            "interviewer": section.interviewer or "",
            "interviewee": section.interviewee or "",
            # Add other fields that might be needed
            "attribution": getattr(section, "attribution", "") or "",  # For quotes
        }
        sections_data.append(section_data)

    # Get dropdown options
    categories = Category.objects.filter(is_active=True).order_by(
        "sort_order", "display_name"
    )
    authors = Author.objects.filter(is_active=True).order_by("name")
    recent_media = CloudinaryMedia.objects.order_by("-created_at")[:50]

    # Prepare article data for JavaScript with proper None handling
    article_data = {
        "id": str(article.id),
        "title": article.title or "",
        "excerpt": article.excerpt or "",
        "category_id": str(article.category.id) if article.category else "",
        "author_id": str(article.author.id) if article.author else "",
        "featured_image_id": (
            str(article.featured_image.id) if article.featured_image else ""
        ),
        "status": article.status or "draft",
        "published_date": (
            article.published_date.isoformat() if article.published_date else ""
        ),
        "content_sections": sections_data,
        # Additional fields for completeness
        "meta_title": article.meta_title or "",
        "meta_description": article.meta_description or "",
        "social_title": article.social_title or "",
        "social_description": article.social_description or "",
        "is_featured": article.is_featured,
        "is_breaking": article.is_breaking,
        "allow_comments": article.allow_comments,
    }

    context = {
        "article": article,
        "article_data_json": json.dumps(article_data),  # Properly serialized data
        "categories": categories,
        "authors": authors,
        "recent_media": recent_media,
    }

    return render(request, "dashboard/article_edit.html", context)


# Bulk operations view
@login_required
@require_http_methods(["POST"])
def bulk_articles_view(request):
    """Handle bulk operations on articles"""
    try:
        data = json.loads(request.body)
        article_ids = data.get("article_ids", [])
        action = data.get("action")

        if not article_ids or not action:
            return JsonResponse(
                {"success": False, "error": "Missing article IDs or action"}, status=400
            )

        articles = Article.objects.filter(id__in=article_ids)

        if action == "publish":
            articles.update(status="published", published_date=timezone.now())
        elif action == "draft":
            articles.update(status="draft")
        elif action == "archive":
            articles.update(status="archived")
        elif action == "delete":
            articles.delete()
        else:
            return JsonResponse(
                {"success": False, "error": "Invalid action"}, status=400
            )

        return JsonResponse(
            {
                "success": True,
                "message": f"Successfully {action}ed {len(article_ids)} article(s)",
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def save_article_view(request):
    """Save or update an article with content sections"""
    try:
        data = json.loads(request.body)

        article_id = data.get("id")
        title = data.get("title", "").strip()
        excerpt = data.get("excerpt", "").strip()
        category_id = data.get("category_id")
        author_id = data.get("author_id")
        featured_image_id = data.get("featured_image_id")
        status = data.get("status", "draft")
        content_sections = data.get("content_sections", [])

        # Basic validation
        if not title:
            return JsonResponse(
                {"success": False, "error": "Article title is required"}, status=400
            )

        # Get or create article
        if article_id:
            try:
                article = Article.objects.get(id=article_id)
                message = "Article updated successfully"
            except Article.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Article not found"}, status=404
                )
        else:
            article = Article(created_by=request.user)
            message = "Article created successfully"

        # Update article fields
        article.title = title
        article.excerpt = excerpt
        article.status = status
        article.last_modified_by = request.user

        # Set foreign key relationships
        if category_id:
            try:
                article.category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        if author_id:
            try:
                article.author = Author.objects.get(id=author_id)
            except Author.DoesNotExist:
                pass

        if featured_image_id:
            try:
                article.featured_image = CloudinaryMedia.objects.get(
                    id=featured_image_id
                )
            except CloudinaryMedia.DoesNotExist:
                article.featured_image = None

        # Set published date if publishing
        if status == "published" and not article.published_date:
            article.published_date = timezone.now()

        # Save article
        article.save()

        # Update content sections
        if content_sections:
            # Delete existing sections for this article
            ContentSection.objects.filter(article=article).delete()

            # Create new sections
            for index, section_data in enumerate(content_sections):
                section = ContentSection(
                    article=article,
                    section_type=section_data.get("type", "paragraph"),
                    order=index,
                    content=section_data.get("content", ""),
                    title=section_data.get("title", ""),
                    caption=section_data.get("caption", ""),
                    alt_text=section_data.get("alt_text", ""),
                    question=section_data.get("question", ""),
                    answer=section_data.get("answer", ""),
                    interviewer=section_data.get("interviewer", ""),
                    interviewee=section_data.get("interviewee", ""),
                )

                # Handle media file relationship
                media_file_id = section_data.get("media_file_id")
                if media_file_id:
                    try:
                        section.media_file = CloudinaryMedia.objects.get(
                            id=media_file_id
                        )
                    except CloudinaryMedia.DoesNotExist:
                        pass

                section.save()

        return JsonResponse(
            {
                "success": True,
                "message": message,
                "article_id": str(article.id),
                "status": article.status,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Failed to save article: {str(e)}"}, status=500
        )


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_article_view(request, article_id):
    """Delete a single article"""
    try:
        article = get_object_or_404(Article, id=article_id)

        # Check permissions (optional - you might want only authors or admins to delete)
        if not request.user.is_staff and article.created_by != request.user:
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        article_title = article.title
        article.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f'Article "{article_title}" deleted successfully',
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Article not found"}, status=404
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Failed to delete article: {str(e)}"},
            status=500,
        )


@login_required
@require_http_methods(["POST"])
def toggle_featured_view(request, article_id):
    """Toggle the featured status of an article"""
    try:
        data = json.loads(request.body)
        is_featured = data.get("is_featured", False)

        article = get_object_or_404(Article, id=article_id)
        article.is_featured = is_featured
        article.last_modified_by = request.user
        article.save(update_fields=["is_featured", "updated_at", "last_modified_by"])

        status_text = "featured" if is_featured else "removed from featured"

        return JsonResponse(
            {
                "success": True,
                "message": f'Article "{article.title}" {status_text}',
                "is_featured": article.is_featured,
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Article not found"}, status=404
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Failed to update article: {str(e)}"},
            status=500,
        )


@login_required
@require_http_methods(["POST"])
def duplicate_article_view(request, article_id):
    """Create a duplicate copy of an article"""
    try:
        original_article = get_object_or_404(Article, id=article_id)

        # Create new article with copied data
        new_article = Article(
            title=f"{original_article.title} (Copy)",
            excerpt=original_article.excerpt,
            category=original_article.category,
            author=original_article.author,
            featured_image=original_article.featured_image,
            status="draft",  # Always create as draft
            meta_title=original_article.meta_title,
            meta_description=original_article.meta_description,
            meta_keywords=original_article.meta_keywords,
            social_title=original_article.social_title,
            social_description=original_article.social_description,
            allow_comments=original_article.allow_comments,
            created_by=request.user,
            last_modified_by=request.user,
        )
        new_article.save()

        # Copy tags
        new_article.tags.set(original_article.tags.all())

        # Copy content sections
        original_sections = original_article.content_sections.all().order_by("order")
        for section in original_sections:
            ContentSection.objects.create(
                article=new_article,
                section_type=section.section_type,
                order=section.order,
                content=section.content,
                title=section.title,
                media_file=section.media_file,
                caption=section.caption,
                alt_text=section.alt_text,
                question=section.question,
                answer=section.answer,
                interviewer=section.interviewer,
                interviewee=section.interviewee,
                list_items=section.list_items,
                table_data=section.table_data,
                embed_code=section.embed_code,
                css_classes=section.css_classes,
                background_color=section.background_color,
                is_visible=section.is_visible,
                is_expandable=section.is_expandable,
            )

        return JsonResponse(
            {
                "success": True,
                "message": f"Article duplicated successfully",
                "new_article_id": str(new_article.id),
                "new_article_title": new_article.title,
            }
        )

    except Article.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Original article not found"}, status=404
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Failed to duplicate article: {str(e)}"},
            status=500,
        )


@login_required
@require_http_methods(["GET"])
def dashboard_stats_view(request):
    """Get dashboard statistics for the home page"""
    try:
        from datetime import datetime, timedelta

        from django.db.models import Count, Q

        # Article statistics
        total_articles = Article.objects.count()
        published_articles = Article.objects.filter(status="published").count()
        draft_articles = Article.objects.filter(status="draft").count()
        review_articles = Article.objects.filter(status="review").count()

        # This month's articles
        this_month = datetime.now().replace(day=1)
        articles_this_month = Article.objects.filter(created_at__gte=this_month).count()

        # Media statistics
        total_media = CloudinaryMedia.objects.count()

        # User/subscriber statistics (you might not have these models yet)
        total_subscribers = 0  # Update when you add newsletter functionality
        new_subscribers = 0

        # View statistics (you might want to implement view tracking)
        total_views = sum(article.view_count for article in Article.objects.all())

        stats = {
            "articles": {
                "total": total_articles,
                "published": published_articles,
                "draft": draft_articles,
                "review": review_articles,
                "this_month": articles_this_month,
            },
            "content": {"total_views": total_views},
            "users": {
                "total_subscribers": total_subscribers,
                "new_subscribers": new_subscribers,
            },
            "media": {"total_files": total_media},
            "events": {"upcoming": 0},  # Update when you add events functionality
        }

        return JsonResponse({"success": True, "stats": stats})

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Failed to get stats: {str(e)}"}, status=500
        )
