import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import type { LoginCredentials } from '../../types/auth.types';

interface LoginFormProps {
    onLoginSuccess: (userData: { 
        username: string; 
        token: string; 
        fullName?: string 
    }) => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onLoginSuccess }) => {
    const [credentials, setCredentials] = useState<LoginCredentials>({
        identifier: '',
        password: ''
    });
    const [error, setError] = useState<string>('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    // Usar la misma configuración que RegisterForm
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://plant-medicator-project-n8n8.onrender.com';

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
    
        try {
            const apiUrl = `${API_BASE_URL}/api/login`;
            console.log('Enviando login a:', apiUrl);
    
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                body: JSON.stringify(credentials)
            });
    
            console.log('Response status:', response.status);
    
            if (!response.ok) {
                let errorMessage = 'Error al iniciar sesión';
                
                try {
                    const errorData = await response.json();
                    console.log('Error data:', errorData);
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch (parseError) {
                    console.log('Error parsing response:', parseError);
                    if (response.status === 401) {
                        errorMessage = 'Usuario o contraseña incorrectos';
                    } else if (response.status === 404) {
                        errorMessage = 'Endpoint no encontrado. Verifique la URL del API.';
                    } else if (response.status >= 500) {
                        errorMessage = 'Error del servidor. Intente nuevamente más tarde.';
                    } else {
                        errorMessage = `Error HTTP ${response.status}: ${response.statusText}`;
                    }
                }
                
                throw new Error(errorMessage);
            }
    
            const data = await response.json();
            console.log('Login exitoso:', data);
    
            if (!data.access_token) {
                throw new Error('No se recibió token de acceso');
            }
    
            // Guardar en localStorage
            localStorage.setItem('token', data.access_token);
            
            const userInfo = {
                username: data.username || credentials.identifier,
                fullName: data.full_name || '',
                token: data.access_token
            };
            
            localStorage.setItem('userInfo', JSON.stringify(userInfo));
            
            // Pasar los datos completos al padre
            onLoginSuccess({
                username: data.username || credentials.identifier,
                token: data.access_token,
                fullName: data.full_name || ''
            });
    
        } catch (error) {
            console.error('Error en login:', error);
            
            if (error instanceof Error) {
                if (error.message.includes('Failed to fetch')) {
                    setError('Error de conexión: No se puede conectar con el servidor. Verifique su conexión a internet.');
                } else if (error.message.includes('NetworkError')) {
                    setError('Error de red: Problema de conectividad. Intente nuevamente.');
                } else if (error.message.includes('CORS')) {
                    setError('Error de CORS: El servidor no permite solicitudes desde este dominio.');
                } else {
                    setError(error.message);
                }
            } else {
                setError('Error desconocido al iniciar sesión');
            }
            
            // Limpiar credenciales en caso de error
            localStorage.removeItem('token');
            localStorage.removeItem('userInfo');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <form onSubmit={handleLogin} className="max-w-md mx-auto p-6 bg-white rounded-lg shadow-md">
            <h2 className="text-2xl font-bold mb-6">Iniciar Sesión</h2>
            
            {error && (
                <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                    {error}
                </div>
            )}

            <div className="space-y-4">
                <div>
                    <label className="block text-sm font-medium mb-1">
                        Nombre de Usuario
                    </label>
                    <input
                        type="text"
                        className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                        value={credentials.identifier}
                        onChange={(e) => setCredentials({...credentials, identifier: e.target.value})}
                        disabled={isLoading}
                        required
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium mb-1">
                        Contraseña
                    </label>
                    <div className="relative">
                        <input
                            type={showPassword ? "text" : "password"}
                            className="w-full p-2 border rounded focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            value={credentials.password}
                            onChange={(e) => setCredentials({...credentials, password: e.target.value})}
                            disabled={isLoading}
                            required
                        />
                        <button
                            type="button"
                            className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
                            onClick={() => setShowPassword(!showPassword)}
                        >
                            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                        </button>
                    </div>
                </div>

                <button
                    type="submit"
                    className={`w-full bg-green-600 text-white p-2 rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 ${
                        isLoading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                    disabled={isLoading || !credentials.identifier || !credentials.password}
                >
                    {isLoading ? 'Ingresando...' : 'Ingresar'}
                </button>
            </div>
        </form>
    );
};
