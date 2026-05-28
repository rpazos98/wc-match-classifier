import { useEffect, useState } from 'react';

export default function LoadingBar({ active, label }: { active: boolean; label?: string }) {
  const [width, setWidth] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (active) {
      setVisible(true);
      setWidth(15);
      const t1 = setTimeout(() => setWidth(45), 300);
      const t2 = setTimeout(() => setWidth(70), 1200);
      const t3 = setTimeout(() => setWidth(85), 4000);
      return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
    } else if (visible) {
      setWidth(100);
      const t = setTimeout(() => { setVisible(false); setWidth(0); }, 400);
      return () => clearTimeout(t);
    }
  }, [active, visible]);

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      pointerEvents: 'none',
    }}>
      <div style={{
        width: 280,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 10,
      }}>
        {label && (
          <span style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-sm)',
            letterSpacing: '0.5px',
          }}>
            {label}
          </span>
        )}
        <div style={{
          width: '100%',
          height: 4,
          borderRadius: 2,
          background: 'var(--border)',
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${width}%`,
            borderRadius: 2,
            background: 'var(--green)',
            boxShadow: '0 0 12px rgba(94,214,74,0.5)',
            transition: 'width 0.4s ease, opacity 0.3s ease',
            opacity: width === 100 ? 0 : 1,
          }} />
        </div>
      </div>
    </div>
  );
}
