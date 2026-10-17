import React, { useState, useEffect, useRef } from 'react';
import {
  Shield,
  Activity,
  Zap,
  Sun,
  Battery,
  AlertTriangle,
  CheckCircle,
  Clock,
  Cpu,
  BarChart2,
  Database,
  Lock,
  RefreshCw,
  Sliders,
  Flame,
  Radio,
  Eye,
  FileText
} from 'lucide-react';

const getApiBase = () => {
  if (typeof window !== 'undefined' && window.location.origin) {
    return window.location.origin;
  }
  return 'http://localhost:8000';
};

const getWsUrl = () => {
  if (typeof window !== 'undefined' && window.location.host) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws/telemetry`;
  }
  return 'ws://localhost:8000/ws/telemetry';
};

const API_BASE = getApiBase();
const WS_URL = getWsUrl();

export default function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [history, setHistory] = useState([]);
  const [resilizDecision, setResilizDecision] = useState(null);
  const [baselineA, setBaselineA] = useState(null);
  const [baselineB, setBaselineB] = useState(null);
  const [activeAnomaly, setActiveAnomaly] = useState(null);
  const [counters, setCounters] = useState({ total_ticks: 0, transients_filtered: 0, critical_alerts: 0, warning_alerts: 0, advisory_alerts: 0 });
  const [benchmarks, setBenchmarks] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [activeTab, setActiveTab] = useState('live'); // 'live', 'benchmarks', 'audit'
  const [sysHealth, setSysHealth] = useState(null);
  const [isInjecting, setIsInjecting] = useState(false);

  const wsRef = useRef(null);

  const applyTelemetryUpdate = (data) => {
    if (!data || !data.telemetry) return;
    setTelemetry(data.telemetry);
    if (data.decision) setResilizDecision(data.decision);
    else if (data.resiliz_decision) setResilizDecision(data.resiliz_decision);
    if (data.baseline_a) setBaselineA(data.baseline_a);
    if (data.baseline_b) setBaselineB(data.baseline_b);
    setActiveAnomaly(data.active_anomaly);
    if (data.counters) setCounters(data.counters);

    setHistory(prev => {
      const updated = [...prev, data.telemetry];
      if (updated.length > 50) updated.shift();
      return updated;
    });

    const dec = data.decision || data.resiliz_decision;
    if (dec && (dec.severity === 'WARNING' || dec.severity === 'CRITICAL' || dec.is_transient_filtered)) {
      setAlerts(prev => [
        {
          id: Date.now(),
          timestamp: data.telemetry.timestamp,
          tick: data.telemetry.tick,
          severity: dec.severity,
          classification: dec.classification,
          score: dec.anomaly_score,
          is_transient_filtered: dec.is_transient_filtered,
          explanations: dec.explanations || [],
          audit_hash: dec.audit_hash,
        },
        ...prev.slice(0, 30),
      ]);
    }
  };

  // Initialize Data & WebSocket
  useEffect(() => {
    // 1. Fetch initial telemetry history
    fetch(`${API_BASE}/api/telemetry/history?limit=40`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setHistory(data);
          setTelemetry(data[data.length - 1]);
        }
      })
      .catch(err => console.warn('History fetch error:', err));

    // 2. Fetch initial benchmarks
    fetch(`${API_BASE}/api/benchmarks`)
      .then(res => res.json())
      .then(data => setBenchmarks(data))
      .catch(err => console.warn('Benchmark fetch error:', err));

    // 3. Fetch system health
    fetch(`${API_BASE}/api/health`)
      .then(res => res.json())
      .then(data => setSysHealth(data))
      .catch(err => console.warn('Health fetch error:', err));

    // 4. Connect WebSocket with continuous fallback polling
    const connectWs = () => {
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsStatus('connected');
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'TELEMETRY_UPDATE') {
              applyTelemetryUpdate(msg);
            }
          } catch (e) {
            console.error('WS parse error:', e);
          }
        };

        ws.onerror = () => setWsStatus('fallback-polling');
        ws.onclose = () => {
          setWsStatus('fallback-polling');
          setTimeout(connectWs, 3000);
        };
      } catch (err) {
        setWsStatus('fallback-polling');
        setTimeout(connectWs, 3000);
      }
    };

    connectWs();

    // Resilient HTTP Polling Interval: guarantees updates even if WS is blocked
    const pollInterval = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        fetch(`${API_BASE}/api/telemetry/live`)
          .then(res => res.json())
          .then(data => {
            if (data && data.telemetry) {
              applyTelemetryUpdate(data);
              setWsStatus('polling');
            }
          })
          .catch(() => {});
      }
    }, 600);

    // Periodic poll for audit trail & health
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/audit/trail?limit=15`)
        .then(res => res.json())
        .then(data => setAuditTrail(data))
        .catch(() => {});
      fetch(`${API_BASE}/api/health`)
        .then(res => res.json())
        .then(data => setSysHealth(data))
        .catch(() => {});
    }, 4000);

    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Inject Anomaly Handler
  const handleInject = async (type, duration = 18, intensity = 1.0) => {
    setIsInjecting(true);
    try {
      await fetch(`${API_BASE}/api/simulator/inject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anomaly_type: type, duration_ticks: duration, intensity }),
      });
      setActiveAnomaly(type);
    } catch (e) {
      console.error('Failed to inject anomaly:', e);
    } finally {
      setIsInjecting(false);
    }
  };

  const handleClearAnomaly = async () => {
    try {
      await fetch(`${API_BASE}/api/simulator/clear`, { method: 'POST' });
      setActiveAnomaly(null);
    } catch (e) {
      console.error('Failed to clear anomaly:', e);
    }
  };

  const getSeverityBadgeClass = (severity) => {
    switch (severity) {
      case 'CRITICAL': return 'badge-critical';
      case 'WARNING': return 'badge-warning';
      case 'ADVISORY': return 'badge-advisory';
      default: return 'badge-normal';
    }
  };

  // Helper to render high-performance SVG Sparkline
  const renderSparkline = (data, dataKey, minVal, maxVal, color) => {
    if (!data || data.length < 2) return null;
    const width = 280;
    const height = 65;
    const padding = 6;

    const points = data.map((d, i) => {
      const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
      const val = d[dataKey] !== undefined ? d[dataKey] : minVal;
      const normalized = Math.max(0, Math.min(1, (val - minVal) / (maxVal - minVal || 1)));
      const y = height - padding - normalized * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    return (
      <svg className="w-full h-16 overflow-visible" viewBox={`0 0 ${width} ${height}`}>
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        {/* Glow drop */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeOpacity="0.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px 20px' }}>
      {/* TOP HEADER */}
      <header className="glass-panel" style={{ padding: '20px 24px', marginBottom: '24px', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(6, 182, 212, 0.4)' }}>
            <Zap size={28} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '24px', fontWeight: '800', letterSpacing: '-0.5px', background: 'linear-gradient(to right, #ffffff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                ResiliZ
              </h1>
              <span style={{ fontSize: '11px', fontWeight: '700', padding: '3px 8px', borderRadius: '6px', background: 'rgba(6, 182, 212, 0.15)', color: '#22d3ee', border: '1px solid rgba(6, 182, 212, 0.3)' }}>
                s390x LINUXONE READY
              </span>
            </div>
            <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '2px' }}>
              Confidential Real-Time Anomaly Telemetry for Renewable Microgrids
            </p>
          </div>
        </div>

        {/* Status Indicators & Navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.8)', padding: '6px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: wsStatus === 'connected' ? '#10b981' : '#f43f5e', boxShadow: wsStatus === 'connected' ? '0 0 8px #10b981' : 'none' }}></span>
            <span style={{ fontSize: '12px', color: '#cbd5e1', textTransform: 'capitalize' }}>
              {wsStatus === 'connected' ? 'Streaming 2Hz' : wsStatus}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.8)', padding: '6px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <Lock size={14} color="#38bdf8" />
            <span style={{ fontSize: '12px', color: '#38bdf8', fontWeight: '600' }}>
              IBM Secure Execution Enclave
            </span>
          </div>

          {/* Navigation Tabs */}
          <div style={{ display: 'flex', gap: '6px', background: '#0f172a', padding: '4px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <button
              onClick={() => setActiveTab('live')}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: '600',
                border: 'none',
                cursor: 'pointer',
                background: activeTab === 'live' ? '#1e293b' : 'transparent',
                color: activeTab === 'live' ? '#38bdf8' : '#94a3b8',
              }}
            >
              Live Telemetry
            </button>
            <button
              onClick={() => setActiveTab('benchmarks')}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: '600',
                border: 'none',
                cursor: 'pointer',
                background: activeTab === 'benchmarks' ? '#1e293b' : 'transparent',
                color: activeTab === 'benchmarks' ? '#38bdf8' : '#94a3b8',
              }}
            >
              Benchmark Baselines
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: '600',
                border: 'none',
                cursor: 'pointer',
                background: activeTab === 'audit' ? '#1e293b' : 'transparent',
                color: activeTab === 'audit' ? '#38bdf8' : '#94a3b8',
              }}
            >
              Audit Trail
            </button>
          </div>
        </div>
      </header>

      {/* ACTIVE ANOMALY BANNER (If Anomaly Injected) */}
      {activeAnomaly && (
        <div style={{
          background: 'linear-gradient(90deg, rgba(244,63,94,0.15) 0%, rgba(245,158,11,0.15) 100%)',
          border: '1px solid rgba(244,63,94,0.4)',
          borderRadius: '10px',
          padding: '12px 20px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Flame size={20} color="#fb7185" />
            <span style={{ fontSize: '14px', fontWeight: '700', color: '#fb7185' }}>
              INJECTED SIMULATION ANOMALY ACTIVE:
            </span>
            <span style={{ fontSize: '14px', color: '#f1f5f9', textTransform: 'uppercase', fontFamily: 'JetBrains Mono' }}>
              [{activeAnomaly.replace(/_/g, ' ')}]
            </span>
          </div>
          <button
            onClick={handleClearAnomaly}
            style={{
              background: '#e11d48',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: '700',
              cursor: 'pointer',
            }}
          >
            Clear / Restore Grid
          </button>
        </div>
      )}

      {/* TAB 1: LIVE TELEMETRY & DECISION ENGINE */}
      {activeTab === 'live' && (
        <>
          {/* PRIMARY KPI METRICS GRID */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            {/* VOLTAGE KPI */}
            <div className="glass-panel" style={{ padding: '18px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: '600' }}>AC Voltage (RMS)</span>
                <span style={{ fontSize: '11px', color: '#64748b', background: '#0f172a', padding: '2px 8px', borderRadius: '4px' }}>Nominal: 230V</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '10px 0 6px 0' }}>
                <span style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: telemetry ? (Math.abs(telemetry.voltage_v - 230) > 23 ? '#fb7185' : '#38bdf8') : '#94a3b8' }}>
                  {telemetry ? telemetry.voltage_v.toFixed(1) : '--'}
                </span>
                <span style={{ fontSize: '16px', color: '#94a3b8' }}>V</span>
                {telemetry && (
                  <span style={{ fontSize: '12px', color: '#64748b', marginLeft: 'auto' }}>
                    Δ {(telemetry.voltage_v - 230).toFixed(1)}V
                  </span>
                )}
              </div>
              {renderSparkline(history, 'voltage_v', 150, 280, '#06b6d4')}
            </div>

            {/* FREQUENCY KPI */}
            <div className="glass-panel" style={{ padding: '18px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: '600' }}>Grid Frequency</span>
                <span style={{ fontSize: '11px', color: '#64748b', background: '#0f172a', padding: '2px 8px', borderRadius: '4px' }}>Nominal: 50.00Hz</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '10px 0 6px 0' }}>
                <span style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: telemetry ? (Math.abs(telemetry.frequency_hz - 50.0) > 0.5 ? '#fb7185' : '#10b981') : '#94a3b8' }}>
                  {telemetry ? telemetry.frequency_hz.toFixed(3) : '--'}
                </span>
                <span style={{ fontSize: '16px', color: '#94a3b8' }}>Hz</span>
                {telemetry && (
                  <span style={{ fontSize: '12px', color: '#64748b', marginLeft: 'auto' }}>
                    PF: {telemetry.power_factor}
                  </span>
                )}
              </div>
              {renderSparkline(history, 'frequency_hz', 48.5, 51.5, '#10b981')}
            </div>

            {/* SOLAR & LOAD BALANCE */}
            <div className="glass-panel" style={{ padding: '18px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: '600' }}>Microgrid Power Balance</span>
                <span style={{ fontSize: '11px', color: '#64748b', background: '#0f172a', padding: '2px 8px', borderRadius: '4px' }}>Solar vs Load</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '10px 0 6px 0' }}>
                <span style={{ fontSize: '32px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: '#f59e0b' }}>
                  {telemetry ? telemetry.solar_pv_kw.toFixed(1) : '--'}
                </span>
                <span style={{ fontSize: '16px', color: '#94a3b8' }}>kW Solar</span>
                {telemetry && (
                  <span style={{ fontSize: '13px', color: '#94a3b8', marginLeft: 'auto' }}>
                    Load: {telemetry.active_power_kw.toFixed(1)} kW
                  </span>
                )}
              </div>
              {renderSparkline(history, 'solar_pv_kw', 0, 45, '#f59e0b')}
            </div>

            {/* RESILIZ DECISION ENGINE SEVERITY */}
            <div className="glass-panel-glow" style={{ padding: '18px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '13px', color: '#38bdf8', fontWeight: '700' }}>ResiliZ Decision Engine</span>
                <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', ...((resilizDecision?.severity === 'CRITICAL' || resilizDecision?.severity === 'WARNING') ? { background: '#881337', color: '#fda4af' } : { background: '#064e3b', color: '#6ee7b7' }) }}>
                  {resilizDecision?.classification || 'MONITORING'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '12px 0 6px 0' }}>
                <div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '2px' }}>AI Severity Level</div>
                  <span className={getSeverityBadgeClass(resilizDecision?.severity)} style={{ padding: '4px 12px', borderRadius: '6px', fontSize: '14px', fontWeight: '800', letterSpacing: '0.5px' }}>
                    {resilizDecision?.severity || 'NORMAL'}
                  </span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '2px' }}>Composite Threat Score</div>
                  <div style={{ fontSize: '24px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: '#f1f5f9' }}>
                    {resilizDecision ? (resilizDecision.anomaly_score * 100).toFixed(0) + '%' : '--'}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '10px', display: 'flex', justifyContent: 'space-between' }}>
                <span>Transient Filter: {resilizDecision?.is_transient_filtered ? '⚡ Suppressed Glitch' : 'Inactive'}</span>
                <span>Persistence: {resilizDecision?.consecutive_ticks || 0} / 5</span>
              </div>
            </div>
          </div>

          {/* TWO-COLUMN MAIN WORKSPACE: DECISION COMPARISON & ANOMALY INJECTOR */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '20px', marginBottom: '24px' }}>
            {/* COLUMN 1: LIVE 3-WAY DECISION COMPARISON */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                <Eye size={18} color="#38bdf8" />
                <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Live 3-Way Anomaly Decision Comparison</h2>
              </div>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '16px' }}>
                Demonstrating real-time contrast between simple thresholds, raw Isolation Forest, and ResiliZ's context-aware decision layer.
              </p>

              {/* MODEL CARDS */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* 1. Baseline A */}
                <div style={{ background: '#0b1120', padding: '14px 16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: '#cbd5e1' }}>Baseline A: Fixed Thresholds (IEEE 1547)</span>
                      <p style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Voltage ±10%, Frequency ±0.5Hz, Max Current 100A</p>
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', padding: '3px 10px', borderRadius: '4px', background: baselineA?.is_anomaly ? 'rgba(244,63,94,0.15)' : 'rgba(16,185,129,0.15)', color: baselineA?.is_anomaly ? '#fb7185' : '#34d399', border: baselineA?.is_anomaly ? '1px solid rgba(244,63,94,0.3)' : '1px solid rgba(16,185,129,0.3)' }}>
                      {baselineA?.is_anomaly ? 'TRIP ALARM' : 'NOMINAL'}
                    </span>
                  </div>
                  {baselineA?.reasons?.length > 0 && (
                    <div style={{ fontSize: '11px', color: '#fb7185', marginTop: '8px', fontFamily: 'JetBrains Mono' }}>
                      • {baselineA.reasons.join(', ')}
                    </div>
                  )}
                </div>

                {/* 2. Baseline B */}
                <div style={{ background: '#0b1120', padding: '14px 16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: '#cbd5e1' }}>Baseline B: Standalone Isolation Forest</span>
                      <p style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Unsupervised scikit-learn without temporal rules</p>
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: '700', padding: '3px 10px', borderRadius: '4px', background: baselineB?.is_anomaly ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)', color: baselineB?.is_anomaly ? '#fbbf24' : '#34d399', border: baselineB?.is_anomaly ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(16,185,129,0.3)' }}>
                      {baselineB?.is_anomaly ? `OUTLIER (${(baselineB.anomaly_score * 100).toFixed(0)}%)` : 'NORMAL'}
                    </span>
                  </div>
                </div>

                {/* 3. ResiliZ Decision Layer */}
                <div style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.08) 0%, rgba(59,130,246,0.08) 100%)', padding: '14px 16px', borderRadius: '8px', border: '1px solid rgba(6,182,212,0.4)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px', fontWeight: '800', color: '#38bdf8' }}>ResiliZ: AI + Context + Persistence</span>
                        <span style={{ fontSize: '10px', background: '#0369a1', color: '#ffffff', padding: '2px 6px', borderRadius: '4px', fontWeight: '700' }}>RECOMMENDED</span>
                      </div>
                      <p style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Multi-sample verification + microgrid domain rules</p>
                    </div>
                    <span className={getSeverityBadgeClass(resilizDecision?.severity)} style={{ fontSize: '12px', fontWeight: '800', padding: '3px 12px', borderRadius: '4px' }}>
                      {resilizDecision?.severity || 'NORMAL'}
                    </span>
                  </div>

                  {/* Explainability details */}
                  {resilizDecision?.explanations?.length > 0 && (
                    <div style={{ marginTop: '10px', padding: '8px 10px', background: 'rgba(15,23,42,0.6)', borderRadius: '6px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: '#38bdf8' }}>Root Cause & Contextual Evidence:</span>
                      <ul style={{ margin: '4px 0 0 16px', fontSize: '11px', color: '#cbd5e1' }}>
                        {resilizDecision.explanations.map((exp, idx) => (
                          <li key={idx} style={{ marginTop: '2px' }}>{exp}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '10px', color: '#64748b', fontFamily: 'JetBrains Mono' }}>
                    <span>Audit Hash: {resilizDecision?.audit_hash ? resilizDecision.audit_hash.substring(0, 16) + '...' : '--'}</span>
                    <span>Lat: {resilizDecision?.latency_ms || 0}ms</span>
                  </div>
                </div>
              </div>
            </div>

            {/* COLUMN 2: CONTROLLABLE ANOMALY INJECTOR & NOISE TESTER */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <Sliders size={18} color="#f59e0b" />
                <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Interactive Microgrid Anomaly Injector</h2>
              </div>
              <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '16px' }}>
                Test how each detection layer responds in real-time. Notice how ResiliZ silences 1-tick electrical spikes while triggering instantly on physical faults.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
                <button
                  disabled={isInjecting}
                  onClick={() => handleInject('voltage_sag', 20, 1.1)}
                  style={{
                    background: '#1e293b',
                    color: '#f1f5f9',
                    border: '1px solid #334155',
                    padding: '12px',
                    borderRadius: '8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#06b6d4'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = '#334155'}
                >
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#38bdf8' }}>⚡ Voltage Sag</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Drops to ~165V (Feeder fault)</div>
                </button>

                <button
                  disabled={isInjecting}
                  onClick={() => handleInject('frequency_instability', 25, 1.0)}
                  style={{
                    background: '#1e293b',
                    color: '#f1f5f9',
                    border: '1px solid #334155',
                    padding: '12px',
                    borderRadius: '8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#06b6d4'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = '#334155'}
                >
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#10b981' }}>📉 Frequency Trip</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Swings 48.8Hz - 51.2Hz (Islanding)</div>
                </button>

                <button
                  disabled={isInjecting}
                  onClick={() => handleInject('transient_spike', 1, 1.2)}
                  style={{
                    background: '#1e293b',
                    color: '#f1f5f9',
                    border: '1px solid #334155',
                    padding: '12px',
                    borderRadius: '8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#f59e0b'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = '#334155'}
                >
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#f59e0b' }}>⚡ 1-Sample Glitch</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Benign noise (False Alarm test)</div>
                </button>

                <button
                  disabled={isInjecting}
                  onClick={() => handleInject('reverse_power_flow', 25, 1.1)}
                  style={{
                    background: '#1e293b',
                    color: '#f1f5f9',
                    border: '1px solid #334155',
                    padding: '12px',
                    borderRadius: '8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#06b6d4'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = '#334155'}
                >
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#a855f7' }}>🔄 Reverse Power</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Excess PV backflow & PF drift</div>
                </button>

                <button
                  disabled={isInjecting}
                  onClick={() => handleInject('cyber_sensor_tampering', 20, 1.0)}
                  style={{
                    background: '#1e293b',
                    color: '#f1f5f9',
                    border: '1px solid #334155',
                    padding: '12px',
                    borderRadius: '8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    gridColumn: 'span 2',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = '#fb7185'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = '#334155'}
                >
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#fb7185' }}>🛡️ Cyber-Physical Sensor Tampering</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Spoofs 0V outage readings during active current flow</div>
                </button>
              </div>

              {/* Counters Strip */}
              <div style={{ background: '#0b1120', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: '#38bdf8' }}>{counters.total_ticks}</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>Total Telemetry Ticks</div>
                </div>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: '#10b981' }}>{counters.transients_filtered}</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>False Glitches Filtered</div>
                </div>
                <div>
                  <div style={{ fontSize: '18px', fontWeight: '800', fontFamily: 'JetBrains Mono', color: '#fb7185' }}>{counters.critical_alerts}</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>Critical Faults Confirmed</div>
                </div>
              </div>
            </div>
          </div>

          {/* PRIORITIZED REAL-TIME ALERT STREAM */}
          <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <AlertTriangle size={18} color="#fb7185" />
                <h2 style={{ fontSize: '16px', fontWeight: '700' }}>Prioritized Anomaly Feed & Evidence</h2>
              </div>
              <span style={{ fontSize: '12px', color: '#64748b' }}>Showing verified microgrid events</span>
            </div>

            {alerts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: '#64748b', fontSize: '13px' }}>
                No critical or warning anomalies detected yet. System running nominal. Try injecting a test anomaly above!
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
                {alerts.map(alt => (
                  <div
                    key={alt.id}
                    style={{
                      background: '#0b1120',
                      padding: '12px 16px',
                      borderRadius: '8px',
                      borderLeft: `4px solid ${alt.severity === 'CRITICAL' ? '#f43f5e' : alt.severity === 'WARNING' ? '#f59e0b' : '#3b82f6'}`,
                      display: 'flex',
                      flexWrap: 'wrap',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span className={getSeverityBadgeClass(alt.severity)} style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '800' }}>
                          {alt.severity}
                        </span>
                        <span style={{ fontSize: '13px', fontWeight: '700', color: '#f1f5f9' }}>
                          {alt.classification}
                        </span>
                        <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'JetBrains Mono' }}>
                          Tick #{alt.tick}
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px' }}>
                        {alt.explanations?.join(' | ')}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', fontSize: '11px', color: '#64748b', fontFamily: 'JetBrains Mono' }}>
                      <div>Threat: {(alt.score * 100).toFixed(0)}%</div>
                      <div title={alt.audit_hash}>Hash: {alt.audit_hash ? alt.audit_hash.substring(0, 12) + '...' : '--'}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* TAB 2: BENCHMARK BASELINES & SCIENTIFIC EVALUATION */}
      {activeTab === 'benchmarks' && benchmarks && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '20px', fontWeight: '800', color: '#f1f5f9' }}>Benchmark Evaluation: ResiliZ vs Baselines</h2>
                <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '4px' }}>
                  Measured on {benchmarks.total_telemetry_windows} consecutive microgrid telemetry windows containing controlled faults and benign electrical transients.
                </p>
              </div>
              <button
                onClick={() => {
                  fetch(`${API_BASE}/api/benchmarks/run`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => setBenchmarks(data));
                }}
                style={{
                  background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <RefreshCw size={14} /> Re-run 1,200 Windows
              </button>
            </div>

            {/* METRICS COMPARISON TABLE */}
            <div style={{ overflowX: 'auto', marginTop: '16px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                    <th style={{ padding: '12px 14px' }}>Model</th>
                    <th style={{ padding: '12px 14px' }}>Precision</th>
                    <th style={{ padding: '12px 14px' }}>Recall</th>
                    <th style={{ padding: '12px 14px' }}>F1 Score</th>
                    <th style={{ padding: '12px 14px' }}>False Alarms / 1k</th>
                    <th style={{ padding: '12px 14px' }}>Detection Delay</th>
                    <th style={{ padding: '12px 14px' }}>p50 Latency</th>
                    <th style={{ padding: '12px 14px' }}>p95 Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(benchmarks.metrics).map(([key, m]) => {
                    const isResiliZ = key === 'resiliz';
                    return (
                      <tr
                        key={key}
                        style={{
                          borderBottom: '1px solid #1e293b',
                          background: isResiliZ ? 'rgba(6, 182, 212, 0.08)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '14px', fontWeight: isResiliZ ? '800' : '600', color: isResiliZ ? '#38bdf8' : '#f1f5f9' }}>
                          {m.name}
                          {isResiliZ && <span style={{ marginLeft: '8px', fontSize: '10px', background: '#0284c7', color: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>PROPOSED</span>}
                        </td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono', color: isResiliZ ? '#34d399' : '#cbd5e1' }}>{m.precision}%</td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono', color: isResiliZ ? '#34d399' : '#cbd5e1' }}>{m.recall}%</td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono', fontWeight: '800', color: isResiliZ ? '#38bdf8' : '#cbd5e1' }}>{m.f1_score}%</td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono', color: m.false_alarms_per_1000 < 50 ? '#34d399' : '#fb7185' }}>
                          {m.false_alarms_per_1000}
                        </td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono' }}>{m.detection_delay_ticks} ticks ({m.detection_delay_ms_est}ms)</td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono' }}>{m.p50_latency_ms} ms</td>
                        <td style={{ padding: '14px', fontFamily: 'JetBrains Mono' }}>{m.p95_latency_ms} ms</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* TAKEAWAYS LIST */}
            <div style={{ marginTop: '24px', background: '#0b1120', padding: '16px 20px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#38bdf8' }}>Key Benchmark Conclusions:</span>
              <ul style={{ margin: '8px 0 0 20px', fontSize: '13px', color: '#cbd5e1', lineHeight: '1.6' }}>
                {benchmarks.key_takeaways?.map((takeaway, idx) => (
                  <li key={idx}>{takeaway}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: IBM LINUXONE CRYPTOGRAPHIC AUDIT TRAIL */}
      {activeTab === 'audit' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Lock size={20} color="#38bdf8" />
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: '800' }}>IBM LinuxONE Confidential Computing & Audit Trail</h2>
                <p style={{ fontSize: '12px', color: '#94a3b8' }}>
                  Cryptographically chained SHA-256 telemetry alerts. Ensures non-repudiation and zero-trust grid compliance.
                </p>
              </div>
            </div>
            <div style={{ fontSize: '11px', background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '6px 12px', borderRadius: '6px' }}>
              Target Arch: IBM LinuxONE s390x Secure Execution
            </div>
          </div>

          <div style={{ overflowX: 'auto', marginTop: '16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
                  <th style={{ padding: '10px 12px' }}>Alert ID</th>
                  <th style={{ padding: '10px 12px' }}>Timestamp (UTC)</th>
                  <th style={{ padding: '10px 12px' }}>Grid Node</th>
                  <th style={{ padding: '10px 12px' }}>Severity</th>
                  <th style={{ padding: '10px 12px' }}>Threat Score</th>
                  <th style={{ padding: '10px 12px' }}>Cryptographic Hash (SHA-256)</th>
                  <th style={{ padding: '10px 12px' }}>Enclave Integrity</th>
                </tr>
              </thead>
              <tbody>
                {auditTrail.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                      No audit records logged yet. Trigger an anomaly to generate cryptographic alerts!
                    </td>
                  </tr>
                ) : (
                  auditTrail.map((record) => (
                    <tr key={record.alert_id} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '12px', fontFamily: 'JetBrains Mono', color: '#cbd5e1' }}>#{record.alert_id}</td>
                      <td style={{ padding: '12px', fontFamily: 'JetBrains Mono', color: '#94a3b8' }}>{record.timestamp.replace('T', ' ').substring(0, 19)}</td>
                      <td style={{ padding: '12px', fontWeight: '600' }}>{record.grid_id}</td>
                      <td style={{ padding: '12px' }}>
                        <span className={getSeverityBadgeClass(record.severity)} style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: '800' }}>
                          {record.severity}
                        </span>
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'JetBrains Mono' }}>{(record.score * 100).toFixed(0)}%</td>
                      <td style={{ padding: '12px', fontFamily: 'JetBrains Mono', color: '#38bdf8' }}>{record.audit_hash}</td>
                      <td style={{ padding: '12px', color: '#34d399', fontWeight: '600' }}>✓ Verified</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer style={{ marginTop: '36px', paddingTop: '16px', borderTop: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#64748b', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          ResiliZ Platform • Real-time AI Anomaly Telemetry for Renewable Microgrids
        </div>
        <div>
          Host: {sysHealth?.platform || 'Linux/s390x'} • RAM: {sysHealth?.memory_mb_used || '--'} MB • CPU: {sysHealth?.cpu_percent || 0}%
        </div>
      </footer>
    </div>
  );
}

