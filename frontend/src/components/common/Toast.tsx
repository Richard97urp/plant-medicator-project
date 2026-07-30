// src/components/common/Toast.tsx
import React, { useEffect } from 'react';

interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ 
  message, 
  type = 'info', 
  onClose 
}) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const colors = {
    success: 'bg-emerald-500',
    error: 'bg-rose-500',
    info: 'bg-sky-500'
  };

  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ'
  };

  return (
    <div className={`fixed top-4 right-4 ${colors[type]} text-white px-6 py-4 rounded-xl shadow-2xl z-50 animate-slide-in-right max-w-md`}>
      <div className="flex items-center gap-3">
        <span className="text-2xl">
          {icons[type]}
        </span>
        <p className="font-medium">{message}</p>
        <button 
          onClick={onClose} 
          className="ml-4 hover:opacity-70"
        >
          <span className="text-xl">×</span>
        </button>
      </div>
    </div>
  );
};