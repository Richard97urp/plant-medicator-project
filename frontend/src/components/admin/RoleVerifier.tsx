import React, { useState, useEffect } from 'react';

const RoleVerifier = () => {
    const [databaseRole, setDatabaseRole] = useState<string | null>(null);
    const [tokenRole, setTokenRole] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    useEffect(() => {
        const verifyRole = async () => {
            try {
                const authStr = localStorage.getItem('auth');
                if (!authStr) {
                    setError('No hay información de autenticación');
                    setIsLoading(false);
                    return;
                }
                
                const authData = JSON.parse(authStr);
                if (!authData.user || !authData.user.username) {
                    setError('Datos de usuario incompletos');
                    setIsLoading(false);
                    return;
                }
                
                // Guardar el rol del token
                setTokenRole(authData.user.role || 'No disponible');
                
                // Verificar el rol en la base de datos
                const response = await fetch(`http://localhost:8000/api/verify-user-role?username=${authData.user.username}`, {
                    headers: {
                        'Authorization': `Bearer ${authData.token}`  // Usa authData.token en lugar de access_token
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`Error al verificar rol: ${response.status}`);
                }
                
                const data = await response.json();
                setDatabaseRole(data.role);
                
            } catch (err: any) {
                setError(`Error: ${err.message}`);
            } finally {
                setIsLoading(false);
            }
        };
        
        verifyRole();
    }, []);
    
    if (isLoading) return (
        <div className="p-3 bg-blue-50 rounded mb-4">Verificando rol...</div>
    );
    
    if (error) return (
        <div className="p-3 bg-red-50 text-red-700 rounded mb-4">{error}</div>
    );
    
    const roleMatch = tokenRole?.toLowerCase() === databaseRole?.toLowerCase();
    
    return (
        <div className={`p-4 rounded mb-4 ${roleMatch ? 'bg-green-50' : 'bg-red-50'}`}>
            <h3 className="font-bold mb-2">Verificación de Rol</h3>
            <div className="space-y-2">
                <p><span className="font-medium">Rol en Token:</span> {tokenRole}</p>
                <p><span className="font-medium">Rol en Base de Datos:</span> {databaseRole}</p>
                {!roleMatch && (
                    <p className="font-bold text-red-600">
                        ¡ALERTA! El rol en el token no coincide con el rol en la base de datos
                    </p>
                )}
            </div>
        </div>
    );
};

export default RoleVerifier;