"""MilkLab RAG Chatbot (S3).

Run locally: streamlit run app.py
Deploy: push to GitHub then Actions deploys to HuggingFace Space

นักศึกษาต้องเติม TODO 5 จุด ใน Session 3 Lab 2.2
"""

import os
import faiss
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from google import genai

load_dotenv()

@st.cache_resource
def load_index():
    """TODO 1+2+3: โหลด menu_kb.md, split เป็น chunk, encode ด้วย sentence-transformers,
    สร้าง faiss index. Cache เพราะโหลด model ครั้งแรกใช้เวลา 30 วินาที

    Returns: (model, index, chunks_list)
    """
    with open("menu_kb.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split into chunks (e.g. by double newline)
    chunks_list = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
    
    # Load sentence transformer model
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    embeddings = model.encode(chunks_list)
    
    # Create Faiss index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    return model, index, chunks_list


def retrieve_top_k(query: str, model, index, chunks: list[str], k: int = 3) -> list[str]:
    """TODO 4: encode query, search index, return top-k chunks"""
    query_vector = model.encode([query])
    distances, indices = index.search(np.array(query_vector).astype('float32'), k)
    return [chunks[i] for i in indices[0]]


def generate_answer(query: str, context_chunks: list[str]) -> str:
    """TODO 5: ส่ง query + context ไป Gemini, return answer"""
    context = "\n\n".join(context_chunks)
    prompt = f"ตอบคำถามจากข้อมูลต่อไปนี้เท่านั้น ถ้าไม่มีในข้อมูลให้บอกว่าไม่รู้\n\nข้อมูล:\n{context}\n\nคำถาม: {query}"
    
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass
    if not api_key:
        return "⚠️ กรุณาตั้งค่า GOOGLE_API_KEY ใน .env หรือใน Space Settings (Secrets) ก่อนใช้งานครับ"
        
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text or ""


def main():
    st.set_page_config(page_title="MilkLab° RAG", page_icon="🥛")
    st.title("MilkLab° RAG Chatbot")
    st.caption("ถามอะไรเกี่ยวกับ MilkLab ได้ ตอบจาก menu_kb.md")

    try:
        model, index, chunks = load_index()
    except NotImplementedError as exc:
        st.error(f"TODO not implemented: {exc}")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("ถามอะไรเกี่ยวกับ MilkLab"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("กำลังค้นข้อมูล..."):
                context = retrieve_top_k(prompt, model, index, chunks)
                answer = generate_answer(prompt, context)
            st.write(answer)
            with st.expander("Source chunks"):
                for i, c in enumerate(context, 1):
                    st.markdown(f"**[{i}]** {c}")
        st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
