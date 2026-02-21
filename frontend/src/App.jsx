import { useState, useCallback } from 'react';
import Header from './components/Header';
import InvestigationForm from './components/InvestigationForm';
import WarRoom from './components/WarRoom';
import IncidentReport from './components/IncidentReport';
import MetricsPanel from './components/MetricsPanel';
import './App.css';

const API_BASE = 'http://localhost:8000';

function App() {
  const [isRunning, setIsRunning] = useState(false);
  const [messages, setMessages] = useState([]);
  const [consensus, setConsensus] = useState('');
  const [warRoomSummary, setWarRoomSummary] = useState('');
  const [activeService, setActiveService] = useState('');
  const [metrics, setMetrics] = useState({
    agentTurns: 0,
    tokensUsed: 0,
    startTime: null,
    elapsed: 0,
  });

  const handleSubmit = useCallback(async ({ service_name, error_type }) => {
    setIsRunning(true);
    setMessages([]);
    setConsensus('');
    setWarRoomSummary('');
    setActiveService(service_name);
    setMetrics({ agentTurns: 0, tokensUsed: 0, startTime: Date.now(), elapsed: 0 });

    const timer = setInterval(() => {
      setMetrics((prev) => ({
        ...prev,
        elapsed: Math.floor((Date.now() - (prev.startTime || Date.now())) / 1000),
      }));
    }, 1000);

    try {
      const res = await fetch(`${API_BASE}/api/investigate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_name, error_type }),
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
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);

              if (parsed.consensus !== undefined) {
                setConsensus(parsed.consensus);
              } else if (parsed.war_room_summary !== undefined) {
                setWarRoomSummary(parsed.war_room_summary);
              } else {
                setMessages((prev) => [...prev, parsed]);
                if (parsed.type === 'agent_message') {
                  setMetrics((prev) => ({
                    ...prev,
                    agentTurns: prev.agentTurns + 1,
                  }));
                }
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          step: 'error',
          type: 'system',
          agent: 'system',
          agent_name: 'System',
          emoji: '',
          content: `Error: ${err.message}`,
        },
      ]);
    } finally {
      clearInterval(timer);
      setIsRunning(false);
    }
  }, []);

  const reportContent = warRoomSummary || consensus;

  return (
    <div className="app">
      <Header isRunning={isRunning} />

      <main className="app__main">
        {/* Left: Form + Metrics */}
        <aside className="app__sidebar">
          <InvestigationForm onSubmit={handleSubmit} isRunning={isRunning} />
          <MetricsPanel
            metrics={{
              ...metrics,
              debateMessages: messages.filter((m) => m.type === 'agent_message').length,
              currentRound: messages.length > 0
                ? messages[messages.length - 1]?.step?.replace('round_', 'Round ') || '-'
                : '-',
            }}
          />
        </aside>

        {/* Right: War Room + Report underneath */}
        <section className="app__center">
          <div className="glass-card app__warroom-card">
            <WarRoom messages={messages} />
          </div>
          {reportContent && <IncidentReport report={reportContent} serviceName={activeService} />}
        </section>
      </main>
    </div>
  );
}

export default App;
