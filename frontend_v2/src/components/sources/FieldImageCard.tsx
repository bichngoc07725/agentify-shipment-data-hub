import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Camera, CheckCircle, Send } from 'lucide-react';
import { api } from '../../lib/api';
import { useAuthedFile } from '../../lib/useAuthedFile';
import type { ExtractionCapabilityStatus, FieldImageConfirmResult, FieldImagePreview } from '../../types/api';

/** Off-screen but still laid out. `display: none` would be simpler, but WebKit
 * will not open the file dialog for an input that is not in the render tree —
 * neither via a label nor via a programmatic click. */
const VISUALLY_HIDDEN: React.CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

const DOC_KIND_LABELS: Record<string, string> = {
  container_photo: 'Ảnh container',
  seal_photo: 'Ảnh seal',
  eir: 'EIR / phiếu giao nhận',
  pod: 'POD (bằng chứng giao hàng)',
};

/** Upload a field photo, let vision read it, then attach it to a container.
 *
 * This used to live inside `ZaloIngestCard`, which meant it was only reachable
 * from `/setup` — a page shown by `system_config`/`manual_ingest` permissions.
 * The upload itself is governed by `field_image.create` (Ops + Driver), and
 * those two sets only overlapped on Ops, so Driver — the role the feature
 * exists for — had no way in. Keeping it standalone lets one permission decide
 * both "can you see it" and "can you use it".
 */
export function FieldImageCard({ onUploaded }: { onUploaded?: () => void }) {
  // Stable per-instance id so the <label> binds to this card's own input even
  // if the component is ever rendered twice on one page.
  const inputId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<FieldImagePreview | null>(null);
  const [containerNo, setContainerNo] = useState('');
  const [sealNo, setSealNo] = useState('');
  const [busy, setBusy] = useState<'upload' | 'confirm' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FieldImageConfirmResult | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  // The attachment endpoint needs a bearer token, which `<img src>` cannot send.
  const previewSrc = useAuthedFile(preview?.file_url);

  // OCR status is operational information, not a secret config value — anyone
  // who can upload needs to know. A failure here must not block uploading, so
  // it is swallowed and simply treated as "unknown" (no banner).
  const [ocrStatus, setOcrStatus] = useState<ExtractionCapabilityStatus | null>(null);
  useEffect(() => {
    api.getExtractionStatus().then(setOcrStatus).catch(() => setOcrStatus(null));
  }, []);

  function reset() {
    setPreview(null);
    setContainerNo('');
    setSealNo('');
    setError(null);
    setResult(null);
    setFileName(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Clear straight away so picking the SAME file again still fires `change`
    // — otherwise a retry after a failed upload silently does nothing.
    e.target.value = '';
    if (!file) return;
    setFileName(file.name);
    setBusy('upload'); setError(null); setResult(null);
    try {
      const p = await api.previewFieldImage(file);
      setPreview(p);
      setContainerNo(p.matched_container ?? (p.container_no_valid ? (p.container_no ?? '') : ''));
      setSealNo(p.seal_no ?? '');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không đọc được ảnh');
    } finally { setBusy(null); }
  }

  async function handleConfirm() {
    if (!preview || !containerNo.trim()) return;
    setBusy('confirm'); setError(null);
    try {
      const confirmed = await api.confirmFieldImage({
        image_id: preview.image_id,
        container_no: containerNo.trim(),
        seal_no: sealNo.trim() || undefined,
      });
      setResult(confirmed);
      setPreview(null);
      setFileName(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onUploaded?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không gắn được ảnh vào container');
    } finally { setBusy(null); }
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <h3 style={{ fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Camera size={16} /> Ảnh hiện trường (container/seal/EIR/POD)
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}>
          Chụp hoặc chọn ảnh từ máy. Agentify đọc thử số container/seal — ảnh vẫn
          được lưu ngay cả khi đọc không ra, và bạn luôn nhập tay được.
        </p>
      </div>

      {/* When OCR is off the upload still works but every field comes back
          empty — indistinguishable from "the AI could not read it". Say so
          outright so nobody retries the same photo over and over. */}
      {ocrStatus && !ocrStatus.image_ocr.ready && (
        <div className="banner banner-warning" style={{ alignItems: 'flex-start' }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ lineHeight: 1.6 }}>
            <strong>Đọc ảnh tự động đang TẮT</strong> — ảnh vẫn được lưu, nhưng
            bạn phải nhập số container/seal bằng tay.
            {ocrStatus.image_ocr.reason && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                Lý do: {ocrStatus.image_ocr.reason}
              </div>
            )}
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              Báo Admin để bật giúp.
            </div>
          </div>
        </div>
      )}

      {/* A <label> opens the picker natively — no JS `.click()`, which WebKit
          refuses to honour on a `display: none` input, and which needs a user
          gesture the browser may not always credit. The input is only visually
          hidden (not removed from layout) for the same WebKit reason.
          No `capture` attribute either: it asks the browser to jump straight to
          a camera device, gaining nothing on desktop while making the dialog
          unreliable. `accept="image/*"` alone already makes mobile offer
          "Take Photo" next to the library. */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <label
          htmlFor={inputId}
          className="btn btn-secondary"
          style={{ cursor: busy !== null ? 'not-allowed' : 'pointer', opacity: busy !== null ? 0.6 : 1 }}
        >
          <Camera size={14} /> Chọn ảnh
        </label>
        <input
          id={inputId}
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleSelected}
          disabled={busy !== null}
          style={VISUALLY_HIDDEN}
        />
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          {fileName ?? 'Chưa chọn ảnh nào'}
        </span>
      </div>

      {error && <div className="banner banner-danger"><AlertTriangle size={15} /> {error}</div>}

      {busy === 'upload' && (
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Đang tải ảnh và đọc số container…</p>
      )}

      {preview && (
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {previewSrc && (
            <img
              src={previewSrc}
              alt={preview.filename}
              style={{ width: 120, height: 120, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border-subtle)' }}
            />
          )}
          <div style={{ flex: 1, minWidth: 220, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {preview.extraction_status === 'skipped' && (
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Chưa cấu hình model đọc ảnh — đã lưu ảnh, nhập số container tay bên dưới.
              </p>
            )}
            {/* The backend already phrases this as a full, actionable sentence
                (see `image_extract.humanize_vision_error`), so wrapping it in
                another "đã lưu ảnh, nhập tay" clause just said it twice. */}
            {preview.extraction_status === 'failed' && (
              <p style={{ fontSize: 12, color: 'var(--warning)' }}>
                {preview.extraction_error ?? 'Không đọc được ảnh tự động. Ảnh đã được lưu — nhập số container tay.'}
              </p>
            )}
            {preview.extraction_status === 'ok' && !preview.container_no_valid && preview.container_no && (
              <p style={{ fontSize: 12, color: 'var(--warning)' }}>
                Đọc được "{preview.container_no}" nhưng số này không hợp lệ (sai checksum) — kiểm tra lại ảnh mờ hay gõ đúng số bên dưới.
              </p>
            )}
            {preview.doc_kind && (
              <span className="badge badge-info" style={{ alignSelf: 'flex-start' }}>
                {DOC_KIND_LABELS[preview.doc_kind] ?? preview.doc_kind}
              </span>
            )}
            <div className="form-group">
              <label className="form-label">Số container</label>
              <input
                className="form-input mono"
                value={containerNo}
                onChange={e => setContainerNo(e.target.value)}
                placeholder="VD MSKU1234567"
                disabled={busy !== null}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Số seal (tuỳ chọn)</label>
              <input
                className="form-input mono"
                value={sealNo}
                onChange={e => setSealNo(e.target.value)}
                disabled={busy !== null}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleConfirm}
                disabled={busy !== null || !containerNo.trim()}
              >
                <Send size={13} /> {busy === 'confirm' ? 'Đang gắn…' : 'Gắn vào container'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={reset} disabled={busy !== null}>
                Huỷ
              </button>
            </div>
          </div>
        </div>
      )}

      {result && (
        <div className="banner banner-info">
          <CheckCircle size={15} style={{ flexShrink: 0 }} />
          Đã gắn {result.fact_count} dữ liệu vào{' '}
          <Link to={`/containers/${result.container_no}`} className="mono" style={{ color: 'var(--accent)' }}>
            {result.container_no}
          </Link>.
        </div>
      )}
    </div>
  );
}
