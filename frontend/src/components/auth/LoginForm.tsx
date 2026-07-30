import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import type { LoginCredentials } from '../../types/auth.types';

interface LoginFormProps {
    onLoginSuccess: (username: string) => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onLoginSuccess }) => {
    const [credentials, setCredentials] = useState<LoginCredentials>({
        identifier: '',
        password: ''
    });
    const [error, setError] = useState<string>('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const response = await fetch('http://localhost:8000/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(credentials)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Error al iniciar sesión');
            }

            if (data.access_token) {
                const authData = {
                    token: data.access_token,
                    user: {
                        username: data.username || credentials.identifier,
                        role: data.role || "user"
                    }
                };

                localStorage.setItem('auth', JSON.stringify(authData));
                console.log('Usuario autenticado:', authData);

                onLoginSuccess(authData.user.username);
            }
        } catch (error) {
            setError(error instanceof Error ? 
                error.message : 
                'Usuario o contraseña incorrectos');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="max-w-md mx-auto">
            {/* 🔥 TARJETA COMPACTA */}
            <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-emerald-100/50 overflow-hidden">
                
                {/* Header compacto - SIN ÍCONO */}
                <div className="bg-gradient-to-r from-emerald-600 to-teal-700 p-6 text-center">
                    <h2 className="text-2xl font-bold text-white">Iniciar Sesión</h2>
                    <p className="text-emerald-100 text-sm mt-1">Accede a tu cuenta</p>
                </div>

                {/* Formulario compacto */}
                <form onSubmit={handleLogin} className="p-6">
                    
                    {/* Error message compacto */}
                    {error && (
                        <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 rounded-lg">
                            <div className="flex items-center gap-2">
                                <span className="text-rose-500 text-lg">⚠️</span>
                                <p className="text-rose-700 text-sm">{error}</p>
                            </div>
                        </div>
                    )}

                    <div className="space-y-4">
                        {/* Campo de usuario compacto */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                Nombre de Usuario
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg className="h-5 w-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                    </svg>
                                </div>
                                <input
                                    type="text"
                                    className="w-full pl-10 pr-4 py-2.5 border-2 border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all bg-white text-slate-700 placeholder-slate-400"
                                    placeholder="Tu usuario"
                                    value={credentials.identifier}
                                    onChange={(e) => setCredentials({...credentials, identifier: e.target.value})}
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        {/* Campo de contraseña compacto */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                                Contraseña
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg className="h-5 w-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                    </svg>
                                </div>
                                <input
                                    type={showPassword ? "text" : "password"}
                                    className="w-full pl-10 pr-12 py-2.5 border-2 border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all bg-white text-slate-700 placeholder-slate-400"
                                    placeholder="Tu contraseña"
                                    value={credentials.password}
                                    onChange={(e) => setCredentials({...credentials, password: e.target.value})}
                                    disabled={isLoading}
                                />
                                <button
                                    type="button"
                                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-emerald-600 transition-colors p-1"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                </button>
                            </div>
                        </div>

                        {/* Botón de login compacto */}
                        <button
                            type="submit"
                            className={`w-full bg-gradient-to-r from-emerald-600 to-teal-700 text-white font-bold py-3 rounded-lg hover:from-emerald-700 hover:to-teal-800 focus:outline-none focus:ring-4 focus:ring-emerald-300 transition-all shadow-lg hover:shadow-xl transform hover:scale-[1.02] mt-6 ${
                                isLoading ? 'opacity-50 cursor-not-allowed' : ''
                            }`}
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <div className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <span>Ingresando...</span>
                                </div>
                            ) : (
                                'Ingresar'
                            )}
                        </button>
                    </div>
                </form>

                {/* Footer compacto */}
                <div className="bg-slate-50 px-6 py-3 border-t border-slate-100">
                    <div className="flex items-center justify-center gap-2 text-sm">
                        <span className="text-slate-600">¿Eres nuevo?</span>
                        <a href="/register" className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline">
                            Crea una cuenta
                        </a>
                    </div>
                </div>
            </div>

            {/* Badge de seguridad compacto */}
            <div className="mt-4 text-center">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-white/10 backdrop-blur-md rounded-full border border-white/20">
                    <svg className="w-3.5 h-3.5 text-emerald-300" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                    </svg>
                    <span className="text-white/90 text-xs font-medium">Conexión segura</span>
                </div>
            </div>
        </div>
    );
};