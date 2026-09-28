import React from 'react';
import { createPortal } from 'react-dom';
import { useToastStore, ToastItem, ToastType } from '../../stores/toastStore';
import { AlertOctagon, AlertTriangle, CheckCircle2, Info, HelpCircle, X } from 'lucide-react';

const toastConfig: Record<ToastType, {
  icon: React.ReactNode;
  bg: string;
  border: string;
  accent: string;
  badgeBg: string;
  badgeText: string;
}> = {
  error: {
    icon: <AlertOctagon size={18} className="text-rose-400 shrink-0" />,
    bg: 'rgba(15, 23, 42, 0.96)',
    border: 'rgba(244, 63, 94, 0.55)',
    accent: '#f43f5e',
    badgeBg: 'rgba(244, 63, 94, 0.22)',
    badgeText: '#fecdd3'
  },
  warning: {
    icon: <AlertTriangle size={18} className="text-amber-400 shrink-0" />,
    bg: 'rgba(15, 23, 42, 0.96)',
    border: 'rgba(245, 158, 11, 0.55)',
    accent: '#f59e0b',
    badgeBg: 'rgba(245, 158, 11, 0.22)',
    badgeText: '#fef3c7'
  },
  success: {
    icon: <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />,
    bg: 'rgba(15, 23, 42, 0.96)',
    border: 'rgba(16, 185, 129, 0.55)',
    accent: '#10b981',
    badgeBg: 'rgba(16, 185, 129, 0.22)',
    badgeText: '#a7f3d0'
  },
  info: {
    icon: <Info size={18} className="text-cyan-400 shrink-0" />,
    bg: 'rgba(15, 23, 42, 0.96)',
    border: 'rgba(56, 189, 248, 0.55)',
    accent: '#38bdf8',
    badgeBg: 'rgba(56, 189, 248, 0.22)',
    badgeText: '#bae6fd'
  },
  confirm: {
    icon: <HelpCircle size={18} className="text-violet-400 shrink-0" />,
    bg: 'rgba(15, 23, 42, 0.98)',
    border: 'rgba(139, 92, 246, 0.65)',
    accent: '#8b5cf6',
    badgeBg: 'rgba(139, 92, 246, 0.25)',
    badgeText: '#ddd6fe'
  }
};

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0 || typeof document === 'undefined') return null;

  const content = (
    <div
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'fixed',
        top: 56,
        right: 18,
        zIndex: 2147483647,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 380,
        width: 'calc(100vw - 36px)',
        pointerEvents: 'none'
      }}
    >
      {toasts.map((t) => {
        const conf = toastConfig[t.type];
        return (
          <div
            key={t.id}
            role="alert"
            data-testid={`toast-${t.type}`}
            style={{
              pointerEvents: 'auto',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              padding: '10px 14px',
              borderRadius: 9,
              background: conf.bg,
              border: `1px solid ${conf.border}`,
              boxShadow: `0 8px 30px rgba(0, 0, 0, 0.65), 0 0 15px ${conf.accent}22`,
              backdropFilter: 'blur(12px)',
              animation: 'toastSlideIn 0.22s cubic-bezier(0.16, 1, 0.3, 1) forwards',
              transition: 'all 0.2s ease',
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            {/* Left Accent indicator stripe */}
            <div
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: 3.5,
                background: conf.accent
              }}
            />

            <div style={{ marginTop: 1, flexShrink: 0 }}>
              {conf.icon}
            </div>

            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {t.title && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      padding: '1px 5px',
                      borderRadius: 4,
                      background: conf.badgeBg,
                      color: conf.badgeText,
                      fontFamily: 'var(--font-mono)'
                    }}
                  >
                    {t.title}
                  </span>
                </div>
              )}
              <div
                style={{
                  fontSize: 12.5,
                  lineHeight: '1.4',
                  color: 'rgba(241, 245, 249, 0.95)',
                  fontWeight: 500,
                  wordBreak: 'break-word'
                }}
              >
                {t.message}
              </div>

              {t.type === 'confirm' && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginTop: 8,
                    paddingTop: 6,
                    borderTop: '1px solid rgba(255, 255, 255, 0.08)'
                  }}
                >
                  <button
                    data-testid="toast-cancel-btn"
                    onClick={() => {
                      t.onCancel?.();
                      removeToast(t.id);
                    }}
                    style={{
                      background: 'rgba(51, 65, 85, 0.7)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#cbd5e1',
                      padding: '4px 10px',
                      fontSize: 11.5,
                      fontWeight: 500,
                      borderRadius: 5,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(71, 85, 105, 0.9)';
                      e.currentTarget.style.color = '#fff';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(51, 65, 85, 0.7)';
                      e.currentTarget.style.color = '#cbd5e1';
                    }}
                  >
                    {t.cancelLabel || 'Cancel'}
                  </button>

                  <button
                    data-testid="toast-confirm-btn"
                    onClick={async () => {
                      try {
                        await t.onConfirm?.();
                      } finally {
                        removeToast(t.id);
                      }
                    }}
                    style={{
                      background: t.confirmVariant === 'danger'
                        ? 'linear-gradient(135deg, #e11d48, #be123c)'
                        : t.confirmVariant === 'warning'
                        ? 'linear-gradient(135deg, #d97706, #b45309)'
                        : 'linear-gradient(135deg, #0284c7, #0369a1)',
                      border: 'none',
                      color: '#ffffff',
                      padding: '4px 12px',
                      fontSize: 11.5,
                      fontWeight: 600,
                      borderRadius: 5,
                      cursor: 'pointer',
                      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.filter = 'brightness(1.15)';
                      e.currentTarget.style.transform = 'translateY(-1px)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.filter = 'none';
                      e.currentTarget.style.transform = 'translateY(0)';
                    }}
                  >
                    {t.confirmLabel || 'Confirm'}
                  </button>
                </div>
              )}
            </div>

            <button
              onClick={() => removeToast(t.id)}
              aria-label="Dismiss notification"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'rgba(148, 163, 184, 0.7)',
                cursor: 'pointer',
                padding: 2,
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                transition: 'color 0.15s, background 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#fff';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'rgba(148, 163, 184, 0.7)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}

      <style>{`
        @keyframes toastSlideIn {
          from {
            opacity: 0;
            transform: translateX(30px) scale(0.96);
          }
          to {
            opacity: 1;
            transform: translateX(0) scale(1);
          }
        }
      `}</style>
    </div>
  );

  return createPortal(content, document.body);
};
