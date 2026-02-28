"""
S3 client for downloading, reading, and moving documents in S3.
"""

import os
from typing import Optional

import boto3


class S3Client:
    """Client for Amazon S3 file operations."""

    def __init__(self):
        """Initialize S3 client and load bucket configuration from environment variables."""
        region = os.getenv("AWS_REGION", "us-east-1")
        self.client = boto3.client("s3", region_name=region)
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "")
        self.processed_prefix = os.getenv("S3_PROCESSED_PREFIX", "processed/")
        self.failed_prefix = os.getenv("S3_FAILED_PREFIX", "failed/")
        print(f"S3Client initialized (bucket={self.bucket_name})")

    def download_file(self, key: str, local_path: str) -> bool:
        """Download a file from S3 to a local path.

        Args:
            key: The S3 object key.
            local_path: The local filesystem path to save the file.

        Returns:
            True if the download succeeded, False otherwise.
        """
        try:
            self.client.download_file(self.bucket_name, key, local_path)
            print(f"Downloaded s3://{self.bucket_name}/{key} -> {local_path}")
            return True
        except Exception as e:
            print(f"Error downloading file {key}: {e}")
            return False

    def read_file_content(self, key: str) -> Optional[str]:
        """Read the content of an S3 file directly as a UTF-8 string.

        Args:
            key: The S3 object key.

        Returns:
            The file content as a string, or None if an error occurred.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            print(f"Read {len(content)} characters from s3://{self.bucket_name}/{key}")
            return content
        except Exception as e:
            print(f"Error reading file {key}: {e}")
            return None

    def move_to_processed(self, key: str) -> bool:
        """Move a file to the processed/ prefix in S3.

        Args:
            key: The S3 object key of the file to move.

        Returns:
            True if the move succeeded, False otherwise.
        """
        filename = key.split("/")[-1]
        destination_key = self.processed_prefix + filename
        return self._move_file(key, destination_key)

    def move_to_failed(self, key: str) -> bool:
        """Move a file to the failed/ prefix in S3.

        Args:
            key: The S3 object key of the file to move.

        Returns:
            True if the move succeeded, False otherwise.
        """
        filename = key.split("/")[-1]
        destination_key = self.failed_prefix + filename
        return self._move_file(key, destination_key)

    def _move_file(self, source_key: str, destination_key: str) -> bool:
        """Copy a file to a new key and delete the original.

        Args:
            source_key: The source S3 object key.
            destination_key: The destination S3 object key.

        Returns:
            True if the operation succeeded, False otherwise.
        """
        try:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}
            self.client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=destination_key,
            )
            self.client.delete_object(Bucket=self.bucket_name, Key=source_key)
            print(
                f"Moved s3://{self.bucket_name}/{source_key} -> "
                f"s3://{self.bucket_name}/{destination_key}"
            )
            return True
        except Exception as e:
            print(f"Error moving file {source_key} -> {destination_key}: {e}")
            return False
