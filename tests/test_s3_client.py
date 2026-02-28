#!/usr/bin/env python3
"""Command-line test script for S3Client.

Usage examples:
    python tests/test_s3_client.py upload tests/sample_data/test_document.txt uploads/test.txt
    python tests/test_s3_client.py read uploads/test.txt
    python tests/test_s3_client.py upload /path/to/file.pdf uploads/document.pdf
    python tests/test_s3_client.py read uploads/document.pdf
    python tests/test_s3_client.py download uploads/test.txt ./downloaded.txt
    python tests/test_s3_client.py move-processed uploads/test.txt
    python tests/test_s3_client.py move-failed uploads/bad_file.txt
"""

import os
import sys

# Allow running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from src.utils.s3_client import S3Client


USAGE = """
Usage: python tests/test_s3_client.py <command> [args]

Commands:
  upload <local_file_path> <s3_key>   Upload a local file to S3
  read <s3_key>                        Read/extract text from an S3 file
  download <s3_key> <local_path>       Download an S3 file locally
  move-processed <s3_key>              Move a file to the processed/ prefix
  move-failed <s3_key>                 Move a file to the failed/ prefix
"""


def cmd_upload(client: S3Client, args: list) -> None:
    if len(args) != 2:
        print("❌  Usage: upload <local_file_path> <s3_key>")
        sys.exit(1)
    local_path, s3_key = args
    success = client.upload_file(local_path, s3_key)
    if success:
        print(f"✅  Upload succeeded: {local_path} -> {s3_key}")
    else:
        print(f"❌  Upload failed: {local_path}")
        sys.exit(1)


def cmd_read(client: S3Client, args: list) -> None:
    if len(args) != 1:
        print("❌  Usage: read <s3_key>")
        sys.exit(1)
    s3_key = args[0]
    content = client.read_file_content(s3_key)
    if content is None:
        print(f"❌  Failed to read: {s3_key}")
        sys.exit(1)
    print(f"✅  Read succeeded ({len(content)} characters)")
    preview = content[:500]
    print(f"\n--- Preview (first 500 chars) ---\n{preview}\n---------------------------------")


def cmd_download(client: S3Client, args: list) -> None:
    if len(args) != 2:
        print("❌  Usage: download <s3_key> <local_path>")
        sys.exit(1)
    s3_key, local_path = args
    success = client.download_file(s3_key, local_path)
    if success:
        print(f"✅  Download succeeded: {s3_key} -> {local_path}")
    else:
        print(f"❌  Download failed: {s3_key}")
        sys.exit(1)


def cmd_move_processed(client: S3Client, args: list) -> None:
    if len(args) != 1:
        print("❌  Usage: move-processed <s3_key>")
        sys.exit(1)
    s3_key = args[0]
    success = client.move_to_processed(s3_key)
    if success:
        print(f"✅  Moved to processed: {s3_key}")
    else:
        print(f"❌  Move to processed failed: {s3_key}")
        sys.exit(1)


def cmd_move_failed(client: S3Client, args: list) -> None:
    if len(args) != 1:
        print("❌  Usage: move-failed <s3_key>")
        sys.exit(1)
    s3_key = args[0]
    success = client.move_to_failed(s3_key)
    if success:
        print(f"✅  Moved to failed: {s3_key}")
    else:
        print(f"❌  Move to failed failed: {s3_key}")
        sys.exit(1)


COMMANDS = {
    "upload": cmd_upload,
    "read": cmd_read,
    "download": cmd_download,
    "move-processed": cmd_move_processed,
    "move-failed": cmd_move_failed,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(USAGE)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    client = S3Client()
    COMMANDS[command](client, args)


if __name__ == "__main__":
    main()
