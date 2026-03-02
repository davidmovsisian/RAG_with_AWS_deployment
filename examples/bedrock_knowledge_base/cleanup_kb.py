"""
cleanup_kb.py: Delete an AWS Bedrock Knowledge Base (educational example).

This script deletes the Knowledge Base resource.  It requires explicit
confirmation before proceeding.

NOTE: This script only deletes the Knowledge Base.  You will need to
manually clean up the following resources to avoid ongoing charges:
  - OpenSearch Serverless collection  (via AWS Console or AOSS API)
  - IAM role created by setup_kb.py   (via AWS Console or IAM API)

Usage:
    python cleanup_kb.py <KB_ID>

Example:
    python cleanup_kb.py ABCDEF1234
"""

import sys

import boto3
from botocore.exceptions import ClientError

CONFIRMATION_WORD = "DELETE"


def delete_knowledge_base(kb_id: str) -> None:
    """Delete the specified Bedrock Knowledge Base.

    Args:
        kb_id: ID of the Knowledge Base to delete.
    """
    bedrock_agent = boto3.client("bedrock-agent")

    print(f"\n🗑️  Deleting Knowledge Base: {kb_id}")
    try:
        bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
        print(f"  ✅ Knowledge Base {kb_id} deleted successfully.")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            print(f"  ℹ️  Knowledge Base {kb_id} not found — already deleted.")
        else:
            print(f"  ❌ Error deleting Knowledge Base: {e}")
            sys.exit(1)


def confirm_deletion(kb_id: str) -> bool:
    """Prompt the user to confirm deletion by typing the confirmation word.

    Args:
        kb_id: Knowledge Base ID shown in the warning message.

    Returns:
        True if the user confirmed, False otherwise.
    """
    print("\n⚠️  WARNING: This will permanently delete the Knowledge Base.")
    print(f"   Knowledge Base ID : {kb_id}")
    print("\n   The following resources will NOT be deleted automatically:")
    print("   - OpenSearch Serverless collection (manual cleanup required)")
    print("   - IAM role created by setup_kb.py (manual cleanup required)")
    print()
    answer = input(f"Type '{CONFIRMATION_WORD}' to confirm deletion: ").strip()
    return answer == CONFIRMATION_WORD


def main() -> None:
    """Entry point: parse arguments and run cleanup with confirmation."""
    if len(sys.argv) != 2:
        print("Usage: python cleanup_kb.py <KB_ID>")
        print("\nExample:")
        print("  python cleanup_kb.py ABCDEF1234")
        sys.exit(1)

    kb_id = sys.argv[1]

    print("=" * 60)
    print("🧹 Bedrock Knowledge Base — Cleanup (Educational Example)")
    print("=" * 60)

    if not confirm_deletion(kb_id):
        print("\nCleanup cancelled.")
        sys.exit(0)

    delete_knowledge_base(kb_id)

    print("\n" + "=" * 60)
    print("Cleanup summary:")
    print(f"  ✅ Knowledge Base {kb_id} deleted")
    print("  ⚠️  Manual cleanup still required:")
    print("      - OpenSearch Serverless collection")
    print("      - IAM role (educational-rag-kb-role)")
    print("=" * 60)


if __name__ == "__main__":
    main()
