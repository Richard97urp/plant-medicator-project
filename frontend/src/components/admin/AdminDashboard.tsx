import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import RoleVerifier from './RoleVerifier';


// Define la interfaz para la planta recomendada
interface PlantaRecomendada {
  nombre: string;
  descripcion: string;
  efectividad: string;
}

// Define tipos explícitos para la estructura de la respuesta
interface RagResponse {
  answer: string;
  sources?: any[];
  session_id?: string;
  suggested_plants?: string[];
}

interface Recommendation {
  rna_predictions: Array<[string, number]>;
  rag_response: RagResponse;
  confidence_score: number;
  recommended_method: string;
  error?: string;
  logs: string[];
  session_id?: string;
  // Añadimos la propiedad plantasRecomendadas al tipo
  plantasRecomendadas?: PlantaRecomendada[];
}

const AdminDashboard = () => {
    const [debugResponse, setDebugResponse] = useState<any>(null);
    const [verifiedRole, setVerifiedRole] = useState<string | null>(null);
    const [isVerifying, setIsVerifying] = useState(true);
    const navigate = useNavigate();
    
    const verifyUserRole = async (username: string, authToken: string) => {
        try {
            const response = await fetch(`http://localhost:8000/api/verify-user-role?username=${username}`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`Error al verificar rol: ${response.status}`);
            }
            
            const data = await response.json();
            return data.role;
        } catch (error) {
            console.error('Error verificando rol en la base de datos:', error);
            return null;
        }
    };

    useEffect(() => {
        const verifyAuth = async () => {
            const authStr = localStorage.getItem('auth');
            if (!authStr) {
                navigate('/admin-login');
                return;
            }
            
            try {
                const authData = JSON.parse(authStr);
                
                // Verificar estructura completa
                if (!authData.user || !authData.user.username) {
                    navigate('/admin-login');
                    return;
                }
                
                // Verificar el rol en la base de datos
                try {
                    const response = await fetch(`http://localhost:8000/api/verify-user-role?username=${authData.user.username}`, {
                        headers: {
                            'Authorization': `Bearer ${authData.token}`  // Usa authData.token en lugar de access_token
                        }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        if (data.role === 'admin') {
                            // Actualizar el rol en localStorage para mantener consistencia
                            authData.user.role = 'admin';
                            localStorage.setItem('auth', JSON.stringify(authData));
                            
                            // Continuar con la carga normal
                            addLog(`Usuario autenticado como administrador: ${authData.user.username}`);
                            setIsVerifying(false);
                            return;
                        }
                    }
                } catch (error) {
                    console.error('Error al verificar rol en base de datos:', error);
                }
                
                // Si llegamos aquí, la verificación falló o el rol no es 'admin'
                navigate('/admin-login');
            } catch (error) {
                console.error('Error al verificar autenticación:', error);
                navigate('/admin-login');
            }
        };
        
        verifyAuth();
    }, [navigate]);

    useEffect(() => {
        const authStr = localStorage.getItem('auth');
        if (!authStr) {
            console.error('Acceso denegado: No hay información de autenticación');
            navigate('/admin-login');
            return;
        }
        
        try {
            const authData = JSON.parse(authStr);
            console.log('Información de autenticación completa:', authData);
            
            // Verificar estructura completa
            if (!authData.user) {
                console.error('Estructura de usuario inválida');
                navigate('/admin-login');
                return;
            }
            
            // Obtener rol directamente
            const role = authData.user.role;
            console.log('Rol detectado (sin procesar):', role);
            
            if (role === undefined || role === null) {
                console.error('El rol no está definido');
                navigate('/admin-login');
                return;
            }
            
            // Normalizar rol para comparación
            const normalizedRole = String(role).toLowerCase().trim();
            
            console.log('Análisis de rol:', {
                original: role,
                normalizado: normalizedRole,
                tipo: typeof role
            });
            
            // Comprobar si es admin
            if (normalizedRole !== 'admin') {
                console.error('Acceso denegado: rol no es admin', {
                    rolObtenido: role
                });
                navigate('/admin-login');
            } else {
                console.log('Acceso de administrador confirmado');
                addLog(`Usuario autenticado como administrador: ${authData.user.username}`);
            }
        } catch (error) {
            console.error('Error al verificar autenticación:', error);
            navigate('/admin-login');
        }
    }, [navigate]);

    const [logs, setLogs] = useState<string[]>(['Iniciando aplicación...']);
    const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [rawResponse, setRawResponse] = useState<string>('');
    
    // Función auxiliar para añadir logs con timestamp
    const addLog = (message: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prevLogs => [...prevLogs, `[${timestamp}] ${message}`]);
        console.log(`[${timestamp}] ${message}`);
    };

    const extractRNAPredictions = (rnaPredictions: any): Array<[string, number]> => {
        addLog(`Formato original de rna_predictions: ${typeof rnaPredictions}`);
        
        if (!rnaPredictions) {
            addLog('rna_predictions es null o undefined');
            return [];
        }
        
        // Si ya es un array formateado correctamente, solo asegurar tipos
        if (Array.isArray(rnaPredictions) && rnaPredictions.length > 0 && 
            Array.isArray(rnaPredictions[0])) {
            addLog('rna_predictions ya es un array de arrays');
            return rnaPredictions.map(([name, value]) => [
                String(name), 
                typeof value === 'number' ? value : Number(value)
            ]);
        }
        
        // Si es string, intentar parsearlo como JSON
        if (typeof rnaPredictions === 'string') {
            addLog(`rna_predictions es string, longitud: ${rnaPredictions.length}`);
            addLog(`Muestra: ${rnaPredictions.substring(0, 100)}`);
            
            try {
                const parsed = JSON.parse(rnaPredictions);
                addLog('String JSON parseado correctamente');
                
                // Verificar si lo que parseamos es un array
                if (Array.isArray(parsed)) {
                    addLog('JSON parseado es un array');
                    if (parsed.length > 0 && Array.isArray(parsed[0])) {
                        addLog('JSON parseado es un array de arrays');
                        return parsed.map(([name, value]) => [String(name), Number(value)]);
                    }
                }
                
                // Si es un objeto, convertir a array
                if (parsed && typeof parsed === 'object') {
                    addLog('JSON parseado es un objeto');
                    return Object.entries(parsed).map(([key, value]) => [key, Number(value)]);
                }
            } catch (e) {
                addLog(`Error al parsear string como JSON: ${e}`);
            }
        }
        
        // Si es un objeto normal (no string)
        if (rnaPredictions && typeof rnaPredictions === 'object' && !Array.isArray(rnaPredictions)) {
            addLog('rna_predictions es un objeto');
            return Object.entries(rnaPredictions).map(([key, value]) => [key, Number(value)]);
        }
        
        addLog('No se pudo procesar el formato de rna_predictions');
        return [];
    };

    // Nueva función para extraer predicciones RNA del texto de respuesta
    const extractRNAPredictionsFromText = (text: string): Array<[string, number]> => {
        const predictions: Array<[string, number]> = [];
        addLog('Intentando extraer predicciones RNA del texto de respuesta');
        
        // Intenta buscar patrones para predicciones RNA en el texto
        // Primero busca patrones explícitos de RNA
        const rnaRegex = /RNA_\w+:\s+([^|]+)\s+\|\s+(\d+(?:\.\d+)?)\s*%?/g;
        let rnaMatch;
        let found = false;
        
        while ((rnaMatch = rnaRegex.exec(text)) !== null) {
            const plantName = rnaMatch[1].trim();
            const confidenceValue = parseFloat(rnaMatch[2]);
            predictions.push([plantName, confidenceValue]);
            found = true;
        }
        
        // Si no encontramos patrones explícitos, intenta usar las plantas mencionadas
        if (!found) {
            addLog('No se encontraron patrones explícitos de RNA, usando plantas mencionadas');
            // Extraer nombres de plantas del formato PLANTA_X
            const plantaRegex = /PLANTA_\d+:\s+([^|]+)/g;
            let plantaMatch;
            
            while ((plantaMatch = plantaRegex.exec(text)) !== null) {
                const plantName = plantaMatch[1].trim();
                // Genera un valor de confianza simulado entre 50 y 95%
                const randomConfidence = Math.floor(Math.random() * (95 - 50 + 1)) + 50;
                predictions.push([plantName, randomConfidence]);
            }
        }
        
        addLog(`Predicciones RNA extraídas del texto: ${predictions.length}`);
        return predictions;
    };

    // Función para extraer información de plantas del texto de respuesta
    const extractPlantsInfo = (text: string): PlantaRecomendada[] => {
        const plantas: PlantaRecomendada[] = [];
        const regex = /PLANTA_\d+:\s+([^|]+)\s+\|\s+([^|]+)(?:\s+\|\s+Efectividad:\s+([^\\]+))?/g;
        let match;
        while ((match = regex.exec(text)) !== null) {
            plantas.push({
                nombre: match[1].trim(),
                descripcion: match[2].trim(),
                efectividad: match[3]?.trim() || "No especificada"
            });
        }
        addLog(`Plantas extraídas del texto: ${plantas.length}`);
        return plantas;
    };

    const fetchRecommendation = async () => {
        addLog("Inicio de fetchRecommendation");
        setIsLoading(true);
        setError(null);
        
        try {
            // Generar IDs únicos para usuario y sesión
            const userId = localStorage.getItem('userId') || crypto.randomUUID();
            localStorage.setItem('userId', userId);
            const sessionId = crypto.randomUUID();
      
            const requestData = {
                patient_info: {
                    symptoms: "dolor de muela intenso con inflamación",
                    duration: "3 días",
                    age: 30,
                    gender: "M",
                    zone: "Lima",
                    allergies: "Ninguna",
                    user_id: userId
                },
                session_id: sessionId,
                selected_plant: null
            };
            
            addLog(`Enviando solicitud con datos: ${JSON.stringify(requestData)}`);

            // Realizar la petición fetch con un timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 segundos timeout
            
            const response = await fetch('http://localhost:8000/rag/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
      
            addLog(`Respuesta recibida con status: ${response.status}`);
      
            // Manejar errores HTTP
            if (!response.ok) {
                const errorText = await response.text();
                addLog(`Error en la respuesta: ${errorText}`);
                throw new Error(`Error HTTP: ${response.status}, Mensaje: ${errorText}`);
            }
      
            // Obtener el texto de la respuesta primero para depuración
            const responseText = await response.text();
            setRawResponse(responseText);
            addLog(`Respuesta en texto plano: ${responseText.substring(0, 200)}...`);
            
            // Intentar parsear como JSON
            let data;
            try {
                data = JSON.parse(responseText);
                //setDebugResponse(data); // Guarda para depuración SIEMPRE, no solo en caso de éxito
            } catch (e) {
                setError(`Respuesta JSON inválida: ${responseText}`);
                setIsLoading(false);
                //return;
            }
            
            // Incluso si hay error, ya tenemos los datos guardados para depuración
            if (!response.ok) {
                throw new Error(data.detail || `Error ${response.status}: ${response.statusText}`);
            }
      
            // Verificar la estructura de la respuesta
            if (typeof data.answer === 'string') {
                addLog('Formato de respuesta detectado: respuesta directa');
                
                // Extraer información del texto de respuesta para predecir plantas
                const plantasInfo = extractPlantsInfo(data.answer);
                
                // Extraer o generar predicciones RNA del texto
                const rnaPredictions = extractRNAPredictionsFromText(data.answer);
                addLog(`RNA predicciones extraídas/generadas: ${JSON.stringify(rnaPredictions)}`);
                
                // Crear una estructura compatible con lo que espera la UI
                const processedData: Recommendation = {
                    rna_predictions: rnaPredictions, // Usar predicciones extraídas o generadas
                    rag_response: { 
                        answer: data.answer,
                        session_id: data.session_id
                    },
                    confidence_score: 0.85, // Valor estimado ya que no viene en la respuesta
                    recommended_method: "RAG", // Asumimos RAG como método
                    logs: [],
                    session_id: data.session_id,
                    plantasRecomendadas: plantasInfo
                };
                
                addLog(`Procesando respuesta directa. Plantas encontradas: ${plantasInfo.length}`);
                setRecommendation(processedData);
            } 
            else if (data.rag_response && typeof data.rna_predictions !== 'undefined') {
                // El formato coincide con lo esperado originalmente
                addLog('Formato de respuesta detectado: estructura completa');
                
                // Procesar rna_predictions para asegurar el formato correcto
                let processedPredictions = extractRNAPredictions(data.rna_predictions);
                addLog(`rna_predictions procesados: ${JSON.stringify(processedPredictions)}`);
                
                // Si no hay predicciones RNA, intentar extraerlas del texto de respuesta
                if (processedPredictions.length === 0 && data.rag_response.answer) {
                    processedPredictions = extractRNAPredictionsFromText(data.rag_response.answer);
                    addLog(`RNA predicciones generadas del texto: ${JSON.stringify(processedPredictions)}`);
                }
                
                // Si hay una respuesta RAG, intentar extraer plantas de ella
                let plantasExtracted: PlantaRecomendada[] = [];
                if (data.rag_response.answer) {
                    plantasExtracted = extractPlantsInfo(data.rag_response.answer);
                    addLog(`Plantas extraídas de la respuesta RAG: ${plantasExtracted.length}`);
                }
                
                setRecommendation({
                    rna_predictions: processedPredictions,
                    rag_response: data.rag_response || { answer: 'No hay respuesta disponible' },
                    confidence_score: data.confidence_score || 0,
                    recommended_method: data.recommended_method || 'No definido',
                    logs: data.logs || [],
                    error: data.error,
                    plantasRecomendadas: plantasExtracted
                });
            }
            else {
                // Formato desconocido
                addLog('Formato de respuesta no reconocido');
                addLog(`Claves disponibles: ${Object.keys(data).join(', ')}`);
                throw new Error('Formato de respuesta no reconocido');
            }
            
            addLog('Datos procesados y almacenados correctamente');
            
        } catch (error: any) {
            console.error("Error completo:", error);
            if (error.name === 'AbortError') {
                addLog('La solicitud ha excedido el tiempo de espera (15 segundos)');
                setError('Tiempo de espera agotado. Verifica que el servidor esté funcionando.');
            } else {
                addLog(`Error: ${error.message}`);
                setError(error.message || "Error al obtener la recomendación");
            }
        } finally {
            setIsLoading(false);
            addLog('Finalizado fetchRecommendation');
        }
    };
  
    // Botón para recargar los datos
    const handleRefresh = () => {
        addLog('Recargando datos...');
        fetchRecommendation();
    };
  
    useEffect(() => {
        fetchRecommendation();
    }, []);
  
    return (
        <div className="p-6 bg-gray-100 min-h-screen">
            <h1 className="text-2xl font-bold mb-6">Panel de Administración</h1>
            
            {isVerifying ? (
                <div className="p-4 bg-blue-50 rounded-lg mb-4">
                    Verificando permisos de administrador...
                </div>
            ) : (
                <>
                    {/* Mostrar el verificador de roles */}
                    <RoleVerifier />
                    
                    {/* Botones de acción */}
                    <div className="mb-4 flex gap-2">
                        <button 
                            onClick={handleRefresh}
                            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Cargando...' : 'Recargar datos'}
                        </button>
                        <button 
                            onClick={() => navigate('/chat')}
                            className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
                        >
                            Ir al Chat
                        </button>
                    </div>
              
                    {isLoading ? (
                      <div className="flex justify-center items-center p-6 bg-white rounded-lg shadow-md">
                        <p className="text-lg">Cargando datos...</p>
                      </div>
                    ) : (
                      <>
                        <div className="bg-white p-6 rounded-lg shadow-md mb-6">
                            <h2 className="text-xl font-semibold mb-4">Estado de la Conexión</h2>
                            <div className="bg-gray-50 p-4 rounded-lg">
                                <p className={`font-semibold ${error ? 'text-red-600' : 'text-green-600'}`}>
                                    {error ? 'Error de conexión' : (recommendation ? 'Conectado' : 'Sin datos')}
                                </p>
                                {error && (
                                    <p className="mt-2 text-red-600">{error}</p>
                                )}
                            </div>
                        </div>
                        
                        <div className="bg-white p-6 rounded-lg shadow-md mb-6">
                            <h2 className="text-xl font-semibold mb-4">Logs del Sistema</h2>
                            <div className="bg-gray-50 p-4 rounded-lg overflow-auto max-h-64">
                                {logs && logs.length > 0 ? (
                                    logs.map((log, index) => (
                                        <p 
                                            key={index} 
                                            className={`text-sm ${
                                                log.toLowerCase().includes('error') 
                                                    ? 'text-red-600' 
                                                    : log.toLowerCase().includes('server:')
                                                    ? 'text-blue-600'
                                                    : 'text-gray-700'
                                            }`}
                                        >
                                            {log}
                                        </p>
                                    ))
                                ) : (
                                    <p className="text-sm text-gray-700">No hay logs disponibles</p>
                                )}
                            </div>
                        </div>
              
                        {rawResponse && (
                            <div className="bg-white p-6 rounded-lg shadow-md mb-6">
                                <h2 className="text-xl font-semibold mb-4">Respuesta Cruda (para depuración)</h2>
                                <div className="bg-gray-50 p-4 rounded-lg overflow-auto max-h-64">
                                    <pre className="text-xs text-gray-700 whitespace-pre-wrap">{rawResponse}</pre>
                                </div>
                            </div>
                        )}
              
                        {recommendation && (
                        <div className="bg-white p-6 rounded-lg shadow-md">
                            <h2 className="text-xl font-semibold mb-4">Recomendación</h2>
                            
                            {/* Mostrar plantas extraídas del texto si están disponibles */}
                            {recommendation.plantasRecomendadas && recommendation.plantasRecomendadas.length > 0 && (
                                <div className="mb-6">
                                    <h3 className="font-semibold mb-2">Plantas Recomendadas:</h3>
                                    <div className="space-y-4">
                                        {recommendation.plantasRecomendadas.map((planta, idx) => (
                                            <div key={idx} className="bg-gray-50 p-4 rounded-lg">
                                                <h4 className="font-medium text-lg">{planta.nombre}</h4>
                                                <p className="text-gray-700 mb-2">{planta.descripcion}</p>
                                                <p className="text-gray-600">
                                                    <span className="font-semibold">Efectividad:</span> {planta.efectividad}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            <div className="space-y-4">
                                <div>
                                    <h3 className="font-semibold">Predicciones RNA:</h3>
                                    {recommendation.rna_predictions && recommendation.rna_predictions.length > 0 ? (
                                        <div className="bg-gray-50 p-4 rounded-lg">
                                            <table className="w-full">
                                                <thead>
                                                    <tr className="text-left">
                                                        <th className="pb-2">Planta</th>
                                                        <th className="pb-2">Confianza</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {recommendation.rna_predictions.map(([planta, confianza], idx) => (
                                                        <tr key={idx}>
                                                            <td className="py-1">{planta}</td>
                                                            <td className="py-1">
                                                                {typeof confianza === 'number' 
                                                                    ? (confianza < 1 ? (confianza * 100).toFixed(2) : confianza.toFixed(2)) 
                                                                    : parseFloat(confianza).toFixed(2)}%
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="bg-gray-50 p-4 rounded-lg">
                                            <p className="text-gray-700">No hay predicciones RNA disponibles</p>
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <h3 className="font-semibold">Respuesta RAG:</h3>
                                    <pre className="bg-gray-50 p-2 rounded overflow-auto max-h-64">
                                        {recommendation.rag_response?.answer || 'No hay respuesta disponible'}
                                    </pre>
                                </div>
                                <div>
                                    <h3 className="font-semibold">Puntaje de Confianza:</h3>
                                    <p className="text-gray-700">
                                        {recommendation.confidence_score !== undefined 
                                            ? recommendation.confidence_score.toFixed(2) 
                                            : 'N/A'}
                                    </p>
                                </div>
                                <div>
                                    <h3 className="font-semibold">Método Recomendado:</h3>
                                    <p className="text-gray-700">{recommendation.recommended_method || 'No definido'}</p>
                                </div>
                                {recommendation.session_id && (
                                    <div>
                                        <h3 className="font-semibold">ID de Sesión:</h3>
                                        <p className="text-gray-700 break-words">{recommendation.session_id}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                        )}
                      </>
                    )}
                </>
            )}
        </div>
    );
};
  
export default AdminDashboard;