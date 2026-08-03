import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Download, FileWarning, Plus, RefreshCw, Scale, Search, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { canApproveReconciliation, canExportErp, canManageDebitNote, canRunReconciliation } from '../lib/permissions';
import type {
  DebitNote, DebitNoteChargeInput, Quote, Reconciliation, ReconciliationMatchStatus,
} from '../types/api';
import { fmtDate, fmtDateTime } from '../lib/format';

const MATCH_LABELS: Record<ReconciliationMatchStatus, string> = {
  matched: 'Khớp',
  variance: 'Lệch',
  missing_actual: 'Thiếu chi phí thực',
  extra_actual: 'Phát sinh ngoài báo giá',
};

const MATCH_ROW_STYLE: Record<ReconciliationMatchStatus, React.CSSProperties> = {
  matched: {},
  variance: { background: 'rgba(179, 58, 58, 0.08)' },
  extra_actual: { background: 'rgba(179, 58, 58, 0.08)' },
  missing_actual: { background: 'var(--bg-app)', color: 'var(--text-muted)' },
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Nháp',
  reviewed: 'Đã rà soát',
  approved: 'Đã duyệt',
  escalated: 'Chờ duyệt (chênh lệch lớn)',
};

const STATUS_BADGE: Record<string, string> = {
  draft: 'badge-neutral',
  reviewed: 'badge-info',
  approved: 'badge-success',
  escalated: 'badge-danger',
};

function emptyCharge(): DebitNoteChargeInput {
  return { charge_code: '', description: '', amount: '0', currency: 'USD', quantity: '1' };
}

export function ReconciliationPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [containerNo, setContainerNo] = useState(searchParams.get('container') ?? '');
  const [inputContainerNo, setInputContainerNo] = useState(containerNo);

  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [debitNotes, setDebitNotes] = useState<DebitNote[]>([]);
  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedQuoteId, setSelectedQuoteId] = useState('');
  const [runBusy, setRunBusy] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [dnPartner, setDnPartner] = useState('');
  const [dnDocNo, setDnDocNo] = useState('');
  const [dnCharges, setDnCharges] = useState<DebitNoteChargeInput[]>([emptyCharge()]);
  const [dnBusy, setDnBusy] = useState(false);
  const [dnError, setDnError] = useState<string | null>(null);

  const [approveBusyId, setApproveBusyId] = useState<string | null>(null);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [exportBusyId, setExportBusyId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async (no: string) => {
    if (!no.trim()) return;
    setLoading(true); setError(null);
    try {
      const [quotesRes, debitNotesRes, reconciliationsRes] = await Promise.all([
        api.getContainerQuotes(no),
        api.getContainerDebitNotes(no),
        api.getContainerReconciliations(no),
      ]);
      setQuotes(quotesRes.items);
      setDebitNotes(debitNotesRes.items);
      setReconciliations(reconciliationsRes.items);
      if (quotesRes.items.length > 0) setSelectedQuoteId(prev => prev || quotesRes.items[0].id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không tải được dữ liệu đối soát');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (containerNo) load(containerNo); }, [containerNo, load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const value = inputContainerNo.trim().toUpperCase();
    setContainerNo(value);
    setSearchParams(value ? { container: value } : {});
  }

  function updateCharge(index: number, patch: Partial<DebitNoteChargeInput>) {
    setDnCharges(prev => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  }

  async function handleAddDebitNote() {
    setDnBusy(true); setDnError(null);
    try {
      await api.createDebitNote({
        container_no: containerNo,
        partner_name: dnPartner || undefined,
        doc_no: dnDocNo || undefined,
        charges: dnCharges.filter(c => c.charge_code.trim()),
      });
      setDnPartner(''); setDnDocNo(''); setDnCharges([emptyCharge()]);
      await load(containerNo);
    } catch (e: unknown) {
      setDnError(e instanceof Error ? e.message : 'Không lưu được debit note');
    } finally { setDnBusy(false); }
  }

  async function handleRunReconciliation() {
    if (!selectedQuoteId) return;
    setRunBusy(true); setRunError(null);
    try {
      await api.createReconciliation({ container_no: containerNo, quote_id: selectedQuoteId });
      await load(containerNo);
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : 'Không chạy được đối soát');
    } finally { setRunBusy(false); }
  }

  async function handleApprove(id: string) {
    setApproveBusyId(id); setApproveError(null);
    try {
      await api.approveReconciliation(id);
      await load(containerNo);
    } catch (e: unknown) {
      setApproveError(e instanceof Error ? e.message : 'Không duyệt được');
    } finally { setApproveBusyId(null); }
  }

  async function handleExport(id: string) {
    setExportBusyId(id); setExportError(null);
    try {
      const { blob, filename } = await api.exportReconciliation(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setExportError(e instanceof Error ? e.message : 'Không xuất được file');
    } finally { setExportBusyId(null); }
  }

  return (
    <div className="page-container">
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Đối soát chi phí</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          So khớp báo giá đã gửi khách với chi phí thực từ debit note — làm nổi khoản lệch, khoản thiếu, khoản phát sinh.
        </p>
      </div>

      <form onSubmit={handleSearch} style={{ maxWidth: 420 }}>
        <div className="toolbar-search" style={{ maxWidth: '100%', height: 40 }}>
          <Search size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            className="mono"
            value={inputContainerNo}
            onChange={e => setInputContainerNo(e.target.value)}
            placeholder="Nhập số container, VD MSCU1234567"
            aria-label="Nhập số container để đối soát"
          />
        </div>
      </form>

      {!containerNo && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px', border: '1px dashed var(--border-strong)' }}>
          <Scale size={32} className="empty-state-icon" />
          <h2 style={{ fontSize: 16, marginBottom: 8 }}>Nhập số container để bắt đầu</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Đối soát được tính theo từng container, dựa trên báo giá và debit note đã có của lô đó.</p>
        </div>
      )}

      {containerNo && error && <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>}

      {containerNo && loading && (
        <div className="skeleton" style={{ height: 160, borderRadius: 10 }} />
      )}

      {containerNo && !loading && !error && (
        <>
          {quotes.length === 0 ? (
            <div className="banner banner-warning">
              <FileWarning size={15} style={{ flexShrink: 0 }} />
              Container <Link to={`/containers/${containerNo}`} className="mono">{containerNo}</Link> chưa có báo giá nào —
              cần tạo báo giá (GĐ4) trước khi đối soát được.
            </div>
          ) : (
            canRunReconciliation(user?.role) && (
              <div className="card">
                <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Chạy đối soát</h2>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div className="form-group" style={{ minWidth: 240 }}>
                    <label className="form-label">Báo giá dùng làm baseline</label>
                    <select className="form-select" value={selectedQuoteId} onChange={e => setSelectedQuoteId(e.target.value)}>
                      {quotes.map(q => (
                        <option key={q.id} value={q.id}>{q.quote_no} — {q.customer_name} ({q.currency} {q.total_amount})</option>
                      ))}
                    </select>
                  </div>
                  <button className="btn btn-primary" onClick={handleRunReconciliation} disabled={runBusy}>
                    <RefreshCw size={14} /> {runBusy ? 'Đang chạy…' : 'Chạy đối soát'}
                  </button>
                </div>
                {runError && <div className="banner banner-danger" style={{ marginTop: 10 }}><AlertTriangle size={15} /> {runError}</div>}
              </div>
            )
          )}

          {canManageDebitNote(user?.role) && (
            <div className="card">
              <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Nạp debit note</h2>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                Nhập tay chi phí thực từ debit note/invoice của hãng tàu hoặc đối tác.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label">Đối tác phát hành</label>
                  <input className="form-input" value={dnPartner} onChange={e => setDnPartner(e.target.value)} placeholder="ONE Line" />
                </div>
                <div className="form-group">
                  <label className="form-label">Số debit note</label>
                  <input className="form-input" value={dnDocNo} onChange={e => setDnDocNo(e.target.value)} placeholder="DN-2026-001" />
                </div>
              </div>

              {dnCharges.map((c, i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 90px 90px 28px', gap: 8, marginBottom: 8 }}>
                  <input className="form-input" style={{ padding: '5px 8px', fontSize: 13 }} value={c.charge_code}
                    onChange={e => updateCharge(i, { charge_code: e.target.value })} placeholder="Mã phí" />
                  <input className="form-input" style={{ padding: '5px 8px', fontSize: 13 }} value={c.description ?? ''}
                    onChange={e => updateCharge(i, { description: e.target.value })} placeholder="Mô tả" />
                  <input className="form-input" type="number" style={{ padding: '5px 8px', fontSize: 13 }} value={c.amount}
                    onChange={e => updateCharge(i, { amount: e.target.value })} placeholder="Số tiền" />
                  <input className="form-input" type="number" style={{ padding: '5px 8px', fontSize: 13 }} value={c.quantity}
                    onChange={e => updateCharge(i, { quantity: e.target.value })} />
                  <button className="btn btn-ghost btn-icon" onClick={() => setDnCharges(prev => prev.filter((_, idx) => idx !== i))}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setDnCharges(prev => [...prev, emptyCharge()])}>
                  <Plus size={13} /> Thêm dòng phí
                </button>
                <button className="btn btn-primary btn-sm" onClick={handleAddDebitNote} disabled={dnBusy}>
                  {dnBusy ? 'Đang lưu…' : 'Lưu debit note'}
                </button>
              </div>
              {dnError && <div className="banner banner-danger" style={{ marginTop: 10 }}><AlertTriangle size={15} /> {dnError}</div>}
            </div>
          )}

          {debitNotes.length > 0 && (
            <section>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
                Debit note đã nạp ({debitNotes.length})
              </h2>
              <div className="card" style={{ padding: 0 }}>
                {debitNotes.map(note => (
                  <div key={note.id} className="list-row">
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{note.partner_name ?? 'Không rõ đối tác'} {note.doc_no ? `· ${note.doc_no}` : ''}</span>
                      <span className="mono">{note.currency} {note.total_amount}</span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      {note.charges.length} dòng phí · {fmtDate(note.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {approveError && <div className="banner banner-danger"><AlertTriangle size={16} /> {approveError}</div>}
          {exportError && <div className="banner banner-danger"><AlertTriangle size={16} /> {exportError}</div>}

          {reconciliations.length > 0 && (
            <section>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
                Kết quả đối soát
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {reconciliations.map(rec => (
                  <div key={rec.id} className="card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={`badge ${STATUS_BADGE[rec.status]}`}>{STATUS_LABELS[rec.status]}</span>
                        <span style={{ fontSize: 13 }}>Baseline: <span className="mono">{rec.quote_no}</span></span>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDateTime(rec.created_at)}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        {rec.needs_approval && rec.status === 'escalated' && canApproveReconciliation(user?.role) && (
                          <button className="btn btn-primary btn-sm" onClick={() => handleApprove(rec.id)} disabled={approveBusyId === rec.id}>
                            <CheckCircle2 size={14} /> {approveBusyId === rec.id ? 'Đang duyệt…' : 'Duyệt chênh lệch'}
                          </button>
                        )}
                        {canExportErp(user?.role) && (
                          <button className="btn btn-secondary btn-sm" onClick={() => handleExport(rec.id)} disabled={exportBusyId === rec.id}>
                            <Download size={14} /> {exportBusyId === rec.id ? 'Đang xuất…' : 'Xuất ERP'}
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ background: 'var(--bg-app)', borderBottom: '1px solid var(--border-subtle)' }}>
                            {['Mã phí', 'Giá báo', 'Giá thực', 'Chênh lệch', 'Trạng thái', 'Ghi chú'].map(h => (
                              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 500, color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {rec.lines.map(line => (
                            <tr key={line.id} style={{ borderBottom: '1px solid var(--border-subtle)', ...MATCH_ROW_STYLE[line.match_status] }}>
                              <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)' }}>{line.charge_code}</td>
                              <td style={{ padding: '8px 12px' }}>{line.quoted_amount ?? '—'}</td>
                              <td style={{ padding: '8px 12px' }}>{line.actual_amount ?? '—'}</td>
                              <td style={{ padding: '8px 12px', fontWeight: 600 }}>{line.variance}</td>
                              <td style={{ padding: '8px 12px' }}>{MATCH_LABELS[line.match_status]}</td>
                              <td style={{ padding: '8px 12px', color: 'var(--text-muted)', fontSize: 12 }}>{line.note ?? ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div style={{ display: 'flex', gap: 20, marginTop: 12, fontSize: 13, fontWeight: 600 }}>
                      <span>Tổng báo giá: {rec.total_quoted}</span>
                      <span>Tổng thực: {rec.total_actual}</span>
                      <span style={{ color: rec.total_variance !== '0.00' && rec.total_variance !== '0' ? 'var(--danger)' : undefined }}>
                        Chênh lệch: {rec.total_variance}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
