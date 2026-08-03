import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { PrivacyPolicyContent } from './PrivacyPolicyContent';

interface PrivacyPolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PrivacyPolicyModal: React.FC<PrivacyPolicyModalProps> = ({ isOpen, onClose }) => {
  // Cierra con la tecla Escape y bloquea el scroll del fondo mientras está abierto
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', handleKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacy-modal-title"
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-700 px-6 py-4 flex items-center justify-between flex-shrink-0">
          <h2 id="privacy-modal-title" className="text-lg font-bold text-white">
            Política de Privacidad
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-white/80 hover:text-white transition-colors"
            aria-label="Cerrar"
          >
            <X size={22} />
          </button>
        </div>

        {/* Cuerpo scrolleable */}
        <div className="overflow-y-auto px-6 py-6 text-slate-700 text-sm leading-relaxed">
          <PrivacyPolicyContent />
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 px-6 py-3 flex justify-end flex-shrink-0 bg-slate-50">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 transition-colors"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicyModal;