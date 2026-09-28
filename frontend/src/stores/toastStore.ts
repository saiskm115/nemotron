import { create } from 'zustand';

export type ToastType = 'error' | 'success' | 'warning' | 'info' | 'confirm';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: 'danger' | 'primary' | 'warning';
  onConfirm?: () => void | Promise<void>;
  onCancel?: () => void;
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, 'id'>) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    const id = `toast_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    // Confirm toasts should not auto-dismiss by default (duration = 0)
    const duration = toast.duration !== undefined ? toast.duration : (
      toast.type === 'confirm' ? 0 : (toast.type === 'error' ? 5000 : 3500)
    );

    const newToast: ToastItem = {
      ...toast,
      id,
      duration
    };

    set((state) => ({
      toasts: [...state.toasts.slice(-4), newToast] // Keep max 5 visible toasts
    }));

    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id)
        }));
      }, duration);
    }

    return id;
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id)
    })),

  clearToasts: () => set({ toasts: [] })
}));

// Standalone toast helper accessible from any function, hook, or non-React file
export const toast = {
  error: (message: string, title?: string, duration?: number) => {
    return useToastStore.getState().addToast({
      type: 'error',
      title: title || 'Action Error',
      message,
      duration: duration ?? 5000
    });
  },

  success: (message: string, title?: string, duration?: number) => {
    return useToastStore.getState().addToast({
      type: 'success',
      title: title || 'Success',
      message,
      duration: duration ?? 3500
    });
  },

  warning: (message: string, title?: string, duration?: number) => {
    return useToastStore.getState().addToast({
      type: 'warning',
      title: title || 'Warning',
      message,
      duration: duration ?? 4000
    });
  },

  info: (message: string, title?: string, duration?: number) => {
    return useToastStore.getState().addToast({
      type: 'info',
      title: title || 'Information',
      message,
      duration: duration ?? 3500
    });
  },

  confirm: (
    message: string,
    options: {
      title?: string;
      confirmLabel?: string;
      cancelLabel?: string;
      confirmVariant?: 'danger' | 'primary' | 'warning';
      duration?: number;
      onConfirm: () => void | Promise<void>;
      onCancel?: () => void;
    }
  ) => {
    return useToastStore.getState().addToast({
      type: 'confirm',
      title: options.title || 'Confirm Action',
      message,
      duration: options.duration ?? 0,
      confirmLabel: options.confirmLabel || 'Confirm',
      cancelLabel: options.cancelLabel || 'Cancel',
      confirmVariant: options.confirmVariant || 'primary',
      onConfirm: options.onConfirm,
      onCancel: options.onCancel
    });
  },

  ask: (
    message: string,
    options?: {
      title?: string;
      confirmLabel?: string;
      cancelLabel?: string;
      confirmVariant?: 'danger' | 'primary' | 'warning';
      duration?: number;
    }
  ): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      useToastStore.getState().addToast({
        type: 'confirm',
        title: options?.title || 'Confirm Action',
        message,
        duration: options?.duration ?? 0,
        confirmLabel: options?.confirmLabel || 'Confirm',
        cancelLabel: options?.cancelLabel || 'Cancel',
        confirmVariant: options?.confirmVariant || 'primary',
        onConfirm: () => resolve(true),
        onCancel: () => resolve(false)
      });
    });
  }
};
