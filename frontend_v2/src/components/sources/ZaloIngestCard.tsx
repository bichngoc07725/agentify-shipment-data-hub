import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Search, Send } from 'lucide-react';
import { api } from '../../lib/api';
import type { ManualIngestPreview, ManualIngestResult } from '../../types/api';

const SAMPLE = `Ops: Xe 51F-12345 lấy cont MSCU1234567 tại Cát Lái, cutoff 14h chiều nay nhé.
Tài xế B: Em nhận. Đã có D/O số DO-2026-4471 chưa anh?
Ops: Có rồi, free time 7 ngày kể từ ngày tàu cập.`;

const FIELD_LABELS: Record<string, string> = {
  container_no: 'Container',
  booking_no: 'Booking',
  bl_no: 'B/L',
  do_no: 'D/O',
  po_no: 'PO',
  seal_no: 'Seal',
  invoice_no: 'Invoice',
  pol: 'POL',
  pod: 'POD',
  vessel: 'Vessel',
  voyage: 'Voyage',
  eta: 'ETA',
  etd: 'ETD',
  ata: 'ATA',
};

/** Flatten identifiers + route into the non-empty pairs worth showing. */
function readableFields(preview: ManualIngestPreview): [string, string][] {
  const merged: Record<string, unknown> = {
    ...(preview.fields.identifiers ?? {}),
    ...(preview.fields.route ?? {}),
  };
  if (preview.fields.free_time_days != null) {
    merged.free_time_days = preview.fields.free_time_days;
  }

  return Object.entries(merged)
    .filter(([, value]) => value !== null && value !== undefined && value !== '' &&
      !(Array.isArray(value) && value.length === 0))
    .map(([key, value]) => [
      FIELD_LABELS[key] ?? (key === 'free_time_days' ? 'Free time (ngày)' : key),
      Array.isArray(value) ? value.join(', ') : String(value),
    ]);
}

export function ZaloIngestCard({ onIngested }: { onIngested?: () => void }) {
  const [content, setContent] = useState('');
  const [sourceLabel, setSourceLabel] = useState('');
  const [sender, setSender] = useState('');
  const [preview, setPreview] = useState<ManualIngestPreview | null>(null);
  const [result, setResult] = useState<ManualIngestResult | null>(null);
  const [busy, setBusy] = useState<'preview' | 'save' | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setPreview(null);
    setResult(null);
    setError(null);
  }

  async function handlePreview() {
    if (!content.trim()) return;
    setBusy('preview'); setError(null); setResult(null);
    try {
      setPreview(await api.previewManualIngest({
        channel: 'zalo',
        content,
        source_label: sourceLabel || undefined,
        sender: sender || undefined,
      }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không đọc được nội dung');
    } finally { setBusy(null); }
  }

  async function handleSave() {
    setBusy('save'); setError(null);
    try {
      const saved = await api.createManualIngest({
        channel: 'zalo',
        content,
        source_label: sourceLabel || undefined,
        sender: sender || undefined,
      });
      setResult(saved);
      setPreview(null);
      setContent('');
      onIngested?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không lưu được');
    } finally { setBusy(null); }
  }

  const fields = preview ? readableFields(preview) : [];

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <h3 style={{ fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          💬 Đưa tin nhắn Zalo vào hồ sơ lô hàng
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}>
          Dán tin nhắn cần lưu. Agentify đọc thử và cho bạn xem trước — không có gì được ghi
          vào hồ sơ cho tới khi bạn xác nhận.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label" htmlFor="zalo-group">Nhóm chat / nguồn</label>
          <input
            id="zalo-group"
            className="form-input"
            value={sourceLabel}
            onChange={e => setSourceLabel(e.target.value)}
            placeholder="Group Điều xe Cát Lái"
          />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="zalo-sender">Người gửi</label>
          <input
            id="zalo-sender"
            className="form-input"
            value={sender}
            onChange={e => setSender(e.target.value)}
            placeholder="Ops - Nguyễn Văn A"
          />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="zalo-content">Nội dung tin nhắn</label>
        <textarea
          id="zalo-content"
          className="form-input"
          value={content}
          onChange={e => { setContent(e.target.value); reset(); }}
          rows={5}
          placeholder="Dán tin nhắn Zalo vào đây…"
          style={{ resize: 'vertical', fontFamily: 'var(--font-ui)', lineHeight: 1.6 }}
        />
        <p className="form-helper">
          Chưa có gì để thử?{' '}
          <button
            type="button"
            onClick={() => { setContent(SAMPLE); setSourceLabel('Group Điều xe Cát Lái'); setSender('Ops - Nguyễn Văn A'); reset(); }}
            style={{ background: 'none', border: 'none', padding: 0, color: 'var(--accent)', cursor: 'pointer', font: 'inherit' }}
          >
            dùng tin nhắn mẫu
          </button>
        </p>
      </div>

      {error && <div className="banner banner-danger"><AlertTriangle size={15} /> {error}</div>}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className="btn btn-secondary"
          onClick={handlePreview}
          disabled={!content.trim() || busy !== null}
        >
          <Search size={14} /> {busy === 'preview' ? 'Đang đọc…' : 'Xem Agentify đọc được gì'}
        </button>
        {preview && (
          <button className="btn btn-primary" onClick={handleSave} disabled={busy !== null}>
            <Send size={14} /> {busy === 'save' ? 'Đang lưu…' : 'Xác nhận lưu vào hồ sơ'}
          </button>
        )}
      </div>

      {preview && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {preview.container_nos.length === 0 ? (
            <div className="banner banner-warning">
              <AlertTriangle size={15} style={{ flexShrink: 0 }} />
              <div>
                Không tìm thấy mã container nào trong tin nhắn này. Agentify chỉ gắn dữ liệu
                vào hồ sơ khi nhận ra được container, nên tin này sẽ không tạo ra fact nào.
              </div>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sẽ gắn vào:</span>
                {preview.matched_containers.map(no => (
                  <span key={no} className="badge badge-success mono">{no} · đã có</span>
                ))}
                {preview.new_containers.map(no => (
                  <span key={no} className="badge badge-warning mono">{no} · tạo mới</span>
                ))}
              </div>
              {preview.new_containers.length > 0 && (
                <p style={{ fontSize: 12, color: 'var(--warning)' }}>
                  Container chưa có trong Agentify sẽ được tạo mới. Kiểm tra lại mã trước khi lưu
                  để tránh tạo hồ sơ từ một lỗi gõ.
                </p>
              )}
            </>
          )}

          {fields.length > 0 && (
            <div className="fact-grid">
              {fields.map(([label, value]) => (
                <div key={label} className="fact-cell">
                  <span className="fact-label">{label}</span>
                  <span className="fact-value mono">{value}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span>Cách đọc: {preview.extraction_method}</span>
            {preview.document_type && <span>Loại: {preview.document_type}</span>}
            {preview.extraction_status !== 'ok' && (
              <span style={{ color: 'var(--warning)' }}>
                Trạng thái: {preview.extraction_status}
                {preview.extraction_error ? ` — ${preview.extraction_error}` : ''}
              </span>
            )}
          </div>
        </div>
      )}

      {result && (
        <div className="banner banner-info">
          <CheckCircle size={15} style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            Đã lưu {result.fact_count} dữ liệu vào{' '}
            {result.linked_containers.length > 0
              ? result.linked_containers.map((no, i) => (
                  <span key={no}>
                    {i > 0 && ', '}
                    <Link to={`/containers/${no}`} className="mono" style={{ color: 'var(--accent)' }}>{no}</Link>
                  </span>
                ))
              : 'hệ thống (chưa gắn được container nào)'}
            .
          </div>
        </div>
      )}
    </div>
  );
}
