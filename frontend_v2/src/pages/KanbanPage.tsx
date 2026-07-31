import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Package, Plus } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { canAdvanceShipment, canCreateShipment, ROLE_LABELS } from '../lib/permissions';
import { STAGE_LABELS } from '../lib/shipmentStage';
import type { Shipment, ShipmentBoardColumn } from '../types/api';
import { fmtDate } from '../lib/format';

function ShipmentCard({ shipment, onAdvance, advancing, onDragStart, onDragEnd, dragging }: {
  shipment: Shipment;
  onAdvance: (s: Shipment) => void;
  advancing: boolean;
  onDragStart: (s: Shipment) => void;
  onDragEnd: () => void;
  dragging: boolean;
}) {
  const { user } = useAuth();
  // The same permission decides the button and the drag: a card you may not
  // move should not even pick up, rather than pick up and be refused on drop.
  const canMove = canAdvanceShipment(user?.role, shipment.owner_role);
  const canAdvance = shipment.stage !== 'closed' && canMove;

  return (
    <div
      className="card"
      draggable={canMove}
      onDragStart={e => {
        e.dataTransfer.effectAllowed = 'move';
        // Some browsers refuse to start a drag without payload on the event.
        e.dataTransfer.setData('text/plain', shipment.id);
        onDragStart(shipment);
      }}
      onDragEnd={onDragEnd}
      style={{
        padding: 12, display: 'flex', flexDirection: 'column', gap: 8,
        cursor: canMove ? 'grab' : 'default',
        opacity: dragging ? 0.4 : 1,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{shipment.shipment_no}</span>
        {shipment.sla_breached && (
          <span className="badge badge-danger" title="Quá hạn SLA của bước hiện tại">
            <AlertTriangle size={11} style={{ marginRight: 4 }} />Quá SLA
          </span>
        )}
      </div>
      {shipment.customer_name && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{shipment.customer_name}</div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
        <Package size={12} /> {shipment.container_count} container
      </div>
      {shipment.quote_no && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Báo giá: <span className="mono">{shipment.quote_no}</span></div>
      )}
      {shipment.owner_role && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Phụ trách: {ROLE_LABELS[shipment.owner_role as keyof typeof ROLE_LABELS] ?? shipment.owner_role}
        </div>
      )}
      {shipment.sla_due_at && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Hạn: {fmtDate(shipment.sla_due_at)}</div>
      )}
      {shipment.container_nos[0] && (
        <Link to={`/containers/${shipment.container_nos[0]}`} style={{ fontSize: 12 }}>
          Xem container →
        </Link>
      )}
      {canAdvance && (
        <button
          className="btn btn-secondary btn-sm"
          disabled={advancing}
          onClick={() => onAdvance(shipment)}
          style={{ marginTop: 4 }}
        >
          Chuyển bước <ArrowRight size={13} />
        </button>
      )}
    </div>
  );
}

export function KanbanPage() {
  const { user } = useAuth();
  const [columns, setColumns] = useState<ShipmentBoardColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [advancingId, setAdvancingId] = useState<string | null>(null);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [customerName, setCustomerName] = useState('');
  const [containerNos, setContainerNos] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [draggingJob, setDraggingJob] = useState<Shipment | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const board = await api.getShipmentBoard();
      setColumns(board.columns);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải bảng Kanban');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAdvance(shipment: Shipment) {
    setAdvancingId(shipment.id);
    try {
      await api.advanceShipment(shipment.id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không chuyển được bước — kiểm tra quyền của vai trò này');
    } finally {
      setAdvancingId(null);
    }
  }

  async function handleDropOn(stage: ShipmentBoardColumn['stage'], droppedId?: string) {
    // Prefer the id carried on the drag itself; `draggingJob` is React state
    // set during `dragstart`, so relying on it alone makes the drop depend on
    // a render having committed in between.
    const id = droppedId || draggingJob?.id;
    const job = columns.flatMap(c => c.jobs).find(j => j.id === id);
    setDraggingJob(null);
    setDropTarget(null);
    if (!job || job.stage === stage) return;

    setAdvancingId(job.id);
    setError(null);
    try {
      await api.moveShipmentStage(job.id, stage);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không chuyển được bước — kiểm tra quyền của vai trò này');
    } finally {
      setAdvancingId(null);
    }
  }

  async function handleCreate() {
    setCreateBusy(true); setCreateError(null);
    try {
      await api.createShipment({
        customer_name: customerName || undefined,
        container_nos: containerNos
          .split(',')
          .map(s => s.trim())
          .filter(Boolean),
      });
      setFormOpen(false);
      setCustomerName(''); setContainerNos('');
      await load();
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Không tạo được job');
    } finally {
      setCreateBusy(false);
    }
  }

  return (
    <div style={{ padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>Kanban lô hàng</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Theo dõi mỗi job đi qua 6 bước, từ báo giá tới đối soát.
          </p>
        </div>
        {canCreateShipment(user?.role) && (
          <button className="btn btn-primary btn-sm" onClick={() => setFormOpen(v => !v)}>
            <Plus size={14} /> Tạo job
          </button>
        )}
      </div>

      {formOpen && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 420 }}>
          <input
            className="form-input"
            placeholder="Tên khách hàng"
            value={customerName}
            onChange={e => setCustomerName(e.target.value)}
            disabled={createBusy}
          />
          <input
            className="form-input"
            placeholder="Số container, phân cách bởi dấu phẩy"
            value={containerNos}
            onChange={e => setContainerNos(e.target.value)}
            disabled={createBusy}
          />
          {createError && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{createError}</div>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={createBusy}>Lưu</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setFormOpen(false)} disabled={createBusy}>Huỷ</button>
          </div>
        </div>
      )}

      {error && (
        <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>
      )}

      {loading ? (
        <div style={{ display: 'flex', gap: 12 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 200, width: 220, borderRadius: 10 }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 12 }}>
          {columns.map(col => (
            <div
              key={col.stage}
              onDragOver={e => {
                if (!draggingJob) return;
                // Without preventDefault the browser treats this as "not a drop
                // target" and never fires onDrop.
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                setDropTarget(col.stage);
              }}
              onDragLeave={() => setDropTarget(t => (t === col.stage ? null : t))}
              onDrop={e => {
                e.preventDefault();
                handleDropOn(col.stage, e.dataTransfer.getData('text/plain'));
              }}
              style={{
                minWidth: 240, flex: '0 0 240px', display: 'flex', flexDirection: 'column', gap: 10,
                borderRadius: 10, padding: 6,
                outline: dropTarget === col.stage ? '2px dashed var(--accent)' : '2px dashed transparent',
                background: dropTarget === col.stage ? 'var(--accent-soft)' : 'transparent',
                transition: 'background 120ms',
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {STAGE_LABELS[col.stage]} ({col.jobs.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {col.jobs.map(job => (
                  <ShipmentCard
                    key={job.id}
                    shipment={job}
                    onAdvance={handleAdvance}
                    advancing={advancingId === job.id}
                    onDragStart={setDraggingJob}
                    onDragEnd={() => { setDraggingJob(null); setDropTarget(null); }}
                    dragging={draggingJob?.id === job.id}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
