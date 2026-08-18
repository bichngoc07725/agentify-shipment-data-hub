import { useCallback, useEffect, useState } from 'react';
import { Ship, Sparkles, Clock, Mail, Pencil } from 'lucide-react';
import { api } from '../lib/api';
import { canManageBooking } from '../lib/permissions';
import type {
  Booking, BookingPrefill, BookingStatus, ComposedMail, EmailListItem, Role,
} from '../types/api';
import { MailComposerCard } from './MailComposerCard';
import { fmtDate } from '../lib/format';

const SECTION_HEADING: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: 10,
};

const STATUS_TEXT: Record<BookingStatus, string> = {
  requested: 'Đã gửi yêu cầu',
  confirmed: 'Hãng tàu đã xác nhận',
  amended: 'Hãng tàu đổi lịch',
  cancelled: 'Đã huỷ',
};

const STATUS_BADGE: Record<BookingStatus, string> = {
  requested: 'badge-neutral',
  confirmed: 'badge-success',
  amended: 'badge-warning',
  cancelled: 'badge-danger',
};

type FormState = {
  booking_no: string;
  status: BookingStatus;
  carrier: string;
  vessel: string;
  voyage: string;
  pol: string;
  pod: string;
  etd: string;
  eta: string;
  si_cutoff_at: string;
  vgm_cutoff_at: string;
  gate_in_cutoff_at: string;
  container_type: string;
  container_qty: string;
  empty_pickup_depot: string;
  container_no: string;
  freight_rate: string;
  currency: string;
  note: string;
};

const EMPTY_FORM: FormState = {
  booking_no: '', status: 'requested', carrier: '', vessel: '', voyage: '',
  pol: '', pod: '', etd: '', eta: '',
  si_cutoff_at: '', vgm_cutoff_at: '', gate_in_cutoff_at: '',
  container_type: '', container_qty: '', empty_pickup_depot: '', container_no: '',
  freight_rate: '', currency: 'USD', note: '',
};

/** `datetime-local` trả chuỗi không có múi giờ. Gửi thẳng lên thì backend đọc
 * là UTC và giờ chốt lệch đúng 7 tiếng — với một mốc cut-off thì đó là khác
 * biệt giữa kịp và rớt chuyến. */
function localInputToIso(value: string): string | undefined {
  if (!value) return undefined;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

/** ISO từ server -> chuỗi cho `datetime-local` (giờ máy, không có múi giờ). */
function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function cutoffTone(hours: number | null): 'danger' | 'warning' | 'info' {
  if (hours === null) return 'info';
  if (hours < 24) return 'danger';
  if (hours < 72) return 'warning';
  return 'info';
}

function cutoffText(booking: Booking): string {
  const hours = booking.hours_to_next_cutoff;
  if (hours === null || booking.next_cutoff_label === null) return '';
  if (hours < 0) {
    return `${booking.next_cutoff_label} ĐÃ QUÁ HẠN ${Math.abs(Math.round(hours))} giờ`;
  }
  if (hours < 48) return `${booking.next_cutoff_label} còn ${Math.round(hours)} giờ`;
  return `${booking.next_cutoff_label} còn ${Math.round(hours / 24)} ngày`;
}

/** Dùng được ở hai chỗ theo đúng hai thời điểm của Bước 2:
 *  - `quoteId`: trên trang báo giá, lúc đi đặt chỗ mà hãng tàu CHƯA cấp container;
 *  - `containerNo`: trên trang container, sau khi booking đã được xác nhận.
 */
export function BookingCard({
  containerNo,
  quoteId,
  role,
}: {
  containerNo?: string;
  quoteId?: string;
  role: Role | undefined;
}) {
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  // id của chỗ đặt đang sửa; null nghĩa là đang tạo mới. Bước 2 sống ở chỗ này:
  // mở yêu cầu trước, hãng tàu xác nhận sau, và bản ghi phải sửa lại được —
  // không có đường sửa thì đúng khoảnh khắc quan trọng nhất lại không ghi được.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prefillNote, setPrefillNote] = useState<string | null>(null);
  const [mail, setMail] = useState<ComposedMail | null>(null);
  const [mailBusy, setMailBusy] = useState(false);
  const [emailPicker, setEmailPicker] = useState<EmailListItem[] | null>(null);

  async function openBookingMail(bookingId: string) {
    setMailBusy(true); setError(null);
    try {
      setMail(await api.getBookingRequestMail(bookingId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không soạn được thư');
    } finally { setMailBusy(false); }
  }

  const canManage = canManageBooking(role);

  const load = useCallback(() => {
    const request = quoteId
      ? api.getQuoteBookings(quoteId)
      : containerNo
        ? api.getContainerBookings(containerNo)
        : null;
    if (!request) return;
    request.then(r => setBookings(r.items)).catch(() => setBookings(null));
  }, [containerNo, quoteId]);

  useEffect(load, [load]);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  // Nguồn gợi ý đổi theo thời điểm của Bước 2, không theo trang đang đứng.
  // Chưa có container (mới gửi yêu cầu đặt chỗ) thì chỉ báo giá mới nói được
  // tuyến và thiết bị. Có container rồi — tức hãng tàu đã xác nhận — thì thư
  // xác nhận mới là nguồn đúng, và nó là nguồn DUY NHẤT biết ba mốc cut-off.
  const factSourceContainer = containerNo || form.container_no || null;

  function applyFields(p: BookingPrefill, source: string) {
    // Chỉ đếm ô thực sự điền được. Nguồn trả cả `customer_name`/`commodity`
    // mà form đặt chỗ không có ô nào nhận; đếm cả chúng thì băng thông báo
    // hứa nhiều hơn những gì người dùng nhìn thấy trên form.
    const keys = (Object.keys(p) as (keyof BookingPrefill)[]).filter(
      k => k in EMPTY_FORM && p[k],
    );
    if (keys.length === 0) {
      setPrefillNote(`Không tìm thấy trong Agentify — ${source} không có thông tin đặt chỗ.`);
      return;
    }
    setForm(prev => ({
      ...prev,
      booking_no: p.booking_no ?? prev.booking_no,
      vessel: p.vessel ?? prev.vessel,
      voyage: p.voyage ?? prev.voyage,
      pol: p.pol ?? prev.pol,
      pod: p.pod ?? prev.pod,
      etd: p.etd ?? prev.etd,
      eta: p.eta ?? prev.eta,
      container_type: p.container_type ?? prev.container_type,
      container_qty: p.container_qty ?? prev.container_qty,
      container_no: p.container_no ?? prev.container_no,
      carrier: p.carrier ?? prev.carrier,
      // Đã ở dạng `datetime-local` từ nguồn, không đi qua `isoToLocalInput`:
      // giờ trên thư là giờ tại cảng xếp, quy đổi múi giờ ở đây sẽ làm mốc
      // 16:00 hiện thành giờ khác trên máy người xem.
      si_cutoff_at: p.si_cutoff_at ?? prev.si_cutoff_at,
      vgm_cutoff_at: p.vgm_cutoff_at ?? prev.vgm_cutoff_at,
      gate_in_cutoff_at: p.gate_in_cutoff_at ?? prev.gate_in_cutoff_at,
      empty_pickup_depot: p.empty_pickup_depot ?? prev.empty_pickup_depot,
    }));
    setPrefillNote(
      `Đã điền ${keys.length} trường từ ${source} (${keys.join(', ')}). ` +
      'Đây là gợi ý — kiểm tra lại trước khi lưu.',
    );
  }

  /** Bước 2.4: người dùng vừa đọc thư xác nhận ở 2.3, để họ chỉ đúng thư đó.
   *  Lúc này chỗ đặt vẫn chưa gắn container nên không có đường tự tìm ra thư,
   *  và báo giá thì không bao giờ biết số booking lẫn ba mốc cut-off. */
  async function openEmailPicker() {
    setPrefillNote(null); setError(null);
    try {
      const res = await api.listEmails({ page: 1, page_size: 30 });
      setEmailPicker(res.items);
    } catch {
      setError('Không tải được danh sách thư');
    }
  }

  async function applyPrefillFromEmail(emailId: string) {
    setEmailPicker(null);
    try {
      applyFields(await api.getBookingPrefillFromEmail(emailId), 'thư đã chọn');
    } catch {
      setPrefillNote('Không đọc được thư này.');
    }
  }

  async function applyPrefill() {
    setPrefillNote(null);
    try {
      if (factSourceContainer) {
        applyFields(await api.getBookingPrefill(factSourceContainer), 'thư hãng tàu đã đọc');
      } else {
        applyFields(await api.getQuoteBookingPrefill(quoteId!), 'báo giá đã chốt');
      }
    } catch {
      setPrefillNote('Không đọc được dữ liệu gợi ý.');
    }
  }

  function startEdit(b: Booking) {
    setEditingId(b.id);
    setFormOpen(true);
    setPrefillNote(null);
    setForm({
      booking_no: b.booking_no ?? '', status: b.status,
      carrier: b.carrier ?? '', vessel: b.vessel ?? '', voyage: b.voyage ?? '',
      pol: b.pol ?? '', pod: b.pod ?? '', etd: b.etd ?? '', eta: b.eta ?? '',
      si_cutoff_at: isoToLocalInput(b.si_cutoff_at),
      vgm_cutoff_at: isoToLocalInput(b.vgm_cutoff_at),
      gate_in_cutoff_at: isoToLocalInput(b.gate_in_cutoff_at),
      container_type: b.container_type ?? '',
      container_qty: b.container_qty != null ? String(b.container_qty) : '',
      empty_pickup_depot: b.empty_pickup_depot ?? '',
      container_no: b.container_no ?? '',
      freight_rate: b.freight_rate ?? '', currency: b.currency ?? 'USD',
      note: b.note ?? '',
    });
  }

  function closeForm() {
    setFormOpen(false); setEditingId(null); setForm(EMPTY_FORM);
    setError(null); setPrefillNote(null); setEmailPicker(null);
  }

  async function submit() {
    setBusy(true); setError(null);
    try {
      const body = {
        container_no: containerNo ?? form.container_no ?? null,
        quote_id: quoteId ?? null,
        booking_no: form.booking_no || undefined,
        status: form.status,
        carrier: form.carrier || undefined,
        vessel: form.vessel || undefined,
        voyage: form.voyage || undefined,
        pol: form.pol || undefined,
        pod: form.pod || undefined,
        etd: form.etd || undefined,
        eta: form.eta || undefined,
        si_cutoff_at: localInputToIso(form.si_cutoff_at),
        vgm_cutoff_at: localInputToIso(form.vgm_cutoff_at),
        gate_in_cutoff_at: localInputToIso(form.gate_in_cutoff_at),
        container_type: form.container_type || undefined,
        container_qty: form.container_qty ? Number(form.container_qty) : undefined,
        empty_pickup_depot: form.empty_pickup_depot || undefined,
        freight_rate: form.freight_rate || undefined,
        currency: form.currency || 'USD',
        note: form.note || undefined,
      };
      if (editingId) await api.updateBooking(editingId, body);
      else await api.createBooking(body);
      closeForm();
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Không lưu được chỗ đặt');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 style={SECTION_HEADING}>Đặt chỗ trên tàu</h2>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {bookings && bookings.length > 0 ? (
          bookings.map(b => (
            <div key={b.id} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Ship size={14} style={{ color: 'var(--text-muted)' }} />
                <strong style={{ fontSize: 14 }}>{b.booking_no ?? 'Chưa có số booking'}</strong>
                <span className={`badge ${STATUS_BADGE[b.status]}`}>{STATUS_TEXT[b.status]}</span>
                {b.quote_no && <span className="chip">Báo giá {b.quote_no}</span>}
              </div>

              {b.next_cutoff_label && (
                <div className={`banner banner-${cutoffTone(b.hours_to_next_cutoff)}`} style={{ marginTop: 8 }}>
                  <Clock size={14} />
                  <span>{cutoffText(b)} · {fmtDate(b.next_cutoff_at)}</span>
                </div>
              )}

              <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, fontSize: 13 }}>
                <Line label="Hãng tàu" value={b.carrier} />
                <Line label="Tàu / chuyến" value={[b.vessel, b.voyage].filter(Boolean).join(' ') || null} />
                <Line label="Tuyến" value={b.pol && b.pod ? `${b.pol} → ${b.pod}` : null} />
                <Line label="ETD / ETA" value={[b.etd, b.eta].filter(Boolean).join(' → ') || null} />
                <Line label="Thiết bị" value={[b.container_type, b.container_qty ? `x${b.container_qty}` : null].filter(Boolean).join(' ') || null} />
                <Line label="Depot lấy rỗng" value={b.empty_pickup_depot} />
                <Line
                  label="Giá cước hãng tàu"
                  value={b.freight_rate ? `${b.freight_rate} ${b.currency}` : null}
                />
              </div>
              {b.note && <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>{b.note}</p>}
              {canManage && (
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginTop: 8 }}
                  disabled={mailBusy}
                  onClick={() => openBookingMail(b.id)}
                >
                  <Mail size={14} /> Soạn thư đặt chỗ gửi hãng tàu
                </button>
              )}
              {canManage && (
                <button className="btn btn-ghost btn-sm" style={{ marginTop: 8, marginLeft: 8 }}
                  disabled={busy} onClick={() => startEdit(b)}>
                  <Pencil size={14} /> Cập nhật sau khi hãng tàu xác nhận
                </button>
              )}
            </div>
          ))
        ) : (
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            {quoteId ? 'Chưa đặt chỗ cho báo giá này.' : 'Chưa đặt chỗ cho container này.'}
          </p>
        )}

        {mail && (
          <MailComposerCard
            title="Thư đặt chỗ gửi hãng tàu"
            hint="Agentify không gửi thư thay bạn. Chép nội dung hoặc mở trong Gmail rồi tự bấm gửi."
            mail={mail}
            onClose={() => setMail(null)}
          />
        )}

        {canManage && (formOpen ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-secondary btn-sm" onClick={applyPrefill} disabled={busy}>
                <Sparkles size={14} />{' '}
                {factSourceContainer
                  ? 'Điền từ thư hãng tàu đã đọc'
                  : 'Điền từ báo giá đã chốt'}
              </button>
              {/* Chỉ hiện khi đang SỬA: đó là lúc hãng tàu đã trả lời, và thư
                  trả lời là nguồn duy nhất có số booking cùng ba mốc cut-off. */}
              {editingId && (
                <button className="btn btn-secondary btn-sm" onClick={openEmailPicker} disabled={busy}>
                  <Mail size={14} /> Điền từ thư xác nhận của hãng tàu
                </button>
              )}
            </div>
            {prefillNote && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{prefillNote}</div>
            )}

            {emailPicker && (
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <strong style={{ fontSize: 14 }}>Chọn thư xác nhận của hãng tàu</strong>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Agentify đọc số booking, tàu/chuyến, số container, ba mốc cut-off và depot
                  trong thư rồi điền vào form. Bạn kiểm tra lại rồi bấm Lưu.
                </p>
                {emailPicker.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Không có thư nào trong hệ thống.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 260, overflowY: 'auto' }}>
                    {emailPicker.map(e => (
                      <button
                        key={e.id}
                        className="btn btn-ghost btn-sm"
                        style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                        onClick={() => applyPrefillFromEmail(e.id)}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {e.subject} — <span style={{ color: 'var(--text-muted)' }}>{e.from_email}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <button className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }}
                  onClick={() => setEmailPicker(null)}>
                  Huỷ
                </button>
              </div>
            )}

            <Row>
              <Field label="Số booking"><input className="form-input" value={form.booking_no} onChange={e => setField('booking_no', e.target.value)} disabled={busy} /></Field>
              <Field label="Trạng thái">
                <select className="form-input" value={form.status} onChange={e => setField('status', e.target.value as BookingStatus)} disabled={busy}>
                  {(Object.keys(STATUS_TEXT) as BookingStatus[]).map(s => (
                    <option key={s} value={s}>{STATUS_TEXT[s]}</option>
                  ))}
                </select>
              </Field>
              <Field label="Hãng tàu"><input className="form-input" value={form.carrier} onChange={e => setField('carrier', e.target.value)} disabled={busy} /></Field>
            </Row>

            <Row>
              <Field label="Tên tàu"><input className="form-input" value={form.vessel} onChange={e => setField('vessel', e.target.value)} disabled={busy} /></Field>
              <Field label="Số chuyến"><input className="form-input" value={form.voyage} onChange={e => setField('voyage', e.target.value)} disabled={busy} /></Field>
              <Field label="Depot lấy rỗng"><input className="form-input" value={form.empty_pickup_depot} onChange={e => setField('empty_pickup_depot', e.target.value)} disabled={busy} /></Field>
              {quoteId && (
                <Field label="Số container (hãng tàu cấp)">
                  <input className="form-input" placeholder="chưa có khi mới gửi yêu cầu"
                    value={form.container_no} onChange={e => setField('container_no', e.target.value)} disabled={busy} />
                </Field>
              )}
            </Row>

            <Row>
              <Field label="Cảng đi (POL)"><input className="form-input" value={form.pol} onChange={e => setField('pol', e.target.value)} disabled={busy} /></Field>
              <Field label="Cảng đến (POD)"><input className="form-input" value={form.pod} onChange={e => setField('pod', e.target.value)} disabled={busy} /></Field>
              <Field label="Loại / số cont">
                <div style={{ display: 'flex', gap: 6 }}>
                  <input className="form-input" placeholder="40HC" value={form.container_type} onChange={e => setField('container_type', e.target.value)} disabled={busy} />
                  <input className="form-input" type="number" min="1" style={{ maxWidth: 80 }} value={form.container_qty} onChange={e => setField('container_qty', e.target.value)} disabled={busy} />
                </div>
              </Field>
            </Row>

            <Row>
              <Field label="ETD"><input type="date" className="form-input" value={form.etd} onChange={e => setField('etd', e.target.value)} disabled={busy} /></Field>
              <Field label="ETA"><input type="date" className="form-input" value={form.eta} onChange={e => setField('eta', e.target.value)} disabled={busy} /></Field>
              <Field label="Giá cước hãng tàu">
                <div style={{ display: 'flex', gap: 6 }}>
                  <input className="form-input" type="number" step="0.01" placeholder="1850.00" value={form.freight_rate} onChange={e => setField('freight_rate', e.target.value)} disabled={busy} />
                  <input className="form-input" style={{ maxWidth: 80 }} value={form.currency} onChange={e => setField('currency', e.target.value)} disabled={busy} />
                </div>
              </Field>
            </Row>

            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Mốc chốt — trễ một trong ba mốc này là rớt chuyến:
            </div>
            <Row>
              <Field label="SI cut-off"><input type="datetime-local" className="form-input" value={form.si_cutoff_at} onChange={e => setField('si_cutoff_at', e.target.value)} disabled={busy} /></Field>
              <Field label="VGM cut-off"><input type="datetime-local" className="form-input" value={form.vgm_cutoff_at} onChange={e => setField('vgm_cutoff_at', e.target.value)} disabled={busy} /></Field>
              <Field label="Hạ container (gate-in)"><input type="datetime-local" className="form-input" value={form.gate_in_cutoff_at} onChange={e => setField('gate_in_cutoff_at', e.target.value)} disabled={busy} /></Field>
            </Row>

            <Field label="Ghi chú"><input className="form-input" value={form.note} onChange={e => setField('note', e.target.value)} disabled={busy} /></Field>

            {error && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary btn-sm" onClick={submit} disabled={busy}>
                {busy ? 'Đang lưu…' : editingId ? 'Lưu thay đổi' : 'Lưu chỗ đặt'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={closeForm} disabled={busy}>
                Huỷ
              </button>
            </div>
          </div>
        ) : (
          <button className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setFormOpen(true)}>
            + Đặt chỗ mới
          </button>
        ))}
      </div>
    </section>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {children}
    </div>
  );
}

/** Thiếu dữ liệu thì nói thẳng là thiếu, không để ô trống cho người đọc tự đoán. */
function Line({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ color: value ? 'inherit' : 'var(--text-muted)' }}>
        {value ?? 'Không tìm thấy trong Agentify'}
      </div>
    </div>
  );
}
