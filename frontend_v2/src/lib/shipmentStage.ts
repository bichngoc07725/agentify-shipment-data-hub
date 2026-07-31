import type { ShipmentStage } from '../types/api';

export const STAGE_LABELS: Record<ShipmentStage, string> = {
  rfq: 'RFQ / Báo giá',
  booking: 'Đặt chỗ',
  documents: 'Chứng từ',
  customs: 'Hải quan',
  delivery: 'Giao nhận',
  reconciliation: 'Đối soát',
  closed: 'Hoàn tất',
};

// Mirrors `backend/services/shipment_service.py::STAGE_ORDER`.
export const STAGE_ORDER: ShipmentStage[] = [
  'rfq', 'booking', 'documents', 'customs', 'delivery', 'reconciliation', 'closed',
];
