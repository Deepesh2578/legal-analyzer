import os
import json
import logging
from typing import Dict, Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)


def extract_text_from_response(response) -> str:
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


class ComplianceAgent:
    _vectorstore = None

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set.")
            self.llm = None
            self.embeddings = None
            return

        models_to_try = ["gemini-3.6-flash"]
        self.llm = None
        for model_name in models_to_try:
            try:
                test_llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=self.api_key,
                    temperature=0,
                )
                test_llm.invoke("hi")
                self.llm = test_llm
                logger.info(f"Compliance LLM: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                continue

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001",
            google_api_key=self.api_key,
        )

        if ComplianceAgent._vectorstore is None:
            self._build_vectorstore()

    def _build_vectorstore(self):
        laws_dir = "/app/data/laws"
        persist_dir = "/app/data/chroma_db"

        if not os.path.isdir(laws_dir) or not os.listdir(laws_dir):
            logger.warning("No law documents found")
            return

        all_docs = []
        for filename in os.listdir(laws_dir):
            filepath = os.path.join(laws_dir, filename)
            try:
                if filename.endswith(".pdf"):
                    loader = PyPDFLoader(filepath)
                elif filename.endswith(".txt"):
                    loader = TextLoader(filepath, encoding="utf-8")
                else:
                    continue
                docs = loader.load_and_split()
                all_docs.extend(docs)
                logger.info(f"Loaded {filename}: {len(docs)} docs")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")

        if not all_docs:
            return

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(all_docs)
        logger.info(f"Split into {len(chunks)} chunks")

        ComplianceAgent._vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            collection_name="indian_laws",
            persist_directory=persist_dir,
        )
        logger.info("Vector store built")

    def check_clause(self, clause_type: str, clause_text: str) -> Dict[str, Any]:
        if not self.llm or ComplianceAgent._vectorstore is None:
            return {
                "clause_type": clause_type,
                "clause_text": clause_text[:200],
                "relevant_law": "N/A",
                "law_text": "N/A",
                "is_violation": None,
                "explanation": "Compliance agent not available."
            }

        try:
            retriever = ComplianceAgent._vectorstore.as_retriever(search_kwargs={"k": 5})
            relevant_docs = retriever.invoke(clause_text)
            
            # Deduplicate by source + content signature
            seen = set()
            unique_chunks = []
            for doc in relevant_docs:
                content = doc.page_content.strip()
                if not content or len(content) < 50:
                    continue
                # Use first 150 chars as signature + source file
                source = doc.metadata.get("source", "unknown")
                signature = (source, content[:150])
                if signature not in seen:
                    seen.add(signature)
                    unique_chunks.append(content)
            
            law_context = "\n\n---\n\n".join(unique_chunks)
            logger.info(f"Retrieved {len(relevant_docs)} chunks, {len(unique_chunks)} unique after dedup")
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            law_context = ""
        prompt = f"""You are a legal compliance expert. Determine if the following contract clause complies with Indian law.

CLAUSE TYPE: {clause_type}
CLAUSE TEXT: {clause_text}

RELEVANT LEGAL SECTIONS:
{law_context}

Answer in JSON:
{{
    "is_violation": true or false,
    "relevant_law": "Name of law and section",
    "explanation": "Brief explanation"
}}
Return ONLY JSON."""

        try:
            response = self.llm.invoke(prompt)
            content = extract_text_from_response(response).strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0]
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0]
            content = content.strip()
            result = json.loads(content)
            return {
                "clause_type": clause_type,
                "clause_text": clause_text[:200],
                "relevant_law": result.get("relevant_law", "N/A"),
                "law_text": law_context[:500],
                "is_violation": result.get("is_violation"),
                "explanation": result.get("explanation", ""),
            }
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return {
                "clause_type": clause_type,
                "clause_text": clause_text[:200],
                "relevant_law": "N/A",
                "law_text": law_context[:200],
                "is_violation": None,
                "explanation": f"Check failed: {str(e)}"
            }
