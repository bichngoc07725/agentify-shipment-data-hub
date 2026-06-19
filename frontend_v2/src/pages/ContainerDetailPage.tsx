import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Copy, Mail, Paperclip, ChevronLeft, AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';
import type { ContainerDetailResponse, ContainerFactsResponse, ContainerFact } from '../types/api';
import { fmtDate, fmtDateTime, fmtRelative } from '../lib/format';

export function ContainerDetailPage() {
  const { containerNo } = useParams<{ containerNo: string }>();
  const [detail, setDetail] = useState<ContainerDetailResponse | null>(null);
  const [facts, setFacts] = useState<ContainerFactsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!containerNo) return;
    setLoading(true); setError(null);
    Promise.all([
      api.getContainer(containerNo),
      api.getContainerFacts(containerNo),
    ]).then(([d, f]) => { setDetail(d); setFacts(f); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [containerNo]);

  function copyNo() {
    if (!containerNo) return;
    navigator.clipboard.writeText(containerNo).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    });
  }

  if (loading) return (
    <div className="detail-panel">
      <div className="skeleton" style={{ height: 100, borderRadius: 10 }} />
      <div className="skeleton" style={{ height: 200, borderRadius: 10 }} />
      <div className="skeleton" style={{ height: 140, borderRadius: 10 }} />
    </div>
  );

  if (error) return (
    <div className="detail-panel">
      <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>
    </div>
  );

  if (!detail) return null;

  const c = detail.container;

  // Group facts by field
  const factsByField: Record<string, ContainerFact[]> = {};
  facts?.items.forEach(f => {
    if (!factsByField[f.field_name]) factsByField[f.field_name] = [];
    factsByField[f.field_name].push(f);
  });

  const IDENTIFIER_FIELDS = ['booking_no', 'bl_no', 'po_no', 'seal_no'];
  const ROUTE_FIELDS = ['pol', 'pod', 'vessel', 'voyage'];
  const SCHEDULE_FIELDS = ['etd', 'eta'];

  function FactCell({ label, key, monoVal = true }: { label: string; key: string; monoVal?: boolean }) {
    const rawVal = c[key as keyof typeof c] as string | null;
    const sourceFacts = factsByField[key] ?? [];
    const latestFact = sourceFacts[0];
    const displayVal = rawVal ?? latestFact?.field_value ?? null;

    return (
      <div className="fact-cell">
        <span className="fact-label">{label}</span>
        {displayVal
          ? <>
              <span className="fact-value" style={{ fontFamily: monoVal ? 'var(--font-mono)' : 'var(--font-ui)' }}>
                {key === 'etd' || key === 'eta' ? fmtDate(displayVal) : displayVal}
              </span>
              {latestFact && (
                <span className="fact-source">
                  {latestFact.source_type === 'attachment' ? `PDF · ${latestFact.source_label ?? 'file'}` : `Email · ${fmtDate(latestFact.source_sent_at)}`}
                </span>
              )}
            </>
          : <span className="fact-missing">Chưa tìm thấy trong dữ liệu Agentify</span>
        }
      </div>
    );
  }

  return (
    <div className="detail-panel">
      {/* Back */}
      <div>
        <Link to="/containers" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none' }}>
          <ChevronLeft size={15} /> Containers
        </Link>
      </div>

      {/* Header */}
      <div className="detail-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Container</div>
            <h1 className="mono" style={{ fontSize: 24 }}>{c.container_no}</h1>
            {c.status_text && <p style={{ marginTop: 6, color: 'var(--text-secondary)' }}>{c.status_text}</p>}
          </div>
          <button className="btn btn-secondary btn-sm" onClick={copyNo} aria-label="Copy container number">
            <Copy size={14} /> {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
          <span>{c.source_count} nguồn</span>
          <span>{c.attachment_count} file đính kèm</span>
          <span>Cập nhật {fmtRelative(c.updated_at)}</span>
        </div>
      </div>

      {/* Summary facts */}
      <section>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Identifiers</h2>
        <div className="fact-grid">
          <FactCell label="Booking" key="booking_no" />
          <FactCell label="B/L" key="bl_no" />
          <FactCell label="PO" key="po_no" />
        </div>
      </section>

      <section>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Route</h2>
        <div className="fact-grid">
          <FactCell label="POL" key="pol" monoVal={false} />
          <FactCell label="POD" key="pod" monoVal={false} />
          <FactCell label="Vessel" key="vessel" monoVal={false} />
          <FactCell label="Voyage" key="voyage" />
        </div>
      </section>

      <section>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Schedule</h2>
        <div className="fact-grid">
          <FactCell label="ETD" key="etd" monoVal={false} />
          <FactCell label="ETA" key="eta" monoVal={false} />
        </div>
      </section>

      {/* Related emails */}
      {detail.related_emails.length > 0 && (
        <section>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Related emails ({detail.related_emails.length})
          </h2>
          <div className="card" style={{ padding: 0 }}>
            {detail.related_emails.map(e => (
              <Link key={e.id} to={`/emails/${e.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                <div className="list-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontWeight: 500, fontSize: 14 }} className="truncate">{e.subject}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{fmtDate(e.sent_at)}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{e.from_email}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Fact history */}
      {facts && facts.items.length > 0 && (
        <section>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Fact history
          </h2>
          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Field', 'Value', 'Source', 'Date'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {facts.items.map(f => (
                  <tr key={f.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>{f.field_name}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{f.field_value}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--accent)', fontSize: 12 }}>
                      {f.source_type === 'attachment' ? `PDF · ${f.source_label ?? 'file'}` : 'Email body'}
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{fmtDate(f.source_sent_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
