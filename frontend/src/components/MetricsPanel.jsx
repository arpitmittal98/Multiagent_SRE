import { useState, useEffect } from 'react';
import './MetricsPanel.css';

const API_BASE = 'http://localhost:8000';

export default function MetricsPanel({ metrics }) {
    const [activeTab, setActiveTab] = useState('session');
    const [ddMetrics, setDdMetrics] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (activeTab === 'datadog' && !ddMetrics) {
            setLoading(true);
            fetch(`${API_BASE}/api/llm/metrics`)
                .then(res => res.json())
                .then(data => setDdMetrics(data))
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        }
    }, [activeTab, ddMetrics]);

    if (!metrics) return null;

    const { agentTurns = 0, debateMessages = 0, elapsed = 0, currentRound = '-' } = metrics;

    const formatTime = (sec) => {
        if (!sec) return '0s';
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
    };

    const formatNumber = (num) => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    };

    const estimatedPhases = 5;
    const completedPhases = agentTurns >= 6 ? (debateMessages > 6 ? 5 : 4)
        : agentTurns >= 3 ? 3
            : agentTurns > 0 ? 2
                : (elapsed > 0 ? 1 : 0);
    const progressPercent = Math.min(Math.round((completedPhases / estimatedPhases) * 100), 100);

    return (
        <div className="metrics-panel glass-card">

            <div className="metrics-panel__tabs">
                <button
                    className={`metrics-panel__tab ${activeTab === 'session' ? 'active' : ''}`}
                    onClick={() => setActiveTab('session')}
                >
                    Session Stats
                </button>
                <button
                    className={`metrics-panel__tab ${activeTab === 'datadog' ? 'active' : ''}`}
                    onClick={() => setActiveTab('datadog')}
                >
                    DD Telemetry
                </button>
            </div>

            {activeTab === 'session' && (
                <div className="metrics-panel__content animation-fade-in">
                    <div className="metrics-panel__progress-wrap">
                        <div className="metrics-panel__progress-bar">
                            <div
                                className="metrics-panel__progress-fill"
                                style={{ width: `${progressPercent}%` }}
                            />
                        </div>
                        <span className="metrics-panel__progress-label">{progressPercent}%</span>
                    </div>

                    <div className="metrics-panel__grid">
                        <div className="metrics-panel__stat">
                            <span className="metrics-panel__stat-value metrics-panel__stat-value--cyan">
                                {formatTime(elapsed)}
                            </span>
                            <span className="metrics-panel__stat-label">Elapsed</span>
                        </div>
                        <div className="metrics-panel__stat">
                            <span className="metrics-panel__stat-value metrics-panel__stat-value--purple">
                                {debateMessages}
                            </span>
                            <span className="metrics-panel__stat-label">Agent Turns</span>
                        </div>
                        <div className="metrics-panel__stat">
                            <span className="metrics-panel__stat-value metrics-panel__stat-value--blue">
                                {currentRound}
                            </span>
                            <span className="metrics-panel__stat-label">Current Phase</span>
                        </div>
                        <div className="metrics-panel__stat">
                            <span className="metrics-panel__stat-value metrics-panel__stat-value--green">
                                3
                            </span>
                            <span className="metrics-panel__stat-label">Agents</span>
                        </div>
                    </div>

                    <div className="metrics-panel__legend">
                        <div className="metrics-panel__legend-item">
                            <span className="metrics-panel__legend-dot" style={{ background: 'var(--accent-blue)' }} />
                            <span>SRE Engineer</span>
                        </div>
                        <div className="metrics-panel__legend-item">
                            <span className="metrics-panel__legend-dot" style={{ background: 'var(--accent-amber)' }} />
                            <span>Product Manager</span>
                        </div>
                        <div className="metrics-panel__legend-item">
                            <span className="metrics-panel__legend-dot" style={{ background: 'var(--accent-red)' }} />
                            <span>Security Analyst</span>
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'datadog' && (
                <div className="metrics-panel__content animation-fade-in">
                    {loading || !ddMetrics ? (
                        <div className="metrics-panel__loading">
                            <div className="datadog-spinner"></div>
                            <span>Fetching APM Spans...</span>
                        </div>
                    ) : (
                        <>
                            <div className="metrics-panel__dd-header">
                                <span className="dd-logo">🤖</span>
                                <span>LLM Observability</span>
                            </div>

                            <div className="metrics-panel__grid">
                                <div className="metrics-panel__stat">
                                    <span className="metrics-panel__stat-value metrics-panel__stat-value--blue">
                                        {formatNumber(ddMetrics.total_tokens)}
                                    </span>
                                    <span className="metrics-panel__stat-label">Total Tokens</span>
                                </div>
                                <div className="metrics-panel__stat">
                                    <span className="metrics-panel__stat-value metrics-panel__stat-value--purple">
                                        {formatNumber(ddMetrics.total_requests)}
                                    </span>
                                    <span className="metrics-panel__stat-label">Global Requests</span>
                                </div>
                                <div className="metrics-panel__stat">
                                    <span className="metrics-panel__stat-value metrics-panel__stat-value--green">
                                        ${ddMetrics.estimated_cost}
                                    </span>
                                    <span className="metrics-panel__stat-label">Est. Cost</span>
                                </div>
                                <div className="metrics-panel__stat">
                                    <span className="metrics-panel__stat-value metrics-panel__stat-value--cyan" style={{ fontSize: '0.95rem', paddingTop: '6px', lineHeight: '1' }}>
                                        claude<br />3.5
                                    </span>
                                    <span className="metrics-panel__stat-label" style={{ marginTop: '0px' }}>Model</span>
                                </div>
                            </div>

                            <div className="metrics-panel__token-split">
                                <div className="token-bar">
                                    <div className="token-bar-prompt" style={{ width: `${(ddMetrics.prompt_tokens / ddMetrics.total_tokens) * 100}%` }}></div>
                                    <div className="token-bar-completion" style={{ width: `${(ddMetrics.completion_tokens / ddMetrics.total_tokens) * 100}%` }}></div>
                                </div>
                                <div className="token-legend">
                                    <span><span className="dot-prompt"></span>Prompt: {formatNumber(ddMetrics.prompt_tokens)}</span>
                                    <span><span className="dot-completion"></span>Completion: {formatNumber(ddMetrics.completion_tokens)}</span>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
