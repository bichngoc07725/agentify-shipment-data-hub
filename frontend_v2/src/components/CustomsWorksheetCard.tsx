import { useCallback, useEffect, useState } from 'react';
import { FileDown, ClipboardList, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '../lib/api';
import { getToken } from '../lib/authStorage';
import type { CustomsWorksheet } from '../types/api';

const SECTION_HEADING: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 10,
};

/** Phiếu nhập liệu tờ khai hải quan, hiển thị ngay trên web.
 *
 *  Cùng nguồn dữ liệu với file .docx tải về — xem trên màn hình rồi tải file
 *  mà thấy khác nhau là kiểu lỗi phá hết lòng tin vào cả hai.
 */
export function CustomsWorksheetCard({ containerNo }: { containerNo: string }) {
  const [worksheet, setWorksheet] = useState<CustomsWorksheet | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(() => {
    api.getCustomsWorksheet(containerNo)
      .then(setWorksheet)
      .catch(() => setWorksheet(null));
  }, [containerNo]);

  useEffect(load, [load]);

  async function downloadDocx() {
    setDownloading(true); setError(null);
    try {
      // Tải bằng fetch chứ không phải thẻ <a href>: endpoint đòi Bearer token,
      // mà thẻ <a> không gắn header được — bấm thẳng sẽ nhận 401.
      const res = await fetch(api.customsWorksheetDocxUrl(containerNo), {
        headers: { Authorization: `Bearer ${getToken() ?? ''}` },
      });
      if (!res.ok) throw new Error(`Tải không được (HTTP ${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `to-khai-${containerNo}.docx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Tải file không được');
    } finally {
      setDownloading(false);
    }
  }

  if (!worksheet) return null;

  const filled = worksheet.field_count - worksheet.missing_count;

  return (
    <section>
      <h2 style={SECTION_HEADING}>Phiếu nhập liệu tờ khai (ECUS/VNACCS)</h2>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <ClipboardList size={16} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: 14 }}>
            <strong>{filled}</strong>/{worksheet.field_count} ô đã có dữ liệu
          </span>
          {worksheet.missing_count > 0 && (
            <span className="badge badge-warning">
              {worksheet.missing_count} ô phải tự bổ sung
            </span>
          )}
          <div style={{ flex: 1 }} />
          <button className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)}>
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {open ? 'Thu gọn' : 'Xem chi tiết'}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={downloadDocx} disabled={downloading}>
            <FileDown size={14} /> {downloading ? 'Đang tải…' : 'Tải file .docx'}
          </button>
        </div>

        {worksheet.missing_count > 0 && (
          <div className="banner banner-warning">
            <AlertTriangle size={14} />
            <span>
              Ô đỏ là ô Agentify chưa có dữ liệu — phải tự tra theo nguồn ghi kèm.
              Bỏ trống trên tờ khai là khai thiếu.
            </span>
          </div>
        )}

        {error && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</div>}

        {open && worksheet.sections.map(section => (
          <div key={section.title}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>{section.title}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {section.fields.map(field => (
                <div
                  key={field.label}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(160px, 260px) 1fr',
                    gap: 10,
                    padding: '5px 8px',
                    fontSize: 13,
                    background: field.is_missing ? 'var(--danger-soft, rgba(192,48,48,0.06))' : 'transparent',
                    borderRadius: 4,
                  }}
                >
                  <span style={{ color: 'var(--text-muted)' }}>{field.label}</span>
                  <span
                    style={{
                      color: field.is_missing ? 'var(--danger)' : 'inherit',
                      fontStyle: field.is_missing ? 'italic' : 'normal',
                    }}
                  >
                    {field.display}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
