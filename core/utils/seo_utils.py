import re

from django.utils.html import strip_tags
from django.utils.text import Truncator


class SEOOptimizer:
    """Utility class for SEO optimization"""

    @staticmethod
    def generate_meta_title(article, max_length=60):
        """Generate optimized meta title"""
        if article.meta_title:
            return article.meta_title[:max_length]

        title = article.title
        if len(title) <= max_length:
            return title

        # Truncate at word boundary
        truncator = Truncator(title)
        return truncator.chars(max_length - 3) + "..."

    @staticmethod
    def generate_meta_description(article, max_length=160):
        """Generate optimized meta description"""
        if article.meta_description:
            return article.meta_description[:max_length]

        description = article.excerpt
        if len(description) <= max_length:
            return description

        truncator = Truncator(description)
        return truncator.chars(max_length - 3) + "..."

    @staticmethod
    def extract_keywords(article, max_keywords=10):
        """Extract keywords from article content"""
        if article.meta_keywords:
            return [k.strip() for k in article.meta_keywords.split(",")]

        # Extract from title, excerpt, and tags
        text = f"{article.title} {article.excerpt}"

        # Add tag names
        tag_names = [tag.name for tag in article.tags.all()]

        # Simple keyword extraction (can be enhanced with NLP)
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        word_freq = {}

        for word in words:
            if word not in [
                "this",
                "that",
                "with",
                "from",
                "they",
                "have",
                "will",
                "been",
                "were",
            ]:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Combine with tags and sort by frequency
        keywords = tag_names + sorted(word_freq.keys(), key=word_freq.get, reverse=True)

        return keywords[:max_keywords]

    @staticmethod
    def generate_structured_data(article):
        """Generate JSON-LD structured data for articles"""
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": article.title,
            "description": article.excerpt,
            "image": (
                article.featured_image.cloudinary_url
                if article.featured_image
                else None
            ),
            "author": {
                "@type": "Person",
                "name": article.author.name,
                "jobTitle": article.author.title or None,
            },
            "publisher": {
                "@type": "Organization",
                "name": "Centre for Inclusive Social Development",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://cisd.org/logo.png",  # Update with actual logo URL
                },
            },
            "datePublished": (
                article.published_date.isoformat() if article.published_date else None
            ),
            "dateModified": article.updated_at.isoformat(),
            "articleSection": article.category.display_name,
            "keywords": SEOOptimizer.extract_keywords(article),
            "wordCount": len(article.excerpt.split()),  # Approximate
            "url": f"https://cisd.org/article/{article.slug}/",  # Update with actual domain
        }
