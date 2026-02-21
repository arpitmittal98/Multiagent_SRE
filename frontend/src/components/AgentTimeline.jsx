import { useEffect, useRef } from 'react';
import './AgentTimeline.css';

const STEP_META = {
    investigate: { icon: '🔍', label: 'Investigate', color: 'var(--accent-blue)' },
    analyze: { icon: '🧠', label: 'Analyze', color: 'var(--accent-purple)' },
    remediate: { icon: '🔧', label: 'Remediate', color: 'var(--accent-amber)' },
    report: { icon: '📰', label: 'Report', color: 'var(--accent-green)' },
};

const TYPE_STYLES = {
    thought: { badge: 'Thinking', className: 'timeline-msg--thought' },
    result: { badge: 'Result', className: 'timeline-msg--result' },
    progress: { badge: 'Progress', className: 'timeline-msg--progress' },
    error: { badge: 'Error', className: 'timeline-msg--error' },
};

export default function AgentTimeline({ messages, currentStep, isRunning }) {
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    if (!messages || messages.length === 0) {
        if (!isRunning) return null;
        return (
            <div className="timeline glass-card">
                <div className="timeline__header">
                    <h2 className="timeline__title">🤖 Agent Activity</h2>
                </div>
                <div className="timeline__empty">
                    <div className="timeline__dots">
                        <span className="timeline__dot" />
                        <span className="timeline__dot" />
                        <span className="timeline__dot" />
                    </div>
                    <p>Initializing agent…</p>
                </div>
            </div>
        );
    }

    // Group messages by step
    const steps = ['investigate', 'analyze', 'remediate', 'report'];
    const completed = new Set();
    messages.forEach((m) => {
        if (m.type === 'result') completed.add(m.step);
    });

    return (
        <div className="timeline glass-card">
            <div className="timeline__header">
                <h2 className="timeline__title">🤖 Agent Activity</h2>
                <div className="timeline__step-indicators">
                    {steps.map((step) => {
                        const meta = STEP_META[step];
                        const isComplete = completed.has(step);
                        const isCurrent = step === currentStep;
                        return (
                            <div
                                key={step}
                                className={`timeline__step-chip ${isComplete ? 'timeline__step-chip--done' : ''} ${isCurrent && isRunning ? 'timeline__step-chip--active' : ''}`}
                                style={{ '--chip-color': meta.color }}
                            >
                                <span>{meta.icon}</span>
                                <span>{meta.label}</span>
                                {isComplete && <span className="timeline__check">✓</span>}
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="timeline__messages">
                {messages.map((msg, i) => {
                    const stepMeta = STEP_META[msg.step] || { icon: '❓', label: msg.step, color: 'var(--text-muted)' };
                    const typeMeta = TYPE_STYLES[msg.type] || TYPE_STYLES.thought;
                    return (
                        <div
                            key={i}
                            className={`timeline-msg ${typeMeta.className}`}
                            style={{ animationDelay: `${i * 0.05}s`, '--step-color': stepMeta.color }}
                        >
                            <div className="timeline-msg__gutter">
                                <div className="timeline-msg__dot" />
                                {i < messages.length - 1 && <div className="timeline-msg__line" />}
                            </div>
                            <div className="timeline-msg__content">
                                <div className="timeline-msg__meta">
                                    <span className="timeline-msg__step-badge">{stepMeta.icon} {stepMeta.label}</span>
                                    <span className="timeline-msg__type-badge">{typeMeta.badge}</span>
                                </div>
                                <p className="timeline-msg__text">{msg.content}</p>
                            </div>
                        </div>
                    );
                })}

                {isRunning && (
                    <div className="timeline-msg timeline-msg--thinking">
                        <div className="timeline-msg__gutter">
                            <div className="timeline-msg__dot timeline-msg__dot--pulse" />
                        </div>
                        <div className="timeline-msg__content">
                            <div className="timeline__dots">
                                <span className="timeline__dot" />
                                <span className="timeline__dot" />
                                <span className="timeline__dot" />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>
        </div>
    );
}
