"""Phase 6: interactive fitness RAG chat. Run: streamlit run app.py"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from src.llm_engine import LLMServiceError, RAGChatService, load_project_env


ROOT = Path(__file__).resolve().parent
IMAGES_DIR = (ROOT / "data" / "images").resolve()


def image_for_source(raw_path: str | None) -> Path | None:
    """Only display images bundled with this project."""
    if not raw_path:
        return None
    candidate = (ROOT / raw_path).resolve()
    try:
        candidate.relative_to(IMAGES_DIR)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def render_answer(result: dict) -> None:
    st.markdown(result["answer"])
    if result.get("avoid_exercises"):
        with st.expander("ท่าที่กราฟระบุให้หลีกเลี่ยง", expanded=False):
            for item in result["avoid_exercises"]:
                st.write(f"• {item.get('exercise', '')} ({item.get('condition', '')})")

    sources = result.get("sources") or []
    with st.expander(f"แหล่งอ้างอิงจากคู่มือ ({len(sources)})", expanded=bool(sources)):
        if not sources:
            st.caption("ไม่มีท่าที่อ้างอิงได้ในผลค้นหานี้")
        for item in sources:
            page = item.get("page") or "ไม่ระบุ"
            st.write(f"{item.get('title') or 'ไม่ระบุชื่อ'} — หน้า {page}")
            image = image_for_source(item.get("image_path"))
            if image:
                st.image(str(image), width=360)

    with st.expander("ข้อมูลการทำงาน"):
        st.write(f"การค้นหา: {result.get('retrieval_mode')} | LLM: {result.get('model') or 'ไม่ได้เรียก'}")
        if result.get("graph_backend"):
            st.write(f"แหล่งกราฟ: {result['graph_backend']}")
        st.write(
            f"เวลา: ค้นหา {result.get('retrieval_latency_ms') or 0:.1f} ms, "
            f"LLM {result.get('llm_latency_ms') or 0:.1f} ms, "
            f"รวม {result.get('total_latency_ms') or 0:.1f} ms"
        )
        if result.get("usage"):
            st.json(result["usage"])


def main() -> None:
    st.set_page_config(page_title="Fitness RAG Assistant", page_icon="🏋️", layout="wide")
    st.title("ผู้ช่วยการใช้เครื่องออกกำลังกาย")
    st.caption("ตอบจากคู่มือสถานกีฬาและสุขภาพ พร้อมแหล่งอ้างอิงและภาพประกอบ")
    st.info("ข้อมูลนี้ใช้ประกอบการเรียน ไม่ใช่การวินิจฉัยหรือคำแนะนำทางการแพทย์")
    load_project_env()

    with st.sidebar:
        st.header("ตั้งค่าการถาม")
        provider_label = st.selectbox(
            "โมเดลตอบ",
            ["Local: Qwen2.5 3B", "Local: Qwen3.5 9B (Q4_K_M)", "API: OpenRouter"],
        )
        provider = "local" if provider_label.startswith("Local") else "openrouter"
        local_model = {
            "Local: Qwen2.5 3B": "qwen2.5:3b",
            "Local: Qwen3.5 9B (Q4_K_M)": "qwen3.5:9b-q4_K_M",
        }.get(provider_label)
        mode = st.selectbox("วิธีค้น", ["auto", "dense", "graph", "hybrid"], index=0)
        top_k = st.slider("จำนวนแหล่งข้อมูล", min_value=1, max_value=8, value=4)
        if provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY", "").strip():
            st.warning("ใส่ OPENROUTER_API_KEY ใน .env ก่อนใช้ API")
        if st.button("ล้างประวัติแชต"):
            st.session_state["messages"] = []
            st.rerun()
        messages = st.session_state.get("messages", [])
        if messages:
            st.download_button(
                "ดาวน์โหลดประวัติ (JSON)",
                data=json.dumps(messages, ensure_ascii=False, indent=2),
                file_name="fitness_chat_history.json",
                mime="application/json",
            )

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and message.get("result"):
                render_answer(message["result"])
            else:
                st.markdown(message["content"])

    query = st.chat_input("เช่น ปวดเข่าควรหลีกเลี่ยงท่าไหน")
    if not query:
        return
    if len(query) > 800:
        st.error("คำถามยาวเกิน 800 ตัวอักษร กรุณาย่อคำถาม")
        return
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        with st.spinner("กำลังค้นคู่มือและสร้างคำตอบ..."):
            try:
                if "rag_chat_service" not in st.session_state:
                    st.session_state["rag_chat_service"] = RAGChatService()
                result = st.session_state["rag_chat_service"].answer(
                    query, provider=provider, mode=mode, top_k=top_k, local_model=local_model
                )
            except LLMServiceError as exc:
                st.error(str(exc))
                return
            except Exception:
                st.error("ระบบขัดข้อง กรุณาดูรายละเอียดใน Terminal ที่เปิด Streamlit")
                raise
            render_answer(result)
    st.session_state["messages"].append({"role": "assistant", "result": result})


if __name__ == "__main__":
    main()
