# api/utils/r2.py
import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class R2Client:
    def __init__(self):
        self.endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name='auto'
        )
        self.bucket_name = settings.r2_bucket_name
        self.public_url = settings.r2_public_url

    def upload_image(self, task_id: str, task_type: str, image_data: bytes, filename: str = None) -> Optional[str]:
        """
        Upload image to R2

        Args:
            task_id: Task ID
            task_type: Task type (face-swap, upscale, remove-background)
            image_data: Image binary data
            filename: Filename (default: task_id.png)

        Returns:
            Public access URL, None on failure
        """
        if not filename:
            filename = f"{task_id}.png"

        # Determine storage path based on task type
        prefix_map = {
            "face-swap": "face-swap",
            "upscale": "upscale",
            "remove-background": "remove-background"
        }
        prefix = prefix_map.get(task_type, "unknown")

        key = f"{prefix}/{filename}"

        try:
            # Upload image
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_data,
                ContentType='image/png'
            )

            # Verify upload (HeadObject)
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )

            # Return public URL
            url = f"{self.public_url}/{key}"
            logger.info(f"Successfully uploaded {key} to R2")
            return url

        except ClientError as e:
            logger.error(f"Failed to upload to R2: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading to R2: {e}")
            return None

    def test_connection(self) -> bool:
        """Test R2 connection"""
        try:
            # Try to list bucket
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info("R2 connection test successful")
            return True
        except ClientError as e:
            logger.error(f"R2 connection test failed: {e}")
            return False

# Global instance
r2_client = R2Client() if settings.r2_access_key_id else None
