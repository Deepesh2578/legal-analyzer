import { useState, useEffect, useCallback } from 'react';
import { api } from './api';
import type { DocumentItem, RiskReport, ComplianceReport, TraceReport } from './api';

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const riskColor = (level?: string) => {
  if (level === 'High') return 'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700';
  if (level === 'Medium') return 'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/40 dark:text-yellow-300 dark:border-yellow-700';
  return 'bg-green-100 text-green-700 border-green-300 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700';
};

const statusColor = (status: string) => {
  if (status === 'parsed') return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300';
  if (status === 'processing') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
  if (status === 'failed') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
  return 'bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-slate-300';
};

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────

function Gauge({ score, level }: { score: number; level: string }) {
  const barColor =
    level === 'High' ? 'bg-red-500' : level === 'Medium' ? 'bg-yellow-500' : 'bg-green-500';
  return (
    <div>
      <div className="flex items-end gap-4 mb-3">
        <div className="text-4xl font-bold text-slate-900 dark:text-slate-100">{score}</div>
        <div className="text-sm text-slate-500 dark:text-slate-400 pb-1">/ 100</div>
        <span className={`ml-auto px-3 py-1 rounded-full text-sm font-medium border ${riskColor(level)}`}>
          {level} Risk
        </span>
      </div>
      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3 overflow-hidden">
        <div
          className={`${barColor} h-3 transition-all duration-700`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}

function Timeline({ steps }: { steps: TraceReport['reasoning_trace'] }) {
  const dotColor = (s: string) =>
    s === 'success' ? 'bg-green-500' : s === 'failed' ? 'bg-red-500' : 'bg-gray-400';
  return (
    <div className="relative pl-6">
      <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-slate-200 dark:bg-slate-700" />
      {steps.map((step, i) => (
        <div key={i} className="relative mb-4 last:mb-0">
          <div className={`absolute -left-[18px] top-1.5 w-3 h-3 rounded-full ${dotColor(step.status)} ring-4 ring-white dark:ring-slate-800`} />
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-sm font-semibold text-slate-800 dark:text-slate-100">{step.step}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">{(step.duration_ms / 1000).toFixed(2)}s</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${dotColor(step.status)} text-white`}>
              {step.status}
            </span>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{step.message}</p>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Main App
// ─────────────────────────────────────────────

function App() {
  const [status, setStatus] = useState<string>('Checking...');
  const [file, setFile] = useState<File | null>(null);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadPct, setUploadPct] = useState(0);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeDoc, setActiveDoc] = useState<number | null>(null);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);
  const [trace, setTrace] = useState<TraceReport | null>(null);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // 🌓 Dark mode: initialize from localStorage or system preference
  const [dark, setDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Apply theme to <html>
  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [dark]);

  useEffect(() => {
    api.ping()
      .then(() => setStatus('✅ Backend running'))
      .catch(() => setStatus('❌ Backend offline'));
    fetchDocuments();
  }, []);

  useEffect(() => {
    const anyProcessing = documents.some(d => d.status === 'processing' || d.status === 'pending');
    if (!anyProcessing) return;
    const t = setInterval(fetchDocuments, 5000);
    return () => clearInterval(t);
  }, [documents]);

  const fetchDocuments = async () => {
    try {
      const res = await api.listDocuments();
      const docs = res.data.documents || [];
      
      docs.sort((a: DocumentItem, b: DocumentItem) =>
	new Date(b.created_at).getTime() -new Date(a.created_at).getTime()
      );	
	
      setDocuments(docs);
    } catch (e) {
      console.error(e);
    }
  };

  const doUpload = useCallback(async (f: File) => {
    setUploadMsg('⏳ Uploading...');
    setUploadPct(0);
    try {
      const res = await api.upload(f, setUploadPct);
      setUploadMsg(`✅ Uploaded! ID: ${res.data.document_id} — processing...`);
      setFile(null);
      setTimeout(fetchDocuments, 2000);
    } catch (e: any) {
      setUploadMsg(`❌ Upload failed: ${e?.response?.data?.detail || e.message}`);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    if (f) doUpload(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) {
      const ext = f.name.split('.').pop()?.toLowerCase();
      if (ext === 'pdf' || ext === 'docx') {
        setFile(f);
        doUpload(f);
      } else {
        setUploadMsg('❌ Only PDF and DOCX are supported');
      }
    }
  };

const loadRisk = async (id: number, displayIndex: number) => {
  setActiveDoc(id);
  setBusy('risk');
  try {
    const res = await api.getRiskReport(id);
    setRisk({ ...res.data, document_id: displayIndex });
    setCompliance(null);
    setTrace(null);
  } catch (e: any) {
    alert(`Risk report not ready: ${e?.response?.data?.detail || e.message}`);
  } finally {
    setBusy(null);
  }
};

const loadCompliance = async (id: number, displayIndex: number) => {
  setActiveDoc(id);
  setBusy('compliance');
  try {
    const res = await api.getCompliance(id);
    setCompliance({ ...res.data, document_id: displayIndex });
    setRisk(null);
    setTrace(null);
  } catch (e: any) {
    alert(`Compliance failed: ${e?.response?.data?.detail || e.message}`);
  } finally {
    setBusy(null);
  }
};
const loadTrace = async (id: number, displayIndex: number) => {
  setActiveDoc(id);
  setBusy('trace');
  try {
    const res = await api.getTrace(id);
    setTrace({ ...res.data, document_id: displayIndex });
    setRisk(null);
    setCompliance(null);
  } catch (e: any) {
    alert(`Trace not available: ${e?.response?.data?.detail || e.message}`);
  } finally {
    setBusy(null);
  }
};
  const downloadReport = async (id: number, filename: string) => {
    setDownloading(id);
    try {
      const res = await api.downloadReport(id);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${filename.replace(/\.(pdf|docx)$/i, '')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert('Report generation failed. Check backend logs.');
    } finally {
      setDownloading(null);
    }
  };

  const handleDelete = async (id: number, filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await api.deleteDocument(id);
      if (activeDoc === id) {
        setActiveDoc(null); setRisk(null); setCompliance(null); setTrace(null);
      }
      fetchDocuments();
    } catch (e) {
      alert('Delete failed');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-slate-800 shadow-sm border-b border-slate-200 dark:border-slate-700 sticky top-0 z-20 transition-colors">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">📄</span>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Legal Contract Analyzer</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">AI-powered contract review with LangGraph</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className={`text-sm px-3 py-1 rounded-full font-medium hidden sm:inline ${
              status.includes('✅')
                ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            }`}>
              {status}
            </span>

            {/* 🌓 Dark/Light Toggle */}
            <button
              onClick={() => setDark(!dark)}
              className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 flex items-center justify-center text-lg transition-all"
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label="Toggle dark mode"
            >
              {dark ? '☀️' : '🌙'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Upload Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-colors">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">📤 Upload a Contract</h2>

          <label
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
              dragging
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                : 'border-slate-300 dark:border-slate-600 hover:border-blue-400 hover:bg-slate-50 dark:hover:bg-slate-700/40'
            }`}
          >
            <input type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileChange} />
            <div className="text-5xl mb-3">📁</div>
            <p className="text-slate-700 dark:text-slate-200 font-medium">
              {file ? file.name : 'Drop a PDF or DOCX here, or click to browse'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Max 10 MB • PDF, DOCX</p>
          </label>

          {uploadPct > 0 && uploadPct < 100 && (
            <div className="mt-4">
              <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
                <span>Uploading...</span><span>{uploadPct}%</span>
              </div>
              <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 transition-all" style={{ width: `${uploadPct}%` }} />
              </div>
            </div>
          )}

          {uploadMsg && (
            <p className={`mt-3 text-sm ${
              uploadMsg.startsWith('✅') ? 'text-green-600 dark:text-green-400' :
              uploadMsg.startsWith('❌') ? 'text-red-600 dark:text-red-400' :
              'text-slate-600 dark:text-slate-300'
            }`}>{uploadMsg}</p>
          )}
        </div>

        {/* Documents List */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-colors">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">📋 Documents ({documents.length})</h2>
            <button onClick={fetchDocuments} className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
              ⟳ Refresh
            </button>
          </div>

          {documents.length === 0 ? (
            <p className="text-slate-500 dark:text-slate-400 text-sm py-8 text-center">
              No documents yet. Upload one to get started.
            </p>
          ) : (
            <div className="space-y-3">
              {documents.map((d, index) => (
                <div
                  key={d.id}
                  className={`border rounded-lg p-4 transition-all ${
                    activeDoc === d.id
                      ? 'border-blue-400 bg-blue-50/50 dark:bg-blue-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
			<span className="font-mono text-xs text-slate-400 dark:text-slate-500">#{index + 1}</span>
                        <span className="font-medium text-slate-800 dark:text-slate-100 truncate">{d.filename}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(d.status)}`}>
                          {d.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                        {d.word_count || 0} words • {new Date(d.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => loadRisk(d.id, index +1)}
                        disabled={d.status !== 'parsed' || busy === 'risk'}
                        className="text-xs px-3 py-1.5 rounded-md bg-purple-100 text-purple-700 hover:bg-purple-200 dark:bg-purple-900/40 dark:text-purple-300 dark:hover:bg-purple-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        📊 Risk
                      </button>
                      <button
                        onClick={() => loadCompliance(d.id, index +1)}
                        disabled={d.status !== 'parsed' || busy === 'compliance'}
                        className="text-xs px-3 py-1.5 rounded-md bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        ⚖️ Compliance
                      </button>
                      <button
                        onClick={() => loadTrace(d.id, index +1)}
                        disabled={d.status !== 'parsed' || busy === 'trace'}
                        className="text-xs px-3 py-1.5 rounded-md bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        🔍 Trace
                      </button>
                      <button
                        onClick={() => downloadReport(d.id, d.filename)}
                        disabled={d.status !== 'parsed' || downloading === d.id}
                        className="text-xs px-3 py-1.5 rounded-md bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/40 dark:text-green-300 dark:hover:bg-green-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {downloading === d.id ? '⏳ Generating...' : '⬇️ Report'}
                      </button>
                      <button
                        onClick={() => handleDelete(d.id, d.filename)}
                        className="text-xs px-2 py-1.5 rounded-md text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30"
                        title="Delete"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Risk Dashboard */}
        {risk && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-colors">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-4">
              📊 Risk Dashboard — Doc #{risk.document_id}
            </h2>

            <Gauge score={risk.overall_risk_score} level={risk.risk_level} />

            <div className="grid grid-cols-3 gap-3 mt-5">
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-600 dark:text-red-400">{risk.breakdown.high}</div>
                <div className="text-xs text-red-700 dark:text-red-300 mt-1">High Risk</div>
              </div>
              <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{risk.breakdown.medium}</div>
                <div className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">Medium Risk</div>
              </div>
              <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">{risk.breakdown.low}</div>
                <div className="text-xs text-green-700 dark:text-green-300 mt-1">Low Risk</div>
              </div>
            </div>

            <p className="text-sm text-slate-700 dark:text-slate-300 mt-5 leading-relaxed">{risk.summary}</p>

            <h3 className="font-semibold text-slate-800 dark:text-slate-100 mt-6 mb-3">Top Risks</h3>
            <div className="space-y-3">
              {risk.top_risks?.map((c, i) => (
                <div key={i} className={`border-l-4 rounded-r-lg p-3 ${riskColor(c.risk_level)}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm">{c.type}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/60 dark:bg-slate-900/40">{c.risk_level}</span>
                  </div>
                  <p className="text-sm italic text-slate-700 dark:text-slate-300">"{c.text}"</p>
                  {c.summary && <p className="text-xs text-slate-600 dark:text-slate-400 mt-2">{c.summary}</p>}
                  {c.suggestion && (
                    <p className="text-xs text-slate-700 dark:text-slate-300 mt-2 bg-white/60 dark:bg-slate-900/40 rounded p-2">
                      <b>💡 Suggestion:</b> {c.suggestion}
                    </p>
                  )}
                </div>
              ))}
            </div>

            <details className="mt-5">
              <summary className="cursor-pointer text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200">
                Show all {risk.clauses.length} clauses
              </summary>
              <div className="mt-3 space-y-2">
                {risk.clauses.map((c, i) => (
                  <div key={i} className="border border-slate-200 dark:border-slate-700 rounded p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm text-slate-800 dark:text-slate-100">{c.type}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${riskColor(c.risk_level)}`}>
                        {c.risk_level}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400">{c.text}</p>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        {/* Compliance Panel */}
        {compliance && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-colors">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                ⚖️ Compliance — Doc #{compliance.document_id}
              </h2>
              <div className="flex items-center gap-3">
                <span className={`text-2xl font-bold ${
                  compliance.compliance_score >= 80 ? 'text-green-600 dark:text-green-400' :
                  compliance.compliance_score >= 50 ? 'text-yellow-600 dark:text-yellow-400' :
                  'text-red-600 dark:text-red-400'
                }`}>
                  {compliance.compliance_score}%
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {compliance.total_checks} checked, {compliance.violations} violations
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {compliance.compliance_results.map((r, i) => {
                const badge =
                  r.is_violation === true ? { t: '❌ Violation', c: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' } :
                  r.is_violation === false ? { t: '✅ Compliant', c: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' } :
                  { t: '⚠️ Unverified', c: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' };
                return (
                  <div key={i} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <span className="font-semibold text-slate-800 dark:text-slate-100">{r.clause_type}</span>
                      <span className={`text-xs px-2 py-1 rounded-full ${badge.c}`}>{badge.t}</span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 italic mb-2">"{r.clause_text}"</p>
                    {r.relevant_law && r.relevant_law !== 'N/A' && (
                      <p className="text-xs text-blue-700 dark:text-blue-400 mb-1"><b>Law:</b> {r.relevant_law}</p>
                    )}
                    {r.explanation && (
                      <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{r.explanation}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Trace Panel */}
        {trace && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 transition-colors">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-5">
              🔍 Agent Reasoning Trace — Doc #{trace.document_id}
            </h2>
            <Timeline steps={trace.reasoning_trace} />
          </div>
        )}
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 mt-12 transition-colors">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center text-xs text-slate-500 dark:text-slate-400">
          Built with React, FastAPI, LangGraph, LangChain, Gemini & Tailwind CSS
        </div>
      </footer>
    </div>
  );
}

export default App;
