import { useState } from 'react';
import { Copy, Check, ExternalLink, X, Info } from 'lucide-react';
import type { ComposedMail } from '../types/api';

/** Khung xem thư đã soạn sẵn.
 *
 *  Agentify KHÔNG gửi thư: quyền Gmail hiện là chỉ-đọc, và gửi thư dưới danh
 *  nghĩa nhân viên là quyết định sản phẩm chưa chốt. Khung này chỉ đưa sẵn nội
 *  dung để người dùng chép hoặc mở thẳng trong Gmail rồi tự bấm gửi — bỏ được
 *  việc gõ tay mà không phải xin thêm quyền nào.
 */
export function MailComposerCard({
  title,
  hint,
  mail,
  onClose,
}: {
  title: string;
  hint: string;
  mail: ComposedMail;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function copyAll() {
    const text = `${mail.subject}\n\n${mail.body}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  // URL soạn thư của Gmail. Dùng nó thay `mailto:` để người dùng không phụ
  // thuộc vào ứng dụng thư mặc định của máy — phần lớn đội đang làm việc
  // thẳng trên Gmail web.
  const gmailUrl =
    'https://mail.google.com/mail/?view=cm&fs=1' +
    `&su=${encodeURIComponent(mail.subject)}` +
    `&body=${encodeURIComponent(mail.body)}`;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <strong style={{ fontSize: 14 }}>{title}</strong>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Đóng">
          <X size={14} />
        </button>
      </div>

      <div className="banner banner-info">
        <Info size={14} />
        <span>{hint}</span>
      </div>

      <div className="form-group">
        <label className="form-label">Tiêu đề</label>
        <input className="form-input" value={mail.subject} readOnly />
      </div>

      <div className="form-group">
        <label className="form-label">Nội dung</label>
        <textarea
          className="form-input"
          value={mail.body}
          readOnly
          rows={16}
          style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.55 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn btn-primary btn-sm" onClick={copyAll}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? 'Đã chép' : 'Chép tiêu đề + nội dung'}
        </button>
        <a
          className="btn btn-secondary btn-sm"
          href={gmailUrl}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink size={14} /> Mở trong Gmail
        </a>
      </div>
    </div>
  );
}
