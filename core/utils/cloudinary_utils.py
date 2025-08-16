import logging
import mimetypes
import os

import cloudinary
import cloudinary.api
import cloudinary.uploader
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
    api_key=getattr(settings, "CLOUDINARY_API_KEY", ""),
    api_secret=getattr(settings, "CLOUDINARY_API_SECRET", ""),
    secure=True,
)


class CloudinaryManager:
    """
    Manager class for handling Cloudinary operations.
    Provides methods for uploading, transforming, and managing media files.
    """

    # File type mappings
    ALLOWED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "webp", "gif", "svg"]
    ALLOWED_VIDEO_FORMATS = ["mp4", "mov", "avi", "mkv", "webm"]
    ALLOWED_AUDIO_FORMATS = ["mp3", "wav", "aac", "flac", "ogg"]
    ALLOWED_DOCUMENT_FORMATS = [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "txt",
    ]

    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_DOCUMENT_SIZE = 25 * 1024 * 1024  # 25MB

    @classmethod
    def determine_file_type(cls, file_or_filename):
        """
        Determine file type based on filename or file object.

        Args:
            file_or_filename: File object or filename string

        Returns:
            tuple: (file_type, file_format)
        """
        if hasattr(file_or_filename, "name"):
            filename = file_or_filename.name
        else:
            filename = str(file_or_filename)

        file_extension = filename.split(".")[-1].lower()

        if file_extension in cls.ALLOWED_IMAGE_FORMATS:
            return "image", file_extension
        elif file_extension in cls.ALLOWED_VIDEO_FORMATS:
            return "video", file_extension
        elif file_extension in cls.ALLOWED_AUDIO_FORMATS:
            return "audio", file_extension
        elif file_extension in cls.ALLOWED_DOCUMENT_FORMATS:
            return "document", file_extension
        else:
            return "other", file_extension

    @classmethod
    def validate_file(cls, file_obj):
        """
        Validate file before upload to Cloudinary.

        Args:
            file_obj: Django file object

        Raises:
            ValidationError: If file doesn't meet requirements
        """
        file_type, file_format = cls.determine_file_type(file_obj)
        file_size = file_obj.size

        # Check file size limits
        if file_type == "image" and file_size > cls.MAX_IMAGE_SIZE:
            raise ValidationError(
                _("Image files must be smaller than {size}MB").format(
                    size=cls.MAX_IMAGE_SIZE // (1024 * 1024)
                )
            )
        elif file_type == "video" and file_size > cls.MAX_VIDEO_SIZE:
            raise ValidationError(
                _("Video files must be smaller than {size}MB").format(
                    size=cls.MAX_VIDEO_SIZE // (1024 * 1024)
                )
            )
        elif file_type == "document" and file_size > cls.MAX_DOCUMENT_SIZE:
            raise ValidationError(
                _("Document files must be smaller than {size}MB").format(
                    size=cls.MAX_DOCUMENT_SIZE // (1024 * 1024)
                )
            )

        # Check if file type is allowed
        all_allowed = (
            cls.ALLOWED_IMAGE_FORMATS
            + cls.ALLOWED_VIDEO_FORMATS
            + cls.ALLOWED_AUDIO_FORMATS
            + cls.ALLOWED_DOCUMENT_FORMATS
        )

        if file_format not in all_allowed:
            raise ValidationError(
                _("File type '{format}' is not allowed").format(format=file_format)
            )

        return True

    @classmethod
    def upload_file(
        cls,
        file_obj,
        folder=None,
        public_id=None,
        tags=None,
        transformation=None,
        context=None,
    ):
        """
        Upload file to Cloudinary with proper organization.

        Args:
            file_obj: Django file object
            folder: Cloudinary folder path
            public_id: Custom public ID (optional)
            tags: List of tags for organization
            transformation: Cloudinary transformation parameters
            context: Custom context metadata

        Returns:
            dict: Upload result with URL, public_id, and metadata
        """
        try:
            # Validate file first
            cls.validate_file(file_obj)

            file_type, file_format = cls.determine_file_type(file_obj)

            # Set default folder based on file type
            if not folder:
                folder = f"cisd/{file_type}s"

            # Set default tags
            if not tags:
                tags = [file_type, file_format]
            elif isinstance(tags, list):
                tags.extend([file_type, file_format])

            # Resource type for Cloudinary
            resource_type = "auto"  # Let Cloudinary auto-detect
            if file_type == "video":
                resource_type = "video"
            elif file_type in ["document", "other"]:
                resource_type = "raw"

            # Upload parameters
            upload_params = {
                "folder": folder,
                "tags": tags,
                "resource_type": resource_type,
                "use_filename": True,
                "unique_filename": True,
            }

            # Add optional parameters
            if public_id:
                upload_params["public_id"] = public_id
            if transformation and file_type == "image":
                upload_params["transformation"] = transformation
            if context:
                upload_params["context"] = context

            # Perform upload
            result = cloudinary.uploader.upload(file_obj, **upload_params)

            logger.info(
                f"Successfully uploaded {file_obj.name} to Cloudinary: {result['public_id']}"
            )

            return {
                "success": True,
                "public_id": result["public_id"],
                "url": result["secure_url"],
                "format": result.get("format", file_format),
                "width": result.get("width"),
                "height": result.get("height"),
                "bytes": result.get("bytes", file_obj.size),
                "resource_type": result.get("resource_type", resource_type),
                "created_at": result.get("created_at"),
                "etag": result.get("etag"),
            }

        except Exception as e:
            logger.error(f"Failed to upload {file_obj.name} to Cloudinary: {str(e)}")
            return {"success": False, "error": str(e)}

    @classmethod
    def delete_file(cls, public_id, resource_type="image"):
        """
        Delete file from Cloudinary.

        Args:
            public_id: Cloudinary public ID
            resource_type: Type of resource (image, video, raw)

        Returns:
            dict: Deletion result
        """
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)

            logger.info(f"Successfully deleted {public_id} from Cloudinary")

            return {"success": result.get("result") == "ok", "result": result}

        except Exception as e:
            logger.error(f"Failed to delete {public_id} from Cloudinary: {str(e)}")
            return {"success": False, "error": str(e)}

    @classmethod
    def get_file_info(cls, public_id, resource_type="image"):
        """
        Get detailed information about a Cloudinary file.

        Args:
            public_id: Cloudinary public ID
            resource_type: Type of resource

        Returns:
            dict: File information
        """
        try:
            result = cloudinary.api.resource(public_id, resource_type=resource_type)

            return {"success": True, "info": result}

        except Exception as e:
            logger.error(f"Failed to get info for {public_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    @classmethod
    def generate_url(cls, public_id, transformation=None, resource_type="image"):
        """
        Generate Cloudinary URL with optional transformations.

        Args:
            public_id: Cloudinary public ID
            transformation: Transformation parameters
            resource_type: Type of resource

        Returns:
            str: Generated URL
        """
        try:
            return cloudinary.CloudinaryImage(public_id).build_url(
                transformation=transformation, resource_type=resource_type, secure=True
            )
        except Exception as e:
            logger.error(f"Failed to generate URL for {public_id}: {str(e)}")
            return None

    @classmethod
    def get_optimized_image_url(
        cls,
        public_id,
        width=None,
        height=None,
        crop="fill",
        quality="auto",
        format="auto",
    ):
        """
        Get optimized image URL with automatic format and quality.

        Args:
            public_id: Cloudinary public ID
            width: Target width
            height: Target height
            crop: Crop mode
            quality: Quality setting
            format: Image format

        Returns:
            str: Optimized image URL
        """
        transformation = {
            "quality": quality,
            "fetch_format": format,
        }

        if width:
            transformation["width"] = width
        if height:
            transformation["height"] = height
        if width or height:
            transformation["crop"] = crop

        return cls.generate_url(public_id, transformation)
