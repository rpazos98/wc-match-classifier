import {
  createContext,
  useContext,
  useCallback,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';

interface ToastItem {
  id: number;
  message: string;
}

type ToastFn = (message: string) => void;

const ToastContext = createContext<ToastFn>(() => {
  throw new Error('useToast used outside ToastProvider');
});

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2800); // CSS animation is 2.5s delay + 0.3s out
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {createPortal(
        <div id="toast">
          {toasts.map((t) => (
            <div key={t.id} className="toast-msg">
              {t.message}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastFn {
  return useContext(ToastContext);
}
