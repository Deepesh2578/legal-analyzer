import os
import json
import logging
from typing import List, Dict, Any
import google.generativeai as genai

logger = logging.getLogger(__name__)


def extract_text_from_response(response) -> str:
    """Handle both old (str) and new (list) response formats."""
    try:
        text = response.text
        return text if isinstance(text, str) else str(text)
    except Exception:
        return str(response)


# Models to try in order (first working one wins)
MODELS_TO_TRY = [
    "gemini-3.6-flash",
]


class GeminiExtractor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Gemini extraction disabled.")
            self.client = None
            return

        genai.configure(api_key=self.api_key)

        # Try models in order until one works
        self.client = None
        self.model_name = None
        for model_name in MODELS_TO_TRY:
            try:
                test_client = genai.GenerativeModel(model_name)
                # Test with a tiny prompt
                test_client.generate_content("hi")
                self.client = test_client
                self.model_name = model_name
                logger.info(f"✅ Gemini extractor using: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {str(e)[:100]}")
                continue

        if self.client is None:
            logger.error("❌ No working Gemini model found for clause extraction")

    def extract(self, text: str) -> List[Dict[str, Any]]:
        if not self.client:
            return []

        if len(text) > 10000:
            text = text[:10000] + "\n...[truncated]"

        prompt = f"""
You are a legal document analyst. Analyze the following contract text and extract **all legal clauses**.

For each clause, provide:
1. **type**: The category (Termination, Liability, Confidentiality, Payment, Governing Law, Warranty, Intellectual Property, Force Majeure, Assignment, etc.)
2. **text**: The exact clause text (a snippet of around 100-200 characters)
3. **summary**: A brief 1-sentence summary of what the clause says
4. **risk_level**: "High", "Medium", or "Low"
5. **suggestion**: If risk is High or Medium, suggest improvements

Return the result as a **JSON list** only, no extra text.

Contract text:
\"\"\"{text}\"\"\"
"""

        try:
            response = self.client.generate_content(prompt)
            content = extract_text_from_response(response).strip()

            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0]
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0]

            clauses = json.loads(content)
            if isinstance(clauses, list):
                return clauses
            return []
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            return []
