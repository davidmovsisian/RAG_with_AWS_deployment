"""
query_kb.py: Query an AWS Bedrock Knowledge Base using retrieve_and_generate()
(educational example).

The retrieve_and_generate() API handles the full RAG pipeline in a single call:
  1. Embed the question using Amazon Titan
  2. Search the OpenSearch Serverless vector index for the top-K most relevant chunks
  3. Build a prompt that includes the retrieved context
  4. Call the specified foundation model (Claude 3 Sonnet) to generate an answer
  5. Return the answer along with source citations

Compare this to the custom RAG query flow in src/api/ where each of these
steps is explicit and fully controllable.

Usage:
    python query_kb.py <KB_ID> "Your question here"

Example:
    python query_kb.py ABCDEF1234 "How do I configure OpenSearch?"
"""

import sys

import boto3
from botocore.exceptions import ClientError

# Number of source chunks to retrieve from the vector index
TOP_K_RESULTS = 5

# Foundation model used for answer generation
# You can swap this for any Bedrock-supported model
MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"


def query_knowledge_base(kb_id: str, question: str) -> None:
    """Query the Knowledge Base and print the answer with source citations.

    Uses the bedrock-agent-runtime client's retrieve_and_generate() which
    performs embedding, retrieval, and generation in a single managed API call.

    Args:
        kb_id: Bedrock Knowledge Base ID.
        question: Natural language question to answer.
    """
    # bedrock-agent-runtime is the runtime plane (queries)
    # bedrock-agent is the control plane (setup/management)
    bedrock_runtime = boto3.client("bedrock-agent-runtime")

    print(f"\n🤖 Querying Knowledge Base")
    print(f"Question: {question}\n")

    try:
        response = bedrock_runtime.retrieve_and_generate(
            input={"text": question},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": kb_id,
                    "modelArn": MODEL_ARN,
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            # Retrieve the 5 most semantically similar chunks
                            "numberOfResults": TOP_K_RESULTS,
                        }
                    },
                },
            },
        )
    except ClientError as e:
        print(f"❌ Error querying Knowledge Base: {e}")
        sys.exit(1)

    # --- Print the generated answer ---
    answer = response["output"]["text"]
    print("💬 Answer:")
    print(answer)

    # --- Print source citations ---
    citations = response.get("citations", [])
    if not citations:
        print("\n(No source citations returned)")
        return

    print(f"\n📚 Sources ({len(citations)} citation(s)):")
    source_num = 1
    for citation in citations:
        for ref in citation.get("retrievedReferences", []):
            location = ref.get("location", {})
            s3_location = location.get("s3Location", {})
            source_uri = s3_location.get("uri", "Unknown source")

            content_preview = ref.get("content", {}).get("text", "")[:200]

            print(f"\n{source_num}. Source: {source_uri}")
            if content_preview:
                print(f"   Content preview: {content_preview}...")
            source_num += 1


def main() -> None:
    """Entry point: parse arguments and run the query."""
    if len(sys.argv) < 3:
        print("Usage: python query_kb.py <KB_ID> \"Your question here\"")
        print("\nExample:")
        print("  python query_kb.py ABCDEF1234 \"How do I configure OpenSearch?\"")
        sys.exit(1)

    kb_id = sys.argv[1]
    question = " ".join(sys.argv[2:])

    print("=" * 60)
    print("🔍 Bedrock Knowledge Base — Query (Educational Example)")
    print("=" * 60)
    print(f"  Knowledge Base ID : {kb_id}")

    query_knowledge_base(kb_id, question)


if __name__ == "__main__":
    main()
