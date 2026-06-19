export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return iso; }
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Vừa xong';
    if (mins < 60) return `${mins} phút trước`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} giờ trước`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days} ngày trước`;
    return fmtDate(iso);
  } catch { return iso; }
}

export function fmtBytes(bytes: number | null | undefined): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function syncStatusLabel(status: string): { label: string; cls: string } {
  switch (status) {
    case 'pending': return { label: 'Đang chờ', cls: 'badge-neutral' };
    case 'running': return { label: 'Đang chạy', cls: 'badge-info' };
    case 'completed': return { label: 'Hoàn thành', cls: 'badge-success' };
    case 'failed': return { label: 'Thất bại', cls: 'badge-danger' };
    default: return { label: status, cls: 'badge-neutral' };
  }
}

export function emailStatusLabel(status: string): { label: string; cls: string } {
  switch (status) {
    case 'synced': return { label: 'Synced', cls: 'badge-neutral' };
    case 'parsed': return { label: 'Parsed', cls: 'badge-info' };
    case 'extracted': return { label: 'Extracted', cls: 'badge-success' };
    case 'no_container_found': return { label: 'No container', cls: 'badge-warning' };
    case 'unsupported_pdf': return { label: 'Unsupported PDF', cls: 'badge-warning' };
    case 'failed': return { label: 'Failed', cls: 'badge-danger' };
    default: return { label: status, cls: 'badge-neutral' };
  }
}
