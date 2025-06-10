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

            // Guardar el token y la información del usuario en localStorage
            if (data.access_token) {
                localStorage.setItem('token', data.access_token);
                
                // Crear y guardar un objeto userInfo estructurado
                const userInfo = {
                    username: data.username || credentials.identifier,
                    // Otros datos si están disponibles
                };
                
                localStorage.setItem('userInfo', JSON.stringify(userInfo));
                console.log('Usuario autenticado:', userInfo);
                
                // Pasar el nombre de usuario al manejar el éxito del inicio de sesión
                onLoginSuccess(userInfo.username);
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
                    disabled={isLoading}
                >
                    {isLoading ? 'Ingresando...' : 'Ingresar'}
                </button>
            </div>
        </form>
    );
};