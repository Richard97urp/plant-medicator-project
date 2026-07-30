import React, { ReactNode } from 'react';
import { Header } from './Header';
import { Footer } from './Footer'; // 🔥 IMPORTAR FOOTER
import { Toast } from '../common/Toast';

interface LayoutProps {
  children: ReactNode;
  isAuthenticated?: boolean;
  userDisplayName?: string;
  userProfile?: any;
  onLogout?: () => void;
  onNewConsultation?: () => void;
  toast?: { message: string; type: 'success' | 'error' | 'info' } | null;
  setToast?: (toast: any) => void;
  showHeader?: boolean;
  showUserMenu?: boolean;
  hideNavigation?: boolean;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  isAuthenticated = false,
  userDisplayName = '',
  userProfile = null,
  onLogout = () => {},
  onNewConsultation = () => {},
  toast = null,
  setToast = () => {},
  showHeader = true,
  showUserMenu = true,
  hideNavigation = false
}) => {
  return (
    <div className="min-h-screen relative">
      {/* 🔥 FONDO CON IMAGEN DE CARHUAZ - AHORA EN TODAS LAS PÁGINAS */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-fixed z-0"
        style={{
          backgroundImage: 'url("/fondos/carhuaz-plantas.jpg")',
        }}
      >
        {/* Overlay oscuro para mejor contraste */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900/80 via-emerald-900/70 to-teal-900/80 backdrop-blur-[2px]"></div>
      </div>

      {/* Contenido principal - z-10 para estar sobre el fondo */}
      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Toast notifications */}
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
        
        {/* Header unificado - ALTURA FIJA: 100px */}
        {showHeader && (
          <Header
            isAuthenticated={isAuthenticated}
            userDisplayName={userDisplayName}
            userProfile={userProfile}
            onLogout={onLogout}
            onNewConsultation={onNewConsultation}
            showUserMenu={showUserMenu}
            hideNavigation={hideNavigation}
          />
        )}
        
        {/* Contenido principal - PADDING FIJO SIEMPRE + flex-1 para ocupar espacio disponible */}
        <main className="pt-4 flex-1">
          {children}
        </main>

        {/* 🔥 FOOTER - NO mostrar cuando hideNavigation es true */}
        {!hideNavigation && <Footer />}
      </div>
    </div>
  );
};