"""Interactive Phase 5 CLI: python scripts/chat_phase5.py --provider local"""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_engine import LLMServiceError, RAGChatService


def main() -> int:
    parser = argparse.ArgumentParser(description="Fitness RAG chat via Ollama or OpenRouter")
    parser.add_argument("--provider", choices=["local", "openrouter"], default="local")
    parser.add_argument("--mode", choices=["auto", "dense", "graph", "hybrid"], default="auto")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--query", help="One question; omit to enter interactive mode")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    try:
        chat = RAGChatService()
    except Exception as exc:
        print(f"เริ่มระบบค้นหาไม่ได้: {exc}", file=sys.stderr)
        return 1

    def ask(query: str) -> None:
        result = chat.answer(query, provider=args.provider, mode=args.mode, top_k=args.top_k)
        print("\nคำตอบ:\n" + result["answer"])
        print("\nข้อมูลการทำงาน:")
        print(json.dumps({key: result[key] for key in (
            "provider", "model", "retrieval_mode", "sources", "avoid_exercises",
            "usage", "retrieval_latency_ms", "llm_latency_ms", "total_latency_ms"
        )}, ensure_ascii=False, indent=2))

    if args.query:
        try:
            ask(args.query)
        except (LLMServiceError, ValueError) as exc:
            print(f"เกิดข้อผิดพลาด: {exc}", file=sys.stderr)
            return 1
        return 0

    print("พิมพ์คำถามเกี่ยวกับการออกกำลังกาย; พิมพ์ exit เพื่อออก")
    while True:
        try:
            query = input("\nถาม> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if query.lower() in ("exit", "quit"):
            return 0
        if not query:
            continue
        try:
            ask(query)
        except (LLMServiceError, ValueError) as exc:
            print(f"เกิดข้อผิดพลาด: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
