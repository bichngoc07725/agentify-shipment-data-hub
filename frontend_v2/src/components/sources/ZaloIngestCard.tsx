import { useState } from 'react';
import type { ClipboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Image as ImageIcon, Link2, Lock, Search, Send, X } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { canCreateManualIngest, ROLE_LABELS } from '../../lib/permissions';
import type { ManualIngestPreview, ManualIngestResult } from '../../types/api';

interface PastedImage {
  base64: string;
  mimeType: string;
  filename: string;
  previewUrl: string;
}

function readImageFromClipboard(items: DataTransferItemList): Promise<PastedImage | null> {
  const imageItem = Array.from(items).find(item => item.type.startsWith('image/'));
  if (!imageItem) return Promise.resolve(null);

  const file = imageItem.getAsFile();
  if (!file) return Promise.resolve(null);

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const [, base64] = dataUrl.split(',', 2);
      resolve({
        base64,
        mimeType: file.type || 'image/png',
        filename: file.name || `pasted-image-${Date.now()}.png`,
        previewUrl: dataUrl,
      });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

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
  const { user } = useAuth();
  const canSave = canCreateManualIngest(user?.role);
  const [content, setContent] = useState('');
  const [sourceLabel, setSourceLabel] = useState('');
  const [sender, setSender] = useState('');
  const [image, setImage] = useState<PastedImage | null>(null);
  const [preview, setPreview] = useState<ManualIngestPreview | null>(null);
  const [result, setResult] = useState<ManualIngestResult | null>(null);
  const [busy, setBusy] = useState<'preview' | 'save' | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setPreview(null);
    setResult(null);
    setError(null);
  }

  async function handlePaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const picked = await readImageFromClipboard(e.clipboardData.items).catch(() => null);
    if (!picked) return;
    e.preventDefault();
    setImage(picked);
    reset();
  }

  function removeImage() {
    setImage(null);
    reset();
  }

  async function handlePreview() {
    if (!content.trim() && !image) return;
    setBusy('preview'); setError(null); setResult(null);
    try {
      setPreview(await api.previewManualIngest({
        channel: 'zalo',
        content,
        source_label: sourceLabel || undefined,
        sender: sender || undefined,
        image_base64: image?.base64,
        image_mime_type: image?.mimeType,
        image_filename: image?.filename,
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
        image_base64: image?.base64,
        image_mime_type: image?.mimeType,
        image_filename: image?.filename,
      });
      setResult(saved);
      setPreview(null);
      setContent('');
      setImage(null);
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
          onPaste={handlePaste}
          rows={5}
          placeholder="Dán tin nhắn Zalo vào đây… (dán được cả ảnh, vd. ảnh chụp POD/EIR/container. Nếu tin có link tới file PDF/ảnh, Agentify tự tải về và đọc)"
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

      {image && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 8, background: 'var(--bg-app)', border: '1px solid var(--border-subtle)', borderRadius: 8 }}>
          <img
            src={image.previewUrl}
            alt="Ảnh đã dán"
            style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6, flexShrink: 0 }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
              <ImageIcon size={13} /> {image.filename}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Sẽ được đọc bằng AI (vision)</div>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            onClick={removeImage}
            aria-label="Bỏ ảnh"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {error && <div className="banner banner-danger"><AlertTriangle size={15} /> {error}</div>}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className="btn btn-secondary"
          onClick={handlePreview}
          disabled={(!content.trim() && !image) || busy !== null}
        >
          <Search size={14} /> {busy === 'preview' ? 'Đang đọc…' : 'Xem Agentify đọc được gì'}
        </button>
        {preview && canSave && (
          <button className="btn btn-primary" onClick={handleSave} disabled={busy !== null}>
            <Send size={14} /> {busy === 'save' ? 'Đang lưu…' : 'Xác nhận lưu vào hồ sơ'}
          </button>
        )}
      </div>

      {preview && !canSave && (
        <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
          <Lock size={13} style={{ flexShrink: 0 }} />
          Vai trò "{user ? ROLE_LABELS[user.role] : ''}" chỉ được xem trước, không được lưu vào hồ sơ. Cần vai trò Vận hành hoặc Chứng từ.
        </p>
      )}

      {preview && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {preview.link_url && (
            <div className="banner banner-info">
              <Link2 size={15} style={{ flexShrink: 0 }} />
              <div style={{ overflowWrap: 'anywhere' }}>
                Đã tự tải file từ link và đọc bằng AI: <span className="mono">{preview.link_url}</span>
              </div>
            </div>
          )}
          {preview.link_fetch_error && (
            <div className="banner banner-warning">
              <AlertTriangle size={15} style={{ flexShrink: 0 }} />
              <div>
                Có link trong tin nhắn nhưng không tải được file ({preview.link_fetch_error}) — vẫn đọc
                phần chữ như bình thường.
              </div>
            </div>
          )}
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
