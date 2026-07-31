import { FieldImageCard } from '../components/sources/FieldImageCard';

/** Standalone home for field-photo upload (GĐ5).
 *
 * Its own route rather than a section of `/setup`: the upload is gated by
 * `field_image.create` (Ops + Driver), while `/setup` is shown for
 * `system_config`/`manual_ingest` (Admin, Manager, Ops, Docs). Nesting it
 * there meant Driver could never reach the one feature built for them.
 */
export function FieldImagesPage() {
  return (
    <div className="page-container page-narrow">
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>Ảnh hiện trường</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.6 }}>
          Gửi ảnh container, seal, EIR hoặc POD chụp tại bãi/kho. Agentify đọc số
          container rồi gắn ảnh vào đúng hồ sơ lô hàng.
        </p>
      </div>

      <FieldImageCard />
    </div>
  );
}
