import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Copy, ChevronLeft, AlertTriangle, CheckCircle2, Circle, CircleDashed } from 'lucide-react';
import { api } from '../lib/api';
import type {
  ContainerDetailResponse, ContainerFactsResponse, ContainerFact, ContainerRiskProfile,
} from '../types/api';
import { fmtDate, fmtRelative } from '../lib/format';
import { documentLabel } from '../lib/exceptions';
import { CHANNEL_BADGE, CHANNEL_LABELS, factSourceLabel } from '../lib/channels';
import { ExceptionCard } from './ExceptionsPage';

const SECTION_HEADING: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 10,
};

export function ContainerDetailPage() {
  const { containerNo } = useParams<{ containerNo: string }>();
  const [detail, setDetail] = useState<ContainerDetailResponse | null>(null);
  const [facts, setFacts] = useState<ContainerFactsResponse | null>(null);
  const [risk, setRisk] = useState<ContainerRiskProfile | null>(null);
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

    // Risk is supplementary: a failure here must not blank the profile page.
    api.getContainerExceptions(containerNo).then(setRisk).catch(() => setRisk(null));
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

  const DATE_FIELDS = new Set(['etd', 'eta', 'ata']);

  // `field` must not be named `key`: React consumes a `key` prop and never
  // passes it to the component, which left every cell rendering as empty.
  function FactCell({ label, field, monoVal = true }: { label: string; field: string; monoVal?: boolean }) {
    const rawVal = c[field as keyof typeof c] as string | number | null;
    const sourceFacts = factsByField[field] ?? [];
    const latestFact = sourceFacts[0];
    const displayVal = rawVal ?? latestFact?.field_value ?? null;

    return (
      <div className="fact-cell">
        <span className="fact-label">{label}</span>
        {displayVal !== null && displayVal !== ''
          ? <>
              <span className="fact-value" style={{ fontFamily: monoVal ? 'var(--font-mono)' : 'var(--font-ui)' }}>
                {DATE_FIELDS.has(field) ? fmtDate(String(displayVal)) : displayVal}
              </span>
              {latestFact && (
                <span className="fact-source">{factSourceLabel(latestFact)}</span>
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

      {/* Exceptions — what needs action on this shipment */}
      {risk && risk.exceptions.length > 0 && (
        <section>
          <h2 style={SECTION_HEADING}>Cần xử lý ({risk.exceptions.length})</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {risk.exceptions.map((exception, index) => (
              <ExceptionCard key={`${exception.code}-${index}`} exception={exception} />
            ))}
          </div>
        </section>
      )}

      {/* Document checklist */}
      {risk && (
        <section>
          <h2 style={SECTION_HEADING}>
            Chứng từ ({risk.documents_present.length}/{risk.documents_present.length + risk.documents_missing.length}
            {' · '}{risk.direction === 'import' ? 'hàng nhập' : 'hàng xuất'})
          </h2>
          <div className="card">
            <div style={{ height: 6, background: 'var(--bg-app)', borderRadius: 999, overflow: 'hidden', marginBottom: 14 }}>
              <div
                style={{
                  height: '100%',
                  width: `${Math.round(risk.completeness * 100)}%`,
                  background: risk.completeness === 1 ? 'var(--success)' : 'var(--accent)',
                }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {risk.documents_present.map(doc => (
                <div key={doc} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <CheckCircle2 size={15} style={{ color: 'var(--success)', flexShrink: 0 }} />
                  <span style={{ color: 'var(--text-primary)' }}>{documentLabel(doc)}</span>
                </div>
              ))}
              {risk.documents_missing.map(doc => {
                const mentioned = risk.documents_mentioned.includes(doc);
                return (
                  <div key={doc} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                    {mentioned
                      ? <CircleDashed size={15} style={{ color: 'var(--warning)', flexShrink: 0 }} />
                      : <Circle size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />}
                    <span style={{ color: mentioned ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                      {documentLabel(doc)}
                    </span>
                    <span
                      className={`badge ${mentioned ? 'badge-info' : 'badge-warning'}`}
                      style={{ marginLeft: 'auto' }}
                      title={mentioned
                        ? 'Một tin nhắn hoặc email có nhắc tới chứng từ này, nhưng file chưa vào Agentify'
                        : undefined}
                    >
                      {mentioned ? 'Có thông tin, chưa có file' : 'Chưa thấy'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* Summary facts */}
      <section>
        <h2 style={SECTION_HEADING}>Identifiers</h2>
        <div className="fact-grid">
          <FactCell label="Booking" field="booking_no" />
          <FactCell label="B/L" field="bl_no" />
          <FactCell label="PO" field="po_no" />
          <FactCell label="D/O" field="do_no" />
          <FactCell label="Seal" field="seal_no" />
        </div>
      </section>

      <section>
        <h2 style={SECTION_HEADING}>Route</h2>
        <div className="fact-grid">
          <FactCell label="POL" field="pol" monoVal={false} />
          <FactCell label="POD" field="pod" monoVal={false} />
          <FactCell label="Vessel" field="vessel" monoVal={false} />
          <FactCell label="Voyage" field="voyage" />
        </div>
      </section>

      <section>
        <h2 style={SECTION_HEADING}>Schedule &amp; free time</h2>
        <div className="fact-grid">
          <FactCell label="ETD" field="etd" monoVal={false} />
          <FactCell label="ETA" field="eta" monoVal={false} />
          <FactCell label="ATA" field="ata" monoVal={false} />
          <FactCell label="Free time (ngày)" field="free_time_days" monoVal={false} />
        </div>
        {risk?.free_time_expires_on && (
          <p style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
            Hết free time: <strong>{fmtDate(risk.free_time_expires_on)}</strong>
            {risk.free_time_is_assumed && ' (số ngày chưa có trong chứng từ, đang tạm tính)'}
          </p>
        )}
      </section>

      {/* Related messages, across every channel */}
      {detail.related_emails.length > 0 && (
        <section>
          <h2 style={SECTION_HEADING}>
            Nguồn liên quan ({detail.related_emails.length})
          </h2>
          <div className="card" style={{ padding: 0 }}>
            {detail.related_emails.map(e => (
              <Link key={e.id} to={`/emails/${e.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                <div className="list-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontWeight: 500, fontSize: 14 }} className="truncate">{e.subject}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{fmtDate(e.sent_at)}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                    <span className={`badge ${CHANNEL_BADGE[e.channel] ?? 'badge-neutral'}`}>
                      {CHANNEL_LABELS[e.channel] ?? e.channel}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }} className="truncate">{e.from_email}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Fact history */}
      {facts && facts.items.length > 0 && (
        <section>
          <h2 style={SECTION_HEADING}>
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
                      {factSourceLabel(f)}
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
