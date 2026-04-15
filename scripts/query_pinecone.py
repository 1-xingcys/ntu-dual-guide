from __future__ import annotations

import os
from pathlib import Path
import argparse
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import query_vectors_pinecone
from ntu_dual_guide_ingestion.vector_clients import require_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Pinecone and print top-k matches.")
    parser.add_argument("query", help="Natural language query text.")
    parser.add_argument(
        "--dataset-version",
        required=True,
        help="Dataset version / default namespace to query.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Pinecone namespace. Defaults to dataset_version.",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model to use for the query.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of matches to return.",
    )
    parser.add_argument(
        "--pinecone-api-version",
        default="2026-04",
        help="Pinecone API version header to send.",
    )
    parser.add_argument(
        "--filter-json",
        default=None,
        help="Raw Pinecone filter JSON string.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    namespace = args.namespace or args.dataset_version
    openai_api_key = require_env("OPENAI_API_KEY")
    pinecone_api_key = require_env("PINECONE_API_KEY")
    pinecone_index_host = require_env("PINECONE_INDEX_HOST")

    query_vector = embed_texts_openai(
        [args.query],
        model=args.embedding_model,
        api_key=openai_api_key,
    )[0]
    filter_payload = json.loads(args.filter_json) if args.filter_json else None
    response = query_vectors_pinecone(
        query_vector,
        namespace=namespace,
        index_host=pinecone_index_host,
        api_key=pinecone_api_key,
        top_k=args.top_k,
        api_version=args.pinecone_api_version,
        filter=filter_payload,
    )
    print(json.dumps(format_response(response), ensure_ascii=False, indent=2))


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def format_response(response: dict) -> dict:
    matches = []
    for item in response.get("matches", []):
        metadata = item.get("metadata") or {}
        matches.append(
            {
                "id": item.get("id"),
                "score": item.get("score"),
                "source_id": metadata.get("source_id"),
                "doc_type": metadata.get("doc_type"),
                "chunk_type": metadata.get("chunk_type"),
                "chunk_title": metadata.get("chunk_title"),
                "text": metadata.get("chunk_text"),
                "metadata": metadata,
            }
        )
    return {
        "namespace": response.get("namespace"),
        "matches": matches,
    }


if __name__ == "__main__":
    main()
