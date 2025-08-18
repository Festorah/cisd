import logging
import os
import tempfile
from typing import Any, Dict, List

from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class FileProcessor:
    """Base class for file processing"""

    @staticmethod
    def process_file(file_obj: UploadedFile) -> Dict[str, Any]:
        """Process uploaded file and return structured content"""
        file_extension = file_obj.name.split(".")[-1].lower()

        if file_extension == "pdf":
            return PDFProcessor.process(file_obj)
        elif file_extension in ["doc", "docx"]:
            return WordProcessor.process(file_obj)
        elif file_extension == "txt":
            return TextProcessor.process(file_obj)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")


class PDFProcessor:
    """Process PDF files"""

    @staticmethod
    def process(file_obj: UploadedFile) -> Dict[str, Any]:
        try:
            import PyPDF2

            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            # Extract text
            text_content = ""
            with open(temp_file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"

            # Clean up
            os.unlink(temp_file_path)

            # Parse content into sections
            sections = PDFProcessor._parse_content_to_sections(text_content)

            return {
                "success": True,
                "title": file_obj.name.replace(".pdf", ""),
                "content": text_content,
                "sections": sections,
                "file_type": "pdf",
            }

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {"success": False, "error": str(e), "file_type": "pdf"}

    @staticmethod
    def _parse_content_to_sections(text: str) -> List[Dict[str, Any]]:
        """Parse text content into structured sections"""
        sections = []
        lines = text.split("\n")
        current_section = {"type": "paragraph", "content": ""}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect headings (lines that are short and might be titles)
            if (
                len(line) < 100
                and line.isupper()
                or (len(line.split()) <= 8 and not line.endswith("."))
            ):
                # Save current section if it has content
                if current_section["content"].strip():
                    sections.append(current_section)

                # Start new heading section
                sections.append({"type": "heading", "content": line, "title": line})
                current_section = {"type": "paragraph", "content": ""}
            else:
                # Add to current paragraph
                current_section["content"] += line + " "

        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)

        return sections


class WordProcessor:
    """Process Word documents"""

    @staticmethod
    def process(file_obj: UploadedFile) -> Dict[str, Any]:
        try:
            from docx import Document

            # Save file temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            # Process document
            doc = Document(temp_file_path)
            sections = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                # Determine section type based on style
                style_name = paragraph.style.name.lower()

                if "heading" in style_name:
                    sections.append({"type": "heading", "content": text, "title": text})
                else:
                    sections.append({"type": "paragraph", "content": text})

            # Clean up
            os.unlink(temp_file_path)

            return {
                "success": True,
                "title": file_obj.name.replace(".docx", "").replace(".doc", ""),
                "sections": sections,
                "file_type": "word",
            }

        except Exception as e:
            logger.error(f"Error processing Word document: {str(e)}")
            return {"success": False, "error": str(e), "file_type": "word"}


class TextProcessor:
    """Process plain text files"""

    @staticmethod
    def process(file_obj: UploadedFile) -> Dict[str, Any]:
        try:
            content = file_obj.read().decode("utf-8")
            sections = TextProcessor._parse_text_to_sections(content)

            return {
                "success": True,
                "title": file_obj.name.replace(".txt", ""),
                "content": content,
                "sections": sections,
                "file_type": "text",
            }

        except Exception as e:
            logger.error(f"Error processing text file: {str(e)}")
            return {"success": False, "error": str(e), "file_type": "text"}

    @staticmethod
    def _parse_text_to_sections(text: str) -> List[Dict[str, Any]]:
        """Parse text into sections based on line breaks and patterns"""
        sections = []
        paragraphs = text.split("\n\n")  # Double line break separates paragraphs

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Simple heading detection
            lines = paragraph.split("\n")
            if len(lines) == 1 and len(paragraph) < 100:
                sections.append(
                    {"type": "heading", "content": paragraph, "title": paragraph}
                )
            else:
                sections.append({"type": "paragraph", "content": paragraph})

        return sections


class ContentGenerator:
    """Generate default article structure"""

    @staticmethod
    def get_default_structure() -> List[Dict[str, Any]]:
        """Get default article content structure"""
        return [
            {
                "type": "paragraph",
                "content": "Introduction paragraph - provide context and overview of the topic.",
                "title": "",
                "order": 0,
            },
            {
                "type": "heading",
                "content": "Main Heading",
                "title": "Main Heading",
                "order": 1,
            },
            {
                "type": "paragraph",
                "content": "Main content paragraph - elaborate on the key points.",
                "title": "",
                "order": 2,
            },
            {
                "type": "image",
                "content": "",
                "title": "",
                "caption": "Add relevant image with descriptive caption",
                "alt_text": "Descriptive alt text for accessibility",
                "order": 3,
            },
            {
                "type": "paragraph",
                "content": "Supporting paragraph - provide additional details and analysis.",
                "title": "",
                "order": 4,
            },
            {
                "type": "quote",
                "content": "Add relevant quote to support your points.",
                "title": "",
                "order": 5,
            },
            {
                "type": "paragraph",
                "content": "Conclusion paragraph - summarize key points and implications.",
                "title": "",
                "order": 6,
            },
        ]

    @staticmethod
    def generate_article_from_file(processed_file: Dict[str, Any]) -> Dict[str, Any]:
        """Generate article structure from processed file"""
        if not processed_file.get("success"):
            raise ValueError("File processing failed")

        article_data = {
            "title": processed_file["title"],
            "excerpt": "",  # Will be set from first paragraph
            "sections": processed_file["sections"],
        }

        # Generate excerpt from first paragraph
        first_paragraph = next(
            (s for s in processed_file["sections"] if s["type"] == "paragraph"), None
        )
        if first_paragraph:
            content = first_paragraph["content"]
            article_data["excerpt"] = content[:500] + (
                "..." if len(content) > 500 else ""
            )

        return article_data
