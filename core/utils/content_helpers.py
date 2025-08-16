import json

# utils/content_helpers.py
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class ContentRenderer:
    """Helper class for rendering different content section types."""

    @staticmethod
    def render_section(section, context=None):
        """
        Render a content section based on its type.

        Args:
            section: ContentSection instance
            context: Additional template context

        Returns:
            str: Rendered HTML
        """
        if not context:
            context = {}

        context["section"] = section

        template_map = {
            "paragraph": "content_sections/paragraph.html",
            "heading": "content_sections/heading.html",
            "subheading": "content_sections/subheading.html",
            "image": "content_sections/image.html",
            "quote": "content_sections/quote.html",
            "interview": "content_sections/interview.html",
            "video": "content_sections/video.html",
            "audio": "content_sections/audio.html",
            "code": "content_sections/code.html",
            "list": "content_sections/list.html",
            "table": "content_sections/table.html",
            "embed": "content_sections/embed.html",
            "divider": "content_sections/divider.html",
            "callout": "content_sections/callout.html",
        }

        template = template_map.get(
            section.section_type, "content_sections/default.html"
        )

        try:
            return render_to_string(template, context)
        except Exception as e:
            # Fallback to basic rendering
            return f'<div class="content-section-error">Error rendering section: {str(e)}</div>'

    @staticmethod
    def generate_table_of_contents(content_sections):
        """
        Generate table of contents from heading sections.

        Args:
            content_sections: QuerySet or list of ContentSection objects

        Returns:
            list: List of TOC items with titles and anchors
        """
        toc = []

        for section in content_sections:
            if section.section_type in ["heading", "subheading"]:
                title = section.title or strip_tags(section.content)
                if title:
                    anchor = slugify(title)
                    toc.append(
                        {
                            "title": title,
                            "anchor": anchor,
                            "level": 1 if section.section_type == "heading" else 2,
                        }
                    )

        return toc

    @staticmethod
    def extract_featured_image(content_sections):
        """
        Extract the first image from content sections if no featured image is set.

        Args:
            content_sections: QuerySet or list of ContentSection objects

        Returns:
            CloudinaryMedia or None: First image found
        """
        for section in content_sections:
            if section.section_type == "image" and section.media_file:
                return section.media_file

        return None
