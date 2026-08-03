import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AlertTriangle, ChevronLeft, Plus, Trash2, Pencil, Save, X } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { canManageQuote } from '../lib/permissions';
import type { ChargeGroup, Quote, QuoteChargeInput, QuoteInput, QuoteStatus } from '../types/api';
import { fmtDate } from '../lib/format';

const CHARGE_GROUPS: { id: ChargeGroup; label: string; hint: string }[] = [
  { id: 'ocean_freight', label: 'Cước biển chính (Ocean Freight)', hint: 'Đơn giá theo loại container, loại giá contract/spot' },
  { id: 'surcharge', label: 'Phụ phí đi kèm cước biển', hint: 'FSC, THC, CIC, phí vệ sinh container, D/O fee, Doc fee...' },
  { id: 'local', label: 'Phí local tại VN', hint: 'Các khoản thu tại đầu VN — khác với cước biển' },
];

const STATUS_OPTIONS: { id: QuoteStatus; label: string }[] = [
  { id: 'draft', label: 'Nháp' },
  { id: 'sent', label: 'Đã gửi' },
  { id: 'accepted', label: 'Khách chấp nhận' },
  { id: 'rejected', label: 'Khách từ chối' },
  { id: 'expired', label: 'Hết hạn' },
];

function emptyCharge(group: ChargeGroup): QuoteChargeInput {
  return { charge_group: group, charge_code: '', description: '', unit_price: '0', currency: 'USD', quantity: '1' };
}

function toInput(quote: Quote): QuoteInput {
  return {
    customer_name: quote.customer_name,
    status: quote.status,
    pol: quote.pol,
    pod: quote.pod,
    commodity: quote.commodity,
    is_dangerous: quote.is_dangerous,
    is_reefer: quote.is_reefer,
    container_type: quote.container_type,
    container_qty: quote.container_qty,
    gross_weight_kg: quote.gross_weight_kg,
    cargo_ready_date: quote.cargo_ready_date,
    incoterm: quote.incoterm,
    payment_term: quote.payment_term,
    transit_time: quote.transit_time,
    valid_until: quote.valid_until,
    note: quote.note,
    currency: quote.currency,
    container_no: quote.container_no,
    charges: quote.charges.map(c => ({
      charge_group: c.charge_group,
      charge_code: c.charge_code,
      description: c.description ?? '',
      unit_price: c.unit_price,
      currency: c.currency,
      quantity: c.quantity,
    })),
  };
}

const EMPTY_FORM: QuoteInput = {
  customer_name: '',
  status: 'draft',
  pol: '',
  pod: '',
  commodity: '',
  is_dangerous: false,
  is_reefer: false,
  container_type: '',
  container_qty: null,
  gross_weight_kg: '',
  cargo_ready_date: '',
  incoterm: '',
  payment_term: '',
  transit_time: '',
  valid_until: '',
  note: '',
  currency: 'USD',
  container_no: '',
  charges: [],
};

export function QuoteDetailPage() {
  const { quoteId } = useParams<{ quoteId: string }>();
  const isNew = quoteId === 'new';
  const navigate = useNavigate();
  const { user } = useAuth();
  const canManage = canManageQuote(user?.role);

  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(isNew);
  const [form, setForm] = useState<QuoteInput>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (isNew || !quoteId) return;
    setLoading(true); setError(null);
    try {
      const q = await api.getQuote(quoteId);
      setQuote(q);
      setForm(toInput(q));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không tải được báo giá');
    } finally { setLoading(false); }
  }, [quoteId, isNew]);

  useEffect(() => { load(); }, [load]);

  function updateField<K extends keyof QuoteInput>(key: K, value: QuoteInput[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function addCharge(group: ChargeGroup) {
    setForm(prev => ({ ...prev, charges: [...prev.charges, emptyCharge(group)] }));
  }

  function updateCharge(index: number, patch: Partial<QuoteChargeInput>) {
    setForm(prev => ({
      ...prev,
      charges: prev.charges.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    }));
  }

  function removeCharge(index: number) {
    setForm(prev => ({ ...prev, charges: prev.charges.filter((_, i) => i !== index) }));
  }

  const previewTotal = form.charges.reduce(
    (sum, c) => sum + Number(c.unit_price || 0) * Number(c.quantity || 1),
    0,
  );

  async function handleSave() {
    setSaving(true); setSaveError(null);
    try {
      const saved = isNew
        ? await api.createQuote(form)
        : await api.updateQuote(quoteId!, form);
      setQuote(saved);
      setForm(toInput(saved));
      setEditing(false);
      if (isNew) navigate(`/quotes/${saved.id}`, { replace: true });
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Không lưu được báo giá');
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!quote) return;
    if (!window.confirm(`Xoá báo giá ${quote.quote_no}?`)) return;
    try {
      await api.deleteQuote(quote.id);
      navigate('/quotes', { replace: true });
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Không xoá được báo giá');
    }
  }

  if (loading) return (
    <div className="detail-panel">
      <div className="skeleton" style={{ height: 100, borderRadius: 10 }} />
      <div className="skeleton" style={{ height: 200, borderRadius: 10 }} />
    </div>
  );

  if (error) return (
    <div className="detail-panel">
      <div className="banner banner-danger"><AlertTriangle size={16} /> {error}</div>
    </div>
  );

  const readOnly = !editing;

  return (
    <div className="detail-panel page-container page-narrow">
      <div>
        <Link to="/quotes" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none' }}>
          <ChevronLeft size={15} /> Báo giá
        </Link>
      </div>

      <div className="detail-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
              Báo giá
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 600 }}>{isNew ? 'Tạo báo giá mới' : quote?.quote_no}</h1>
          </div>
          {canManage && !isNew && !editing && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>
                <Pencil size={14} /> Sửa
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleDelete} style={{ color: 'var(--danger)' }}>
                <Trash2 size={14} /> Xoá
              </button>
            </div>
          )}
        </div>
      </div>

      {!canManage && (
        <div className="banner banner-info">
          Vai trò của bạn chỉ được xem báo giá. Sửa/tạo cần vai trò Sales/CS.
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Tên khách hàng</label>
        <input
          className="form-input"
          value={form.customer_name}
          onChange={e => updateField('customer_name', e.target.value)}
          disabled={readOnly}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label">Trạng thái</label>
          <select
            className="form-select"
            value={form.status}
            onChange={e => updateField('status', e.target.value as QuoteStatus)}
            disabled={readOnly}
          >
            {STATUS_OPTIONS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Container liên kết (tuỳ chọn)</label>
          <input
            className="form-input mono"
            value={form.container_no ?? ''}
            onChange={e => updateField('container_no', e.target.value)}
            placeholder="VD MSCU1234567"
            disabled={readOnly}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label">POL</label>
          <input className="form-input" value={form.pol ?? ''} onChange={e => updateField('pol', e.target.value)} disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">POD</label>
          <input className="form-input" value={form.pod ?? ''} onChange={e => updateField('pod', e.target.value)} disabled={readOnly} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label">Tên hàng</label>
          <input className="form-input" value={form.commodity ?? ''} onChange={e => updateField('commodity', e.target.value)} disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">Loại container</label>
          <input className="form-input" value={form.container_type ?? ''} onChange={e => updateField('container_type', e.target.value)} placeholder="40HC" disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">Số lượng cont</label>
          <input
            className="form-input"
            type="number"
            min={0}
            value={form.container_qty ?? ''}
            onChange={e => updateField('container_qty', e.target.value ? Number(e.target.value) : null)}
            disabled={readOnly}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 20 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={form.is_dangerous} onChange={e => updateField('is_dangerous', e.target.checked)} disabled={readOnly} />
          Hàng nguy hiểm
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={form.is_reefer} onChange={e => updateField('is_reefer', e.target.checked)} disabled={readOnly} />
          Hàng lạnh
        </label>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label">Cargo ready date</label>
          <input type="date" className="form-input" value={form.cargo_ready_date ?? ''} onChange={e => updateField('cargo_ready_date', e.target.value)} disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">Incoterm</label>
          <input className="form-input" value={form.incoterm ?? ''} onChange={e => updateField('incoterm', e.target.value)} placeholder="FOB/CIF/EXW" disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">Hiệu lực đến</label>
          <input type="date" className="form-input" value={form.valid_until ?? ''} onChange={e => updateField('valid_until', e.target.value)} disabled={readOnly} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-group">
          <label className="form-label">Điều khoản thanh toán</label>
          <input className="form-input" value={form.payment_term ?? ''} onChange={e => updateField('payment_term', e.target.value)} placeholder="Trả trước 30%" disabled={readOnly} />
        </div>
        <div className="form-group">
          <label className="form-label">Transit time</label>
          <input className="form-input" value={form.transit_time ?? ''} onChange={e => updateField('transit_time', e.target.value)} placeholder="25 ngày" disabled={readOnly} />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Ghi chú</label>
        <textarea className="form-textarea" value={form.note ?? ''} onChange={e => updateField('note', e.target.value)} disabled={readOnly} rows={2} />
      </div>

      {/* Charges — 3 blocks per BA Spec Bước 1 Luồng C */}
      <section>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
          Chi tiết phí
        </h2>
        {CHARGE_GROUPS.map(group => {
          const rows = form.charges
            .map((c, i) => ({ c, i }))
            .filter(({ c }) => c.charge_group === group.id);
          return (
            <div key={group.id} className="card" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div>
                  <strong style={{ fontSize: 14 }}>{group.label}</strong>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{group.hint}</p>
                </div>
                {!readOnly && (
                  <button className="btn btn-secondary btn-sm" onClick={() => addCharge(group.id)}>
                    <Plus size={13} /> Thêm dòng
                  </button>
                )}
              </div>

              {rows.length === 0 && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>Chưa có dòng phí nào</p>
              )}

              {rows.map(({ c, i }) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 90px 70px 70px 90px 28px', gap: 8, alignItems: 'center', marginTop: 8 }}>
                  <input
                    className="form-input"
                    style={{ padding: '5px 8px', fontSize: 13 }}
                    value={c.charge_code}
                    onChange={e => updateCharge(i, { charge_code: e.target.value })}
                    placeholder="Mã phí"
                    disabled={readOnly}
                  />
                  <input
                    className="form-input"
                    style={{ padding: '5px 8px', fontSize: 13 }}
                    value={c.description ?? ''}
                    onChange={e => updateCharge(i, { description: e.target.value })}
                    placeholder="Mô tả"
                    disabled={readOnly}
                  />
                  <input
                    className="form-input"
                    style={{ padding: '5px 8px', fontSize: 13 }}
                    value={c.currency}
                    onChange={e => updateCharge(i, { currency: e.target.value })}
                    disabled={readOnly}
                  />
                  <input
                    className="form-input"
                    type="number"
                    style={{ padding: '5px 8px', fontSize: 13 }}
                    value={c.unit_price}
                    onChange={e => updateCharge(i, { unit_price: e.target.value })}
                    disabled={readOnly}
                  />
                  <input
                    className="form-input"
                    type="number"
                    style={{ padding: '5px 8px', fontSize: 13 }}
                    value={c.quantity}
                    onChange={e => updateCharge(i, { quantity: e.target.value })}
                    disabled={readOnly}
                  />
                  <span className="mono" style={{ fontSize: 13, textAlign: 'right' }}>
                    {(Number(c.unit_price || 0) * Number(c.quantity || 1)).toFixed(2)}
                  </span>
                  {!readOnly ? (
                    <button className="btn btn-ghost btn-icon" onClick={() => removeCharge(i)} aria-label="Xoá dòng phí">
                      <Trash2 size={14} />
                    </button>
                  ) : <span />}
                </div>
              ))}
            </div>
          );
        })}

        <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: 15, fontWeight: 600, paddingTop: 4 }}>
          Tổng: {form.currency} {(readOnly && quote ? Number(quote.total_amount) : previewTotal).toFixed(2)}
        </div>
      </section>

      {saveError && <div className="banner banner-danger"><AlertTriangle size={16} /> {saveError}</div>}

      {!readOnly && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || !form.customer_name.trim()}>
            <Save size={14} /> {saving ? 'Đang lưu…' : 'Lưu báo giá'}
          </button>
          {!isNew && (
            <button className="btn btn-secondary" onClick={() => { setEditing(false); if (quote) setForm(toInput(quote)); }} disabled={saving}>
              <X size={14} /> Huỷ
            </button>
          )}
        </div>
      )}

      {quote && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Tạo lúc {fmtDate(quote.created_at)}
          {quote.updated_at && ` · Sửa lần cuối ${fmtDate(quote.updated_at)}`}
        </p>
      )}
    </div>
  );
}
