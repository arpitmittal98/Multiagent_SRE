import { useState, useEffect } from 'react';
import './Header.css';

export default function Header({ isRunning }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header">
      <div className="header__left">
        <div className={`header__logo ${isRunning ? 'header__logo--active' : ''}`}>
          <div className="header__logo-icon">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="16" cy="16" r="14" stroke="url(#logo-gradient)" strokeWidth="2" />
              <path d="M10 16l4 4 8-8" stroke="url(#logo-gradient)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              <defs>
                <linearGradient id="logo-gradient" x1="4" y1="4" x2="28" y2="28">
                  <stop stopColor="#3b82f6" />
                  <stop offset="0.5" stopColor="#8b5cf6" />
                  <stop offset="1" stopColor="#06b6d4" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div className="header__branding">
            <h1 className="header__title">
              AI<span className="header__title-accent"> War Room</span>
            </h1>
            <p className="header__subtitle">Multi-Agent Incident Debate</p>
          </div>
        </div>
      </div>

      <div className="header__right">
        <div className="header__status">
          <div className={`header__status-dot ${isRunning ? 'header__status-dot--active' : ''}`} />
          <span className="header__status-text">
            {isRunning ? 'War Room Active' : 'Standby'}
          </span>
        </div>
        <div className="header__clock">
          <span className="header__clock-time">
            {time.toLocaleTimeString('en-US', { hour12: false })}
          </span>
          <span className="header__clock-date">
            {time.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </span>
        </div>
      </div>
    </header>
  );
}
