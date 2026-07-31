// Mirrors `backend/config/permissions.py` for UI purposes only — deciding
// whether to SHOW a button. The backend re-checks every one of these on the
// actual request and is the only real enforcement; getting this file wrong
// only means a confusing 403 later, never a security hole.

import type { ExceptionSeverity, Role } from '../types/api';

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Quản trị hệ thống',
  manager: 'Quản lý',
  sales_cs: 'Sales / CS',
  docs: 'Chứng từ',
  ops: 'Vận hành',
  accountant: 'Kế toán',
  driver: 'Tài xế',
};

const MANUAL_INGEST_CREATE_ROLES: Role[] = ['ops', 'docs'];

export function canCreateManualIngest(role: Role | undefined): boolean {
  return !!role && MANUAL_INGEST_CREATE_ROLES.includes(role);
}

const CONTAINER_FACTS_EDIT_ROLES: Role[] = ['docs', 'ops', 'accountant'];

type FieldGroup = 'document' | 'operation' | 'finance';

const ROLE_FIELD_GROUP: Partial<Record<Role, FieldGroup>> = {
  docs: 'document',
  ops: 'operation',
  accountant: 'finance',
};

// Keep in sync with `backend/config/permissions.py::CONTAINER_FACT_FIELD_GROUPS`.
const CONTAINER_FACT_FIELD_GROUPS: Record<string, FieldGroup> = {
  container_no: 'operation',
  booking_no: 'operation',
  seal_no: 'operation',
  vessel: 'operation',
  voyage: 'operation',
  pol: 'operation',
  pod: 'operation',
  etd: 'operation',
  eta: 'operation',
  ata: 'operation',
  do_no: 'operation',
  free_time_days: 'operation',
  bl_no: 'document',
  po_no: 'document',
  debit_note_no: 'finance',
  invoice_no: 'finance',
  invoice_amount: 'finance',
  charge_amount: 'finance',
};

export function canEditContainerFact(role: Role | undefined, fieldName: string): boolean {
  if (!role || !CONTAINER_FACTS_EDIT_ROLES.includes(role)) return false;
  return ROLE_FIELD_GROUP[role] === CONTAINER_FACT_FIELD_GROUPS[fieldName];
}

type Tier = 'normal' | 'critical';

function tierOf(severity: ExceptionSeverity): Tier {
  return severity === 'critical' ? 'critical' : 'normal';
}

// Keep in sync with `backend/config/permissions.py::EXCEPTION_ACTIONS_BY_SEVERITY`.
const EXCEPTION_ACTIONS_BY_SEVERITY: Record<Tier, { resolve: Role[]; approve: Role[] }> = {
  normal: { resolve: ['docs', 'ops'], approve: ['admin', 'manager'] },
  critical: { resolve: [], approve: ['admin', 'manager'] },
};

export function canResolveException(role: Role | undefined, severity: ExceptionSeverity): boolean {
  if (!role) return false;
  return EXCEPTION_ACTIONS_BY_SEVERITY[tierOf(severity)].resolve.includes(role);
}

export function canApproveException(role: Role | undefined, severity: ExceptionSeverity): boolean {
  if (!role) return false;
  return EXCEPTION_ACTIONS_BY_SEVERITY[tierOf(severity)].approve.includes(role);
}

export function canAccessSystemConfig(role: Role | undefined): boolean {
  return role === 'admin' || role === 'manager';
}

// Resource `system_config` reused verbatim for the GĐ9B admin pages (user
// management, permission matrix) — same gate, just named for its context.
export const canManageUsers = canAccessSystemConfig;

// Resource `quote`: everyone except Driver may view; only Sales/CS may
// create/edit/delete — Admin/Manager are view-only here too.
export function canViewQuote(role: Role | undefined): boolean {
  return !!role && role !== 'driver';
}

export function canManageQuote(role: Role | undefined): boolean {
  return role === 'sales_cs';
}

// Resources `container_facts` / `exception` / `shipping_document`, all of
// which the backend gates with its `ALL_STAFF` set. Driver is excluded on
// purpose: they only ever see rows scoped to themselves, so the fleet-wide
// container/exception/email lists 403 for them. Nav uses this to hide those
// pages rather than sending a driver into a wall of permission errors.
// TODO(GĐ7 dispatch_order): give Driver a scoped container view instead.
const FLEET_VIEW_ROLES: Role[] = ['admin', 'manager', 'sales_cs', 'docs', 'ops', 'accountant'];

export function canViewFleetData(role: Role | undefined): boolean {
  return !!role && FLEET_VIEW_ROLES.includes(role);
}

// Resource `field_image`: Ops/Driver upload. View mirrors the backend's
// ALL_STAFF group exactly (Admin/Manager/Sales/Docs/Ops/Accountant) — a
// driver who just uploaded a photo cannot list a container's photos back via
// this same-named permission. TODO(GĐ7 dispatch_order): row-level scoping
// should replace this once photos tie to a specific dispatch assignment.
const FIELD_IMAGE_VIEW_ROLES: Role[] = ['admin', 'manager', 'sales_cs', 'docs', 'ops', 'accountant'];

export function canUploadFieldImage(role: Role | undefined): boolean {
  return role === 'ops' || role === 'driver';
}

export function canViewFieldImages(role: Role | undefined): boolean {
  return !!role && FIELD_IMAGE_VIEW_ROLES.includes(role);
}

// Resources `debit_note` / `reconciliation` (GĐ6): both share the same
// view set — Sales/CS and Driver are excluded on purpose, since a variance
// report is real cost vs. quoted price, i.e. margin, which is internal-only.
const COST_DATA_VIEW_ROLES: Role[] = ['admin', 'manager', 'docs', 'ops', 'accountant'];

export function canViewCostData(role: Role | undefined): boolean {
  return !!role && COST_DATA_VIEW_ROLES.includes(role);
}

export function canManageDebitNote(role: Role | undefined): boolean {
  return role === 'accountant';
}

export function canRunReconciliation(role: Role | undefined): boolean {
  return role === 'accountant';
}

export function canApproveReconciliation(role: Role | undefined): boolean {
  return role === 'admin' || role === 'manager';
}

// Resource `customs_declaration` (GĐ7A): view set is identical to cost data
// (Sales/CS and Driver excluded — phân luồng chỉ liên quan nội bộ Ops/Docs/Kế toán).
export function canViewCustomsDeclaration(role: Role | undefined): boolean {
  return canViewCostData(role);
}

export function canCreateCustomsDeclaration(role: Role | undefined): boolean {
  return role === 'ops';
}

export function canEditCustomsDeclaration(role: Role | undefined): boolean {
  return role === 'admin' || role === 'ops';
}

// Resource `shipment` (GĐ7B Kanban): everyone except Driver may view a job
// board card; Sales/CS, Ops, Manager, Admin create new jobs.
const SHIPMENT_VIEW_ROLES: Role[] = ['admin', 'manager', 'sales_cs', 'docs', 'ops', 'accountant'];
const SHIPMENT_CREATE_ROLES: Role[] = ['admin', 'manager', 'sales_cs', 'ops'];

export function canViewShipment(role: Role | undefined): boolean {
  return !!role && SHIPMENT_VIEW_ROLES.includes(role);
}

export function canCreateShipment(role: Role | undefined): boolean {
  return !!role && SHIPMENT_CREATE_ROLES.includes(role);
}

// Row-level: only the stage's current owner (or Admin/Manager, who oversee
// every stage) may push a job forward — mirrors `services/shipment_service.py::can_advance`.
export function canAdvanceShipment(role: Role | undefined, ownerRole: string | null): boolean {
  if (!role) return false;
  if (role === 'admin' || role === 'manager') return true;
  return role === ownerRole;
}

// Resource `audit` (GĐ8A): admin-only — the audit trail is dispute evidence,
// not something any operating role should be able to browse or alter.
export function canViewAuditLog(role: Role | undefined): boolean {
  return role === 'admin';
}

// Resource `erp_export` (GĐ8B): accountant-only, mirrors `config/permissions.py`.
export function canExportErp(role: Role | undefined): boolean {
  return role === 'accountant';
}

/** Where a role lands after login when no specific page was requested.
 *
 * Driver has no access to the fleet-wide Overview, so sending them to `/`
 * would greet them with a permission error on every login. */
export function landingPathFor(role: Role | undefined): string {
  if (role === 'driver') return '/field-images';
  return '/';
}
