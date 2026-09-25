import re
from typing import List, Dict, Any

class ClauseExtractor:
    # Define keywords for each clause type
    CLAUSE_PATTERNS = {
        "Termination": r"(?i)(termination|terminate|terminating|terminated|end of agreement|expiration)",
        "Intellectual Property": r"(?i)(intellectual property|ip|trademark|copyright|patent|ownership of work)",
        "Liability": r"(?i)(liability|liable|indemnify|indemnification|hold harmless|limitation of liability)",
        "Confidentiality": r"(?i)(confidential|non-disclosure|nd[a|e]|trade secret|not disclose)",
        "Governing Law": r"(?i)(governing law|jurisdiction|applicable law|choice of law)",
        "Payment": r"(?i)(payment|fee|cost|invoice|compensation|royalty)",
        "Warranty": r"(?i)(warranty|representations|warrant|guarantee)",
        "Term": r"(?i)(term|duration|period|effective date|renewal)",
        "Force Majeure": r"(?i)(force majeure|act of god|unforeseeable)",
        "Assignment": r"(?i)(assignment|assign|transfer rights|novation)",
    }

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Scan the document text and return a list of detected clauses.
        """
        clauses = []
        for clause_type, pattern in self.CLAUSE_PATTERNS.items():
            # Find all matches in the text
            matches = re.finditer(pattern, text)
            for match in matches:
                # Capture a snippet of 100 chars before and after the keyword
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 150)
                snippet = text[start:end]
                
                clauses.append({
                    "type": clause_type,
                    "start_char": start,
                    "end_char": end,
                    "snippet": snippet.strip(),
                    "keyword": match.group(),
                    "confidence": 0.75  # placeholder confidence
                })
        return clauses
