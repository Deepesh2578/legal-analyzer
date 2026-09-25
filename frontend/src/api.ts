import axios from 'axios';

export const API_BASE = 'http://localhost:8000';

export interface DocumentItem {
  id: number;
  filename: string;
  status: string;
  progress: number;
  word_count?: number;
  created_at: string;
}

export interface Clause {
  type: string;
  text?: string;
  snippet?: string;
  summary?: string;
  risk_level?: string;
  suggestion?: string | null;
  keyword?: string;
  confidence?: number;
}

export interface RiskReport {
  document_id: number;
  overall_risk_score: number;
  risk_level: string;
  summary: string;
  breakdown: { high: number; medium: number; low: number };
  top_risks: Clause[];
  clauses: Clause[];
  total_clauses: number;
}

export interface ComplianceResult {
  clause_type: string;
  clause_text: string;
  relevant_law: string;
  law_text: string;
  is_violation: boolean | null;
  explanation: string;
}

export interface ComplianceReport {
  document_id: number;
  compliance_score: number;
  total_checks: number;
  violations: number;
  compliance_results: ComplianceResult[];
}

export interface TraceStep {
  step: string;
  status: string;
  duration_ms: number;
  message: string;
}

export interface TraceReport {
  document_id: number;
  filename: string;
  status: string;
  reasoning_trace: TraceStep[];
}

export const api = {
  ping: () => axios.get(`${API_BASE}/ping`),
  listDocuments: () => axios.get(`${API_BASE}/api/documents/`),
  upload: (file: File, onProgress?: (p: number) => void) => {
    const form = new FormData();
    form.append('file', file);
    return axios.post(`${API_BASE}/api/documents/upload`, form, {
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded * 100) / e.total));
      },
    });
  },
  getRiskReport: (id: number) => axios.get<RiskReport>(`${API_BASE}/api/documents/${id}/risk-report`),
  getCompliance: (id: number) => axios.get<ComplianceReport>(`${API_BASE}/api/documents/${id}/compliance`),
  getTrace: (id: number) => axios.get<TraceReport>(`${API_BASE}/api/documents/${id}/trace`),
  getClauses: (id: number) => axios.get(`${API_BASE}/api/documents/${id}/clauses`),
  downloadReport: (id: number) =>
    axios.get(`${API_BASE}/api/documents/${id}/report`, {
      responseType: 'blob',
      timeout: 180000,
    }),
  deleteDocument: (id: number) => axios.delete(`${API_BASE}/api/documents/${id}`),
};
