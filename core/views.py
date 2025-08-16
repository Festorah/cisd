import json
import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import models, transaction
from django.db.models import F, Prefetch, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .forms import ArticleForm, ContentSectionFormSet
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
from .serializers import (
    ArticleDetailSerializer,
    ArticleSerializer,
    ArticleSummarySerializer,
    AuthorSerializer,
    BulkArticleUpdateSerializer,
    CategorySerializer,
    CloudinaryMediaSerializer,
    ContentSectionSerializer,
    DashboardStatsSerializer,
    EventSerializer,
    MediaUploadSerializer,
    NewsletterSerializer,
    SubscriberSerializer,
    TagSerializer,
)
from .utils.cloudinary_utils import CloudinaryManager
from .utils.model_utils import optimize_database_queries

logger = logging.getLogger(__name__)


# Helper function to check if user is admin
def is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# Public Frontend Views
class HomePageView(ListView):
    """Homepage with featured articles and recent content"""

    model = Article
    template_name = "core/home.html"
    context_object_name = "featured_articles"

    def get_queryset(self):
        return optimize_database_queries().get_featured_articles(limit=3)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get recent articles if not enough featured
        featured_count = context["featured_articles"].count()
        if featured_count < 3:
            recent_articles = (
                optimize_database_queries()
                .get_published_articles()
                .exclude(
                    id__in=context["featured_articles"].values_list("id", flat=True)
                )[: 3 - featured_count]
            )
            context["recent_articles"] = recent_articles

        context.update(
            {
                "recent_events": Event.objects.filter(
                    status="upcoming",
                    is_public=True,
                    start_datetime__gte=timezone.now(),
                )
                .select_related("organizer", "featured_image")
                .prefetch_related("speakers")[:3],
                "site_settings": SiteSettings.get_settings(),
                "popular_tags": Tag.objects.filter(is_featured=True).order_by(
                    "-usage_count"
                )[:5],
            }
        )
        return context


class ArticleListView(ListView):
    """Enhanced News & Analysis listing page with search, filtering, and sorting"""

    model = Article
    template_name = "core/list_articles.html"
    context_object_name = "articles"
    paginate_by = 10

    def get_queryset(self):
        queryset = optimize_database_queries().get_published_articles()

        # Search functionality
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(excerpt__icontains=search_query)
                | Q(content_sections__content__icontains=search_query)
                | Q(tags__name__icontains=search_query)
                | Q(author__name__icontains=search_query)
            ).distinct()

        # Category filter
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category__name=category)

        # Tag filter
        tag = self.request.GET.get("tag")
        if tag:
            queryset = queryset.filter(tags__slug=tag)

        # Status filter (for admin users)
        if is_admin_user(self.request.user):
            status_filter = self.request.GET.get("status")
            if status_filter:
                queryset = (
                    Article.objects.filter(status=status_filter)
                    .select_related("category", "author", "featured_image")
                    .prefetch_related("tags")
                )

        # If no filters are applied, exclude the featured articles that will be shown in the hero/featured section
        if not any([search_query, category, tag]):
            # Get featured article IDs to exclude from main results
            featured_ids = Article.objects.filter(
                status="published", is_featured=True
            ).values_list("id", flat=True)[:4]

            if featured_ids:
                queryset = queryset.exclude(id__in=featured_ids)

        # Sorting functionality
        sort_by = self.request.GET.get("sort", "newest")
        if sort_by == "newest":
            queryset = queryset.order_by("-published_date", "-created_at")
        elif sort_by == "oldest":
            queryset = queryset.order_by("published_date", "created_at")
        elif sort_by == "popular":
            queryset = queryset.order_by("-view_count", "-published_date")
        elif sort_by == "title":
            queryset = queryset.order_by("title")
        elif sort_by == "updated":
            queryset = queryset.order_by("-updated_at")
        else:
            queryset = queryset.order_by("-published_date", "-created_at")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter options
        context.update(
            {
                "categories": Category.objects.filter(is_active=True).order_by(
                    "sort_order", "display_name"
                ),
                "popular_tags": Tag.objects.filter(is_featured=True).order_by(
                    "-usage_count", "name"
                )[
                    :15
                ],  # Limit to top 15 tags for UI
                "search_query": self.request.GET.get("search", ""),
                "selected_category": self.request.GET.get("category", ""),
                "selected_tag": self.request.GET.get("tag", ""),
                "selected_status": self.request.GET.get("status", ""),
                "selected_sort": self.request.GET.get("sort", "newest"),
                "is_admin": is_admin_user(self.request.user),
            }
        )

        # Get total results count for display
        total_queryset = optimize_database_queries().get_published_articles()

        # Apply the same filters to get accurate count
        if context["search_query"]:
            total_queryset = total_queryset.filter(
                Q(title__icontains=context["search_query"])
                | Q(excerpt__icontains=context["search_query"])
                | Q(content_sections__content__icontains=context["search_query"])
                | Q(tags__name__icontains=context["search_query"])
                | Q(author__name__icontains=context["search_query"])
            ).distinct()

        if context["selected_category"]:
            total_queryset = total_queryset.filter(
                category__name=context["selected_category"]
            )

        if context["selected_tag"]:
            total_queryset = total_queryset.filter(tags__slug=context["selected_tag"])

        # Exclude featured articles if no filters
        if not any(
            [
                context["search_query"],
                context["selected_category"],
                context["selected_tag"],
            ]
        ):
            featured_ids = Article.objects.filter(
                status="published", is_featured=True
            ).values_list("id", flat=True)[:4]

            if featured_ids:
                total_queryset = total_queryset.exclude(id__in=featured_ids)

        context["total_results"] = total_queryset.count()

        # Get featured articles for hero and featured sections
        if not any(
            [
                context["search_query"],
                context["selected_category"],
                context["selected_tag"],
            ]
        ):
            # Get featured articles for the hero section and featured section
            featured_articles = (
                Article.objects.filter(status="published", is_featured=True)
                .select_related("category", "author", "featured_image")
                .order_by("-published_date")[:4]
            )

            # If we don't have enough featured articles, get recent ones
            if featured_articles.count() < 4:
                recent_articles = (
                    Article.objects.filter(status="published")
                    .exclude(id__in=featured_articles.values_list("id", flat=True))
                    .select_related("category", "author", "featured_image")
                    .order_by("-published_date")[: 4 - featured_articles.count()]
                )

                context["featured_articles"] = list(featured_articles) + list(
                    recent_articles
                )
            else:
                context["featured_articles"] = featured_articles
        else:
            # When filtering, don't show featured articles section
            context["featured_articles"] = []

        # Add active filters summary for display
        active_filters = []
        if context["search_query"]:
            active_filters.append(f'Search: "{context["search_query"]}"')
        if context["selected_category"]:
            category_obj = Category.objects.filter(
                name=context["selected_category"]
            ).first()
            if category_obj:
                active_filters.append(f"Category: {category_obj.display_name}")
        if context["selected_tag"]:
            tag_obj = Tag.objects.filter(slug=context["selected_tag"]).first()
            if tag_obj:
                active_filters.append(f"Topic: {tag_obj.name}")

        context["active_filters"] = active_filters
        context["has_filters"] = len(active_filters) > 0

        # Add sorting options for the template
        context["sort_options"] = [
            ("newest", "Newest First"),
            ("oldest", "Oldest First"),
            ("popular", "Most Popular"),
            ("title", "Title A-Z"),
            ("updated", "Recently Updated"),
        ]

        # Add pagination info
        if context.get("is_paginated"):
            page_obj = context["page_obj"]
            # Calculate showing range
            start_index = (page_obj.number - 1) * self.paginate_by + 1
            end_index = min(
                page_obj.number * self.paginate_by, page_obj.paginator.count
            )
            context["showing_start"] = start_index
            context["showing_end"] = end_index
            context["total_count"] = page_obj.paginator.count

        # Add reading time calculation for all articles
        for article in context["articles"]:
            if not hasattr(article, "_reading_time_calculated"):
                # This will trigger the property calculation
                _ = article.reading_time
                article._reading_time_calculated = True

        return context


class ArticleDetailView(DetailView):
    """Individual article detail page"""

    model = Article
    template_name = "core/news_details.html"
    context_object_name = "article"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        queryset = Article.objects.select_related(
            "category", "author", "featured_image", "created_by", "last_modified_by"
        ).prefetch_related(
            "tags",
            Prefetch(
                "content_sections",
                queryset=ContentSection.objects.select_related("media_file")
                .filter(is_visible=True)
                .order_by("order"),
            ),
        )

        # Allow admin users to see all articles
        if is_admin_user(self.request.user):
            return queryset
        else:
            return queryset.filter(status="published")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get content sections for the article
        content_sections = self.object.content_sections.filter(
            is_visible=True
        ).order_by("order")

        # Get related articles
        related_articles = self.object.get_related_articles(limit=6)

        # Additional context for the template
        context.update(
            {
                "content_sections": content_sections,
                "related_articles": related_articles,
                "is_admin": is_admin_user(self.request.user),
                "site_settings": SiteSettings.get_settings(),
                "reading_time": self.object.reading_time,
                "page_title": self.object.meta_title or self.object.title,
                "page_description": self.object.meta_description or self.object.excerpt,
            }
        )

        # Increment view count (atomic operation) for non-admin users
        if not is_admin_user(self.request.user):
            self.object.increment_view_count()

        return context


# Admin Dashboard Views
@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin_user), name="dispatch")
class AdminDashboardView(ListView):
    """Main admin dashboard"""

    model = Article
    template_name = "home.html"
    context_object_name = "recent_articles"

    def get_queryset(self):
        return Article.objects.select_related("category", "author").order_by(
            "-updated_at"
        )[:10]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Dashboard statistics
        stats = {
            "total_articles": Article.objects.count(),
            "published_articles": Article.objects.filter(status="published").count(),
            "draft_articles": Article.objects.filter(status="draft").count(),
            "review_articles": Article.objects.filter(status="review").count(),
            "total_subscribers": Subscriber.objects.filter(is_active=True).count(),
            "upcoming_events": Event.objects.filter(
                status="upcoming", start_datetime__gte=timezone.now()
            ).count(),
            "total_media_files": CloudinaryMedia.objects.count(),
            "page_views_total": Article.objects.aggregate(
                total=models.Sum("view_count")
            )["total"]
            or 0,
        }

        context.update(
            {
                "stats": stats,
                "recent_media": CloudinaryMedia.objects.select_related("uploaded_by")[
                    :5
                ],
                "pending_reviews": Article.objects.filter(status="review")[:5],
                "scheduled_posts": Article.objects.filter(
                    status="scheduled", scheduled_publish_date__gte=timezone.now()
                )[:5],
            }
        )

        return context


# API Views for Admin Interface
class ArticleViewSet(viewsets.ModelViewSet):
    """API viewset for article management"""

    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Article.objects.select_related(
            "category", "author", "featured_image"
        ).prefetch_related("tags")

        # Apply filters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        category_filter = self.request.query_params.get("category")
        if category_filter:
            queryset = queryset.filter(category__name=category_filter)

        author_filter = self.request.query_params.get("author")
        if author_filter:
            queryset = queryset.filter(author__id=author_filter)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(excerpt__icontains=search)
            )

        return queryset.order_by("-updated_at")

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return ArticleDetailSerializer
        return ArticleSerializer

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user, last_modified_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(last_modified_by=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish an article"""
        article = self.get_object()
        article.status = "published"
        if not article.published_date:
            article.published_date = timezone.now()
        article.last_modified_by = request.user
        article.save()

        logger.info(f"Article '{article.title}' published by {request.user.username}")
        return Response(
            {"status": "published", "published_date": article.published_date}
        )

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        """Unpublish an article"""
        article = self.get_object()
        article.status = "draft"
        article.last_modified_by = request.user
        article.save()

        logger.info(f"Article '{article.title}' unpublished by {request.user.username}")
        return Response({"status": "unpublished"})

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplicate an article"""
        original = self.get_object()

        # Create duplicate
        duplicate = Article.objects.create(
            title=f"{original.title} (Copy)",
            excerpt=original.excerpt,
            category=original.category,
            author=original.author,
            featured_image=original.featured_image,
            status="draft",
            meta_title=original.meta_title,
            meta_description=original.meta_description,
            created_by=request.user,
            last_modified_by=request.user,
        )

        # Copy tags
        duplicate.tags.set(original.tags.all())

        # Copy content sections
        for section in original.content_sections.all():
            ContentSection.objects.create(
                article=duplicate,
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
            )

        serializer = self.get_serializer(duplicate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContentSectionViewSet(viewsets.ModelViewSet):
    """API viewset for content section management"""

    queryset = ContentSection.objects.all()
    serializer_class = ContentSectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        article_id = self.request.query_params.get("article_id")
        if article_id:
            return self.queryset.filter(article_id=article_id).order_by("order")
        return self.queryset

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Reorder content sections"""
        section_orders = request.data.get("sections", [])

        updated_count = 0
        for item in section_orders:
            try:
                section = ContentSection.objects.get(id=item["id"])
                section.order = item["order"]
                section.save(update_fields=["order"])
                updated_count += 1
            except (ContentSection.DoesNotExist, KeyError):
                continue

        return Response(
            {
                "success": True,
                "updated_count": updated_count,
                "message": f"Updated order for {updated_count} sections",
            }
        )

    @action(detail=True, methods=["post"])
    def move_up(self, request, pk=None):
        """Move section up in order"""
        section = self.get_object()
        previous_section = (
            ContentSection.objects.filter(
                article=section.article, order__lt=section.order
            )
            .order_by("-order")
            .first()
        )

        if previous_section:
            # Swap orders
            section.order, previous_section.order = (
                previous_section.order,
                section.order,
            )
            section.save(update_fields=["order"])
            previous_section.save(update_fields=["order"])
            return Response({"success": True})

        return Response({"success": False, "message": "Already at top"})

    @action(detail=True, methods=["post"])
    def move_down(self, request, pk=None):
        """Move section down in order"""
        section = self.get_object()
        next_section = (
            ContentSection.objects.filter(
                article=section.article, order__gt=section.order
            )
            .order_by("order")
            .first()
        )

        if next_section:
            # Swap orders
            section.order, next_section.order = next_section.order, section.order
            section.save(update_fields=["order"])
            next_section.save(update_fields=["order"])
            return Response({"success": True})

        return Response({"success": False, "message": "Already at bottom"})


class CloudinaryMediaViewSet(viewsets.ModelViewSet):
    """API viewset for media file management"""

    queryset = CloudinaryMedia.objects.all()
    serializer_class = CloudinaryMediaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset.select_related("uploaded_by")

        # Filter by file type
        file_type = self.request.query_params.get("file_type")
        if file_type:
            queryset = queryset.filter(file_type=file_type)

        # Search
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(tags__icontains=search)
                | Q(caption__icontains=search)
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Delete media file from both database and Cloudinary"""
        media = self.get_object()

        # Delete from Cloudinary
        delete_result = CloudinaryManager.delete_file(
            media.cloudinary_public_id,
            resource_type="image" if media.file_type == "image" else "raw",
        )

        if delete_result["success"]:
            # Delete from database
            media.delete()
            logger.info(
                f"Deleted media file: {media.title} ({media.cloudinary_public_id})"
            )
            return Response({"success": True, "message": "File deleted successfully"})
        else:
            logger.error(f"Failed to delete from Cloudinary: {delete_result['error']}")
            return Response(
                {"success": False, "error": "Failed to delete from Cloudinary"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def upload(self, request):
        """Handle file upload to Cloudinary"""
        serializer = MediaUploadSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            try:
                media = serializer.save()
                response_serializer = CloudinaryMediaSerializer(media)
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
            except Exception as e:
                logger.error(f"Upload failed: {str(e)}")
                return Response(
                    {"error": f"Upload failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def upload_multiple(self, request):
        """Handle multiple file uploads"""
        files = request.FILES.getlist("files")
        uploaded_files = []
        errors = []

        for file in files:
            try:
                serializer = MediaUploadSerializer(
                    data={"file": file}, context={"request": request}
                )

                if serializer.is_valid():
                    media = serializer.save()
                    uploaded_files.append(CloudinaryMediaSerializer(media).data)
                else:
                    errors.append(f"{file.name}: {serializer.errors}")

            except Exception as e:
                errors.append(f"{file.name}: {str(e)}")

        return Response(
            {
                "uploaded": uploaded_files,
                "errors": errors,
                "success_count": len(uploaded_files),
                "error_count": len(errors),
            }
        )


# Event ViewSet
class EventViewSet(viewsets.ModelViewSet):
    """API viewset for event management"""

    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset.select_related(
            "category", "organizer", "featured_image"
        ).prefetch_related("speakers", "tags")

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by upcoming/past
        time_filter = self.request.query_params.get("time")
        if time_filter == "upcoming":
            queryset = queryset.filter(start_datetime__gt=timezone.now())
        elif time_filter == "past":
            queryset = queryset.filter(end_datetime__lt=timezone.now())

        return queryset.order_by("start_datetime")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# API endpoints for specific functionality
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_article_content(request):
    """Save article content including sections"""
    try:
        data = request.data
        article_id = data.get("article_id")

        if article_id:
            article = get_object_or_404(Article, id=article_id)
            serializer = ArticleDetailSerializer(article, data=data, partial=True)
        else:
            # Create new article
            serializer = ArticleDetailSerializer(data=data)

        if serializer.is_valid():
            article = serializer.save(
                created_by=request.user if not article_id else article.created_by,
                last_modified_by=request.user,
            )

            # Handle content sections if provided
            if "content_sections" in data:
                # Clear existing sections
                article.content_sections.all().delete()

                # Create new sections
                for i, section_data in enumerate(data["content_sections"]):
                    ContentSection.objects.create(
                        article=article,
                        section_type=section_data.get("type"),
                        order=i,
                        content=section_data.get("content", ""),
                        title=section_data.get("title", ""),
                        question=section_data.get("question", ""),
                        answer=section_data.get("answer", ""),
                        caption=section_data.get("caption", ""),
                        media_file_id=(
                            section_data.get("media_file_id")
                            if section_data.get("media_file_id")
                            else None
                        ),
                    )

            logger.info(f"Article saved: {article.title} by {request.user.username}")

            return Response(
                {
                    "success": True,
                    "article_id": str(article.id),
                    "message": "Article saved successfully",
                    "article": ArticleDetailSerializer(article).data,
                }
            )

        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(f"Error saving article: {str(e)}")
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_article_action(request):
    """Handle bulk operations on articles"""
    serializer = BulkArticleUpdateSerializer(data=request.data)

    if serializer.is_valid():
        article_ids = serializer.validated_data["article_ids"]
        action = serializer.validated_data["action"]

        articles = Article.objects.filter(id__in=article_ids)

        if action == "publish":
            articles.update(
                status="published",
                published_date=timezone.now(),
                last_modified_by=request.user,
            )
            message = f"Published {articles.count()} articles"

        elif action == "unpublish":
            articles.update(status="draft", last_modified_by=request.user)
            message = f"Unpublished {articles.count()} articles"

        elif action == "archive":
            articles.update(status="archived", last_modified_by=request.user)
            message = f"Archived {articles.count()} articles"

        elif action == "delete":
            count = articles.count()
            articles.delete()
            message = f"Deleted {count} articles"

        logger.info(
            f"Bulk action '{action}' performed on {len(article_ids)} articles by {request.user.username}"
        )

        return Response(
            {"success": True, "message": message, "affected_count": len(article_ids)}
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])  # This is the key fix!
@csrf_exempt
def subscribe_newsletter(request):
    """Handle newsletter subscriptions"""
    try:
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"success": False, "error": "Email is required"}, status=400
            )

        # Simple validation
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        try:
            validate_email(email)
        except ValidationError:
            return Response({"success": False, "error": "Invalid email"}, status=400)

        # Create subscriber
        subscriber, created = Subscriber.objects.get_or_create(
            email=email,
            defaults={
                "first_name": request.data.get("first_name", "")[:100],
                "last_name": request.data.get("last_name", "")[:100],
                "zip_code": request.data.get("zip_code", "")[:20],
                "frequency": "weekly",
                "is_active": True,
                "confirmed_at": timezone.now(),
                "source": "website",
            },
        )

        message = "Successfully subscribed!" if created else "Already subscribed!"
        return Response({"success": True, "message": message})

    except Exception as e:
        return Response({"success": False, "error": "Something went wrong"}, status=500)


@login_required
@user_passes_test(is_admin_user)
def article_create_view(request):
    """Create new article form view"""
    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES)
        formset = ContentSectionFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            article = form.save(commit=False)
            article.created_by = request.user
            article.last_modified_by = request.user
            article.save()
            form.save_m2m()  # Save many-to-many relationships

            formset.instance = article
            formset.save()

            messages.success(
                request, f'Article "{article.title}" created successfully!'
            )
            return HttpResponseRedirect(reverse_lazy("admin_dashboard"))
    else:
        form = ArticleForm()
        formset = ContentSectionFormSet()

    return render(
        request,
        "admin/article_form.html",
        {
            "form": form,
            "formset": formset,
            "title": "Create New Article",
            "media_files": CloudinaryMedia.objects.order_by("-created_at")[:20],
        },
    )


@login_required
@user_passes_test(is_admin_user)
def article_edit_view(request, article_id):
    """Edit existing article form view"""
    article = get_object_or_404(Article, id=article_id)

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        formset = ContentSectionFormSet(request.POST, instance=article)

        if form.is_valid() and formset.is_valid():
            article = form.save(commit=False)
            article.last_modified_by = request.user
            article.save()
            form.save_m2m()

            formset.save()

            messages.success(
                request, f'Article "{article.title}" updated successfully!'
            )
            return HttpResponseRedirect(reverse_lazy("admin_dashboard"))
    else:
        form = ArticleForm(instance=article)
        formset = ContentSectionFormSet(instance=article)

    return render(
        request,
        "admin/article_form.html",
        {
            "form": form,
            "formset": formset,
            "article": article,
            "title": f"Edit: {article.title}",
            "media_files": CloudinaryMedia.objects.order_by("-created_at")[:20],
        },
    )


# AJAX endpoints for real-time features
@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
@require_http_methods(["POST"])
def update_article_field(request):
    """Update a single article field via AJAX with proper validation"""
    try:
        data = json.loads(request.body)
        article_id = data.get("article_id")
        field_name = data.get("field")
        field_value = data.get("value")

        if not all([article_id, field_name]):
            return JsonResponse(
                {"success": False, "error": "Missing required fields"}, status=400
            )

        article = get_object_or_404(Article, id=article_id)

        # Security check - only allow certain fields
        allowed_fields = {
            "title": {"max_length": 300, "required": True},
            "excerpt": {"max_length": 500, "required": True},
            "status": {"choices": [choice[0] for choice in Article.STATUS_CHOICES]},
            "is_featured": {"type": "boolean"},
            "is_breaking": {"type": "boolean"},
            "meta_title": {"max_length": 60},
            "meta_description": {"max_length": 160},
            "social_title": {"max_length": 100},
            "social_description": {"max_length": 200},
        }

        if field_name not in allowed_fields:
            return JsonResponse(
                {"success": False, "error": "Field not allowed for editing"}, status=403
            )

        # Validate field value
        field_config = allowed_fields[field_name]

        if field_config.get("required") and not field_value:
            return JsonResponse(
                {"success": False, "error": f"{field_name} is required"}, status=400
            )

        if (
            field_config.get("max_length")
            and len(str(field_value)) > field_config["max_length"]
        ):
            return JsonResponse(
                {
                    "success": False,
                    "error": f"{field_name} must be {field_config['max_length']} characters or less",
                },
                status=400,
            )

        if field_config.get("choices") and field_value not in field_config["choices"]:
            return JsonResponse(
                {"success": False, "error": f"Invalid value for {field_name}"},
                status=400,
            )

        if field_config.get("type") == "boolean":
            field_value = str(field_value).lower() in ["true", "1", "yes", "on"]

        # Update the field
        with transaction.atomic():
            setattr(article, field_name, field_value)
            article.last_modified_by = request.user
            article.save(update_fields=[field_name, "last_modified_by", "updated_at"])

        logger.info(
            f"Field '{field_name}' updated for article '{article.title}' by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'{field_name.replace("_", " ").title()} updated successfully',
                "field": field_name,
                "value": field_value,
                "updated_at": article.updated_at.isoformat(),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error updating article field: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while updating"}, status=500
        )


@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
@require_http_methods(["POST"])
def update_content_section(request):
    """Update content section via AJAX"""
    try:
        data = json.loads(request.body)
        section_id = data.get("section_id")
        field_name = data.get("field")
        field_value = data.get("value")

        if not all([section_id, field_name]):
            return JsonResponse(
                {"success": False, "error": "Missing required fields"}, status=400
            )

        section = get_object_or_404(ContentSection, id=section_id)

        # Check if user can edit this article
        if not (
            request.user.is_superuser
            or section.article.created_by == request.user
            or request.user.is_staff
        ):
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        # Allowed fields for content sections
        allowed_fields = [
            "content",
            "title",
            "question",
            "answer",
            "caption",
            "alt_text",
        ]

        if field_name not in allowed_fields:
            return JsonResponse(
                {"success": False, "error": "Field not allowed for editing"}, status=403
            )

        # Update the field
        with transaction.atomic():
            setattr(section, field_name, field_value)
            section.save(update_fields=[field_name, "updated_at"])

            # Update article's last modified
            section.article.last_modified_by = request.user
            section.article.save(update_fields=["last_modified_by", "updated_at"])

        logger.info(
            f"Content section '{field_name}' updated by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'{field_name.replace("_", " ").title()} updated successfully',
                "field": field_name,
                "value": field_value,
                "updated_at": section.updated_at.isoformat(),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error updating content section: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while updating"}, status=500
        )


@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
@require_http_methods(["POST"])
def add_content_section(request):
    """Add new content section via AJAX"""
    try:
        data = json.loads(request.body)
        article_id = data.get("article_id")
        section_type = data.get("section_type", "paragraph")
        content = data.get("content", "")
        order = data.get("order")

        if not article_id:
            return JsonResponse(
                {"success": False, "error": "Article ID required"}, status=400
            )

        article = get_object_or_404(Article, id=article_id)

        # Check permissions
        if not (
            request.user.is_superuser
            or article.created_by == request.user
            or request.user.is_staff
        ):
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        # Get next order if not specified
        if order is None:
            last_section = article.content_sections.order_by("-order").first()
            order = (last_section.order + 1) if last_section else 0

        # Create new section
        with transaction.atomic():
            section = ContentSection.objects.create(
                article=article, section_type=section_type, content=content, order=order
            )

            # Update article's last modified
            article.last_modified_by = request.user
            article.save(update_fields=["last_modified_by", "updated_at"])

        logger.info(
            f"New content section added to article '{article.title}' by {request.user.username}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Content section added successfully",
                "section_id": str(section.id),
                "section": {
                    "id": str(section.id),
                    "type": section.section_type,
                    "content": section.content,
                    "order": section.order,
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Error adding content section: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while adding section"},
            status=500,
        )


@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
@require_http_methods(["DELETE"])
def delete_content_section(request, section_id):
    """Delete content section via AJAX"""
    try:
        section = get_object_or_404(ContentSection, id=section_id)

        # Check permissions
        if not (
            request.user.is_superuser
            or section.article.created_by == request.user
            or request.user.is_staff
        ):
            return JsonResponse(
                {"success": False, "error": "Permission denied"}, status=403
            )

        article = section.article
        section_order = section.order

        with transaction.atomic():
            section.delete()

            # Reorder remaining sections
            remaining_sections = article.content_sections.filter(
                order__gt=section_order
            )
            for remaining_section in remaining_sections:
                remaining_section.order -= 1
                remaining_section.save(update_fields=["order"])

            # Update article's last modified
            article.last_modified_by = request.user
            article.save(update_fields=["last_modified_by", "updated_at"])

        logger.info(
            f"Content section deleted from article '{article.title}' by {request.user.username}"
        )

        return JsonResponse(
            {"success": True, "message": "Content section deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting content section: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while deleting section"},
            status=500,
        )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def delete_article(request, article_id):
    """Delete an article"""
    try:
        article = get_object_or_404(Article, id=article_id)
        title = article.title
        article.delete()

        logger.info(f"Article '{title}' deleted by {request.user.username}")

        return JsonResponse(
            {"success": True, "message": f'Article "{title}" deleted successfully'}
        )

    except Exception as e:
        logger.error(f"Error deleting article: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)


# Utility views
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    """Get comprehensive dashboard statistics"""
    try:
        stats = {
            "total_articles": Article.objects.count(),
            "published_articles": Article.objects.filter(status="published").count(),
            "draft_articles": Article.objects.filter(status="draft").count(),
            "review_articles": Article.objects.filter(status="review").count(),
            "archived_articles": Article.objects.filter(status="archived").count(),
            "total_subscribers": Subscriber.objects.filter(is_active=True).count(),
            "upcoming_events": Event.objects.filter(
                status="upcoming", start_datetime__gte=timezone.now()
            ).count(),
            "total_page_views": Article.objects.aggregate(
                total=models.Sum("view_count")
            )["total"]
            or 0,
            "total_media_files": CloudinaryMedia.objects.count(),
            "recent_articles": ArticleSummarySerializer(
                Article.objects.order_by("-updated_at")[:5], many=True
            ).data,
            "popular_tags": TagSerializer(
                Tag.objects.order_by("-usage_count")[:10], many=True
            ).data,
        }

        serializer = DashboardStatsSerializer(data=stats)
        if serializer.is_valid():
            return Response(serializer.data)

        return Response(stats)

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventListView(ListView):
    """Events listing page"""

    model = Event
    template_name = "events.html"
    context_object_name = "events"
    paginate_by = 10

    def get_queryset(self):
        return (
            Event.objects.filter(is_public=True)
            .select_related("organizer", "featured_image")
            .prefetch_related("speakers")
            .order_by("start_datetime")
        )


# Error handlers
def handler404(request, exception):
    return render(request, "404.html", status=404)


def handler500(request):
    return render(request, "500.html", status=500)
