import { useRef, useEffect, useState } from 'react';
import './WarRoom.css';

const AGENT_CONFIG = {
    sre: {
        name: 'SRE Engineer',
        emoji: '\u{1F527}',
        color: 'var(--accent-blue)',
        gradient: 'linear-gradient(135deg, rgba(0, 228, 255, 0.15), rgba(0, 228, 255, 0.05))',
        borderColor: 'var(--accent-blue-glow)',
    },
    product: {
        name: 'Product Manager',
        emoji: '\u{1F4CA}',
        color: 'var(--accent-amber)',
        gradient: 'linear-gradient(135deg, rgba(255, 179, 0, 0.15), rgba(255, 179, 0, 0.05))',
        borderColor: 'var(--accent-amber-glow)',
    },
    security: {
        name: 'Security Analyst',
        emoji: '\u{1F6E1}\u{FE0F}',
        color: 'var(--accent-red)',
        gradient: 'linear-gradient(135deg, rgba(255, 42, 42, 0.15), rgba(255, 42, 42, 0.05))',
        borderColor: 'var(--accent-red-glow)',
    },
    moderator: {
        name: 'War Room Moderator',
        emoji: '\u{2696}\u{FE0F}',
        color: 'var(--accent-purple)',
        gradient: 'linear-gradient(135deg, rgba(181, 53, 255, 0.15), rgba(181, 53, 255, 0.05))',
        borderColor: 'var(--accent-purple-glow)',
    },
    system: {
        name: 'System',
        emoji: '\u{2699}\u{FE0F}',
        color: 'var(--text-muted)',
        gradient: 'transparent',
        borderColor: 'var(--border-subtle)',
    },
};

/**
 * Parse a message that might contain **TL;DR: ...**
 * Returns { tldr: string|null, detail: string }
 */
function parseTldr(content) {
    // Match **TL;DR: ...** at the start (with possible whitespace)
    const match = content.match(/^\s*\*\*TL;DR:\s*(.*?)\*\*/i);
    if (match) {
        const tldr = match[1].trim();
        const detail = content.slice(match[0].length).trim();
        return { tldr, detail };
    }
    return { tldr: null, detail: content };
}

function AgentBubble({ msg, config }) {
    const [expanded, setExpanded] = useState(false);
    const { tldr, detail } = parseTldr(msg.content);
    const isModerator = msg.agent === 'moderator';

    // Moderator always expanded (it's the consensus document)
    const showFull = isModerator || expanded;

    return (
        <div
            className={`warroom-bubble ${isModerator ? 'moderator' : ''}`}
            style={{
                background: config.gradient,
                borderLeft: `3px solid ${config.borderColor}`,
                '--agent-color': config.color,
            }}
        >
            <div className="warroom-bubble-header">
                <span className="warroom-avatar">{config.emoji}</span>
                <span className="warroom-agent-name" style={{ color: config.color }}>
                    {config.name}
                </span>
                {msg.step && (
                    <span className="warroom-round-badge">
                        {msg.step.replace('round_', 'R').replace('consensus', 'Consensus')}
                    </span>
                )}
            </div>

            {/* TL;DR headline */}
            {tldr && (
                <div className="warroom-tldr" style={{ color: config.color }}>
                    {tldr}
                </div>
            )}

            {/* Expandable detail */}
            {detail && (
                <>
                    <div className={`warroom-bubble-content ${showFull ? '' : 'collapsed'}`}>
                        {(showFull ? detail : detail).split('\n').map((line, j) => (
                            <p key={j}>{line}</p>
                        ))}
                    </div>
                    {!isModerator && detail.length > 100 && (
                        <button
                            className="warroom-expand-btn"
                            onClick={() => setExpanded(!expanded)}
                            style={{ color: config.color }}
                        >
                            {expanded ? '▲ Collapse' : '▼ Read more'}
                        </button>
                    )}
                </>
            )}

            {/* Fallback: no TL;DR parsed, show content directly */}
            {!tldr && !detail && (
                <div className="warroom-bubble-content">
                    {msg.content.split('\n').map((line, j) => (
                        <p key={j}>{line}</p>
                    ))}
                </div>
            )}
        </div>
    );
}

function WarRoom({ messages }) {
    const chatRef = useRef(null);

    useEffect(() => {
        if (chatRef.current) {
            chatRef.current.scrollTop = chatRef.current.scrollHeight;
        }
    }, [messages]);

    if (!messages || messages.length === 0) {
        return (
            <div className="warroom-empty">
                <div className="warroom-empty-icon">&#x1F3DB;&#xFE0F;</div>
                <h3>War Room Inactive</h3>
                <p>Select a service and activate the war room to begin the multi-agent incident debate.</p>
            </div>
        );
    }

    return (
        <div className="warroom" ref={chatRef}>
            <div className="warroom-header-bar">
                <span className="warroom-live-dot"></span>
                <span>WAR ROOM ACTIVE</span>
                <span className="warroom-agent-count">3 agents connected</span>
            </div>

            <div className="warroom-messages">
                {messages.map((msg, i) => {
                    const config = AGENT_CONFIG[msg.agent] || AGENT_CONFIG.system;

                    if (msg.type === 'system') {
                        return (
                            <div key={i} className="warroom-system-msg">
                                <span>{msg.content}</span>
                            </div>
                        );
                    }

                    if (msg.type === 'thought') {
                        return (
                            <div key={i} className="warroom-thinking" style={{ color: config.color }}>
                                <span className="thinking-dots">
                                    <span></span><span></span><span></span>
                                </span>
                                {msg.content}
                            </div>
                        );
                    }

                    return <AgentBubble key={i} msg={msg} config={config} />;
                })}
            </div>
        </div>
    );
}

export default WarRoom;
