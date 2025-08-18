
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import CloudinaryMedia
from dashboard.utils.media_optimizer import MediaOptimizer
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Optimize existing media files on Cloudinary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of files to process in each batch',
        )
        parser.add_argument(
            '--file-type',
            type=str,
            choices=['image', 'video', 'document'],
            help='Only optimize specific file type',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        file_type = options['file_type']

        # Get media files to optimize
        queryset = CloudinaryMedia.objects.all()
        
        if file_type:
            queryset = queryset.filter(file_type=file_type)

        total_files = queryset.count()
        self.stdout.write(f"Found {total_files} files to process")

        processed = 0
        optimized = 0
        errors = 0

        for media in queryset.iterator(chunk_size=batch_size):
            try:
                with transaction.atomic():
                    # Re-upload with optimization
                    if media.file_type == 'image':
                        # Get optimized URL and update
                        optimized_url = MediaOptimizer.get_optimized_url(
                            media, width=1920, height=1080
                        )
                        
                        if optimized_url and optimized_url != media.cloudinary_url:
                            media.cloudinary_url = optimized_url
                            media.save(update_fields=['cloudinary_url'])
                            optimized += 1
                            
                processed += 1
                
                if processed % 10 == 0:
                    self.stdout.write(f"Processed {processed}/{total_files} files")
                    
            except Exception as e:
                errors += 1
                logger.error(f"Error optimizing {media.title}: {str(e)}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Optimization complete: {optimized} optimized, {errors} errors"
            )
        )
```

## dashboard/management/commands/generate_stats.py
```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Article, Author, Category, Tag, Subscriber
from dashboard.managers import DashboardStatsManager
import json

class Command(BaseCommand):
    help = 'Generate comprehensive site statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for JSON stats',
        )
        parser.add_argument(
            '--period',
            type=str,
            choices=['week', 'month', 'year'],
            default='month',
            help='Time period for stats',
        )

    def handle(self, *args, **options):
        period = options['period']
        output_file = options.get('output')

        now = timezone.now()
        
        if period == 'week':
            start_date = now - timezone.timedelta(days=7)
        elif period == 'month':
            start_date = now - timezone.timedelta(days=30)
        else:  # year
            start_date = now - timezone.timedelta(days=365)

        # Generate comprehensive stats
        stats = {
            'generated_at': now.isoformat(),
            'period': period,
            'overview': DashboardStatsManager.get_overview_stats(),
            'content_analysis': self.get_content_analysis(start_date),
            'author_performance': self.get_author_performance(start_date),
            'category_performance': self.get_category_performance(start_date),
            'engagement_metrics': self.get_engagement_metrics(start_date),
        }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            self.stdout.write(f"Stats saved to {output_file}")
        else:
            self.stdout.write(json.dumps(stats, indent=2, default=str))

    def get_content_analysis(self, start_date):
        """Analyze content performance"""
        articles = Article.objects.filter(
            published_date__gte=start_date,
            status='published'
        )

        return {
            'total_published': articles.count(),
            'avg_reading_time': articles.aggregate(
                avg=models.Avg('content_sections__order')
            )['avg'] or 0,
            'most_viewed': list(articles.order_by('-view_count')[:5].values(
                'title', 'view_count', 'published_date'
            )),
            'content_sections_distribution': dict(
                articles.values('content_sections__section_type').annotate(
                    count=models.Count('content_sections')
                ).values_list('content_sections__section_type', 'count')
            )
        }

    def get_author_performance(self, start_date):
        """Analyze author performance"""
        authors = Author.objects.filter(
            articles__published_date__gte=start_date,
            articles__status='published'
        ).annotate(
            article_count=models.Count('articles'),
            total_views=models.Sum('articles__view_count')
        ).order_by('-total_views')

        return [
            {
                'name': author.name,
                'article_count': author.article_count,
                'total_views': author.total_views or 0,
                'avg_views_per_article': (author.total_views or 0) / max(author.article_count, 1)
            }
            for author in authors[:10]
        ]

    def get_category_performance(self, start_date):
        """Analyze category performance"""
        categories = Category.objects.filter(
            articles__published_date__gte=start_date,
            articles__status='published'
        ).annotate(
            article_count=models.Count('articles'),
            total_views=models.Sum('articles__view_count')
        ).order_by('-total_views')

        return [
            {
                'name': category.display_name,
                'article_count': category.article_count,
                'total_views': category.total_views or 0,
                'avg_views_per_article': (category.total_views or 0) / max(category.article_count, 1)
            }
            for category in categories
        ]

    def get_engagement_metrics(self, start_date):
        """Analyze engagement metrics"""
        return {
            'newsletter_growth': Subscriber.objects.filter(
                created_at__gte=start_date
            ).count(),
            'top_shared_articles': list(
                Article.objects.filter(
                    published_date__gte=start_date,
                    status='published'
                ).order_by('-share_count')[:5].values(
                    'title', 'share_count', 'view_count'
                )
            ),
            'engagement_rate': self.calculate_engagement_rate(start_date),
        }

    def calculate_engagement_rate(self, start_date):
        """Calculate overall engagement rate"""
        articles = Article.objects.filter(
            published_date__gte=start_date,
            status='published'
        )
        
        total_views = articles.aggregate(
            total=models.Sum('view_count')
        )['total'] or 0
        
        total_shares = articles.aggregate(
            total=models.Sum('share_count')
        )['total'] or 0
        
        if total_views > 0:
            return (total_shares / total_views) * 100
        return 0
```

## dashboard/management/commands/import_content.py
```python
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from core.models import Article, Author, Category
from dashboard.utils.file_processors import FileProcessor, ContentGenerator
import os
import glob

class Command(BaseCommand):
    help = 'Bulk import content from files in a directory'

    def add_arguments(self, parser):
        parser.add_argument(
            'directory',
            type=str,
            help='Directory containing files to import',
        )
        parser.add_argument(
            '--author',
            type=str,
            help='Default author name for imported content',
            default='System Import'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Default category for imported content',
            default='analysis'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )

    def handle(self, *args, **options):
        directory = options['directory']
        author_name = options['author']
        category_name = options['category']
        dry_run = options['dry_run']

        if not os.path.exists(directory):
            self.stdout.write(
                self.style.ERROR(f"Directory {directory} does not exist")
            )
            return

        # Get or create author
        try:
            author = Author.objects.get(name=author_name)
        except Author.DoesNotExist:
            if dry_run:
                self.stdout.write(f"Would create author: {author_name}")
                author = None
            else:
                author = Author.objects.create(
                    name=author_name,
                    email='import@cisd.org'
                )
                self.stdout.write(f"Created author: {author_name}")

        # Get category
        try:
            category = Category.objects.get(name=category_name)
        except Category.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Category {category_name} does not exist")
            )
            return

        # Get system user for created_by
        try:
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                system_user = User.objects.filter(is_staff=True).first()
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("No admin user found for created_by field")
            )
            return

        # Find files to import
        supported_extensions = ['*.pdf', '*.doc', '*.docx', '*.txt']
        files_to_import = []
        
        for extension in supported_extensions:
            files_to_import.extend(
                glob.glob(os.path.join(directory, extension))
            )

        self.stdout.write(f"Found {len(files_to_import)} files to import")

        imported = 0
        errors = 0

        for file_path in files_to_import:
            try:
                filename = os.path.basename(file_path)
                self.stdout.write(f"Processing: {filename}")

                if dry_run:
                    self.stdout.write(f"Would import: {filename}")
                    continue

                # Read and process file
                with open(file_path, 'rb') as f:
                    # Create a mock file object
                    class MockFile:
                        def __init__(self, file_path, content):
                            self.name = os.path.basename(file_path)
                            self.content = content
                            
                        def chunks(self):
                            yield self.content
                    
                    file_content = f.read()
                    mock_file = MockFile(file_path, file_content)
                
                # Process file
                processed_file = FileProcessor.process_file(mock_file)
                
                if not processed_file['success']:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to process {filename}: {processed_file['error']}")
                    )
                    errors += 1
                    continue

                # Generate article data
                article_data = ContentGenerator.generate_article_from_file(processed_file)

                # Create article
                with transaction.atomic():
                    article = Article.objects.create(
                        title=article_data['title'],
                        excerpt=article_data['excerpt'],
                        category=category,
                        author=author,
                        status='draft',
                        created_by=system_user,
                        last_modified_by=system_user,
                    )

                    # Create content sections
                    from core.models import ContentSection
                    for order, section_data in enumerate(article_data['sections']):
                        ContentSection.objects.create(
                            article=article,
                            section_type=section_data['type'],
                            order=order,
                            content=section_data.get('content', ''),
                            title=section_data.get('title', ''),
                        )

                self.stdout.write(
                    self.style.SUCCESS(f"Imported: {article.title}")
                )
                imported += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error importing {filename}: {str(e)}")
                )
                errors += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import complete: {imported} successful, {errors} errors"
                )
            )
        else:
            self.stdout.write(f"Dry run complete: {len(files_to_import)} files would be processed")
```

## dashboard/utils/content_validators.py
```python
import re
import html
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

class ContentValidator:
    """Validate and clean content before saving"""
    
    @staticmethod
    def validate_article_data(data):
        """Validate article data before saving"""
        errors = {}
        
        # Title validation
        if not data.get('title', '').strip():
            errors['title'] = 'Title is required'
        elif len(data['title']) > 300:
            errors['title'] = 'Title must be 300 characters or less'
        
        # Excerpt validation
        if not data.get('excerpt', '').strip():
            errors['excerpt'] = 'Excerpt is required'
        elif len(data['excerpt']) > 500:
            errors['excerpt'] = 'Excerpt must be 500 characters or less'
        
        # Category validation
        if not data.get('category_id'):
            errors['category_id'] = 'Category is required'
        
        # Author validation
        if not data.get('author_id'):
            errors['author_id'] = 'Author is required'
        
        # Content sections validation
        if 'content_sections' in data:
            section_errors = ContentValidator.validate_content_sections(
                data['content_sections']
            )
            if section_errors:
                errors['content_sections'] = section_errors
        
        if errors:
            raise ValidationError(errors)
        
        return True
    
    @staticmethod
    def validate_content_sections(sections):
        """Validate content sections"""
        errors = []
        
        for i, section in enumerate(sections):
            section_errors = {}
            
            # Type validation
            valid_types = [
                'paragraph', 'heading', 'subheading', 'image', 'quote', 
                'interview', 'video', 'audio', 'code', 'list', 'table', 
                'embed', 'divider', 'callout'
            ]
            
            if section.get('type') not in valid_types:
                section_errors['type'] = f'Invalid section type: {section.get("type")}'
            
            # Content validation based on type
            section_type = section.get('type')
            
            if section_type in ['paragraph', 'heading', 'subheading']:
                if not section.get('content', '').strip():
                    section_errors['content'] = f'{section_type.title()} content is required'
            
            elif section_type == 'interview':
                if not section.get('question', '').strip():
                    section_errors['question'] = 'Interview question is required'
                if not section.get('answer', '').strip():
                    section_errors['answer'] = 'Interview answer is required'
            
            elif section_type == 'image':
                if not section.get('media_file_id'):
                    section_errors['media_file_id'] = 'Image is required for image sections'
            
            if section_errors:
                errors.append({f'section_{i}': section_errors})
        
        return errors if errors else None
    
    @staticmethod
    def clean_html_content(content):
        """Clean and sanitize HTML content"""
        if not content:
            return ''
        
        # Allowed HTML tags
        allowed_tags = [
            'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'ul', 'ol', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'
        ]
        
        # Remove script and style tags completely
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove potentially dangerous attributes
        content = re.sub(r'on\w+="[^"]*"', '', content, flags=re.IGNORECASE)
        content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        return content.strip()
    
    @staticmethod
    def validate_file_upload(file_obj):
        """Validate uploaded files"""
        if not file_obj:
            raise ValidationError('No file provided')
        
        # Check file size (25MB limit)
        max_size = 25 * 1024 * 1024
        if file_obj.size > max_size:
            raise ValidationError('File size must be less than 25MB')
        
        # Check file type
        allowed_extensions = [
            'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'gif', 
            'webp', 'mp4', 'mov', 'avi', 'webm'
        ]
        
        file_extension = file_obj.name.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            raise ValidationError(f'File type .{file_extension} is not allowed')
        
        return True
    
    @staticmethod
    def generate_excerpt(content, max_length=500):
        """Generate excerpt from content"""
        if not content:
            return ''
        
        # Strip HTML tags
        text = strip_tags(content)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate to max length
        if len(text) <= max_length:
            return text
        
        # Find last complete sentence within limit
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        if last_sentence_end > max_length * 0.7:  # At least 70% of max length
            return text[:last_sentence_end + 1]
        else:
            # Truncate at word boundary
            last_space = truncated.rfind(' ')
            if last_space > 0:
                return text[:last_space] + '...'
            else:
                return truncated + '...'

class SecurityValidator:
    """Additional security validations"""
    
    @staticmethod
    def validate_user_permissions(user, action, resource=None):
        """Validate user permissions for specific actions"""
        if not user.is_authenticated:
            return False
        
        # Super admin can do everything
        if user.is_superuser:
            return True
        
        # Staff users can manage content
        if user.is_staff:
            return action in ['create', 'read', 'update']
        
        # Regular users can only read
        return action == 'read'
    
    @staticmethod
    def validate_csrf_token(request):
        """Additional CSRF validation"""
        # Django handles CSRF automatically, but we can add extra checks
        return True
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize uploaded filenames"""
        # Remove path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        
        return filename