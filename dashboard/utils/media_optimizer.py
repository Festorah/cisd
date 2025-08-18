import logging

from core.models import CloudinaryMedia
from core.utils.cloudinary_utils import CloudinaryManager
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class MediaOptimizer:
    """Optimize media files for web delivery"""

    @staticmethod
    def upload_and_optimize(
        file_obj: UploadedFile, user, folder=None
    ) -> CloudinaryMedia:
        """Upload file to Cloudinary with optimization"""

        # Determine file type and set optimization parameters
        file_type, file_format = CloudinaryManager.determine_file_type(file_obj)

        # Set folder based on file type if not specified
        if not folder:
            folder = f"cisd/{file_type}s"

        # Optimization parameters based on file type
        transformation = None
        if file_type == "image":
            transformation = {
                "quality": "auto:best",
                "fetch_format": "auto",
                "crop": "limit",
                "width": 1920,  # Max width for web
                "height": 1080,  # Max height for web
            }

        # Upload to Cloudinary
        upload_result = CloudinaryManager.upload_file(
            file_obj=file_obj,
            folder=folder,
            transformation=transformation,
            tags=[file_type, "dashboard_upload", "optimized"],
        )

        if not upload_result["success"]:
            raise Exception(f"Upload failed: {upload_result['error']}")

        # Create CloudinaryMedia record
        media = CloudinaryMedia.objects.create(
            title=file_obj.name,
            cloudinary_url=upload_result["url"],
            cloudinary_public_id=upload_result["public_id"],
            file_type=file_type,
            file_format=upload_result["format"],
            file_size=upload_result["bytes"],
            width=upload_result.get("width"),
            height=upload_result.get("height"),
            alt_text="",
            caption="",
            uploaded_by=user,
        )

        logger.info(f"Media uploaded and optimized: {media.title}")
        return media

    @staticmethod
    def get_optimized_url(media: CloudinaryMedia, width=None, height=None, crop="fill"):
        """Get optimized URL for specific dimensions"""
        return CloudinaryManager.get_optimized_image_url(
            public_id=media.cloudinary_public_id,
            width=width,
            height=height,
            crop=crop,
            quality="auto:best",
            format="auto",
        )

    @staticmethod
    def batch_optimize_existing():
        """Batch optimize existing media files"""
        # This could be a management command for optimizing existing files
        unoptimized_media = CloudinaryMedia.objects.filter(
            file_type="image"
            # Add criteria for files that need optimization
        )

        for media in unoptimized_media:
            try:
                # Re-upload with optimization
                # Implementation depends on your specific needs
                pass
            except Exception as e:
                logger.error(f"Failed to optimize {media.title}: {str(e)}")
