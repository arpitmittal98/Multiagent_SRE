import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import html2pdf from 'html2pdf.js';
import './IncidentReport.css';

const API_BASE = 'http://localhost:8000';

export default function IncidentReport({ report, serviceName }) {
    const [isExecuting, setIsExecuting] = useState(false);
    const [remediationLogs, setRemediationLogs] = useState([]);
    const terminalRef = useRef(null);

    useEffect(() => {
        if (terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [remediationLogs]);

    const handleExecute = async () => {
        setIsExecuting(true);
        setRemediationLogs(['> Starting AI Actionable Remediation Agent...']);

        try {
            const res = await fetch(`${API_BASE}/api/remediate/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service_name: serviceName, incident_summary: report }),
            });

            if (!res.ok) throw new Error(`Server error: ${res.status}`);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6).trim();
                        if (data === '[DONE]') {
                            setRemediationLogs((prev) => [...prev, '> \u2705 Remediation complete. Returning control.']);
                            continue;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.text) {
                                setRemediationLogs((prev) => [...prev, `> ${parsed.text}`]);
                            }
                        } catch {
                            // ignore parsing errors
                        }
                    }
                }
            }
        } catch (err) {
            setRemediationLogs((prev) => [...prev, `> \u274C Error executing remediation: ${err.message}`]);
        }
    };

    const handleExportPdf = () => {
        const element = document.getElementById('report-pdf-content');
        if (!element) return;

        // Generate timestamp YYYYMMDD_HHMMSS
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const hh = String(now.getHours()).padStart(2, '0');
        const min = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        const timestamp = `${yyyy}${mm}${dd}_${hh}${min}${ss}`;

        const safeServiceName = serviceName ? serviceName.replace(/[^a-zA-Z0-9]/g, '_') : 'UnknownService';
        const filename = `Incident_Report_${safeServiceName}_${timestamp}.pdf`;

        const opt = {
            margin: 15,
            filename: filename,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(element).save();
    };

    if (!report) return null;

    return (
        <div className="incident-report glass-card">
            <div className="incident-report__header">
                <div className="incident-report__badge">⚖️ WAR ROOM CONSENSUS</div>
                <div className="incident-report__actions">
                    <button
                        className="incident-report__action"
                        onClick={() => navigator.clipboard.writeText(report)}
                        title="Copy to clipboard"
                    >
                        📋 Copy
                    </button>
                    <button
                        className="incident-report__action"
                        onClick={handleExportPdf}
                        title="Download as PDF"
                    >
                        📄 Export PDF
                    </button>
                    <button
                        className="incident-report__action execute-btn"
                        onClick={handleExecute}
                        disabled={isExecuting}
                    >
                        {isExecuting ? '⏳ Executing...' : '⚡ Auto-Remediate'}
                    </button>
                </div>
            </div>

            <div className="incident-report__body" id="report-pdf-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </div>

            {remediationLogs.length > 0 && (
                <div className="remediation-terminal">
                    <div className="terminal-header">
                        <div className="terminal-dots">
                            <span className="dot dot-red"></span>
                            <span className="dot dot-amber"></span>
                            <span className="dot dot-green"></span>
                        </div>
                        <div className="terminal-title">SRE Actionable Agent</div>
                    </div>
                    <div className="terminal-body" ref={terminalRef}>
                        {remediationLogs.map((log, i) => (
                            <div key={i} className="terminal-line">{log}</div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
