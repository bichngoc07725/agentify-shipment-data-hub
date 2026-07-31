import type { ExceptionSeverity } from '../types/api';

export const SEVERITY_LABELS: Record<ExceptionSeverity, string> = {
  critical: 'Nguy cấp',
  warning: 'Cảnh báo',
  info: 'Thông tin',
};

export const SEVERITY_BADGE: Record<ExceptionSeverity, string> = {
  critical: 'badge-danger',
  warning: 'badge-warning',
  info: 'badge-neutral',
};

export const DOCUMENT_LABELS: Record<string, string> = {
  arrival_notice: 'Arrival Notice',
  booking_confirmation: 'Booking Confirmation',
  bill_of_lading: 'Bill of Lading',
  delivery_order: 'Delivery Order (D/O)',
  invoice: 'Invoice',
  packing_list: 'Packing List',
  debit_note: 'Debit Note',
  certificate_of_origin: 'Certificate of Origin',
  customs_declaration: 'Tờ khai Hải quan',
};

export function documentLabel(code: string): string {
  return DOCUMENT_LABELS[code] ?? code;
}

/** Human-readable countdown for a free-time or arrival deadline. */
export function formatDaysRemaining(days: number | null): string | null {
  if (days === null || days === undefined) return null;
  if (days < 0) return `Quá hạn ${Math.abs(days)} ngày`;
  if (days === 0) return 'Hết hạn hôm nay';
  return `Còn ${days} ngày`;
}
