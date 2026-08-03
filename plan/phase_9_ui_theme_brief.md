# GĐ9 — Brief tự chứa: Theme Slash Admin (light/dark) + RBAC UI + Container Progress Timeline

> Brief tự chứa — KHÔNG cần đọc tài liệu ngoài repo. Trước khi code, đọc `CLAUDE.md` (gốc repo) + `plan/agentify_slash_admin_design.docx` (bối cảnh/wireframe đã duyệt). Giai đoạn này gồm 3 phần độc lập, có thể làm tuần tự: **9A Theme** → **9B RBAC UI** → **9C Container Progress Timeline**. Không đổi stack (giữ React + CSS thuần, KHÔNG cài Tailwind/shadcn) — chỉ đổi token màu/spacing/radius/shadow/font trong `frontend_v2/src/index.css` cho giống Slash Admin (github.com/d3george/slash-admin), cộng thêm light/dark toggle.

Ghi chú quyền: `backend/config/permissions.py` đã có `system_config` (view/create/edit/approve/export: chỉ `admin`, `view` thêm `manager`) — dùng lại nguyên, KHÔNG sửa ma trận. Component ẩn/hiện dùng `canAccessSystemConfig()` đã có trong `frontend_v2/src/lib/permissions.ts`.

---

# PHẦN 9A — Theme token (light + dark), lấy đúng từ Slash Admin

## 1. Mục tiêu & vì sao
Slash Admin dùng bộ token màu/typography/shadow riêng (không phải Tailwind mặc định). Để "giống" mà không phải cài Tailwind, ta chép đúng giá trị hex của họ vào biến CSS hiện có trong `index.css`, thêm khối `[data-theme="dark"]`, và một nút toggle lưu lựa chọn vào `localStorage`. Nguồn token (đã xác minh trực tiếp từ repo `d3george/slash-admin`, file `src/theme/tokens/color.ts`, `typography.ts`, `shadow.ts`):

- Primary (accent): lighter `#C8FAD6`, light `#5BE49B`, default `#00A76F`, dark `#007867`, darker `#004B50`.
- Success: default `#36B37E`, dark `#1B806A`, lighter `#D8FBDE`.
- Warning: default `#FFAB00`, dark `#B76E00`, lighter `#FFF5CC`.
- Error: default `#FF5630`, dark `#B71D18`, lighter `#FFE9D5`.
- Info: default `#00B8D9`, dark `#006C9C`, lighter `#CAFDF5`.
- Gray scale: 100 `#F9FAFB`, 200 `#F4F6F8`, 300 `#DFE3E8`, 400 `#C4CDD5`, 500 `#919EAB`, 600 `#637381`, 700 `#454F5B`, 800 `#1C252E`, 900 `#141A21`.
- Dark mode nền: `background.default = #09090B` (đen), `background.neutral = #27272A`.
- Font: `Inter Variable` (fallback hệ thống nếu không load được font variable — dùng `Inter, "Segoe UI", sans-serif`).
- Cỡ chữ: xs 12px, sm 14px, default 16px, lg 18px, xl 20px. Weight: normal 400, medium 500, semibold 600, bold 700.
- Shadow card: `0 0 2px 0 rgba(145,158,171,.2), 0 12px 24px -4px rgba(145,158,171,.12)`.

## 2. Việc cần làm trong `frontend_v2/src/index.css`
Thay khối `:root` hiện tại (dòng ~2-22) bằng bảng ánh xạ sau — **giữ nguyên tên biến cũ** (để không phải sửa lại toàn bộ file, vì mọi component đang dùng `var(--accent)`, `var(--text-primary)`... theo tên này), chỉ đổi GIÁ TRỊ:

| Biến (giữ tên) | Giá trị light mới | Giá trị dark mới |
|---|---|---|
| `--bg-app` | `#F9FAFB` | `#141A21` |
| `--bg-surface` (card — biến mới, thêm) | `#FFFFFF` | `#1C252E` |
| `--bg-hover` | `rgba(145,158,171,.08)` | `rgba(145,158,171,.16)` |
| `--bg-selected` | `#C8FAD6` | `#004B50` |
| `--text-primary` | `#1C252E` | `#F9FAFB` |
| `--text-secondary` | `#637381` | `#C4CDD5` |
| `--text-muted` | `#919EAB` | `#919EAB` |
| `--border-subtle` | `#F4F6F8` | `#27272A` |
| `--border-strong` | `#DFE3E8` | `#454F5B` |
| `--accent` | `#00A76F` | `#5BE49B` |
| `--accent-hover` | `#007867` | `#00A76F` |
| `--accent-soft` | `#C8FAD6` | `#004B50` |
| `--success` | `#1B806A` (text) / `#36B37E` (fill — thêm `--success-fill`) | `#5BE49B` text / `#36B37E` fill |
| `--warning` | `#B76E00` text / `#FFAB00` fill | `#FFD666` text / `#FFAB00` fill |
| `--danger` | `#B71D18` text / `#FF5630` fill | `#FFAC82` text / `#FF5630` fill |
| `--card-shadow` (biến mới) | `0 0 2px 0 rgba(145,158,171,.2), 0 12px 24px -4px rgba(145,158,171,.12)` | `0 0 2px 0 rgba(0,0,0,.4), 0 12px 24px -4px rgba(0,0,0,.32)` |
| `--radius-card` (biến mới) | `12px` | `12px` |
| `--radius-control` (biến mới) | `8px` | `8px` |
| `font-family` trên `body` | `"Inter", "Segoe UI", Roboto, sans-serif` | (giữ nguyên cả 2 mode) |

Bọc khối thứ 2 y hệt trong `[data-theme="dark"] { ... }` với các giá trị cột "dark mới". Toàn bộ `.card`, `.btn`, `.badge`, `.status-strip-item`... trong `index.css` đang tham chiếu các biến này nên **tự động đổi** — không cần sửa từng class, trừ 3 việc bổ sung:
- `.card` thêm `box-shadow: var(--card-shadow); border-radius: var(--radius-card);` (thay cho border đơn thuần hiện có, hoặc giữ cả hai).
- `.btn`, `.form-input` đổi `border-radius` sang `var(--radius-control)`.
- `.sidebar` background dùng `var(--bg-surface)` thay vì màu cứng đang có (kiểm tra dòng ~81 trong `index.css`).

## 3. Toggle theme — file mới `frontend_v2/src/lib/theme.ts`
```ts
const KEY = 'agentify-theme';
export type ThemeMode = 'light' | 'dark';

export function getStoredTheme(): ThemeMode {
  return (localStorage.getItem(KEY) as ThemeMode) || 'light';
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.setAttribute('data-theme', mode);
  localStorage.setItem(KEY, mode);
}
```
Gọi `applyTheme(getStoredTheme())` một lần trong `frontend_v2/src/main.tsx` trước khi render (tránh flash sai theme).

## 4. Component nút toggle — trong `AppShell.tsx`
Thêm nút cạnh `ROLE_LABELS` badge trong `<header className="toolbar">` (gần dòng có `{user && (...)}` hiển thị role hiện tại), dùng icon `Sun`/`Moon` từ `lucide-react` (đã có sẵn dependency). State cục bộ `const [mode, setMode] = useState<ThemeMode>(getStoredTheme())`, `onClick` gọi `applyTheme` rồi `setMode`.

## 5. Checkpoint 9A
- [ ] Bấm nút toggle → toàn bộ nền/chữ/card/badge đổi giữa light/dark, không có phần tử nào giữ màu cứng gây chói mắt hoặc mất chữ (đặc biệt `.badge-danger/-success/-warning` — kiểm tra `index.css` phần badge dùng đúng biến, không hardcode hex).
- [ ] Reload trang (F5) → theme đã chọn được giữ nguyên (đọc từ `localStorage`).
- [ ] Xem 3 trang bất kỳ (`OverviewPage`, `KanbanPage`, `ContainersPage`) ở cả 2 theme → không còn text/nền cùng màu (contrast đủ đọc).

---

# PHẦN 9B — RBAC UI: trang quản lý người dùng + ma trận quyền

## 1. Mục tiêu & vì sao
Hiện `permissions.py` là nguồn sự thật nhưng không ai xem được ngoài đọc code; và không có API/UI tạo-sửa user ngoài script seed ở GĐ1. Thêm 2 trang chỉ `admin` thấy được, đặt trong nhóm sidebar "Hệ thống" (theo `plan/agentify_slash_admin_design.docx` mục 3.3).

## 2. Backend

### 2.1 `backend/api/routes/users.py` (route mới, prefix `/api/v1/users`)
- `GET /` — list toàn bộ user (id, username, display_name, role, is_active, created_at). Quyền: `require_permission("system_config", "view")`.
- `POST /` — tạo user (username, display_name, role, password). Quyền: `require_permission("system_config", "create")`. Hash password bằng hàm đã có trong `backend/services/auth_service.py` (tái dùng, không viết lại bcrypt).
- `PATCH /{user_id}` — sửa `role` / `is_active` / reset password. Quyền: `require_permission("system_config", "edit")`.
- Validate: `role` phải nằm trong enum `UserRole` (7 giá trị), không cho set nhiều role — đúng nguyên tắc "1 tài khoản = đúng 1 vai trò" trong `CLAUDE.md`.

### 2.2 `backend/api/routes/admin.py` (route mới, prefix `/api/v1/admin`)
- `GET /permissions` — serialize trực tiếp dict `PERMISSIONS` từ `backend/config/permissions.py` sang JSON `{resource: {action: [role, ...]}}` (role.value, không phải enum object). Quyền: `require_permission("system_config", "view")`. KHÔNG tạo bảng DB — đọc thẳng từ file Python để tránh 2 nguồn sự thật.

### 2.3 Đăng ký router
Thêm `users.router` và `admin.router` vào `backend/api/routes/api_main.py` (xem cách các router khác đã đăng ký ở đó để theo đúng pattern).

### 2.4 Test — `backend/tests/test_users_routes.py`, `test_admin_routes.py`
- `admin` gọi `GET /users` → 200, thấy đủ user.
- Role khác (`sales_cs`, `ops`...) gọi `GET /users` hoặc `GET /admin/permissions` → 403.
- `admin` tạo user role không hợp lệ (chuỗi tuỳ ý ngoài enum) → 422.
- `admin` `PATCH` đổi role user khác → user đó login lại nhận đúng role mới.

## 3. Frontend

### 3.1 `frontend_v2/src/types/api.ts`
Thêm types: `AdminUser { id, username, display_name, role, is_active, created_at }`, `AdminUserListResponse`, `PermissionMatrix = Record<string, Record<string, Role[]>>`.

### 3.2 `frontend_v2/src/lib/api.ts`
Thêm hàm gọi API: `listUsers()`, `createUser(payload)`, `updateUser(id, payload)`, `getPermissionMatrix()` — theo đúng pattern các hàm `api.xxx` hiện có trong file này (fetch wrapper + xử lý lỗi/refresh token đã có sẵn, không viết lại).

### 3.3 `frontend_v2/src/pages/admin/UsersPage.tsx` (mới)
- Bảng: cột Tên hiển thị, Username, badge Role (dùng `ROLE_LABELS`), badge trạng thái Active/Khoá, ngày tạo.
- Nút "Tạo user" mở form (giống pattern `KanbanPage.tsx` phần `formOpen`/`createBusy`/`createError` — copy cấu trúc y hệt, chỉ đổi field).
- Dropdown Role: đúng 7 option cứng từ `ROLE_LABELS` (không cho multi-select).
- Toggle Active/Khoá theo hàng — gọi `updateUser(id, { is_active })`.
- Bọc toàn trang bằng kiểm tra `canAccessSystemConfig(user?.role)`, nếu false → `<Navigate to="/" />` (pattern giống `RequireAuth.tsx`).

### 3.4 `frontend_v2/src/pages/admin/PermissionMatrixPage.tsx` (mới)
- Gọi `getPermissionMatrix()`, render bảng: hàng = resource, cột = action, ô = danh sách badge role (dùng `ROLE_LABELS`). Chỉ đọc, không có nút sửa (ma trận là static trong code, cố tình không cho sửa qua UI — xem mục "Việc KHÔNG làm" trong `plan/agentify_slash_admin_design.docx`).

### 3.5 `frontend_v2/src/lib/permissions.ts`
Thêm alias rõ nghĩa: `export const canManageUsers = canAccessSystemConfig;` (không đổi logic, chỉ đặt tên đúng ngữ cảnh trang mới).

### 3.6 `frontend_v2/src/router.tsx`
Thêm 2 route con trong children của `AppShell`: `{ path: 'admin/users', Component: UsersPage }`, `{ path: 'admin/permissions', Component: PermissionMatrixPage }`.

### 3.7 `frontend_v2/src/components/layout/AppShell.tsx`
Trong mảng `NAV`, thêm 2 phần tử mới với field `requiresSystemAccess: true`, cập nhật hàm filter `nav` thêm nhánh `if (item.requiresSystemAccess) return canAccessSystemConfig(user?.role);`. Thêm 1 dòng `<div className="nav-group-label">Hệ thống</div>` trước 2 mục này trong JSX (mục `/setup` "Data Sources" hiện có cũng chuyển xuống nhóm này, xem mục 3.3 trong file design đã duyệt). Style `.nav-group-label` thêm vào `index.css`: `font-size: 11px; font-weight: 600; letter-spacing: .04em; color: var(--text-muted); padding: 14px 10px 4px; text-transform: uppercase;`.

## 4. Checkpoint 9B
- [ ] Đăng nhập `admin` → thấy mục "Quản lý người dùng" + "Ma trận quyền" trong sidebar, mở được cả hai.
- [ ] Đăng nhập role khác (vd `sales`) → không thấy 2 mục này; cố vào thẳng URL `/admin/users` → bị chặn về Overview (và gọi API trực tiếp vẫn 403, chứng minh không chỉ ẩn ở UI, đúng nguyên tắc GĐ3 đã áp dụng).
- [ ] Tạo 1 user mới qua UI → login được bằng tài khoản đó, đúng role đã chọn.
- [ ] Bảng ma trận quyền hiển thị đúng khớp với nội dung `backend/config/permissions.py` (đối chiếu tay 3-4 dòng).
- [ ] `pytest` phần users/admin PASS + toàn bộ test cũ vẫn PASS.

---

# PHẦN 9C — Container Progress Timeline (stepper 7 bước)

## 1. Mục tiêu & vì sao
Cho biết 1 container đã đi qua bước nào — dữ liệu đã có (`Shipment.stage`, container_facts, customs_declarations, reconciliation_log) nhưng rải rác, chưa có nơi tổng hợp. Xem mục 4 trong `plan/agentify_slash_admin_design.docx` để biết đối chiếu 7 bước ↔ nguồn dữ liệu — brief này chỉ mô tả PHẦN CODE.

## 2. Backend — mở rộng response chi tiết container
Trong `backend/db/models.py`, `Container` đã có quan hệ trực tiếp tới `Shipment` (`Shipment.containers = relationship("Container", back_populates="shipment")` — tức bảng `containers` có cột `shipment_id` FK, KHÔNG phải bảng liên kết nhiều-nhiều). Vậy trong `backend/api/routes/containers.py`, endpoint trả chi tiết 1 container chỉ cần load `container.shipment` (đã có sẵn qua relationship, thêm `selectinload`/`joinedload` nếu route đang dùng lazy loading async) và serialize sang response. Trả về:
```json
{ "shipment": { "id": "...", "stage": "customs", "sla_breached": false, "sla_due_at": "2026-08-02T00:00:00Z" } }
```
Nếu container chưa gắn shipment nào → `"shipment": null`. Cập nhật schema response trong `backend/api/models.py` tương ứng (thêm field optional, không phá response cũ — các client khác vẫn đọc được các field hiện có).

## 3. Frontend

### 3.1 `frontend_v2/src/types/api.ts`
Container detail response thêm `shipment: { id: string; stage: ShipmentStage; sla_breached: boolean; sla_due_at: string | null } | null`.

### 3.2 `frontend_v2/src/components/ContainerProgressTimeline.tsx` (mới)
Props: `{ stage: ShipmentStage | null; slaBreached?: boolean }`. Danh sách 7 bước dùng lại đúng `STAGE_LABELS` đã định nghĩa trong `KanbanPage.tsx` — di chuyển hằng số này sang `frontend_v2/src/lib/format.ts` (hoặc file mới `lib/shipmentStage.ts`) rồi import ở cả 2 nơi (tránh định nghĩa trùng 2 chỗ).

Cấu trúc: hàng ngang, mỗi bước là 1 chấm tròn nối bằng đường kẻ:
- Bước có index < index(stage hiện tại): chấm nền `var(--success-fill)`, có icon check (lucide `Check` size 10).
- Bước === stage hiện tại: chấm viền 3px `var(--warning-fill)` nếu `slaBreached`, ngược lại viền `var(--accent)`, nền `var(--bg-surface)`.
- Bước chưa tới: chấm nền `var(--border-strong)`, opacity 0.6.
- Nếu `stage === null` (container chưa gắn shipment): render dòng chữ xám "Chưa có job — chưa xác định tiến độ" thay cho stepper, kèm placeholder không phá layout.

CSS thêm vào `index.css`: `.timeline-step`, `.timeline-line`, `.timeline-label` — dùng đúng biến màu ở Phần 9A, KHÔNG hardcode hex mới.

### 3.3 `frontend_v2/src/pages/ContainerDetailPage.tsx`
Chèn `<ContainerProgressTimeline stage={container.shipment?.stage ?? null} slaBreached={container.shipment?.sla_breached} />` ngay dưới phần header container (trước phần liệt kê `container_facts`) — xem cấu trúc JSX hiện tại của trang quanh dòng có `c.status_text` (đã đọc, khoảng dòng 225) để chèn đúng vị trí.

### 3.4 `frontend_v2/src/pages/ContainersPage.tsx`
Thêm cột "Tiến độ" trong bảng danh sách: badge rút gọn `"{index+1}/7 · {STAGE_LABELS[stage]}"`, hoặc badge-neutral "Chưa có job" nếu `shipment` null. Cần API list container cũng trả kèm `shipment.stage` tóm tắt (mở rộng tương tự mục 2, áp cho endpoint list, không chỉ endpoint detail).

## 4. Test
- `backend/tests/test_containers_routes.py`: container có shipment → response chứa đúng `shipment.stage`; container không gắn shipment nào → `shipment: null`, không lỗi 500.
- Frontend: kiểm tra thủ công (không có test UI tự động trong repo hiện tại) — mở 1 container có job đang ở bước "Hải quan" → stepper tô đúng 3 chấm xanh + 1 chấm viền cam/vàng ở đúng vị trí "Hải quan".

## 5. Checkpoint 9C
- [ ] Mở 1 container có shipment → thấy đúng vị trí hiện tại trên stepper, khớp với cột đang chứa job đó trên trang Kanban.
- [ ] Mở 1 container chưa có job → không lỗi, hiện thông báo "Chưa có job" thay vì stepper trống/vỡ layout.
- [ ] Container có `sla_breached = true` → chấm hiện tại đổi màu cảnh báo, khớp với badge "Quá SLA" đã có trên card Kanban của job đó.
- [ ] Cột "Tiến độ" trong `ContainersPage` hiển thị đúng cho ít nhất 5 container mẫu khác nhau (có/không có job, ở các bước khác nhau).

---

# Việc KHÔNG làm (nhắc lại từ tài liệu thiết kế đã duyệt)
- Không cài Tailwind/shadcn, không viết lại component bằng class Tailwind.
- Không tạo bảng roles/permissions trong DB — ma trận quyền vẫn là static dict trong `permissions.py`, trang 9B chỉ đọc.
- Không gắn `stage` trực tiếp vào bảng `containers` — luôn suy ra qua `shipment` liên kết.
- Không đổi cấu trúc RBAC hiện có (`require_permission`, `PERMISSIONS` dict) — chỉ thêm route mới dùng lại dependency đã có.

# Thứ tự khuyến nghị
9A (theme — không phụ thuộc gì, làm trước để mọi trang sau đó lên đúng màu ngay) → 9B (RBAC UI) → 9C (Container Progress). Sau khi xong cả 3, đối chiếu lại với "Checkpoint nghiệm thu" từng phần ở trên và báo cáo từng ô đạt/chưa, đúng quy tắc làm việc trong `CLAUDE.md`.
