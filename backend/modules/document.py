"""
Document Module - PDF RAG with FAISS Vector Store
==================================================
Gemini Embeddings + Gemini 1.5 Flash use karta hai PDF Q&A ke liye.
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

import asyncio
import io
import os
import hashlib
from typing import Dict


class DocumentModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        os.environ["GOOGLE_API_KEY"] = api_key

        # Gemini Embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001"
        )

        # Gemini Flash for Q&A
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

        self.vector_stores: Dict[str, FAISS] = {}

        self.qa_prompt = PromptTemplate(
            template="""You are a helpful document assistant. Use the context to answer the question.

Context:
{context}

Question: {question}

Instructions:
- Answer based ONLY on the provided context
- If not found, say "This information is not in the document"
- Be specific and clear

Answer:""",
            input_variables=["context", "question"]
        )

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(f"\n[Page {i+1}]\n{page_text}")
        return "\n".join(text_parts)

    def _generate_doc_id(self, filename: str, content: str) -> str:
        content_hash = hashlib.md5(content[:1000].encode()).hexdigest()[:8]
        clean_name = "".join(c if c.isalnum() else "_" for c in filename)
        return f"{clean_name}_{content_hash}"

    async def process_pdf(self, pdf_bytes: bytes, filename: str) -> dict:
        text = await asyncio.to_thread(self._extract_text_from_pdf, pdf_bytes)

        if not text.strip():
            raise ValueError("❌ PDF se text extract nahi hua. Text-based PDF use karo.")

        doc_id = self._generate_doc_id(filename, text)
        chunks = self.text_splitter.split_text(text)

        if not chunks:
            raise ValueError("❌ Document too small.")

        vector_store = await asyncio.to_thread(FAISS.from_texts, chunks, self.embeddings)
        self.vector_stores[doc_id] = vector_store

        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)

        return {
            "status": "✅ PDF successfully indexed!",
            "doc_id": doc_id,
            "filename": filename,
            "page_count": len(reader.pages),
            "chunk_count": len(chunks),
            "text_length": len(text),
            "message": f"Document ready. Ask anything about '{filename}'!"
        }

    async def query(self, question: str, doc_id: str) -> str:
        if doc_id not in self.vector_stores:
            raise ValueError(f"❌ Document '{doc_id}' nahi mila. Pehle PDF upload karo.")

        vector_store = self.vector_stores[doc_id]

        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=vector_store.as_retriever(search_kwargs={"k": 4}),
            chain_type_kwargs={"prompt": self.qa_prompt},
            return_source_documents=False
        )

        result = await asyncio.to_thread(qa_chain.invoke, {"query": question})
        return result["result"]

    def list_documents(self) -> list:
        return list(self.vector_stores.keys())

    def remove_document(self, doc_id: str) -> bool:
        if doc_id in self.vector_stores:
            del self.vector_stores[doc_id]
            return True
        return False
