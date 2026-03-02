"""
sync_documents.py: Start an ingestion job to sync documents from S3 into the
Bedrock Knowledge Base (educational example).

When you run a sync Bedrock will:
  1. Crawl the S3 bucket/prefix configured on the data source
  2. Read and parse each document (PDF, DOCX, TXT, HTML, etc.)
  3. Split the text into chunks using the strategy you configured
  4. Generate an embedding vector for each chunk via Amazon Titan
  5. Write the vectors into OpenSearch Serverless

This is the "managed" equivalent of the custom ingestion pipeline in the
worker/ directory of this repository.

Usage:
    python sync_documents.py <KB_ID> <DATA_SOURCE_ID>

Example:
    python sync_documents.py ABCDEF1234 GHIJKL5678
"""

import sys
import time

import boto3
from botocore.exceptions import ClientError

POLL_INTERVAL_SECONDS = 10


def start_ingestion_job(kb_id: str, ds_id: str) -> str:
    """Start an ingestion job and return its ID.

    Args:
        kb_id: Bedrock Knowledge Base ID.
        ds_id: Data source ID to ingest from.

    Returns:
        The ingestion job ID.
    """
    bedrock_agent = boto3.client("bedrock-agent")

    print(f"🔄 Starting ingestion job for Knowledge Base: {kb_id}")
    try:
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )
        job_id = response["ingestionJob"]["ingestionJobId"]
        print(f"  ✅ Ingestion job started: {job_id}")
        return job_id
    except ClientError as e:
        print(f"  ❌ Error starting ingestion job: {e}")
        sys.exit(1)


def monitor_ingestion_job(kb_id: str, ds_id: str, job_id: str) -> None:
    """Poll the ingestion job until it completes and print statistics.

    Args:
        kb_id: Bedrock Knowledge Base ID.
        ds_id: Data source ID.
        job_id: Ingestion job ID to monitor.
    """
    bedrock_agent = boto3.client("bedrock-agent")

    print(f"\n📊 Monitoring ingestion job: {job_id}")
    print(f"   (polling every {POLL_INTERVAL_SECONDS} seconds)\n")

    while True:
        try:
            response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job_id,
            )
        except ClientError as e:
            print(f"  ❌ Error retrieving job status: {e}")
            sys.exit(1)

        job = response["ingestionJob"]
        status = job["status"]
        stats = job.get("statistics", {})

        # Display current counts on a single updating line
        scanned = stats.get("numberOfDocumentsScanned", 0)
        indexed = stats.get("numberOfNewDocumentsIndexed", 0)
        updated = stats.get("numberOfModifiedDocumentsIndexed", 0)
        deleted = stats.get("numberOfDocumentsDeleted", 0)
        failed = stats.get("numberOfDocumentsFailed", 0)

        print(
            f"  🔄 Status: {status} | "
            f"Scanned: {scanned} | Indexed: {indexed} | "
            f"Updated: {updated} | Deleted: {deleted} | Failed: {failed}",
            end="\r",
        )

        if status == "COMPLETE":
            print()  # newline after the \r line
            print("\n✅ Ingestion job complete!")
            print(f"   Documents scanned : {scanned}")
            print(f"   Documents indexed : {indexed}")
            print(f"   Documents updated : {updated}")
            print(f"   Documents deleted : {deleted}")
            if failed > 0:
                print(f"   ⚠️  Documents failed: {failed}")
                _print_failure_details(job)
            return

        if status == "FAILED":
            print()
            print("  ❌ Ingestion job FAILED")
            _print_failure_details(job)
            sys.exit(1)

        time.sleep(POLL_INTERVAL_SECONDS)


def _print_failure_details(job: dict) -> None:
    """Print failure reason details from an ingestion job response.

    Args:
        job: The ingestionJob dict returned by get_ingestion_job.
    """
    for failure in job.get("failureReasons", []):
        print(f"   Failure reason: {failure}")


def main() -> None:
    """Entry point: parse arguments and run the ingestion job."""
    if len(sys.argv) != 3:
        print("Usage: python sync_documents.py <KB_ID> <DATA_SOURCE_ID>")
        print("\nExample:")
        print("  python sync_documents.py ABCDEF1234 GHIJKL5678")
        sys.exit(1)

    kb_id = sys.argv[1]
    ds_id = sys.argv[2]

    print("=" * 60)
    print("📥 Bedrock Knowledge Base — Document Sync (Educational Example)")
    print("=" * 60)
    print(f"  Knowledge Base ID : {kb_id}")
    print(f"  Data Source ID    : {ds_id}")
    print()

    job_id = start_ingestion_job(kb_id, ds_id)
    monitor_ingestion_job(kb_id, ds_id, job_id)

    print("\nNext step:")
    print(f"  python query_kb.py {kb_id} 'Your question here'")


if __name__ == "__main__":
    main()
