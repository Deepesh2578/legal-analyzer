import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# Curated database of landmark Indian case laws mapped to clause types.
# In production, this would come from a legal API (e.g., Indian Kanoon).
CASE_LAW_DATABASE = {
    "Termination": [
        {
            "case_name": "Niranjan Shankar Golikari v. Century Spinning & Mfg. Co.",
            "court": "Supreme Court of India",
            "year": 1967,
            "citation": "AIR 1967 SC 1098",
            "summary": "Established that reasonable termination clauses are enforceable; only unreasonable restraints are void.",
            "relevance": "Confirms termination clauses with reasonable notice are valid under Indian contract law."
        },
        {
            "case_name": "Suresh Kumar Wadhwa v. State of M.P.",
            "court": "Supreme Court of India",
            "year": 2017,
            "citation": "(2017) 14 SCC 757",
            "summary": "Held that termination must follow the procedure specified in the contract.",
            "relevance": "Supports the enforceability of notice-period requirements in termination clauses."
        }
    ],
    "Liability": [
        {
            "case_name": "Bharathi Knitting Co. v. DHL Worldwide Express Courier",
            "court": "Supreme Court of India",
            "year": 1996,
            "citation": "AIR 1996 SC 2508",
            "summary": "Upheld limitation of liability clauses where the parties had expressly agreed to cap damages.",
            "relevance": "Establishes that liability caps are valid when mutually agreed."
        },
        {
            "case_name": "Central Inland Water Transport Corp. v. Brojo Nath Ganguly",
            "court": "Supreme Court of India",
            "year": 1986,
            "citation": "AIR 1986 SC 1571",
            "summary": "Held that unconscionable clauses in standard-form contracts may be struck down.",
            "relevance": "Warning: liability caps must not be unconscionable or one-sided."
        }
    ],
    "Confidentiality": [
        {
            "case_name": "Bombay Dyeing & Mfg. Co. Ltd. v. Mehar Karan Singh",
            "court": "Bombay High Court",
            "year": 2010,
            "citation": "2010 (112) Bom LR 375",
            "summary": "Recognized that confidentiality obligations are enforceable if clearly defined in scope and duration.",
            "relevance": "Confirms enforceability, but highlights need for clear definition."
        },
        {
            "case_name": "Zee Telefilms Ltd. v. Sundial Communications",
            "court": "Bombay High Court",
            "year": 2003,
            "citation": "2003 (5) Bom CR 404",
            "summary": "Held that breach of confidentiality can be restrained through injunctions.",
            "relevance": "Supports judicial enforcement of confidentiality clauses."
        }
    ],
    "Governing Law": [
        {
            "case_name": "Modi Entertainment Network v. W.S.G. Cricket Pte. Ltd.",
            "court": "Supreme Court of India",
            "year": 2003,
            "citation": "AIR 2003 SC 1177",
            "summary": "Upheld party autonomy in choosing foreign governing law and jurisdiction.",
            "relevance": "Confirms that selecting foreign law is valid under Indian conflict of laws."
        },
        {
            "case_name": "National Thermal Power Corp. v. Singer Co.",
            "court": "Supreme Court of India",
            "year": 1992,
            "citation": "AIR 1993 SC 998",
            "summary": "Held that foreign governing law does not oust Indian courts' jurisdiction if the contract has sufficient Indian connection.",
            "relevance": "Important limitation on foreign governing law clauses with Indian nexus."
        }
    ],
    "Payment": [
        {
            "case_name": "State of Karnataka v. Shreyas Papers Pvt. Ltd.",
            "court": "Supreme Court of India",
            "year": 2006,
            "citation": "(2006) 1 SCC 615",
            "summary": "Held that payment terms must be honored as per the contract.",
            "relevance": "Standard enforcement of payment obligations."
        }
    ],
    "Intellectual Property": [
        {
            "case_name": "Eastern Book Company v. D.B. Modak",
            "court": "Supreme Court of India",
            "year": 2008,
            "citation": "AIR 2008 SC 809",
            "summary": "Established the 'modicum of creativity' test for copyright in India.",
            "relevance": "Relevant for IP ownership clauses in contracts."
        }
    ],
    "Warranty": [
        {
            "case_name": "Karsandas H. Thacker v. The Saran Engineering Co. Ltd.",
            "court": "Supreme Court of India",
            "year": 1965,
            "citation": "AIR 1965 SC 1981",
            "summary": "Held that warranty clauses must be reasonable and specific.",
            "relevance": "Standard warranty enforceability."
        }
    ],
    "Force Majeure": [
        {
            "case_name": "Energy Watchdog v. CERC & Ors.",
            "court": "Supreme Court of India",
            "year": 2017,
            "citation": "(2017) 14 SCC 80",
            "summary": "Defined the scope of force majeure and its distinction from frustration of contract.",
            "relevance": "Landmark case for force majeure clause interpretation."
        }
    ],
    "Assignment": [
        {
            "case_name": "Khared & Co. v. Ramanlal",
            "court": "Bombay High Court",
            "year": 1958,
            "citation": "AIR 1959 Bom 150",
            "summary": "Held that assignment clauses must respect the original contract terms.",
            "relevance": "Standard assignment clause interpretation."
        }
    ],
}


class CitationAgent:
    """
    Finds relevant Indian case laws for contract clauses.
    Uses a curated database of landmark cases mapped to clause types.
    """

    def __init__(self):
        self.database = CASE_LAW_DATABASE

    def find_citations(self, clause_type: str, clause_text: str = "") -> List[Dict[str, Any]]:
        """
        Find relevant case laws for a given clause type.

        Args:
            clause_type: Type of clause (e.g., "Termination", "Liability")
            clause_text: Optional clause text for more context

        Returns:
            List of case law citations with metadata
        """
        # Normalize clause type to match our database keys
        normalized = self._normalize_clause_type(clause_type)

        if not normalized:
            logger.info(f"No citations found for clause type: {clause_type}")
            return []

        cases = self.database.get(normalized, [])
        logger.info(f"Found {len(cases)} cases for clause type: {normalized}")
        return cases

    def _normalize_clause_type(self, clause_type: str) -> str:
        """Map arbitrary clause type names to our database keys."""
        if not clause_type:
            return ""

        ct = clause_type.lower().strip()

        # Direct matches
        mapping = {
            "termination": "Termination",
            "liability": "Liability",
            "limitation of liability": "Liability",
            "indemnity": "Liability",
            "indemnification": "Liability",
            "confidentiality": "Confidentiality",
            "non-disclosure": "Confidentiality",
            "nda": "Confidentiality",
            "governing law": "Governing Law",
            "jurisdiction": "Governing Law",
            "choice of law": "Governing Law",
            "payment": "Payment",
            "fees": "Payment",
            "compensation": "Payment",
            "intellectual property": "Intellectual Property",
            "ip": "Intellectual Property",
            "copyright": "Intellectual Property",
            "patent": "Intellectual Property",
            "warranty": "Warranty",
            "warranties": "Warranty",
            "force majeure": "Force Majeure",
            "act of god": "Force Majeure",
            "assignment": "Assignment",
            "transfer": "Assignment",
        }

        for key, value in mapping.items():
            if key in ct:
                return value

        return ""
