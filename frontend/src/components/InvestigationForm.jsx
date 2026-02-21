import { useState } from 'react';
import './InvestigationForm.css';

const PRESET_SERVICES = [
    { name: 'UserAuth', error: '500', icon: '🔐' },
    { name: 'PaymentGateway', error: '502', icon: '💳' },
    { name: 'InventoryAPI', error: '503', icon: '📦' },
    { name: 'NotificationService', error: '500', icon: '🔔' },
];

export default function InvestigationForm({ onSubmit, isRunning }) {
    const [serviceName, setServiceName] = useState('');
    const [errorType, setErrorType] = useState('500');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!serviceName.trim() || isRunning) return;
        onSubmit({ service_name: serviceName.trim(), error_type: errorType });
    };

    const handlePreset = (preset) => {
        if (isRunning) return;
        setServiceName(preset.name);
        setErrorType(preset.error);
    };

    return (
        <div className="investigation-form glass-card">
            <div className="investigation-form__header">
                <div className="investigation-form__icon">🏛️</div>
                <div>
                    <h2 className="investigation-form__title">Activate War Room</h2>
                    <p className="investigation-form__desc">Select a service to trigger a multi-agent incident debate</p>
                </div>
            </div>

            {/* Quick presets */}
            <div className="investigation-form__presets">
                {PRESET_SERVICES.map((preset) => (
                    <button
                        key={preset.name}
                        className={`investigation-form__preset ${serviceName === preset.name ? 'investigation-form__preset--active' : ''}`}
                        onClick={() => handlePreset(preset)}
                        disabled={isRunning}
                        type="button"
                    >
                        <span className="investigation-form__preset-icon">{preset.icon}</span>
                        <span className="investigation-form__preset-name">{preset.name}</span>
                        <span className="investigation-form__preset-error">{preset.error}</span>
                    </button>
                ))}
            </div>

            <form onSubmit={handleSubmit} className="investigation-form__form">
                <div className="investigation-form__fields">
                    <div className="investigation-form__field">
                        <label className="investigation-form__label" htmlFor="service-name">Service Name</label>
                        <input
                            id="service-name"
                            className="investigation-form__input"
                            type="text"
                            placeholder="e.g. UserAuth, PaymentGateway"
                            value={serviceName}
                            onChange={(e) => setServiceName(e.target.value)}
                            disabled={isRunning}
                        />
                    </div>
                    <div className="investigation-form__field investigation-form__field--small">
                        <label className="investigation-form__label" htmlFor="error-type">Error Code</label>
                        <select
                            id="error-type"
                            className="investigation-form__select"
                            value={errorType}
                            onChange={(e) => setErrorType(e.target.value)}
                            disabled={isRunning}
                        >
                            <option value="500">500 Internal Server Error</option>
                            <option value="502">502 Bad Gateway</option>
                            <option value="503">503 Service Unavailable</option>
                            <option value="504">504 Gateway Timeout</option>
                            <option value="429">429 Too Many Requests</option>
                        </select>
                    </div>
                </div>

                <button
                    type="submit"
                    className={`investigation-form__btn ${isRunning ? 'investigation-form__btn--running' : ''}`}
                    disabled={!serviceName.trim() || isRunning}
                >
                    {isRunning ? (
                        <>
                            <span className="investigation-form__spinner" />
                            <span>War Room Active…</span>
                        </>
                    ) : (
                        <>
                            <span>🚨</span>
                            <span>Activate War Room</span>
                        </>
                    )}
                </button>
            </form>
        </div>
    );
}
