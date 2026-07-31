import { Check } from 'lucide-react';
import { STAGE_LABELS, STAGE_ORDER } from '../lib/shipmentStage';
import type { ShipmentStage } from '../types/api';

export function ContainerProgressTimeline({ stage, slaBreached }: {
  stage: ShipmentStage | null;
  slaBreached?: boolean;
}) {
  if (stage === null) {
    return (
      <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '4px 0' }}>
        Chưa có job — chưa xác định tiến độ
      </div>
    );
  }

  const currentIndex = STAGE_ORDER.indexOf(stage);

  return (
    <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
      {STAGE_ORDER.map((step, index) => {
        const isDone = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isLast = index === STAGE_ORDER.length - 1;

        let dotStyle: React.CSSProperties;
        if (isDone) {
          dotStyle = { background: 'var(--success-fill)', border: 'none' };
        } else if (isCurrent) {
          dotStyle = {
            background: 'var(--bg-surface)',
            border: `3px solid ${slaBreached ? 'var(--warning-fill)' : 'var(--accent)'}`,
          };
        } else {
          dotStyle = { background: 'var(--border-strong)', opacity: 0.6, border: 'none' };
        }

        return (
          <div key={step} style={{ display: 'flex', alignItems: 'center', flex: isLast ? '0 0 auto' : 1 }}>
            <div className="timeline-step" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div
                style={{
                  width: 20, height: 20, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                  ...dotStyle,
                }}
              >
                {isDone && <Check size={11} color="#fff" />}
              </div>
              <span
                className="timeline-label"
                style={{
                  fontSize: 11, whiteSpace: 'nowrap',
                  color: isCurrent ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontWeight: isCurrent ? 600 : 400,
                }}
              >
                {STAGE_LABELS[step]}
              </span>
            </div>
            {!isLast && (
              <div
                className="timeline-line"
                style={{
                  flex: 1, height: 2, margin: '0 4px 18px',
                  background: isDone ? 'var(--success-fill)' : 'var(--border-strong)',
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
