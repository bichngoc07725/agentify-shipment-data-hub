import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search, Package, AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';
import type { ContainerListItem } from '../types/api';
import { fmtDate, fmtRelative } from '../lib/format';
import { STAGE_LABELS, STAGE_ORDER } from '../lib/shipmentStage';

function ProgressBadge({ shipment }: { shipment: ContainerListItem['shipment'] }) {
  if (!shipment) {
    return <span className="badge badge-neutral">Chưa có job</span>;
  }
  const index = STAGE_ORDER.indexOf(shipment.stage);
  return (
    <span className={`badge ${shipment.sla_breached ? 'badge-danger' : 'badge-info'}`}>
      {index + 1}/{STAGE_ORDER.length} · {STAGE_LABELS[shipment.stage]}
    </span>
  );
}

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'has_data', label: 'Complete enough' },
  { id: 'missing', label: 'Missing data' },
];

export function ContainersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<ContainerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [q, setQ] = useState(searchParams.get('q') ?? '');
  const [inputQ, setInputQ] = useState(searchParams.get('q') ?? '');
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async (query: string) => {
    setLoading(true); setError(null);
    try {
      const r = await api.listContainers({ q: query || undefined, page_size: 50 });
      setItems(r.items); setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải dữ liệu');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(q); }, [q, load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQ(inputQ.trim());
    setSearchParams(inputQ.trim() ? { q: inputQ.trim() } : {});
  }

  const displayed = filter === 'missing'
    ? items.filter(c => !c.booking_no || !c.bl_no || !c.eta)
    : filter === 'has_data'
    ? items.filter(c => c.booking_no && c.bl_no)
    : items;

  const selectedItem = items.find(c => c.container_no === selected);

  return (
    <div className="split-view" style={{ height: '100%' }}>
      {/* List pane */}
      <div className="split-list">
        <div className="split-list-header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 style={{ fontSize: 16, fontWeight: 600 }}>Containers</h1>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{total} tổng</span>
          </div>
          <form onSubmit={handleSearch}>
            <div className="toolbar-search" style={{ maxWidth: '100%', height: 34 }}>
              <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <input
                id="container-search"
                value={inputQ}
                onChange={e => setInputQ(e.target.value)}
                placeholder="Tìm container, booking, B/L…"
                aria-label="Tìm container"
              />
            </div>
          </form>
          <div className="filter-chips">
            {FILTERS.map(f => (
              <button
                key={f.id}
                className={`chip${filter === f.id ? ' active' : ''}`}
                onClick={() => setFilter(f.id)}
              >{f.label}</button>
            ))}
          </div>
        </div>

        <div className="split-list-scroll">
          {loading && [...Array(8)].map((_, i) => (
            <div key={i} style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
              <div className="skeleton" style={{ height: 14, width: '60%', marginBottom: 6 }} />
              <div className="skeleton" style={{ height: 11, width: '80%' }} />
            </div>
          ))}

          {!loading && error && (
            <div className="banner banner-danger" style={{ margin: 12 }}>
              <AlertTriangle size={15} /> {error}
            </div>
          )}

          {!loading && !error && displayed.length === 0 && (
            <div className="empty-state">
              <Package size={32} className="empty-state-icon" />
              <h3>No containers found</h3>
              <p>Container xuất hiện khi email hoặc PDF có container_no được trích xuất.</p>
              <Link to="/setup" className="btn btn-primary btn-sm" style={{ marginTop: 12 }}>Go to data source</Link>
            </div>
          )}

          {!loading && displayed.map(c => {
            const missing = !c.booking_no || !c.bl_no || !c.eta;
            return (
              <div
                key={c.container_no}
                className={`list-row${selected === c.container_no ? ' selected' : ''}`}
                onClick={() => setSelected(c.container_no)}
                role="button"
                tabIndex={0}
                aria-selected={selected === c.container_no}
                onKeyDown={e => e.key === 'Enter' && setSelected(c.container_no)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <span className="container-row-no">{c.container_no}</span>
                  <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                    {missing && <span className="badge badge-warning">Missing data</span>}
                  </div>
                </div>
                <div className="container-row-meta">
                  {c.booking_no ? <span>BK: {c.booking_no}</span> : <span style={{ color: 'var(--text-muted)' }}>No booking</span>}
                  {c.bl_no && <span>B/L: {c.bl_no}</span>}
                  {c.pod && <span>→ {c.pod}</span>}
                </div>
                <div className="container-row-meta" style={{ marginTop: 4 }}>
                  <ProgressBadge shipment={c.shipment} />
                </div>
                <div className="container-row-meta" style={{ marginTop: 4 }}>
                  {c.status_text && <span style={{ color: 'var(--text-primary)' }}>{c.status_text}</span>}
                  <span style={{ marginLeft: 'auto' }}>{fmtRelative(c.updated_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Detail pane */}
      <div className="split-detail">
        {selectedItem
          ? <ContainerDetailInline container={selectedItem} />
          : (
            <div className="empty-state" style={{ height: '100%' }}>
              <Package size={36} className="empty-state-icon" />
              <h3>Chọn một container</h3>
              <p>Chọn container từ danh sách bên trái để xem chi tiết.</p>
            </div>
          )
        }
      </div>
    </div>
  );
}

function ContainerDetailInline({ container: c }: { container: ContainerListItem }) {
  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Container</div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>{c.container_no}</div>
            {c.status_text && <div style={{ marginTop: 6, fontSize: 14, color: 'var(--text-secondary)' }}>{c.status_text}</div>}
          </div>
          <Link
            to={`/containers/${c.container_no}`}
            className="btn btn-secondary btn-sm"
          >
            Mở trang đầy đủ
          </Link>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
          <span>{c.source_count} nguồn</span>
          <span>{c.attachment_count} file</span>
          <span>Cập nhật {fmtRelative(c.updated_at)}</span>
        </div>
      </div>

      <div className="fact-grid">
        {[
          { label: 'Booking', value: c.booking_no },
          { label: 'B/L', value: c.bl_no },
          { label: 'PO', value: c.po_no },
          { label: 'POL', value: c.pol },
          { label: 'POD', value: c.pod },
          { label: 'Vessel', value: c.vessel },
          { label: 'Voyage', value: c.voyage },
          { label: 'ETD', value: fmtDate(c.etd) === '—' ? null : fmtDate(c.etd) },
          { label: 'ETA', value: fmtDate(c.eta) === '—' ? null : fmtDate(c.eta) },
        ].map(({ label, value }) => (
          <div key={label} className="fact-cell">
            <span className="fact-label">{label}</span>
            {value
              ? <span className="fact-value mono" style={{ fontFamily: ['Booking','B/L','PO'].includes(label) ? 'var(--font-mono)' : 'var(--font-ui)' }}>{value}</span>
              : <span className="fact-missing">Chưa tìm thấy trong dữ liệu Agentify</span>
            }
          </div>
        ))}
      </div>
    </div>
  );
}
