// components/layout/Header.tsx
import React from 'react';
import { Link } from 'react-router-dom';

const BotIcon = ({ className = "w-10 h-10" }: { className?: string }) => {
  return (
    <img 
      src="/robot-planta.png"
      alt="Robot Planta"
      className={`object-contain ${className}`}
      onError={(e) => {
        console.error('Error loading bot icon');
        const target = e.target as HTMLImageElement;
        target.style.display = 'none';
        const fallbackDiv = document.createElement('div');
        fallbackDiv.className = 'w-7 h-7 bg-emerald-100 rounded-full flex items-center justify-center';
        fallbackDiv.innerHTML = '<span class="text-emerald-600 font-bold">🌿</span>';
        target.parentNode?.insertBefore(fallbackDiv, target.nextSibling);
      }}
    />
  );
};

const BotHeadIcon = ({ className = "w-8 h-8" }: { className?: string }) => {
  return (
    <img 
      src="/robot-head.png"
      alt="Robot Planta"
      className={`object-contain ${className}`}
    />
  );
};

interface HeaderProps {
  isAuthenticated: boolean;
  userDisplayName: string;
  userProfile: any;
  onLogout: () => void;
  onNewConsultation?: () => void;
  showUserMenu: boolean;
  hideNavigation: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  isAuthenticated,
  userDisplayName,
  userProfile,
  onLogout,
  onNewConsultation,
  showUserMenu,
  hideNavigation
}) => {
  return (
    <header className="sticky top-0 z-50 bg-gradient-to-r from-emerald-600 to-teal-700 text-white shadow-xl border-b border-emerald-500/30">
      <div className="h-[100px] flex items-center max-w-7xl mx-auto px-4">
        
        <div className="grid grid-cols-3 items-center w-full gap-4">
          
          {/* COLUMNA IZQUIERDA - MENÚ HAMBURGUESA */}
          <div className="flex items-center justify-start">
            <Link 
              to="/" 
              className="flex items-center justify-center p-3 rounded-lg hover:bg-emerald-500/30 transition-all group"
              title="Ir al Inicio"
              aria-label="Menú principal - Ir al inicio"
            >
              <div className="flex flex-col items-center justify-center gap-1.5 w-8 h-8">
                <div className="w-6 h-0.5 bg-white rounded-full group-hover:bg-emerald-100 transition-colors"></div>
                <div className="w-6 h-0.5 bg-white rounded-full group-hover:bg-emerald-100 transition-colors"></div>
                <div className="w-6 h-0.5 bg-white rounded-full group-hover:bg-emerald-100 transition-colors"></div>
              </div>
            </Link>
          </div>
          
          {/* COLUMNA CENTRAL - LOGO Y TÍTULO ACTUALIZADO */}
          <div className="flex items-center justify-center">
            <Link 
              to={isAuthenticated ? "/chat" : "/"} 
              className="flex items-center gap-6 hover:opacity-80 transition-opacity"
              title="Sistema Multi-Agente de Prescripción Herbolaria"
            >
              <div className="flex-shrink-0">
                <BotIcon className="w-20 h-20" />
              </div>
              <div className="text-left">
                <h1 className="text-2xl font-bold tracking-tight leading-tight whitespace-nowrap">
                  Fauno - Asistente Herbolario
                </h1>
                
              </div>
            </Link>
          </div>
          
          {/* COLUMNA DERECHA - MENÚ DE USUARIO */}
          <div className="flex items-center justify-end">
            {isAuthenticated && showUserMenu ? (
              <div className="flex items-center gap-4">
                {/* NOMBRE DE USUARIO (DESKTOP) */}
                <div className="text-right hidden lg:block">
                  <p className="text-white font-semibold text-base leading-tight">
                    Hola, {userDisplayName || 'Usuario'}
                  </p>
                  <div className="flex items-center justify-end gap-2 mt-1">
                    <div className="flex items-center gap-1 bg-emerald-500/40 px-2 py-0.5 rounded-full">
                      <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></div>
                      <span className="text-xs text-emerald-100 font-medium">En línea</span>
                    </div>
                  </div>
                </div>
                
                {/* AVATAR CON MENÚ DESPLEGABLE */}
                <div className="relative group">
                  {userProfile?.profile_picture_url ? (
                    <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-white shadow-lg cursor-pointer hover:shadow-xl transition-all hover:scale-105">
                      <img 
                        src={userProfile.profile_picture_url}
                        alt={`Foto de perfil de ${userDisplayName}`}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                          const fallbackDiv = target.parentNode as HTMLDivElement;
                          fallbackDiv.className = 'w-12 h-12 bg-gradient-to-br from-emerald-400 to-teal-500 rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg';
                          fallbackDiv.innerHTML = (userDisplayName || 'U').charAt(0).toUpperCase();
                        }}
                      />
                    </div>
                  ) : (
                    <div className="w-12 h-12 bg-gradient-to-br from-emerald-400 to-teal-500 rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg cursor-pointer hover:shadow-xl transition-all hover:scale-105">
                      {(userDisplayName || 'U').charAt(0).toUpperCase()}
                    </div>
                  )}
                  
                  <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-emerald-700 shadow-sm"></div>
                  
                  {/* MENÚ DESPLEGABLE */}
                  <div className="absolute right-0 top-16 w-64 bg-white rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 border border-slate-200 overflow-hidden">
                    <div className="p-0">
                      {/* Encabezado del menú */}
                      <div className="bg-gradient-to-r from-emerald-500 to-teal-600 p-4">
                        <div className="flex items-center gap-3">
                          {userProfile?.profile_picture_url ? (
                            <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-white/30 bg-white/20 backdrop-blur-sm">
                              <img 
                                src={userProfile.profile_picture_url}
                                alt={`Foto de perfil`}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  const target = e.target as HTMLImageElement;
                                  target.style.display = 'none';
                                  const fallbackDiv = target.parentNode as HTMLDivElement;
                                  fallbackDiv.className = 'w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white font-bold text-lg border border-white/30';
                                  fallbackDiv.innerHTML = (userDisplayName || 'U').charAt(0).toUpperCase();
                                }}
                              />
                            </div>
                          ) : (
                            <div className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white font-bold text-lg border border-white/30">
                              {(userDisplayName || 'U').charAt(0).toUpperCase()}
                            </div>
                          )}
                          <div>
                            <p className="font-semibold text-white text-base">{userDisplayName || 'Usuario'}</p>
                            <p className="text-xs text-emerald-200">Usuario Verificado</p>
                          </div>
                        </div>
                        <div className="mt-3 flex items-center gap-2 bg-emerald-400/30 px-3 py-1.5 rounded-lg">
                          <div className="w-1.5 h-1.5 bg-green-300 rounded-full animate-pulse"></div>
                          <span className="text-xs text-white font-medium">Sesión activa</span>
                        </div>
                      </div>
                      
                      {/* Opciones del menú */}
                      <div className="p-2">
                        {/* OPCIÓN 1: NUEVA CONSULTA */}
                        {onNewConsultation && (
                          <button
                            onClick={onNewConsultation}
                            className="w-full px-3 py-3 mb-1 hover:bg-emerald-50 text-slate-700 rounded-lg text-sm font-medium transition-all text-left flex items-center gap-3 hover:text-emerald-700 group"
                          >
                            <div className="w-9 h-9 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-600 group-hover:bg-emerald-200 transition-all flex-shrink-0">
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm">Nueva Consulta</p>
                              <p className="text-xs text-slate-400 mt-0.5">Reiniciar conversación</p>
                            </div>
                          </button>
                        )}
                        
                        {/* OPCIÓN 2: EDITAR PERFIL */}
                        <Link
                          to="/editar-perfil"
                          className="w-full px-3 py-3 mb-1 hover:bg-sky-50 text-slate-700 rounded-lg text-sm font-medium transition-all text-left flex items-center gap-3 hover:text-sky-700 group block"
                        >
                          <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center text-sky-600 group-hover:bg-sky-200 transition-all flex-shrink-0">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm">Editar Perfil</p>
                            <p className="text-xs text-slate-400 mt-0.5">Modificar datos personales</p>
                          </div>
                        </Link>
                        
                        <div className="h-px bg-slate-100 my-1"></div>
                        
                        {/* OPCIÓN 3: CERRAR SESIÓN */}
                        <button
                          onClick={onLogout}
                          className="w-full px-3 py-3 mt-1 hover:bg-rose-50 text-slate-700 rounded-lg text-sm font-medium transition-all text-left flex items-center gap-3 hover:text-rose-700 group"
                        >
                          <div className="w-9 h-9 rounded-lg bg-rose-100 flex items-center justify-center text-rose-600 group-hover:bg-rose-200 transition-all flex-shrink-0">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm">Cerrar Sesión</p>
                            <p className="text-xs text-slate-400 mt-0.5">Salir del sistema</p>
                          </div>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="w-12 h-12 opacity-0 pointer-events-none" aria-hidden="true"></div>
            )}
          </div>
          
        </div>
      </div>
    </header>
  );
};