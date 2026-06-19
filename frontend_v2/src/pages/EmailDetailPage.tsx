import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ChevronLeft, Paperclip, AlertTriangle, FileText } from 'lucide-react';
import { api } from '../lib/api';
import type { EmailDetail, EmailAttachment } from '../types/api';
import { fmtDateTime, fmtBytes, emailStatusLabel } from '../lib/format';

export function EmailDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<EmailDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAttachment, setActiveAttachment] = useState<EmailAttachment | null>(null);
  const [showCc, setShowCc] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true); setError(null);
    api.getEmail(id)
      .then(d => { setDetail(d); if (d.attachments.length) setActiveAttachment(d.attachments[0]); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <div style={{ flex: 1, padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="skeleton" style={{ height: 24, width: '60%' }} />
        <div className="skeleton" style={{ height: 16, width: '35%' }} />
        <div className="skeleton" style={{ flex: 1, borderRadius: 10 }} />
      </div>
      <div style={{ width: 280, borderLeft: '1px solid var(--border-subtle)', padding: 16 }}>
        <div className="skeleton" style={{ height: 200 }} />
      </div>
    </div>
  );

  if (error || !detail) return (
    <div style={{ padding: 24 }}>
      <div className="banner banner-danger"><AlertTriangle size={16} /> {error ?? 'Email không tồn tại'}</div>
    </div>
  );

  const { label, cls } = emailStatusLabel(detail.email.processing_status);
  const bodyContent = detail.email.body_text ?? detail.email.snippet ?? '';

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Email reader (65%) */}
      <div className="email-reader">
        <Link to="/emails" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none', flexShrink: 0 }}>
          <ChevronLeft size={15} /> Emails
        </Link>

        {/* Email header */}
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.3 }}>{detail.email.subject}</h1>
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: 'var(--text-secondary)' }}>
            <div><span style={{ color: 'var(--text-muted)', minWidth: 40, display: 'inline-block' }}>From</span> {detail.email.from_email}</div>
            {detail.email.to_emails.length > 0 && (
              <div><span style={{ color: 'var(--text-muted)', minWidth: 40, display: 'inline-block' }}>To</span> {detail.email.to_emails.join(', ')}</div>
            )}
            {detail.email.cc_emails.length > 0 && (
              <button onClick={() => setShowCc(!showCc)} style={{ textAlign: 'left', background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, padding: 0 }}>
                {showCc ? 'Ẩn CC' : `CC (${detail.email.cc_emails.length})`}
              </button>
            )}
            {showCc && <div style={{ paddingLeft: 44 }}>{detail.email.cc_emails.join(', ')}</div>}
            <div><span style={{ color: 'var(--text-muted)', minWidth: 40, display: 'inline-block' }}>Sent</span> {fmtDateTime(detail.email.sent_at)}</div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span className={`badge ${cls}`}>{label}</span>
            {detail.email.has_pdf_attachments && <span className="badge badge-neutral"><Paperclip size={10} style={{ marginRight: 4 }} /> {detail.attachments.length} attachment</span>}
          </div>
        </div>

        {/* Email body */}
        <div className="email-body">
          {bodyContent
            ? <pre style={{ fontFamily: 'var(--font-ui)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>{bodyContent}</pre>
            : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Nội dung email không có trong dữ liệu Agentify</span>
          }
        </div>

        {/* Attachments */}
        {detail.attachments.length > 0 && (
          <section>
            <h2 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Attachments ({detail.attachments.length})</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {detail.attachments.map(a => (
                <div
                  key={a.id}
                  className={`attachment-item${activeAttachment?.id === a.id ? ' selected' : ''}`}
                  onClick={() => setActiveAttachment(a)}
                  role="button" tabIndex={0}
                  onKeyDown={k => k.key === 'Enter' && setActiveAttachment(a)}
                >
                  <FileText size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }} className="truncate">{a.filename}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.mime_type} · {fmtBytes(a.size_bytes)}</div>
                  </div>
                  <AttachmentStatusBadge status={a.text_extract_status} />
                </div>
              ))}
            </div>

            {/* Active attachment detail */}
            {activeAttachment && (
              <div style={{ marginTop: 12, padding: 16, background: 'var(--bg-panel)', border: '1px solid var(--border-subtle)', borderRadius: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: 'var(--text-secondary)' }}>{activeAttachment.filename}</div>
                {activeAttachment.text_extract_status === 'completed' ? (
                  activeAttachment.extracted_record ? (
                    <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflow: 'auto' }}>
                      {JSON.stringify(activeAttachment.extracted_record, null, 2)}
                    </pre>
                  ) : <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Text extracted — no structured fields found.</span>
                ) : activeAttachment.text_extract_status === 'no_text_layer' ? (
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 4 }}>Unsupported in prototype</p>
                    <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>This prototype only processes text-based PDFs.</p>
                  </div>
                ) : (
                  <span className="badge badge-neutral">{activeAttachment.text_extract_status}</span>
                )}
              </div>
            )}
          </section>
        )}
      </div>

      {/* Source inspector (30-35%) */}
      <div className="inspector-panel" style={{ width: 300 }}>
        {/* Linked containers */}
        <div>
          <div className="inspector-section-title">Linked containers</div>
          {detail.linked_containers.length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Chưa tìm thấy trong dữ liệu Agentify</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {detail.linked_containers.map(cn => (
                <Link key={cn} to={`/containers/${cn}`} style={{ textDecoration: 'none' }}>
                  <div style={{ padding: '8px 10px', background: 'var(--accent-soft)', borderRadius: 7, cursor: 'pointer' }}>
                    <span className="mono" style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}>{cn}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="divider" />

        {/* Extracted facts */}
        <div>
          <div className="inspector-section-title">Extracted facts ({detail.extracted_facts.length})</div>
          {detail.extracted_facts.length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Chưa tìm thấy trong dữ liệu Agentify</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {detail.extracted_facts.map(f => (
                <div key={f.id} style={{ borderLeft: '2px solid var(--border-strong)', paddingLeft: 10 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{f.field_name}</div>
                  <div style={{ fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-mono)', marginTop: 2 }}>{f.field_value}</div>
                  <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 2 }}>
                    {f.source_type === 'attachment' ? `PDF · ${f.source_label ?? 'file'}` : 'Email body'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="divider" />

        {/* Processing details */}
        <div>
          <div className="inspector-section-title">Processing details</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Status</span>
              <span className={`badge ${cls}`} style={{ fontSize: 10 }}>{label}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Attachments</span>
              <span>{detail.attachments.length}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Facts</span>
              <span>{detail.extracted_facts.length}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AttachmentStatusBadge({ status }: { status: string }) {
  if (status === 'completed') return <span className="badge badge-success" style={{ fontSize: 10 }}>Extracted</span>;
  if (status === 'no_text_layer') return <span className="badge badge-warning" style={{ fontSize: 10 }}>No text layer</span>;
  if (status === 'failed') return <span className="badge badge-danger" style={{ fontSize: 10 }}>Failed</span>;
  return <span className="badge badge-neutral" style={{ fontSize: 10 }}>{status}</span>;
}
