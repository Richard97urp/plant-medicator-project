// App.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { LoginForm } from './components/auth/LoginForm';
import { RegisterForm } from './components/auth/RegisterForm';
import { BrowserRouter as Router, Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom';

interface Message {
  id: string;
  message: string;
  isUser: boolean;
}

interface PatientInfo {
  symptoms?: string;
  duration?: string;
  allergies?: string;
}

interface FeedbackData {
  effectiveness: number;
  sideEffects: string;
  timeToImprovement: string;
  additionalComments: string;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const QUESTIONS = {
  SYMPTOMS: '¿Cuáles son tus síntomas principales?',
  DURATION: '¿Hace cuánto tiempo tienes estos síntomas?',
  ALLERGIES: '¿Tienes alguna alergia conocida? Si no tienes, escribe "ninguna"'
};

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState('SYMPTOMS');
  const [patientInfo, setPatientInfo] = useState<PatientInfo>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [awaitingPlantSelection, setAwaitingPlantSelection] = useState(false);
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedbackStep, setFeedbackStep] = useState(0);
  const [feedbackData, setFeedbackData] = useState<FeedbackData>({
    effectiveness: 0,
    sideEffects: '',
    timeToImprovement: '',
    additionalComments: ''
  });
  const [userDisplayName, setUserDisplayName] = useState('Usuario');

  const sessionIdRef = useRef<string>(uuidv4());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const resetConsultation = useCallback(() => {
    sessionIdRef.current = uuidv4();
    setMessages([{
      id: uuidv4(),
      message: QUESTIONS.SYMPTOMS,
      isUser: false
    }]);
    setCurrentQuestion('SYMPTOMS');
    setPatientInfo({});
    setAwaitingPlantSelection(false);
    setShowFeedbackForm(false);
    setInputValue('');
    setFeedbackStep(0);
    setFeedbackData({
      effectiveness: 0,
      sideEffects: '',
      timeToImprovement: '',
      additionalComments: ''
    });
  }, []);

  useEffect(() => {
    resetConsultation();
  }, [resetConsultation]);

  const validateAnswer = (question: string, answer: string): boolean => {
    const trimmedAnswer = answer.trim();
    
    switch (question) {
      case 'SYMPTOMS':
        return trimmedAnswer.length >= 3;
      case 'DURATION':
        return trimmedAnswer.length > 0;
      case 'ALLERGIES':
        return trimmedAnswer.length > 0;
      default:
        return false;
    }
  };

  const saveFeedback = async (feedbackData: FeedbackData) => {
    try {
      if (!feedbackData.effectiveness || !sessionIdRef.current) {
        throw new Error('Faltan datos requeridos para el feedback');
      }

      const response = await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          effectiveness_rating: parseInt(feedbackData.effectiveness.toString()),
          side_effects: feedbackData.sideEffects || '',
          improvement_time: feedbackData.timeToImprovement || '',
          additional_comments: feedbackData.additionalComments || ''
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al guardar la evaluación');
      }

      const data = await response.json();
      
      setFeedbackStep(4);
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: 'Gracias por tu evaluación. Ha sido guardada correctamente.',
        isUser: false
      }]);
      
      setTimeout(() => {
        resetConsultation();
      }, 5000);

    } catch (error: unknown) {
      console.error('Error saving feedback:', error);
      let errorMessage = 'Error al guardar la evaluación';
      
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (error && typeof error === 'object' && 'message' in error) {
        errorMessage = String(error.message);
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
      
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: `Error al guardar la evaluación: ${errorMessage}`,
        isUser: false
      }]);
    }
  };

  const requestMedication = async (selectedPlant?: string) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          message: "Error: Sesión no válida. Por favor, inicia sesión nuevamente.",
          isUser: false
        }]);
        setIsAuthenticated(false);
        return;
      }
  
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      if (!userInfo.username) {
        setMessages(prev => [...prev, {
          id: uuidv4(),
          message: "Error: No se encontró información del usuario. Por favor, inicia sesión nuevamente.",
          isUser: false
        }]);
        setIsAuthenticated(false);
        return;
      }
  
      const allergies = patientInfo.allergies || 'ninguna';
  
      const requestBody = {
        session_id: sessionIdRef.current,
        patient_info: {
          user_id: userInfo.username,
          symptoms: patientInfo.symptoms || '',
          duration: patientInfo.duration || '',
          allergies: allergies,
          session_id: sessionIdRef.current
        },
        selected_plant: selectedPlant || null
      };
  
      console.log('🔍 Debugging Info:');
      console.log('API_BASE_URL:', API_BASE_URL);
      console.log('Full URL:', `${API_BASE_URL}/rag/chat`);
      console.log('Request body:', requestBody);
      console.log('Token exists:', !!token);
      console.log('Token preview:', token?.substring(0, 20) + '...');
  
      // Agregar un timeout para detectar si el servidor no responde
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 segundos timeout
  
      const response = await fetch(`${API_BASE_URL}/rag/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });
  
      clearTimeout(timeoutId);
  
      console.log('Response status:', response.status);
      console.log('Response headers:', Object.fromEntries(response.headers.entries()));
  
      // Intentar obtener el cuerpo de la respuesta incluso si hay error
      let data: any;
      try {
        data = await response.json();
        console.log('Response data:', data);
      } catch (parseError) {
        console.error('Error parsing response JSON:', parseError);
        const textResponse = await response.text();
        console.log('Response as text:', textResponse);
        throw new Error(`Error del servidor: ${response.status} - ${textResponse}`);
      }
      
      if (!response.ok) {
        throw new Error(data.detail || data.error || `Error HTTP: ${response.status}`);
      }
  
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: data.answer,
        isUser: false
      }]);
  
      if (!selectedPlant) {
        setAwaitingPlantSelection(true);
      } else {
        setAwaitingPlantSelection(false);
        setShowFeedbackForm(true);
      }
  
    } catch (error: unknown) {
      console.error('❌ Error in requestMedication:', error);
      
      let errorMessage = 'Error desconocido';
      
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          errorMessage = 'Timeout: El servidor tardó demasiado en responder. Verifica que esté ejecutándose.';
        } else if (error instanceof TypeError && error.message.includes('fetch')) {
          errorMessage = 'Error de conexión: No se puede conectar al servidor. Verifica que esté ejecutándose en ' + API_BASE_URL;
        } else {
          errorMessage = error.message;
        }
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
      
      if (errorMessage.includes('401') || errorMessage.includes('autenticación')) {
        setIsAuthenticated(false);
        localStorage.removeItem('token');
        localStorage.removeItem('userInfo');
        errorMessage = 'Sesión expirada. Por favor, inicia sesión nuevamente.';
      }
      
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: `Error: ${errorMessage}`,
        isUser: false
      }]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFeedbackSubmit = (data: Partial<FeedbackData>) => {
    const updatedFeedbackData = {
      ...feedbackData,
      ...data
    };
    
    setFeedbackData(updatedFeedbackData);
  
    if (feedbackStep < 3) {
      setFeedbackStep(prev => prev + 1);
      setInputValue('');
    } else {
      saveFeedback(updatedFeedbackData as FeedbackData);
      setInputValue('');
    }
  };

  const processAnswer = async (answer: string) => {
    if (isProcessing) return;
    
    const normalizedAnswer = answer.trim();
    
    if (awaitingPlantSelection) {
      setIsProcessing(true);
      await requestMedication(normalizedAnswer);
      setIsProcessing(false);
      return;
    }
  
    if (!validateAnswer(currentQuestion, normalizedAnswer)) {
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: 'Por favor proporciona una respuesta válida.',
        isUser: false
      }]);
      return;
    }
  
    setIsProcessing(true);
  
    try {
      switch (currentQuestion) {
        case 'SYMPTOMS':
          setPatientInfo(prev => ({ ...prev, symptoms: normalizedAnswer }));
          setCurrentQuestion('DURATION');
          setMessages(prev => [...prev, {
            id: uuidv4(),
            message: QUESTIONS.DURATION,
            isUser: false
          }]);
          break;
        case 'DURATION':
          setPatientInfo(prev => ({ ...prev, duration: normalizedAnswer }));
          setCurrentQuestion('ALLERGIES');
          setMessages(prev => [...prev, {
            id: uuidv4(),
            message: QUESTIONS.ALLERGIES,
            isUser: false
          }]);
          break;
        case 'ALLERGIES':
          const normalizedAllergies = normalizedAnswer.toLowerCase();
          await new Promise<void>(resolve => {
            setPatientInfo(prev => {
              const updated = { 
                ...prev, 
                allergies: normalizedAllergies === '' ? 'ninguna' : normalizedAllergies 
              };
              resolve();
              return updated;
            });
          });
          
          await new Promise(resolve => setTimeout(resolve, 100));
          
          await requestMedication();
          break;
      }
    } catch (error) {
      console.error('Error processing answer:', error);
      setMessages(prev => [...prev, {
        id: uuidv4(),
        message: 'Ocurrió un error al procesar tu respuesta. Por favor, intenta nuevamente.',
        isUser: false
      }]);
    }
    
    setIsProcessing(false);
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isProcessing) return;

    const userMessage = {
      id: uuidv4(),
      message: inputValue,
      isUser: true
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    await processAnswer(userMessage.message.trim());
  };

  useEffect(() => {
    const checkAuth = () => {
        const token = localStorage.getItem('token');
        const userInfo = localStorage.getItem('userInfo');
        
        if (!token || !userInfo) {
            setIsAuthenticated(false);
            return;
        }
        
        try {
            const parsedUser = JSON.parse(userInfo);
            setUserDisplayName(parsedUser.fullName || parsedUser.username || 'Usuario');
            setIsAuthenticated(true);
            
            // Opcional: verificar token con el backend
            verifyToken(token);
        } catch (error) {
            console.error('Error parsing user info:', error);
            setIsAuthenticated(false);
        }
    };
  
    const verifyToken = async (token: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/health`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (!response.ok) {
                throw new Error('Token inválido');
            }
        } catch (error) {
            console.error('Error verifying token:', error);
            localStorage.removeItem('userInfo');
            localStorage.removeItem('token');
            setIsAuthenticated(false);
        }
    };
  
    checkAuth();
}, []);

  const handleLoginSuccess = (userData: any) => {
    setIsAuthenticated(true);
    setUserDisplayName(userData.fullName || userData.username || 'Usuario');
  };

  const handleLogout = () => {
    localStorage.removeItem('userInfo');
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setUserDisplayName('Usuario');
    resetConsultation();
  };

  const ChatComponent = () => {
    const inputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
  
    useEffect(() => {
      if (!showFeedbackForm && inputRef.current) {
        inputRef.current.focus();
      }
      if (showFeedbackForm && textareaRef.current && (feedbackStep === 1 || feedbackStep === 2 || feedbackStep === 3)) {
        textareaRef.current.focus();
        const length = inputValue.length;
        textareaRef.current.setSelectionRange(length, length);
      }
    }, [showFeedbackForm, feedbackStep]);
  
    const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      setInputValue(newValue);
      
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          const length = newValue.length;
          textareaRef.current.setSelectionRange(length, length);
        }
      });
    };

    const renderFeedbackStep = (step: number) => {
      switch (step) {
        case 1:
          return (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">¿Experimentó algún efecto secundario?</p>
              <div className="relative">
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={handleTextareaChange}
                  className="w-full p-2 border rounded focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="Describa cualquier efecto secundario observado"
                  rows={4}
                />
              </div>
              <button
                onClick={() => handleFeedbackSubmit({ sideEffects: inputValue })}
                className="mt-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Continuar
              </button>
            </div>
          );
        
        case 2:
          return (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">¿Cuánto tiempo tardó en notar mejoría?</p>
              <div className="relative">
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={handleTextareaChange}
                  className="w-full p-2 border rounded focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="Ejemplo: 2 días, 1 semana, etc."
                  rows={4}
                />
              </div>
              <button
                onClick={() => handleFeedbackSubmit({ timeToImprovement: inputValue })}
                className="mt-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Continuar
              </button>
            </div>
          );

        case 3:
          return (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Comentarios adicionales:</p>
              <div className="relative">
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={handleTextareaChange}
                  className="w-full p-2 border rounded focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="Comparta cualquier observación adicional sobre su experiencia"
                  rows={4}
                />
              </div>
              <button
                onClick={() => handleFeedbackSubmit({ additionalComments: inputValue })}
                className="mt-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Enviar Evaluación
              </button>
            </div>
          );
        
        default:
          return null;
      }
    };
    
    return (
      <div className="bg-white rounded-lg shadow-lg p-4 min-h-[500px] flex flex-col">
        {showFeedbackForm && (
          <div className="mb-4 bg-green-50 border-l-4 border-green-500 p-4 rounded-lg shadow-md">
            <h2 className="text-lg font-semibold text-green-800 mb-2">
              ¡Su opinión es importante!
            </h2>
            <p className="text-green-700">
              Nos gustaría conocer su experiencia con la planta medicinal recomendada. 
              Sus comentarios nos ayudarán a mejorar nuestras recomendaciones para futuros pacientes.
            </p>
          </div>
        )}
  
        <div className="flex-grow space-y-4 overflow-y-auto mb-4">
          {messages.map((msg) => (
            <div key={msg.id} 
              className={`p-3 rounded-lg max-w-[80%] ${
                msg.isUser ? 'bg-green-100 ml-auto' : 'bg-gray-100'
              }`}>
              {msg.message}
              </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
  
        {!showFeedbackForm ? (
          <div className="mt-auto">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => {
                  e.preventDefault();
                  setInputValue(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                disabled={isProcessing}
                className="flex-grow p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                placeholder={awaitingPlantSelection ? "Escribe el nombre de la planta que deseas..." : "Escribe tu respuesta..."}
              />
              <button
                onClick={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
                disabled={isProcessing}
                className={`px-4 py-2 rounded-lg text-white ${
                  isProcessing ? 'bg-gray-400' : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                Enviar
              </button>
            </div>
            <button
              onClick={(e) => {
                e.preventDefault();
                resetConsultation();
              }}
              className="w-full mt-4 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              Nueva Consulta
            </button>
          </div>
        ) : (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-green-200">
            <h3 className="font-semibold mb-2 text-green-800">Evaluación del Tratamiento</h3>
            
            {feedbackStep === 4 ? (
              <div className="p-4 bg-green-100 rounded-lg text-green-800">
                <p className="text-center font-medium">
                  Gracias por compartir su experiencia. Su evaluación ha sido registrada y contribuirá a mejorar nuestras recomendaciones de medicina natural.
                </p>
              </div>
            ) : (
              <>
                {feedbackStep === 0 && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600">Efectividad en el alivio de síntomas:</p>
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5].map((rating) => (
                        <button
                          key={rating}
                          onClick={() => handleFeedbackSubmit({ effectiveness: rating })}
                          className="p-2 rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
                        >
                          {rating}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                {feedbackStep > 0 && feedbackStep < 4 && renderFeedbackStep(feedbackStep)}
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  const ProtectedChat = () => {
    if (!isAuthenticated) {
      return <Navigate to="/login" replace />;
    }
  
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-green-600 text-white p-4 relative">
          <div className="flex justify-between items-center max-w-6xl mx-auto">
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-center">Sistema de Consulta Médica Natural</h1>
              <p className="text-green-100 text-center text-sm mt-1">
                Bienvenid@ {userDisplayName}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors whitespace-nowrap"
            >
              Cerrar Sesión
            </button>
          </div>
        </header>
        
        <main className="container mx-auto p-4 max-w-2xl">
          <ChatComponent />
        </main>
      </div>
    );
  };

  const RegisterComponent = () => {
    const navigate = useNavigate();
    
    const handleRegisterSuccess = () => {
      navigate('/login');
    };

    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-green-600 text-white p-4 text-center">
          <h1 className="text-2xl font-bold">Sistema de Consulta Médica Natural</h1>
        </header>
        <main className="container mx-auto p-4 max-w-2xl">
          <RegisterForm onRegisterSuccess={handleRegisterSuccess} />
          <p className="text-center mt-4">
            ¿Ya tienes una cuenta?{' '}
            <Link to="/login" className="text-green-600 hover:text-green-700">
              Inicia sesión
            </Link>
          </p>
        </main>
      </div>
    );
  };

  return (
    <Router>
      <Routes>
        <Route 
          path="/" 
          element={isAuthenticated ? <Navigate to="/chat" replace /> : <Navigate to="/login" replace />} 
        />

        <Route 
          path="/login" 
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <div className="min-h-screen bg-gray-50">
                <header className="bg-green-600 text-white p-4 text-center">
                  <h1 className="text-2xl font-bold">Sistema de Consulta Médica Natural</h1>
                </header>
                <main className="container mx-auto p-4 max-w-2xl">
                  <LoginForm onLoginSuccess={handleLoginSuccess} />
                  <p className="text-center mt-4">
                    ¿No tienes una cuenta?{' '}
                    <Link to="/register" className="text-green-600 hover:text-green-700">
                      Regístrate aquí
                    </Link>
                  </p>
                </main>
              </div>
            )
          } 
        />
        
        <Route 
          path="/register" 
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <RegisterComponent />
            )
          } 
        />

        <Route 
          path="/chat" 
          element={<ProtectedChat />} 
        />

        <Route 
          path="*" 
          element={<Navigate to="/" replace />} 
        />
      </Routes>
    </Router>
  );
};

export default App;
