import type { MessageChannel } from '../types/api';

export const CHANNEL_LABELS: Record<MessageChannel, string> = {
  email: 'Email',
  zalo: 'Zalo',
  note: 'Ghi chú',
  other: 'Khác',
};

export const CHANNEL_BADGE: Record<MessageChannel, string> = {
  email: 'badge-neutral',
  zalo: 'badge-info',
  note: 'badge-neutral',
  other: 'badge-neutral',
};

/**
 * How each source stands today. Kept honest on purpose: the product must not
 * imply it reads Zalo automatically, because it does not and should not.
 */
export type SourceState = 'live' | 'manual' | 'roadmap' | 'out_of_scope';

export const SOURCE_STATE_LABELS: Record<SourceState, string> = {
  live: 'Đang chạy',
  manual: 'Thủ công, có kiểm duyệt',
  roadmap: 'Trong roadmap',
  out_of_scope: 'Ngoài phạm vi',
};

export const SOURCE_STATE_BADGE: Record<SourceState, string> = {
  live: 'badge-success',
  manual: 'badge-info',
  roadmap: 'badge-warning',
  out_of_scope: 'badge-neutral',
};

/**
 * Where a single extracted fact came from, for the provenance line under a value.
 * `source_type` is what the ingestion pipeline recorded: `pdf_text`,
 * `image_vision`, `email_body`, `zalo_message`, `note_message`.
 */
const ATTACHMENT_SOURCE_LABELS: Record<string, string> = {
  pdf_text: 'PDF',
  // `image_vision` đến từ OCR ảnh đính kèm Gmail, `image` từ ảnh hiện trường
  // người dùng tự upload — hai luồng khác nhau nhưng hiển thị như nhau.
  image_vision: 'Ảnh',
  image: 'Ảnh',
};

export function factSourceLabel(fact: {
  source_type: string;
  source_label: string | null;
  attachment_id: string | null;
}): string {
  if (fact.attachment_id) {
    const kind = ATTACHMENT_SOURCE_LABELS[fact.source_type] ?? 'File';
    return `${kind} · ${fact.source_label ?? 'file'}`;
  }

  const channel = fact.source_type.replace(/_message$/, '');
  if (channel !== fact.source_type) {
    const label = CHANNEL_LABELS[channel as MessageChannel] ?? channel;
    return fact.source_label ? `${label} · ${fact.source_label}` : label;
  }

  return fact.source_label ? `Email · ${fact.source_label}` : 'Email';
}

export interface SourceDefinition {
  id: string;
  name: string;
  icon: string;
  state: SourceState;
  summary: string;
  detail: string;
}

export const SOURCES: SourceDefinition[] = [
  {
    id: 'gmail',
    name: 'Gmail',
    icon: '📧',
    state: 'live',
    summary: 'Email và file PDF đính kèm của hộp thư dùng chung',
    detail:
      'Kết nối OAuth chỉ đọc. Agentify không gửi, sửa hoặc xóa email. Đây là nguồn chính: arrival notice, booking confirmation, B/L, D/O, debit note đều đi qua đây.',
  },
  {
    id: 'zalo',
    name: 'Zalo',
    icon: '💬',
    state: 'manual',
    summary: 'Dán hoặc forward tin nhắn quan trọng vào Agentify',
    detail:
      'Agentify cố tình KHÔNG đọc Zalo tự động — việc đó cần quyền truy cập toàn bộ hội thoại cá nhân mà sản phẩm không nên xin. Bạn dán tin cần lưu, xem Agentify đọc ra gì, rồi mới xác nhận. Tích hợp Zalo OA sẽ làm khi doanh nghiệp có kênh chính thức.',
  },
  {
    id: 'upload',
    name: 'Upload chứng từ',
    icon: '📎',
    state: 'roadmap',
    summary: 'Tải lên PDF, ảnh POD/EIR, ảnh container',
    detail:
      'Cần OCR/vision cho ảnh chụp và PDF scan. Đây là mắt xích còn thiếu để đóng vòng free time: bằng chứng trả rỗng hiện nằm trong ảnh EIR gửi qua Zalo.',
  },
  {
    id: 'excel',
    name: 'Excel / Google Sheet',
    icon: '📊',
    state: 'roadmap',
    summary: 'Import file tracking đang dùng để seed dữ liệu ngày đầu',
    detail:
      '97,8% doanh nghiệp logistics vẫn dùng Excel song song. Import file tracking cho phép Agentify có dữ liệu ngay từ ngày đầu thay vì chờ sync đủ email.',
  },
  {
    id: 'ecus',
    name: 'ECUS / VNACCS, ePort, TMS',
    icon: '🖥️',
    state: 'out_of_scope',
    summary: 'Hệ thống lõi — Agentify nằm cạnh, không thay thế',
    detail:
      'Agentify không khai hải quan và không thay TMS/WMS/ERP. Tích hợp sâu chỉ cân nhắc sau khi lớp dữ liệu email/file đã chứng minh giá trị.',
  },
];
