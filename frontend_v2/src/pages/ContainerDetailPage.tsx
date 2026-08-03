import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Copy, ChevronLeft, AlertTriangle, CheckCircle2, Circle, CircleDashed, Pencil, X, Check, FileText, Camera, Scale, ShieldAlert } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import {
  canEditContainerFact, canViewCostData, canViewFieldImages,
  canCreateCustomsDeclaration, canEditCustomsDeclaration, canViewCustomsDeclaration,
} from '../lib/permissions';
import type {
  ContainerDetailResponse, ContainerFactsResponse, ContainerFact, ContainerRiskProfile, Quote,
  FieldImageListItem, Reconciliation, CustomsDeclaration, CustomsChannel,
} from '../types/api';
import { fmtDate, fmtRelative } from '../lib/format';
import { useAuthedFile } from '../lib/useAuthedFile';
import { documentLabel } from '../lib/exceptions';
import { CHANNEL_BADGE, CHANNEL_LABELS, factSourceLabel } from '../lib/channels';
import { ExceptionCard } from './ExceptionsPage';
import { ContainerProgressTimeline } from '../components/ContainerProgressTimeline';

const SECTION_HEADING: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 10,
};

const CHANNEL_BADGE_CLASS: Record<CustomsChannel, string> = {
  green: 'badge-success',
  yellow: 'badge-warning',
  red: 'badge-danger',
};

const CHANNEL_TEXT: Record<CustomsChannel, string> = {
  green: 'Luồng Xanh',
  yellow: 'Luồng Vàng',
  red: 'Luồng Đỏ',
};

/** One field-photo tile. Split out of the list so `useAuthedFile` — which
 * fetches the token-gated attachment endpoint — can be called per image
 * rather than inside a `.map()`. */
function FieldImageThumb({ image }: { image: FieldImageListItem }) {
  const src = useAuthedFile(image.file_url);

  return (
    <a
      href={src ?? undefined}
      target="_blank"
      rel="noreferrer"
      className="card"
      style={{ padding: 8, width: 140, textDecoration: 'none', color: 'inherit' }}
    >
      {src ? (
        <img
          src={src}
          alt={image.filename}
          style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: 6 }}
        />
      ) : (
        <div style={{ width: '100%', height: 100, borderRadius: 6, background: 'var(--bg-app)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Camera size={20} style={{ color: 'var(--text-muted)' }} />
        </div>
      )}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
        {image.document_type ?? 'field_image'}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{fmtDate(image.created_at)}</div>
    </a>
  );
}

export function ContainerDetailPage() {
  const { containerNo } = useParams<{ containerNo: string }>();
  const [detail, setDetail] = useState<ContainerDetailResponse | null>(null);
  const [facts, setFacts] = useState<ContainerFactsResponse | null>(null);
  const [risk, setRisk] = useState<ContainerRiskProfile | null>(null);
  const [quotes, setQuotes] = useState<Quote[] | null>(null);
  const [images, setImages] = useState<FieldImageListItem[] | null>(null);
  const [reconciliations, setReconciliations] = useState<Reconciliation[] | null>(null);
  const [customsDeclarations, setCustomsDeclarations] = useState<CustomsDeclaration[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { user } = useAuth();
  const [editingFactId, setEditingFactId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [customsFormOpen, setCustomsFormOpen] = useState(false);
  const [customsBusy, setCustomsBusy] = useState(false);
  const [customsError, setCustomsError] = useState<string | null>(null);
  const [customsDeclarationNo, setCustomsDeclarationNo] = useState('');
  const [customsChannel, setCustomsChannel] = useState<CustomsChannel | ''>('');
  const [customsHsCode, setCustomsHsCode] = useState('');

  // Kept callable so resolving an exception can re-read the risk profile —
  // the backend hides an actioned exception, so the refetch is what removes
  // the card. Failures leave the profile page intact (Driver gets a 403).
  const loadRisk = useCallback(() => {
    if (!containerNo) return;
    api.getContainerExceptions(containerNo).then(setRisk).catch(() => setRisk(null));
  }, [containerNo]);

  useEffect(() => {
    if (!containerNo) return;
    setLoading(true); setError(null);
    Promise.all([
      api.getContainer(containerNo),
      api.getContainerFacts(containerNo),
    ]).then(([d, f]) => { setDetail(d); setFacts(f); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));

    // Risk and quotes are supplementary: a failure here must not blank the
    // profile page (and quotes 403 for Driver, who has no reason to see them).
    loadRisk();
    api.getContainerQuotes(containerNo).then(r => setQuotes(r.items)).catch(() => setQuotes(null));
    api.getContainerFieldImages(containerNo).then(r => setImages(r.items)).catch(() => setImages(null));
    api.getContainerReconciliations(containerNo).then(r => setReconciliations(r.items)).catch(() => setReconciliations(null));
    api.getContainerCustoms(containerNo).then(r => setCustomsDeclarations(r.items)).catch(() => setCustomsDeclarations(null));
  }, [containerNo, loadRisk]);

  async function submitCustomsDeclaration() {
    if (!containerNo) return;
    setCustomsBusy(true); setCustomsError(null);
    try {
      const created = await api.createCustomsDeclaration({
        container_no: containerNo,
        declaration_no: customsDeclarationNo || undefined,
        channel: customsChannel || undefined,
        hs_code: customsHsCode || undefined,
      });
      setCustomsDeclarations(prev => [created, ...(prev ?? [])]);
      setCustomsFormOpen(false);
      setCustomsDeclarationNo(''); setCustomsChannel(''); setCustomsHsCode('');
    } catch (e: unknown) {
      setCustomsError(e instanceof Error ? e.message : 'Không lưu được tờ khai');
    } finally {
      setCustomsBusy(false);
    }
  }

  async function changeCustomsChannel(declaration: CustomsDeclaration, channel: CustomsChannel) {
    setCustomsBusy(true); setCustomsError(null);
    try {
      const updated = await api.updateCustomsDeclaration(declaration.id, {
        declaration_no: declaration.declaration_no ?? undefined,
        declaration_type: declaration.declaration_type,
        channel,
        hs_code: declaration.hs_code ?? undefined,
        channel_change_reason: 'Bẻ luồng thủ công',
      });
      setCustomsDeclarations(prev =>
        (prev ?? []).map(d => (d.id === updated.id ? updated : d)),
      );
    } catch (e: unknown) {
      setCustomsError(e instanceof Error ? e.message : 'Không đổi được luồng');
    } finally {
      setCustomsBusy(false);
    }
  }

  function copyNo() {
    if (!containerNo) return;
    navigator.clipboard.writeText(containerNo).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    });
  }

  function startEdit(fact: ContainerFact) {
    setEditingFactId(fact.id);
    setEditValue(fact.field_value);
    setEditError(null);
  }

  function cancelEdit() {
    setEditingFactId(null);
    setEditError(null);
  }

  async function saveEdit(fact: ContainerFact) {
    if (!containerNo) return;
    setEditBusy(true); setEditError(null);
    try {
      const updated = await api.editContainerFact(containerNo, fact.id, editValue);
      setFacts(prev => prev && {
        items: prev.items.map(f => (f.id === updated.id ? updated : f)),
      });
      setEditingFactId(null);
    } catch (e: unknown) {
      setEditError(e instanceof Error ? e.message : 'Không sửa được — kiểm tra lại quyền của vai trò này');
    } finally {
      setEditBusy(false);
    }
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
        <div style={{ marginTop: 16 }}>
          <ContainerProgressTimeline
            stage={c.shipment?.stage ?? null}
            slaBreached={c.shipment?.sla_breached}
          />
        </div>
      </div>

      {/* Exceptions — what needs action on this shipment */}
      {risk && risk.exceptions.length > 0 && (
        <section>
          <h2 style={SECTION_HEADING}>Cần xử lý ({risk.exceptions.length})</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {risk.exceptions.map((exception, index) => (
              <ExceptionCard key={`${exception.code}-${index}`} exception={exception} onActed={loadRisk} />
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

      {/* Quotes linked to this container */}
      {quotes && quotes.length > 0 && (
        <section>
          <h2 style={SECTION_HEADING}>Báo giá liên quan ({quotes.length})</h2>
          <div className="card" style={{ padding: 0 }}>
            {quotes.map(quote => (
              <Link
                key={quote.id}
                to={`/quotes/${quote.id}`}
                style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
              >
                <div className="list-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span className="mono" style={{ fontWeight: 600, fontSize: 14 }}>{quote.quote_no}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {quote.currency} {quote.total_amount}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                    <FileText size={13} style={{ color: 'var(--text-muted)' }} />
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{quote.customer_name}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Cost reconciliation: quoted vs. real charges (GĐ6) */}
      {reconciliations && reconciliations.length > 0 && canViewCostData(user?.role) && (
        <section>
          <h2 style={SECTION_HEADING}>Đối soát chi phí ({reconciliations.length})</h2>
          <div className="card" style={{ padding: 0 }}>
            {reconciliations.map(rec => (
              <Link
                key={rec.id}
                to={`/reconciliation?container=${containerNo}`}
                style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
              >
                <div className="list-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Scale size={13} style={{ color: 'var(--text-muted)' }} />
                      <span style={{ fontSize: 13 }}>Baseline <span className="mono">{rec.quote_no}</span></span>
                      <span
                        className={`badge ${
                          rec.status === 'escalated' ? 'badge-danger'
                          : rec.status === 'approved' ? 'badge-success'
                          : 'badge-neutral'
                        }`}
                      >
                        {rec.status === 'escalated' ? 'Chờ duyệt' : rec.status === 'approved' ? 'Đã duyệt' : 'Nháp'}
                      </span>
                    </div>
                    <span
                      className="mono"
                      style={{ fontSize: 12, color: rec.total_variance !== '0.00' && rec.total_variance !== '0' ? 'var(--danger)' : 'var(--text-muted)' }}
                    >
                      Chênh lệch: {rec.total_variance}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Customs declarations + phân luồng history (GĐ7A) */}
      {canViewCustomsDeclaration(user?.role) && (
        <section>
          <h2 style={SECTION_HEADING}>Hải quan</h2>
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {customsDeclarations && customsDeclarations.length > 0 ? (
              customsDeclarations.map(dec => (
                <div key={dec.id} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <ShieldAlert size={14} style={{ color: 'var(--text-muted)' }} />
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                      {dec.declaration_no ?? 'Chưa có số tờ khai'}
                    </span>
                    <span className={`badge ${dec.channel ? CHANNEL_BADGE_CLASS[dec.channel] : 'badge-neutral'}`}>
                      {dec.channel ? CHANNEL_TEXT[dec.channel] : 'Chưa phân luồng'}
                    </span>
                    {dec.hs_code && (
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }} className="mono">HS: {dec.hs_code}</span>
                    )}
                  </div>
                  {canEditCustomsDeclaration(user?.role) && (
                    <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                      {(['green', 'yellow', 'red'] as CustomsChannel[])
                        .filter(ch => ch !== dec.channel)
                        .map(ch => (
                          <button
                            key={ch}
                            className="btn btn-secondary btn-sm"
                            disabled={customsBusy}
                            onClick={() => changeCustomsChannel(dec, ch)}
                          >
                            Đổi sang {CHANNEL_TEXT[ch]}
                          </button>
                        ))}
                    </div>
                  )}
                  {dec.channel_history.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {dec.channel_history.map(h => (
                        <div key={h.id} style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {fmtDate(h.changed_at)}: {h.from_channel ? CHANNEL_TEXT[h.from_channel] : 'Khởi tạo'} → {CHANNEL_TEXT[h.to_channel]}
                          {h.reason ? ` (${h.reason})` : ''}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Chưa có tờ khai hải quan cho container này.</p>
            )}

            {canCreateCustomsDeclaration(user?.role) && (
              customsFormOpen ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <input
                    className="form-input"
                    placeholder="Số tờ khai"
                    value={customsDeclarationNo}
                    onChange={e => setCustomsDeclarationNo(e.target.value)}
                    disabled={customsBusy}
                  />
                  <input
                    className="form-input"
                    placeholder="Mã HS"
                    value={customsHsCode}
                    onChange={e => setCustomsHsCode(e.target.value)}
                    disabled={customsBusy}
                  />
                  <select
                    className="form-input"
                    value={customsChannel}
                    onChange={e => setCustomsChannel(e.target.value as CustomsChannel | '')}
                    disabled={customsBusy}
                  >
                    <option value="">Chưa có kết quả phân luồng</option>
                    <option value="green">Luồng Xanh</option>
                    <option value="yellow">Luồng Vàng</option>
                    <option value="red">Luồng Đỏ</option>
                  </select>
                  {customsError && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{customsError}</div>}
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={submitCustomsDeclaration} disabled={customsBusy}>
                      Lưu tờ khai
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setCustomsFormOpen(false)} disabled={customsBusy}>
                      Huỷ
                    </button>
                  </div>
                </div>
              ) : (
                <button className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setCustomsFormOpen(true)}>
                  + Nhập tờ khai
                </button>
              )
            )}
          </div>
        </section>
      )}

      {/* Field photos: container/seal/EIR/POD, read with vision */}
      {images && images.length > 0 && canViewFieldImages(user?.role) && (
        <section>
          <h2 style={SECTION_HEADING}>Ảnh hiện trường ({images.length})</h2>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {images.map(image => (
              <FieldImageThumb key={image.id} image={image} />
            ))}
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
                  {['Field', 'Value', 'Source', 'Date', ''].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {facts.items.map(f => {
                  const editable = canEditContainerFact(user?.role, f.field_name);
                  const isEditing = editingFactId === f.id;
                  return (
                    <tr key={f.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>{f.field_name}</td>
                      <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
                        {isEditing ? (
                          <input
                            className="form-input"
                            style={{ padding: '4px 8px', fontSize: 13, fontFamily: 'var(--font-mono)' }}
                            value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            autoFocus
                            disabled={editBusy}
                          />
                        ) : f.field_value}
                        {isEditing && editError && (
                          <div style={{ color: 'var(--danger)', fontFamily: 'var(--font-ui)', fontWeight: 400, fontSize: 12, marginTop: 4 }}>
                            {editError}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--accent)', fontSize: 12 }}>
                        {factSourceLabel(f)}
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{fmtDate(f.source_sent_at)}</td>
                      <td style={{ padding: '10px 14px' }}>
                        {isEditing ? (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button
                              className="btn btn-ghost btn-icon"
                              onClick={() => saveEdit(f)}
                              disabled={editBusy}
                              aria-label="Lưu"
                              title="Lưu"
                            >
                              <Check size={14} />
                            </button>
                            <button
                              className="btn btn-ghost btn-icon"
                              onClick={cancelEdit}
                              disabled={editBusy}
                              aria-label="Huỷ"
                              title="Huỷ"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ) : editable ? (
                          <button
                            className="btn btn-ghost btn-icon"
                            onClick={() => startEdit(f)}
                            aria-label={`Sửa ${f.field_name}`}
                            title="Sửa"
                          >
                            <Pencil size={14} />
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
