import React, { useState, useEffect } from 'react';

// Configuración de URLs según el entorno - IGUAL que en AdminDashboard
const getApiUrl = () => {
  // Verificar si hay variable de entorno configurada
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // Si estamos en desarrollo (localhost)
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  
  // Si estamos en producción, usar la URL de tu backend en Render
  return 'https://plant-medicator-project-n8n8.onrender.com';
};

const API_BASE_URL = getApiUrl();

const RoleVerifier = () => {
    const [databaseRole, setDatabaseRole] = useState<string | null>(null);
    const [tokenRole, setTokenRole] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    useEffect(() => {
        const verifyRole = async () => {
            try {
                // Usar el mismo sistema de autenticación que AdminDashboard
                const token = localStorage.getItem('token');
                const userInfo = localStorage.getItem('userInfo');
                
                if (!token || !userInfo) {
                    setError('No hay información de autenticación');
                    setIsLoading(false);
                    return;
                }
                
                const userData = JSON.parse(userInfo);
                if (!userData.username) {
                    setError('Datos de usuario incompletos');
                    setIsLoading(false);
                    return;
                }
                
                // Guardar el rol del token si está disponible
                setTokenRole(userData.role || 'No disponible en token');
                
                // Verificar el rol en la base de datos usando la URL dinámica
                const response = await fetch(`${API_BASE_URL}/api/verify-user-role?username=${userData.username}`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`Error al verificar rol: ${response.status}`);
                }
                
                const data = await response.json();
                setDatabaseRole(data.role);
                
            } catch (err: any) {
                console.error('Error en RoleVerifier:', err);
                setError(`Error: ${err.message}`);
            } finally {
                setIsLoading(false);
            }
        };
        
        verifyRole();
    }, []);
    
    if (isLoading) return (
        <div className="p-3 bg-blue-50 rounded mb-4">
            <p>Verificando rol...</p>
            <p className="text-sm text-blue-600">Conectando a: {API_BASE_URL}</p>
        </div>
    );
    
    if (error) return (
        <div className="p-3 bg-red-50 text-red-700 rounded mb-4">
            <p className="font-semibold">Error en verificación de rol:</p>
            <p>{error}</p>
            <p className="text-sm mt-2">API URL: {API_BASE_URL}</p>
        </div>
    );
    
    const roleMatch = tokenRole?.toLowerCase() === databaseRole?.toLowerCase();
    
    return (
        <div className={`p-4 rounded mb-4 ${roleMatch ? 'bg-green-50' : 'bg-red-50'}`}>
            <h3 className="font-bold mb-2">Verificación de Rol</h3>
            <div className="space-y-2">
                <p><span className="font-medium">Rol en Token:</span> {tokenRole}</p>
                <p><span className="font-medium">Rol en Base de Datos:</span> {databaseRole}</p>
                <p className="text-sm text-gray-600">
                    <span className="font-medium">Entorno:</span> {window.location.hostname === 'localhost' ? 'Desarrollo' : 'Producción'}
                </p>
                <p className="text-sm text-gray-600">
                    <span className="font-medium">API URL:</span> {API_BASE_URL}
                </p>
                {!roleMatch && (
                    <p className="font-bold text-red-600">
                        ¡ALERTA! El rol en el token no coincide con el rol en la base de datos
                    </p>
                )}
                {roleMatch && (
                    <p className="font-bold text-green-600">
                        ✅ Verificación exitosa: Los roles coinciden
                    </p>
                )}
            </div>
        </div>
    );
};

export default RoleVerifier;
