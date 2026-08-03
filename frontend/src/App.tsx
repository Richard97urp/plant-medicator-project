//OK
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { LoginForm } from './components/auth/LoginForm';
import { RegisterForm } from './components/auth/RegisterForm';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { EditProfilePage } from './components/auth/EditProfilePage'; 
import { Layout } from './components/layout/Layout';

interface Message {
  id: string;
  message: string;
  isUser: boolean;
  timestamp?: Date;
  isRecommendations?: boolean;
  recommendations?: any[];
  preMessage?: string;
  systemInfo?: {
    system?: string;
    precision?: number;
    sources?: string[];
  };
}

interface PatientInfo {
  symptoms?: string;
  duration?: string;
  allergies?: string;
  intensidad_sintomas?: string;
  causa_ambiental?: string;
  causa_emocional?: string;
  causa_dietetica?: string;
  recommended_plants?: string[];
  pending_plant_suggestion?: string | null;
  user_id?: string;
}

interface FeedbackData {
  effectiveness: number | string;
  sideEffects: string;
  timeToImprovement: string;
  additionalComments: string;
}

interface ConversationState {
  hasSymptoms: boolean;
  hasDuration: boolean;
  hasAllergies: boolean;
  hasIntensity: boolean;
  hasCausaAmbiental: boolean;
  hasCausaEmocional: boolean;
  hasCausaDietetica: boolean;
  isComplete: boolean;
  needsEmergencyCheck: boolean;
  hasReceivedRecommendations?: boolean;
}

export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── HELPERS PARA PLANT PREPARATION CARD ───────────────────────────────────

const SectionTitle = ({
  icon,
  label,
  color,
}: {
  icon: string;
  label: string;
  color: 'emerald' | 'sky' | 'amber';
}) => {
  const colorMap = {
    emerald: '#065f46',
    sky: '#0369a1',
    amber: '#92400e',
  };
  return (
    <p
      style={{
        fontFamily: 'var(--font-sans)',
        fontSize: '11px',
        fontWeight: 500,
        letterSpacing: '0.1em',
        textTransform: 'uppercase' as const,
        color: colorMap[color],
        margin: '0 0 10px',
      }}
    >
      {icon} {label}
    </p>
  );
};

const CardDivider = () => (
  <hr
    style={{
      border: 'none',
      borderTop: '0.5px solid var(--color-border-tertiary)',
      margin: '20px 0 0',
    }}
  />
);

const PosologiaPill = ({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string;
}) => (
  <div
    style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 'var(--border-radius-md)',
      padding: '12px 14px',
    }}
  >
    <p
      style={{
        fontFamily: 'var(--font-sans)',
        fontSize: '11px',
        color: 'var(--color-text-tertiary)',
        textTransform: 'uppercase' as const,
        letterSpacing: '0.08em',
        margin: '0 0 4px',
      }}
    >
      {icon} {label}
    </p>
    <p
      style={{
        fontFamily: 'var(--font-sans)',
        fontWeight: 500,
        fontSize: '13px',
        margin: 0,
        color: 'var(--color-text-primary)',
        lineHeight: 1.4,
      }}
    >
      {value}
    </p>
  </div>
);

// ─── BOT ICONS ──────────────────────────────────────────────────────────────

const BotIcon = ({ className = 'w-10 h-10' }: { className?: string }) => (
  <img
    src="/robot-planta.png"
    alt="Robot Planta"
    className={`object-contain ${className}`}
    onError={(e) => {
      const target = e.target as HTMLImageElement;
      target.style.display = 'none';
    }}
  />
);

const BotHeadIcon = ({ className = 'w-8 h-8' }: { className?: string }) => (
  <img src="/robot-head.png" alt="Robot Planta" className={`object-contain ${className}`} />
);

// ─── TOAST ──────────────────────────────────────────────────────────────────

const Toast = ({
  message,
  type = 'info',
  onClose,
}: {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose: () => void;
}) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const colors = { success: 'bg-emerald-500', error: 'bg-rose-500', info: 'bg-sky-500' };

  return (
    <div
      className={`fixed top-4 right-4 ${colors[type]} text-white px-6 py-4 rounded-xl shadow-2xl z-50 animate-slide-in-right max-w-md`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
        <p className="font-medium">{message}</p>
        <button onClick={onClose} className="ml-4 hover:opacity-70">
          <span className="text-xl">×</span>
        </button>
      </div>
    </div>
  );
};

// ─── EFFECTIVENESS CONVERTER ─────────────────────────────────────────────────

const convertEffectivenessToNumber = (effectiveness: string | number): number => {
  if (typeof effectiveness === 'number') return effectiveness;
  const ratingMap: Record<string, number> = {
    'Muy deficiente': 1,
    Deficiente: 2,
    Regular: 3,
    Bueno: 4,
    'Muy bueno': 5,
  };
  return ratingMap[effectiveness] || 3;
};

// ────────────────────────────────────────────────────────────────────────────
//  APP COMPONENT
// ────────────────────────────────────────────────────────────────────────────

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [patientInfo, setPatientInfo] = useState<PatientInfo>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [awaitingPlantSelection, setAwaitingPlantSelection] = useState(false);
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedbackStep, setFeedbackStep] = useState(0);
  const [conversationHistory, setConversationHistory] = useState<
    Array<{ role: string; content: string }>
  >([]);
  const [conversationState, setConversationState] = useState<ConversationState>({
    hasSymptoms: false,
    hasDuration: false,
    hasAllergies: false,
    hasIntensity: false,
    hasCausaAmbiental: false,
    hasCausaEmocional: false,
    hasCausaDietetica: false,
    isComplete: false,
    needsEmergencyCheck: false,
    hasReceivedRecommendations: false,
  });
  const [plantReports, setPlantReports] = useState<string[]>([]);
  const [feedbackData, setFeedbackData] = useState<FeedbackData>({
    effectiveness: 0,
    sideEffects: '',
    timeToImprovement: '',
    additionalComments: '',
  });
  const [toast, setToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info';
  } | null>(null);
  const [userProfile, setUserProfile] = useState<any>(null);

  const sessionIdRef = useRef<string>(uuidv4());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const welcomeToastShownRef = useRef<boolean>(false);
  const hasInitialized = useRef<boolean>(false);
  const recommendationTriggeredRef = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const getUserDisplayName = (context: 'header' | 'chat' = 'header'): string => {
    try {
      if (context === 'header') {
        const auth = localStorage.getItem('auth');
        if (auth) {
          const parsed = JSON.parse(auth);
          if (parsed.user?.username) return parsed.user.username;
        }
        if (userProfile?.username) return userProfile.username;
        return 'Usuario';
      }
      if (context === 'chat') {
        if (userProfile) {
          if (userProfile.full_name?.trim()) return userProfile.full_name;
          if (userProfile.name?.trim()) return userProfile.name;
          if (userProfile.first_name?.trim()) {
            return userProfile.last_name
              ? `${userProfile.first_name} ${userProfile.last_name}`
              : userProfile.first_name;
          }
        }
        const auth = localStorage.getItem('auth');
        if (auth) {
          const parsed = JSON.parse(auth);
          if (parsed.user?.full_name) return parsed.user.full_name;
          if (parsed.user?.name) return parsed.user.name;
          if (parsed.user?.first_name) {
            return parsed.user.last_name
              ? `${parsed.user.first_name} ${parsed.user.last_name}`
              : parsed.user.first_name;
          }
        }
        return 'Usuario';
      }
    } catch {
      /* ignore */
    }
    return 'Usuario';
  };

  const detectUserIntent = (userMessage: string) => {
    const lowerMsg = userMessage.toLowerCase();
    return {
      isQuestion:
        /^(puede|puedes|sabes|eres|tiene|tienes|hay|qué|cómo|dónde|cuándo|quién|por qué|para qué|acaso)\b/i.test(
          lowerMsg,
        ) ||
        /\?$/.test(userMessage) ||
        /no me puedes ayudar con|puedes ayudarme con/.test(lowerMsg),
      isAskingAboutScope:
        /(puede|puedes).*ayudar.*(con|cabeza|gripe|fiebre|otro)/i.test(lowerMsg) ||
        /solo.*sintomas digestivos|solamente digestivo|limitado|alcance|especializado/i.test(
          lowerMsg,
        ),
      isAskingAboutLimitations:
        /(limite|limitación|qué no|no puedes|no sirve|no ayuda)/i.test(lowerMsg),
      isConfirmingScope:
        /(así es|entonces|o sea|decís).*solo.*digestivo/i.test(lowerMsg) ||
        /solo.*(estómago|barriga|digestivo)/i.test(lowerMsg),
      isRudeOrConfused:
        /(feo|malo|aburrido|estúpido|tonto|no entiendo|confund)/i.test(lowerMsg),
    };
  };

  const processUserMessage = async (userMessage: string) => {
    const intent = detectUserIntent(userMessage);

    const askingAboutCapabilities = /qué puedes|que puedes|en qué me ayudas|para qué sirves|cómo me ayudas|qué haces|que haces|sobre qué/i.test(userMessage);

    if (askingAboutCapabilities && !conversationState.hasSymptoms) {
      const response = `Soy Fauno, herbolario especializado en plantas medicinales para el sistema digestivo. Puedo ayudarte con:

    - Dolor abdominal o estomacal
    - Náuseas y vómitos  
    - Acidez o reflujo gástrico
    - Gases e inflamación abdominal
    - Diarrea o estreñimiento
    - Indigestión o pesadez después de comer
    - Cólicos intestinales

    ¿Tienes alguno de estos síntomas?`;
      
      setMessages((prev) => [
        ...prev,
        { id: generateSessionId(), message: response, isUser: false, timestamp: new Date() },
      ]);
      return;
    }

    if (conversationState.hasSymptoms) {
      await processNaturalConversation(userMessage);
      return;
    }

    if (intent.isAskingAboutScope) {
      const bodyPartMatch = userMessage.match(
        /(cabeza|cuello|espalda|brazo|pierna|gripe|fiebre|tos|garganta)/i,
      );
      if (bodyPartMatch) {
        const bodyPart = bodyPartMatch[1].toLowerCase();
        let response = `😔 Por ahora solo puedo ayudarte con síntomas digestivos, no con ${bodyPart}. `;
        if (bodyPart === 'cabeza')
          response +=
            'Para dolores de cabeza, migrañas o mareos, te recomendaría consultar con un neurólogo o médico general.';
        else if (bodyPart === 'cuello')
          response +=
            'Para molestias en el cuello, sería mejor consultar con un ortopedista o fisioterapeuta.';
        else if (['gripe', 'fiebre', 'tos', 'garganta'].includes(bodyPart))
          response +=
            'Eso suena más como un síntoma respiratorio. Un médico general podría ayudarte mejor.';
        response += '\n\n¿Tienes algún síntoma digestivo con el que sí pueda ayudarte? 🤰';
        setMessages((prev) => [
          ...prev,
          { id: generateSessionId(), message: response, isUser: false, timestamp: new Date() },
        ]);
        return;
      }
    }

    if (intent.isConfirmingScope) {
      const response =
        `¡Así es! 😊 Soy especialista exclusivamente en **síntomas digestivos**.\n\n` +
        `Puedo ayudarte con:\n` +
        `• Dolor abdominal o estomacal 🤰\n• Náuseas y vómitos 🤢\n• Acidez o reflujo 🔥\n` +
        `• Gases o inflamación 💨\n• Diarrea o estreñimiento 🚽\n• Indigestión o pesadez 🍽️\n\n` +
        `¿Cuál de estos síntomas tienes?`;
      setMessages((prev) => [
        ...prev,
        { id: generateSessionId(), message: response, isUser: false, timestamp: new Date() },
      ]);
      return;
    }

    if (intent.isRudeOrConfused) {
      const empatheticResponses = [
        'Entiendo que pueda ser frustrante 😔. Mi especialidad es solo en síntomas digestivos.',
        'Lamento la confusión 🤗. Déjame explicarte mejor qué puedo hacer...',
        "Parece que hay un malentendido 😅. Soy como un 'gastroenterólogo virtual' especializado en plantas medicinales.",
      ];
      const response =
        `${empatheticResponses[Math.floor(Math.random() * empatheticResponses.length)]}\n\n` +
        `**Mi alcance es limitado pero profundo:**\n` +
        `✅ SÍ puedo: Recomendar plantas para problemas digestivos\n` +
        `❌ NO puedo: Diagnosticar otras enfermedades o dar consejos generales\n\n` +
        `¿Te ayudaría si te cuento sobre algún remedio natural para molestias digestivas?`;
      setMessages((prev) => [
        ...prev,
        { id: generateSessionId(), message: response, isUser: false, timestamp: new Date() },
      ]);
      return;
    }

    if (intent.isQuestion && !conversationState.hasSymptoms) {
      const questionResponses: Record<string, string> = {
        puede: 'Sí, puedo ayudarte... pero solo con síntomas digestivos 😊',
        puedes: '¡Claro que puedo! Siempre que sea sobre el sistema digestivo 🌿',
        sabes: 'Sé bastante sobre plantas medicinales para problemas digestivos',
        eres: 'Soy Fauno, tu asistente especializado en herbolaria para síntomas digestivos',
        qué: 'Puedo recomendarte plantas medicinales para molestias digestivas',
        cómo: 'Analizando tus síntomas y encontrando la planta más adecuada para ti',
      };
      const questionWord = Object.keys(questionResponses).find((word) =>
        userMessage.toLowerCase().includes(word),
      );
      if (questionWord) {
        const response =
          `${questionResponses[questionWord]}\n\nPara empezar, ¿qué síntoma digestivo tienes?`;
        setMessages((prev) => [
          ...prev,
          { id: generateSessionId(), message: response, isUser: false, timestamp: new Date() },
        ]);
        return;
      }
    }

    await processNaturalConversation(userMessage);
  };

  const isInActiveConsultation = (): boolean => {
    if (conversationState.hasSymptoms) return true;
    if (patientInfo.symptoms || patientInfo.duration || patientInfo.allergies) return true;
    const lastAssistantMessage =
      messages.filter((m) => !m.isUser).slice(-1)[0]?.message || '';
    return (
      lastAssistantMessage.includes('¿') &&
      (lastAssistantMessage.includes('síntomas') ||
        lastAssistantMessage.includes('cuánto tiempo') ||
        lastAssistantMessage.includes('intensidad') ||
        lastAssistantMessage.includes('frío') ||
        lastAssistantMessage.includes('calor') ||
        lastAssistantMessage.includes('estrés') ||
        lastAssistantMessage.includes('comida') ||
        lastAssistantMessage.includes('alergia'))
    );
  };

  useEffect(() => {
    console.log('🔄 Estado actualizado:', { conversationState, patientInfo });
  }, [conversationState, patientInfo]);

  useEffect(() => {
    const loadUserProfile = async () => {
      try {
        const auth = localStorage.getItem('auth');
        if (auth && isAuthenticated) {
          const parsed = JSON.parse(auth);
          const username = parsed.user?.username;
          if (username) {
            const response = await fetch(`${API_BASE_URL}/api/user/${username}`);
            if (response.ok) setUserProfile(await response.json());
          }
        }
      } catch {}
    };
    loadUserProfile();
  }, [isAuthenticated]);

  const generateSessionId = () =>
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });

  const showToast = useCallback(
    (message: string, type: 'success' | 'error' | 'info' = 'info') => {
      setToast((prev) => {
        if (prev?.message === message && prev?.type === type) return prev;
        return { message, type };
      });
    },
    [],
  );

  const resetConsultation = useCallback(
    async (showToastMessage = false) => {
      sessionIdRef.current = generateSessionId();
      try {
        const response = await fetch(`${API_BASE_URL}/chat/welcome`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        let welcomeMessage = response.ok
          ? (await response.json()).message
          : '¡Hola! Soy Fauno, tu asistente de salud natural. ¿Qué síntomas o molestias tienes hoy?';

        setMessages([
          { id: generateSessionId(), message: welcomeMessage, isUser: false, timestamp: new Date() },
        ]);
        setPatientInfo({});
        setAwaitingPlantSelection(false);
        setShowFeedbackForm(false);
        setInputValue('');
        setFeedbackStep(0);
        setConversationHistory([{ role: 'assistant', content: welcomeMessage }]);
        setConversationState({
          hasSymptoms: false, hasDuration: false, hasAllergies: false,
          hasIntensity: false, hasCausaAmbiental: false, hasCausaEmocional: false,
          hasCausaDietetica: false, isComplete: false, needsEmergencyCheck: false,
          hasReceivedRecommendations: false,
        });
        setFeedbackData({ effectiveness: 0, sideEffects: '', timeToImprovement: '', additionalComments: '' });
      } catch {
        const fallbackMessage =
          '¡Hola! Soy Fauno, tu asistente de salud natural. ¿Qué síntomas o molestias tienes hoy?';
        setMessages([
          { id: generateSessionId(), message: fallbackMessage, isUser: false, timestamp: new Date() },
        ]);
        setPatientInfo({});
        setAwaitingPlantSelection(false);
        setShowFeedbackForm(false);
        setInputValue('');
        setFeedbackStep(0);
        setConversationHistory([{ role: 'assistant', content: fallbackMessage }]);
        setConversationState({
          hasSymptoms: false, hasDuration: false, hasAllergies: false,
          hasIntensity: false, hasCausaAmbiental: false, hasCausaEmocional: false,
          hasCausaDietetica: false, isComplete: false, needsEmergencyCheck: false,
          hasReceivedRecommendations: false,
        });
        setFeedbackData({ effectiveness: 0, sideEffects: '', timeToImprovement: '', additionalComments: '' });
      }
    },
    [showToast],
  );

  useEffect(() => {
    if (isAuthenticated && !hasInitialized.current) {
      hasInitialized.current = true;
      resetConsultation();
    }
  }, [isAuthenticated, resetConsultation]);

  const handlePlantSelection = async (plantName: string) => {
    try {
      setIsProcessing(true);
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      let actualPlantName = plantName.trim();
      const plantNumberMap: Record<string, string> = {
        '1': patientInfo.recommended_plants?.[0] || '',
        '2': patientInfo.recommended_plants?.[1] || '',
        '3': patientInfo.recommended_plants?.[2] || '',
        uno: patientInfo.recommended_plants?.[0] || '',
        dos: patientInfo.recommended_plants?.[1] || '',
        tres: patientInfo.recommended_plants?.[2] || '',
      };
      const lowerInput = actualPlantName.toLowerCase();
      if (plantNumberMap[lowerInput]) actualPlantName = plantNumberMap[lowerInput];

      if (!actualPlantName || actualPlantName.length < 3) {
        setMessages((prev) => [
          ...prev,
          {
            id: generateSessionId(),
            message: 'Por favor selecciona una planta válida (escribe el nombre o el número: 1, 2, 3)',
            isUser: false,
            timestamp: new Date(),
          },
        ]);
        setIsProcessing(false);
        return;
      }

      const response = await fetch(`${API_BASE_URL}/rag/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          selected_plant: actualPlantName,
          patient_info: { ...patientInfo, user_id: userInfo.username || 'anonymous' },
        }),
      });

      if (!response.ok) throw new Error('Error en la respuesta del servidor');
      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        { id: generateSessionId(), message: data.answer, isUser: false, timestamp: new Date() },
      ]);
      fetchPlantReports(actualPlantName);
      setConversationHistory((prev) => [
        ...prev,
        { role: 'user', content: actualPlantName },
        { role: 'assistant', content: data.answer },
      ]);

      if (data.requires_selection || data.result_type === 'invalid_selection') {
        setAwaitingPlantSelection(true);
        setShowFeedbackForm(false);
        showToast('Por favor selecciona una planta válida', 'info');
      } else if (
        data.preparation_method === 'RAG_GROQ' ||
        data.preparation_method === 'HYBRID_SYSTEM' ||
        data.phase === 'DETAILED_PREPARATION'
      ) {
        setAwaitingPlantSelection(false);
        setShowFeedbackForm(true);
        showToast('Preparación recibida. Por favor evalúa el tratamiento', 'success');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Error desconocido';
      setMessages((prev) => [
        ...prev,
        {
          id: generateSessionId(),
          message: `Error al procesar la selección: ${errorMessage}`,
          isUser: false,
          timestamp: new Date(),
        },
      ]);
      showToast(`Error: ${errorMessage}`, 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const processNaturalConversation = async (userMessage: string) => {
    try {
      const updatedHistory = [...conversationHistory, { role: 'user', content: userMessage }];

      const response = await fetch(`${API_BASE_URL}/chat/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: userMessage,
          conversation_history: updatedHistory,
          current_state: conversationState,
          patient_info: patientInfo,
        }),
      });

      if (!response.ok) throw new Error('Error al procesar el mensaje');
      const data = await response.json();

      const isAllergyResponse =
        conversationHistory.slice(-1)[0]?.content?.includes('alergia') ||
        conversationHistory.slice(-1)[0]?.content?.includes('alergias') ||
        (userMessage.toLowerCase().includes('no') && conversationState.hasCausaDietetica);

      if (isAllergyResponse) {
        const immediatePatientInfo = {
          ...patientInfo,
          allergies: userMessage.toLowerCase().includes('no') ? 'ninguna' : userMessage,
        };
        setPatientInfo(immediatePatientInfo);
        setConversationState((prev) => ({
          ...prev,
          hasAllergies: true,
          isComplete:
            prev.hasSymptoms &&
            prev.hasDuration &&
            prev.hasIntensity &&
            prev.hasCausaAmbiental &&
            prev.hasCausaEmocional &&
            prev.hasCausaDietetica,
        }));
      }

      let updatedPatientInfo = { ...patientInfo };
      if (data.extracted_info) {
        if (data.extracted_info.allergies !== undefined)
          updatedPatientInfo.allergies = data.extracted_info.allergies;
        updatedPatientInfo = { ...updatedPatientInfo, ...data.extracted_info };
      }
      if (data.patient_info) updatedPatientInfo = { ...updatedPatientInfo, ...data.patient_info };
      setPatientInfo(updatedPatientInfo);

      let newState = { ...data.conversation_state };
      if (data.extracted_info?.allergies !== undefined || updatedPatientInfo.allergies)
        newState.hasAllergies = true;
      setConversationState(newState);

      const hasRecommendationsInData = data.has_recommendations && data.recommendations;

      if (hasRecommendationsInData) {
        setTimeout(() => {
          const recommendationsMessage = {
            id: generateSessionId(),
            message: data.assistant_response || '',  // ← usa el mensaje del agente
            isUser: false,
            timestamp: new Date(),
            isRecommendations: true,
            recommendations: data.recommendations.final_recommendations || [],
            systemInfo: {
              system: data.recommendations.selected_system || data.recommendations.system,
              precision:
                data.recommendations.intelligent_precision || data.recommendations.precision,
              sources: data.recommendations.sources || ['RNA', 'RAG'],
            },
          };
          setMessages((prev) => [...prev, recommendationsMessage]);

          const plantNames = Array.isArray(data.recommendations.final_recommendations)
            ? data.recommendations.final_recommendations.map((p: any) => p.name || p)
            : Array.isArray(data.recommendations.plants)
            ? data.recommendations.plants
            : data.recommendations;

          setPatientInfo((prev) => ({ ...prev, recommended_plants: plantNames }));
          setConversationState((prev) => ({
            ...prev,
            hasReceivedRecommendations: true,
            hasAllergies: true,
            isComplete: true,
          }));
          setAwaitingPlantSelection(true);
          showToast('Recomendaciones generadas. Selecciona una planta', 'success');
          setConversationHistory([
            ...updatedHistory,
            { role: 'assistant', content: 'He generado recomendaciones de plantas para ti.' },
          ]);
        }, 800);
      } else {
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              id: generateSessionId(),
              message: data.assistant_response,
              isUser: false,
              timestamp: new Date(),
            },
          ]);
          setConversationHistory([
            ...updatedHistory,
            { role: 'assistant', content: data.assistant_response },
          ]);
        }, 100);
      }

      if (data.is_emergency) {
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              id: generateSessionId(),
              message:
                '⚠️ IMPORTANTE: He detectado síntomas que podrían requerir atención médica urgente.',
              isUser: false,
              timestamp: new Date(),
            },
          ]);
          showToast('⚠️ Se requiere atención médica urgente', 'error');
        }, 1000);
      }
    } catch {
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: generateSessionId(),
            message: 'Lo siento, hubo un error al procesar tu mensaje. ¿Podrías intentar nuevamente?',
            isUser: false,
            timestamp: new Date(),
          },
        ]);
      }, 100);
      showToast('Error al procesar el mensaje', 'error');
    }
  };

  const generateRecommendations = async (
    info: PatientInfo,
    state: ConversationState,
  ) => {
    try {
      if (!state.hasAllergies || state.hasReceivedRecommendations || recommendationTriggeredRef.current)
        return;
      if (!info.allergies && info.allergies !== 'ninguna') return;
      recommendationTriggeredRef.current = true;

      const response = await fetch(`${API_BASE_URL}/hybrid_recommender`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          patient_info: { ...info, session_id: sessionIdRef.current },
          conversation_state: state,
        }),
      });

      if (!response.ok) throw new Error('Error al generar recomendaciones');
      const data = await response.json();

      if (data.recommendations?.final_recommendations) {
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              id: generateSessionId(),
              message: '',
              isUser: false,
              timestamp: new Date(),
              isRecommendations: true,
              recommendations: data.recommendations.final_recommendations,
              systemInfo: {
                system: data.recommendations.selected_system,
                precision: data.recommendations.intelligent_precision,
                sources: ['RNA', 'RAG'],
              },
            },
          ]);
          const plantNames = data.recommendations.final_recommendations.map((p: any) => p.name);
          setPatientInfo((prev) => ({ ...prev, recommended_plants: plantNames }));
          setConversationState((prev) => ({
            ...prev,
            hasReceivedRecommendations: true,
            isComplete: true,
          }));
          setAwaitingPlantSelection(true);
          showToast('Recomendaciones generadas. Selecciona una planta', 'success');
        }, 500);
      } else {
        throw new Error('No se generaron recomendaciones');
      }
    } catch {
      recommendationTriggeredRef.current = false;
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: generateSessionId(),
            message: 'Lo siento, hubo un error al generar las recomendaciones.',
            isUser: false,
            timestamp: new Date(),
          },
        ]);
      }, 100);
      showToast('Error generando recomendaciones', 'error');
    }
  };

  const checkIfReadyForRecommendations = (
    state: ConversationState,
    info: PatientInfo,
  ): boolean => {
    const allStatesTrue =
      state.hasSymptoms &&
      state.hasDuration &&
      state.hasIntensity &&
      state.hasCausaAmbiental &&
      state.hasCausaEmocional &&
      state.hasCausaDietetica &&
      state.hasAllergies;
    const hasAllergiesValue = info.allergies !== undefined && info.allergies !== '';
    return allStatesTrue && hasAllergiesValue && !state.hasReceivedRecommendations;
  };

  useEffect(() => {
    const isReady = checkIfReadyForRecommendations(conversationState, patientInfo);
    const shouldGenerate =
      isReady && !conversationState.hasReceivedRecommendations && !recommendationTriggeredRef.current;
    if (shouldGenerate) {
      recommendationTriggeredRef.current = true;
      setTimeout(() => generateRecommendations(patientInfo, conversationState), 1000);
    }
    if (!isReady) recommendationTriggeredRef.current = false;
  }, [conversationState, patientInfo]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isProcessing) return;
    const userMessage = inputValue.trim();
    setMessages((prev) => [
      ...prev,
      { id: generateSessionId(), message: userMessage, isUser: true, timestamp: new Date() },
    ]);
    setInputValue('');
    setIsProcessing(true);

    try {
      if (conversationState.hasReceivedRecommendations) {
        const normalizedMsg = userMessage.toLowerCase().trim();
        const recommendedPlants = (patientInfo.recommended_plants || []).map((p: string) =>
          p.toLowerCase().trim(),
        );
        const isPlantSel =
          /^(1|2|3|uno|dos|tres)$/i.test(normalizedMsg) ||
          recommendedPlants.some(
            (p) => normalizedMsg === p || normalizedMsg.includes(p) || p.includes(normalizedMsg),
          );
        if (isPlantSel) {
          await handlePlantSelection(userMessage);
        } else if (awaitingPlantSelection) {
        const plants = patientInfo.recommended_plants || [];
        const lowerMsg = userMessage.toLowerCase();
        
        // Detectar si es pregunta/confusión sobre las plantas
        const isQuestion = /cual|cuál|qué|que|cómo|como|puedo|debo|mejor|recomiend|elegir|escoger|\?/.test(lowerMsg);
        
        if (isQuestion) {
          // Respuesta empática explicando las opciones
          const plantListFormatted = plants
            .map((p: string, i: number) => `**${i + 1}. ${p}**`)
            .join(', ');
          setMessages((prev) => [
            ...prev,
            {
              id: generateSessionId(),
              message: `Todas son buenas opciones para tus síntomas. ${plantListFormatted}. Si no conoces alguna, puedes elegir por el número — escribe 1, 2 o 3 y te explico cómo prepararla.`,
              isUser: false,
              timestamp: new Date(),
            },
          ]);
        } else {
          // Selección no reconocida — tono amable
          const plantListFormatted = plants
            .map((p: string, i: number) => `${i + 1}. ${p}`)
            .join(' · ');
          setMessages((prev) => [
            ...prev,
            {
              id: generateSessionId(),
              message: `No encontré esa planta entre las recomendadas. Las opciones son: ${plantListFormatted}. Puedes escribir el nombre completo o simplemente el número (1, 2 o 3).`,
              isUser: false,
              timestamp: new Date(),
            },
          ]);
        }
      } else {
          await processUserMessage(userMessage);
        }
      } else {
        await processUserMessage(userMessage);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: generateSessionId(),
          message: 'Lo siento, hubo un error. Por favor, intenta nuevamente.',
          isUser: false,
          timestamp: new Date(),
        },
      ]);
      showToast('Error al enviar mensaje', 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  const saveFeedback = async (fd: FeedbackData) => {
    try {
      if (!fd.effectiveness || !sessionIdRef.current) throw new Error('Faltan datos requeridos');
      const response = await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          effectiveness_rating: convertEffectivenessToNumber(fd.effectiveness),
          side_effects: fd.sideEffects || '',
          improvement_time: fd.timeToImprovement || '',
          additional_comments: fd.additionalComments || '',
          plant_name:
            patientInfo.pending_plant_suggestion || patientInfo.recommended_plants?.[0] || '',
        }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al guardar la evaluación');
      }
      setFeedbackStep(4);
      
      setTimeout(() => resetConsultation(), 5000);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Error al guardar la evaluación';
      setMessages((prev) => [
        ...prev,
        {
          id: generateSessionId(),
          message: `Error al guardar la evaluación: ${errorMessage}`,
          isUser: false,
          timestamp: new Date(),
        },
      ]);
      showToast(`Error: ${errorMessage}`, 'error');
    }
  };

  const handleFeedbackSubmit = (data: Partial<FeedbackData>) => {
    const updated = { ...feedbackData, ...data };
    setFeedbackData(updated);
    if (feedbackStep < 3) {
      setFeedbackStep((prev) => prev + 1);
      setInputValue('');
    } else {
      saveFeedback(updated as FeedbackData);
      setInputValue('');
    }
  };

  useEffect(() => {
    if (messages.length < 2) return;
    const last = messages[messages.length - 1];
    const secondLast = messages[messages.length - 2];
    if (
      last.isUser &&
      !secondLast.isUser &&
      (secondLast.message.includes('alergia') || secondLast.message.includes('alergias')) &&
      last.message.trim().length > 0
    ) {
      const userResponse = last.message.toLowerCase();
      const hasAllergies = !(
        userResponse.includes('no') ||
        userResponse.includes('ninguna') ||
        userResponse.includes('nada')
      );
      setConversationState((prev) => ({
        ...prev,
        hasAllergies: true,
        isComplete:
          prev.hasSymptoms &&
          prev.hasDuration &&
          prev.hasIntensity &&
          prev.hasCausaAmbiental &&
          prev.hasCausaEmocional &&
          prev.hasCausaDietetica,
      }));
      setPatientInfo((prev) => ({
        ...prev,
        allergies: hasAllergies ? userResponse : 'ninguna',
      }));
    }
  }, [messages]);

  useEffect(() => {
    const checkAuth = async () => {
      const auth = localStorage.getItem('auth');
      if (!auth) { setIsAuthenticated(false); return; }
      try {
        const parsed = JSON.parse(auth);
        const token = parsed.token;
        const username = parsed.user?.username;
        if (!token || !username) {
          localStorage.removeItem('auth');
          setIsAuthenticated(false);
          return;
        }
        try {
          const response = await fetch(`${API_BASE_URL}/api/validate-token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          });
          if (!response.ok) {
            localStorage.removeItem('auth');
            setIsAuthenticated(false);
            return;
          }
          setIsAuthenticated(true);
          try {
            const profileResponse = await fetch(`${API_BASE_URL}/api/user/${username}`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (profileResponse.ok) setUserProfile(await profileResponse.json());
          } catch {}
        } catch {
          localStorage.removeItem('auth');
          setIsAuthenticated(false);
        }
      } catch {
        localStorage.removeItem('auth');
        setIsAuthenticated(false);
      }
    };
    checkAuth();
  }, []);

  const handleLoginSuccess = async (userData?: any) => {
    setIsAuthenticated(true);
    if (userData?.username) {
      try {
        const auth = localStorage.getItem('auth');
        if (auth) {
          const parsed = JSON.parse(auth);
          const token = parsed.token;
          setTimeout(async () => {
            try {
              const response = await fetch(`${API_BASE_URL}/api/user/${userData.username}`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (response.ok) setUserProfile(await response.json());
            } catch {}
          }, 1000);
        }
      } catch {}
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('userInfo');
    localStorage.removeItem('token');
    localStorage.removeItem('auth');
    localStorage.removeItem('userProfile');
    setIsAuthenticated(false);
    setUserProfile(null);
    welcomeToastShownRef.current = false;
    hasInitialized.current = false;
    resetConsultation();
  };

  // ─── PARSEPLANTPREPARATION ─────────────────────────────────────────────────

  const parsePlantPreparation = (text: string) => {
    const sections: any = {};

    let nameMatch =
      text.match(/Planta:\s*\*\*([^*]+)\*\*/i) ||
      text.match(/Planta:\s*([A-ZÁÉÍÓÚÑ][^\n]+)/i) ||
      text.match(/🌿\s*\*\*\s*([A-ZÁÉÍÓÚÑ\s]+?)\s*-/i);
    if (nameMatch?.[1]) {
      sections.plantName = nameMatch[1].replace(/\*\*/g, '').trim();
    } else {
      const titleMatch = text.match(/🌿\s*\*\*\s*([^-]+?)\s*-/i);
      if (titleMatch?.[1]) sections.plantName = titleMatch[1].replace(/\*\*/g, '').trim();
    }

    const sciMatch =
      text.match(/\(([A-Z][a-z]+(?:\s+[a-z]+)+(?:\s+[A-Z][a-z.]+)?)\)/) ||
      text.match(/Scientific[^:]*:\s*([^\n]+)/i) ||
      text.match(/Nombre científico[^:]*:\s*([^\n]+)/i);
    if (sciMatch?.[1]) sections.scientificName = sciMatch[1].trim();

    const propsSectionMatch = text.match(
      /Propiedades Terapéuticas:[^\n]*([\s\S]*?)(?=\n\s*\n|\nParte Utilizada:|\n[A-Z][a-z]+:|$)/i,
    );
    if (propsSectionMatch?.[1]) {
      const validProps = propsSectionMatch[1]
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line && !line.toLowerCase().includes('parte utilizada:'))
        .map((line) => line.replace(/^[•\-\*]\s*/, '').trim())
        .filter((prop) => prop.length > 2 && !prop.toLowerCase().includes('propiedad'));
      if (validProps.length > 0) sections.properties = validProps.slice(0, 6);
    }

    const parteMatch =
      text.match(/(?<=Propiedades Terapéuticas:[^\n]*[\s\S]*?)\nParte Utilizada:\s*([^\n]+)/i) ||
      text.match(/Parte Utilizada:\s*([^\n]+)/i);
    if (parteMatch?.[1]) {
      const parte = parteMatch[1].replace(/\*\*/g, '').trim();
      if (parte?.length > 1) sections.parte = parte;
    }

    const dosisMatch =
      text.match(/Cantidad\/Dosis:\s*([^\n]+)/i) || text.match(/Dosis:\s*([^\n]+)/i);
    if (dosisMatch?.[1]) {
      const cantidad = dosisMatch[1].replace(/\*\*/g, '').trim();
      if (cantidad?.length > 1 && cantidad !== 'a') sections.cantidad = cantidad;
    }

    const prepMatch = text.match(
      /Preparación:[^\n]*([\s\S]*?)(?=\n\s*\n|\nFrecuencia:|$)/i,
    );
    if (prepMatch?.[1]) {
      const steps: string[] = [];
      const stepRegex = /\d+\.\s*([^\n]+)/g;
      let stepMatch;
      while ((stepMatch = stepRegex.exec(prepMatch[1])) !== null) {
        const step = stepMatch[1].trim();
        if (step?.length > 5) steps.push(step);
      }
      if (steps.length === 0) {
        steps.push(
          ...prepMatch[1]
            .split('\n')
            .map((l) => l.trim())
            .filter((l) => l?.length > 5)
            .slice(0, 4),
        );
      }
      if (steps.length > 0) sections.preparation = steps;
    }

    const freqMatch = text.match(/Frecuencia:\s*([^\n]+)/i);
    if (freqMatch?.[1]) {
      const frequency = freqMatch[1].replace(/\*\*/g, '').trim();
      if (frequency?.length > 1 && frequency !== 'a') sections.frequency = frequency;
    }

    const durationMatch =
      text.match(/Duración del Tratamiento:\s*([^\n]+)/i) ||
      text.match(/Duración:\s*([^\n]+)/i);
    if (durationMatch?.[1]) {
      const duration = durationMatch[1].replace(/\*\*/g, '').trim();
      if (duration?.length > 1 && duration !== 's') sections.duration = duration;
    }

    const contraMatch = text.match(
      /Contraindicaciones:[^\n]*([\s\S]*?)(?=\n\s*\n|\nAdvertencias:|\n[A-Z]|$)/i,
    );
    if (contraMatch?.[1]) {
      const contra = contraMatch[1]
        .split('\n')
        .map((c) => c.replace(/[•\-*]\s*/, '').trim())
        .filter((c) => c.length > 5);
      if (contra.length > 0) sections.contraindications = contra.slice(0, 4);
    }

    const warningMatch = text.match(
      /Advertencias:[^\n]*([\s\S]*?)(?=\n\s*\n|\n[A-Z]|$)/i,
    );
    if (warningMatch?.[1]) {
      const warnings = warningMatch[1]
        .split('\n')
        .map((w) => w.replace(/[•\-*]\s*/, '').trim())
        .filter((w) => w.length > 5);
      if (warnings.length > 0) sections.warnings = warnings.slice(0, 3);
    }

    if (!sections.parte) sections.parte = 'Hojas';

    if (sections.properties) {
      const uniqueProps: string[] = [];
      for (const prop of sections.properties) {
        if (prop && !prop.toLowerCase().includes('parte utilizada:') && !uniqueProps.includes(prop))
          uniqueProps.push(prop);
      }
      sections.properties = uniqueProps;
    }

    return sections;
  };

  // ─── RENDER RECOMMENDATIONS CARD ──────────────────────────────────────────

  const renderRecommendationsCard = (
    recommendations: any[],
    systemInfo?: { system?: string; precision?: number; sources?: string[] },
    message?: string, 
  ) => (
    <div className="flex justify-start mb-3">
      <div className="max-w-[98%] bg-gradient-to-br from-sky-50 to-blue-50 border border-sky-200 rounded-xl p-3 shadow-sm">
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-full bg-white flex-shrink-0 shadow-sm flex items-center justify-center overflow-hidden">
            <BotHeadIcon className="w-full h-full" />
          </div>
          <div className="flex-1">
            <div className="text-xs font-medium mb-1 text-emerald-600">Fauno</div>
            
              <div className="text-sm text-slate-700 mb-3 leading-relaxed">
                {message || "Basándome en tus síntomas, te recomiendo estas plantas medicinales:"}
              </div>
            
            {systemInfo && (
              <div className="mb-3 p-2 bg-white border border-emerald-100 rounded-lg">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-emerald-700 font-medium">
                    Sistema: {systemInfo.system || 'Híbrido'}
                  </span>
                  <span className="bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
                    Precisión:{' '}
                    {systemInfo.precision ? `${(systemInfo.precision * 100).toFixed(1)}%` : 'Alta'}
                  </span>
                </div>
              </div>
            )}
            <div className="flex flex-row gap-3 mb-3 overflow-x-auto pb-2">
              {recommendations.map((plant, index) => (
                <div
                  key={index}
                  className="flex-shrink-0 w-48 bg-white border border-slate-200 rounded-lg hover:border-emerald-300 hover:shadow-sm transition-all p-3"
                >
                  <div className="flex items-start gap-2 mb-2">
                    <div className="flex-shrink-0 w-7 h-7 bg-emerald-500 text-white font-bold rounded-md flex items-center justify-center text-xs">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-slate-800 text-sm truncate">
                        {plant.name}
                      </div>
                      {plant.scientific_name && (
                        <div className="text-xs text-slate-500 italic truncate mt-0.5">
                          {plant.scientific_name}
                        </div>
                      )}
                    </div>
                  </div>
                  {plant.confidence && (
                    <div className="mt-2">
                      <div className="text-xs text-slate-600 mb-1">Confianza:</div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-emerald-400 to-teal-500 rounded-full"
                            style={{ width: `${Math.min(plant.confidence * 100, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-semibold text-emerald-700">
                          {(plant.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  )}
                  {Array.isArray(plant.sources) && (
                    <div className="mt-2">
                      <div className="text-xs text-slate-600 mb-1">Fuentes:</div>
                      <div className="flex flex-wrap gap-1">
                        {plant.sources.map((source: any, idx: number) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 text-xs rounded-full"
                            style={{
                              backgroundColor:
                                source === 'RNA' ? '#d1fae5' : source === 'RAG' ? '#e0f2fe' : '#f3e8ff',
                              color:
                                source === 'RNA' ? '#065f46' : source === 'RAG' ? '#075985' : '#7c3aed',
                            }}
                          >
                            {source}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="bg-white border border-sky-200 rounded-lg p-2">
              <p className="text-slate-700 text-xs leading-relaxed">
                💡 <strong>Escribe el nombre o número</strong> (1, 2, 3) de la planta que deseas
                usar y te daré las instrucciones de preparación.
              </p>
            </div>
            <div className="text-xs mt-2 text-slate-400">
              {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const fetchPlantReports = async (plantName: string) => {
    if (!plantName) return;
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/plant-reports/${encodeURIComponent(plantName)}`,
      );
      if (res.ok) {
        const data = await res.json();
        setPlantReports(
          data.reports.map((r: any) => r.side_effect).filter((e: string) => e.length > 3),
        );
      }
    } catch {
      setPlantReports([]);
    }
  };

  // ─── TRADUCCIÓN INTELIGENTE DE PROPIEDADES ────────────────────────────────────

const translateProperty = (prop: string): { text: string; sub: string } => {
  const normalized = prop.toLowerCase().trim()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, ''); // quita tildes para comparar

  const map: Record<string, { text: string; sub: string }> = {
    // Inflamación
    'antiinflamatoria':       { text: 'Reduce la inflamación',          sub: 'Alivia hinchazón y malestar abdominal' },
    'antiinflamatorio':       { text: 'Reduce la inflamación',          sub: 'Alivia hinchazón y malestar abdominal' },
    // Diarrea
    'antidiarreica':          { text: 'Frena la diarrea',               sub: 'Ayuda a normalizar las deposiciones' },
    'antidiarreico':          { text: 'Frena la diarrea',               sub: 'Ayuda a normalizar las deposiciones' },
    // Picor / irritación
    'antipruriginosa':        { text: 'Alivia el picor e irritación',   sub: 'Calma la mucosa digestiva irritada' },
    'antipruriginoso':        { text: 'Alivia el picor e irritación',   sub: 'Calma la mucosa digestiva irritada' },
    // Espasmos / cólicos
    'antiespasmódica':        { text: 'Relaja los espasmos',            sub: 'Calma los cólicos y retortijones' },
    'antiespasmódico':        { text: 'Relaja los espasmos',            sub: 'Calma los cólicos y retortijones' },
    'antiespasmódica (relaja los espasmos intestinales)': { text: 'Relaja los espasmos', sub: 'Calma los cólicos y retortijones' },
    // Gases
    'carminativa':            { text: 'Elimina los gases',              sub: 'Reduce la flatulencia y la distensión' },
    'carminativo':            { text: 'Elimina los gases',              sub: 'Reduce la flatulencia y la distensión' },
    // Digestión
    'digestiva':              { text: 'Mejora la digestión',            sub: 'Facilita el proceso digestivo general' },
    'digestivo':              { text: 'Mejora la digestión',            sub: 'Facilita el proceso digestivo general' },
    'eupéptica':              { text: 'Facilita la digestión',          sub: 'Estimula los jugos digestivos' },
    'eupéptico':              { text: 'Facilita la digestión',          sub: 'Estimula los jugos digestivos' },
    // Náuseas / vómitos
    'antiemética':            { text: 'Reduce las náuseas',             sub: 'Ayuda a controlar las ganas de vomitar' },
    'antiemético':            { text: 'Reduce las náuseas',             sub: 'Ayuda a controlar las ganas de vomitar' },
    'antinauseabunda':        { text: 'Calma las náuseas',              sub: 'Alivia el malestar estomacal' },
    // Acidez / reflujo
    'antiácida':              { text: 'Neutraliza la acidez',           sub: 'Alivia el ardor y el reflujo' },
    'antiácido':              { text: 'Neutraliza la acidez',           sub: 'Alivia el ardor y el reflujo' },
    'antirreflujo':           { text: 'Reduce el reflujo',              sub: 'Protege el esófago del ácido gástrico' },
    // Bacterias
    'antibacteriana':         { text: 'Combate bacterias dañinas',      sub: 'Ayuda a limpiar el tracto digestivo' },
    'antibacteriano':         { text: 'Combate bacterias dañinas',      sub: 'Ayuda a limpiar el tracto digestivo' },
    'antimicrobiana':         { text: 'Elimina microorganismos',        sub: 'Protege contra infecciones intestinales' },
    'antimicrobiano':         { text: 'Elimina microorganismos',        sub: 'Protege contra infecciones intestinales' },
    // Estreñimiento
    'laxante':                { text: 'Alivia el estreñimiento',        sub: 'Favorece el tránsito intestinal' },
    'laxante suave':          { text: 'Alivia el estreñimiento',        sub: 'Favorece el tránsito intestinal de forma suave' },
    // Protección estómago
    'gastroprotectora':       { text: 'Protege el estómago',           sub: 'Forma una capa que cuida la mucosa gástrica' },
    'gastroprotector':        { text: 'Protege el estómago',           sub: 'Forma una capa que cuida la mucosa gástrica' },
    'citoprotectora':         { text: 'Protege las células digestivas', sub: 'Cuida la pared del estómago e intestinos' },
    // Hígado
    'hepatoprotectora':       { text: 'Cuida el hígado',               sub: 'Favorece la función hepática y biliar' },
    'hepatoprotector':        { text: 'Cuida el hígado',               sub: 'Favorece la función hepática y biliar' },
    'colerética':             { text: 'Estimula la bilis',              sub: 'Mejora la digestión de grasas' },
    'colerético':             { text: 'Estimula la bilis',              sub: 'Mejora la digestión de grasas' },
    // Parásitos
    'antiparasitaria':        { text: 'Combate parásitos intestinales', sub: 'Ayuda a eliminar lombrices y protozoos' },
    'antiparasitario':        { text: 'Combate parásitos intestinales', sub: 'Ayuda a eliminar lombrices y protozoos' },
    'antihelmíntica':         { text: 'Elimina lombrices intestinales', sub: 'Acción antiparasitaria directa' },
    'antihelmíntico':         { text: 'Elimina lombrices intestinales', sub: 'Acción antiparasitaria directa' },
    // Calmante / sedante
    'sedante':                { text: 'Calma el sistema nervioso',      sub: 'Reduce el estrés que afecta la digestión' },
    'ansiolítica':            { text: 'Reduce la ansiedad',             sub: 'Ayuda cuando el estrés provoca síntomas digestivos' },
    'ansiolítico':            { text: 'Reduce la ansiedad',             sub: 'Ayuda cuando el estrés provoca síntomas digestivos' },
    // Cicatrizante / regeneradora
    'cicatrizante':           { text: 'Ayuda a cicatrizar',             sub: 'Favorece la regeneración de la mucosa intestinal' },
    'regeneradora':           { text: 'Regenera los tejidos',           sub: 'Repara la mucosa dañada del tracto digestivo' },
    'vulneraria':             { text: 'Cura las heridas internas',      sub: 'Favorece la reparación de la mucosa gástrica' },
    // Astringente
    'astringente':            { text: 'Reduce la permeabilidad intestinal', sub: 'Útil en diarreas y heces sueltas' },
    // Antioxidante
    'antioxidante':           { text: 'Protege las células',            sub: 'Combate el daño oxidativo en el tracto digestivo' },
    // Inmunoestimulante
    'inmunoestimulante':      { text: 'Refuerza las defensas',          sub: 'Apoya el sistema inmune del intestino' },
    'inmunomoduladora':       { text: 'Regula las defensas',            sub: 'Equilibra la respuesta inmune intestinal' },
    // Analgésica
    'analgésica':             { text: 'Alivia el dolor',                sub: 'Reduce el dolor abdominal y los retortijones' },
    'analgésico':             { text: 'Alivia el dolor',                sub: 'Reduce el dolor abdominal y los retortijones' },
    // Emoliente
    'emoliente':              { text: 'Suaviza e hidrata',              sub: 'Calma y protege la mucosa digestiva' },
    // Tónica
    'tónica':                 { text: 'Tonifica el sistema digestivo',  sub: 'Mejora el funcionamiento general del aparato digestivo' },
    'tónico':                 { text: 'Tonifica el sistema digestivo',  sub: 'Mejora el funcionamiento general del aparato digestivo' },
    // Diurética (mencionada a veces)
    'diurética':              { text: 'Favorece la eliminación de líquidos', sub: 'Ayuda a depurar el organismo' },
    'diurético':              { text: 'Favorece la eliminación de líquidos', sub: 'Ayuda a depurar el organismo' },
  };

  // Búsqueda exacta
  if (map[normalized]) return map[normalized];

  // Búsqueda parcial: si la prop contiene alguna clave conocida
  for (const key of Object.keys(map)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return map[key];
    }
  }

  // Fallback inteligente: capitaliza y muestra sin subtítulo
  const capitalized = prop.charAt(0).toUpperCase() + prop.slice(1).toLowerCase();
  return { text: capitalized, sub: '' };
};

  // ─── RENDER PLANT PREPARATION (NUEVO DISEÑO) ──────────────────────────────
  const renderPlantPreparation = (text: string) => {
    const plantText = text.includes('**Evaluación del Tratamiento**')
      ? text.split('**Evaluación del Tratamiento**')[0]
      : text;

    const sections = parsePlantPreparation(plantText);

    // Deduplicar y limpiar propiedades
    if (sections.properties) {
      const unique: string[] = [];
      for (const p of sections.properties) {
        if (
          p &&
          p.trim().length > 0 &&
          !p.toLowerCase().includes('terapéuticas') &&
          !unique.includes(p)
        )
          unique.push(p);
      }
      sections.properties = unique;
    }

    const shortenDosis = (dosis: string): string => {
      if (!dosis) return 'Ver indicaciones';
      return dosis
        .replace('cucharaditas', 'cdtas.')
        .replace('cucharadita', 'cdta.')
        .replace('por taza de agua', '/ taza')
        .replace('por taza', '/ taza');
    };

    const cardStyles: React.CSSProperties = {
      maxWidth: '680px',
      background: '#f0f9ff',
      border: '0.5px solid #bae6fd',
      borderRadius: '12px',
      overflow: 'hidden',
      fontFamily: 'var(--font-sans)',
    };

    const headerStyles: React.CSSProperties = {
      background: '#0ea5e9',
      padding: '18px 22px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
    };

    return (
      <div style={{ fontFamily: 'var(--font-sans)', padding: '4px 0' }}>

        {/* Label Fauno */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '50%',
            background: 'white', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden', border: '1px solid var(--color-border-tertiary)',
          }}>
            <BotHeadIcon className="w-full h-full" />
          </div>
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#059669' }}>Fauno</span>
        </div>

        {/* Card principal */}
        <div style={cardStyles}>

          {/* Header */}
          <div style={headerStyles}>
            <div>
              <p style={{
                fontSize: '11px', letterSpacing: '0.09em',
                textTransform: 'uppercase', color: '#a7f3d0',
                margin: '0 0 5px', fontWeight: 400,
              }}>
                Prescripción herbolaria · Fauno
              </p>
              <h2 style={{
                fontSize: '28px', fontWeight: 500, color: '#fff',
                margin: 0, letterSpacing: '0.04em',
                fontFamily: 'Georgia, serif', lineHeight: 1.1,
              }}>
                {(sections.plantName || 'Planta Medicinal').toUpperCase()}
              </h2>
              {sections.scientificName && (
                <p style={{ fontSize: '13px', fontStyle: 'italic', color: '#6ee7b7', margin: '5px 0 0' }}>
                  {sections.scientificName}
                </p>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '16px' }}>
              <span style={{
                display: 'inline-block',
                background: 'rgba(255,255,255,0.18)',
                color: '#ecfdf5', fontSize: '12px',
                padding: '3px 12px', borderRadius: '20px',
                border: '0.5px solid rgba(255,255,255,0.3)',
              }}>
                Digestivo
              </span>
              {sections.parte && (
                <p style={{ fontSize: '12px', color: '#a7f3d0', margin: '6px 0 0' }}>
                  {sections.parte}
                </p>
              )}
            </div>
          </div>

          {/* Posología */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
            background: '#e0f2fe',
          }}>
            {[
              { label: 'Dosis',      value: shortenDosis(sections.cantidad) },
              { label: 'Frecuencia', value: sections.frequency || '2–3 veces al día' },
              { label: 'Duración',   value: sections.duration  || '5–7 días' },
            ].map((item, i) => (
              <div key={i} style={{
                padding: '14px 16px',
                textAlign: 'center',
                borderRight: i < 2 ? '1px solid rgba(56, 139, 202, 0.3)' : 'none',
              }}>
                <p style={{
                  fontSize: '10px', textTransform: 'uppercase',
                  letterSpacing: '0.1em', color: 'var(--color-text-tertiary)',
                  margin: '0 0 6px', fontWeight: 600,
                }}>
                  {item.label}
                </p>
                <p style={{
                  fontSize: '15px', fontWeight: 600,
                  color: 'var(--color-text-primary)', margin: 0, lineHeight: 1.3,
                }}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>

          {/* Cuerpo 2 columnas */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
          }}>

            {/* Propiedades — en lenguaje común */}
            <div style={{ padding: '16px 18px', borderRight: '0.5px solid var(--color-border-tertiary)' }}>
              <p style={{
                fontSize: '11px', fontWeight: 500,
                textTransform: 'uppercase', letterSpacing: '0.09em',
                color: 'var(--color-text-tertiary)', margin: '0 0 12px',
              }}>
                ¿Para qué sirve?
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {sections.properties && sections.properties.length > 0
                  ? sections.properties.slice(0, 5).map((prop: string, i: number) => {
                      const translated = translateProperty(prop);
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                          <div style={{
                            width: '6px', height: '6px', borderRadius: '50%',
                            background: '#2e7d52', flexShrink: 0, marginTop: '8px',
                          }} />
                          <div>
                            <div style={{ fontSize: '14px', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>
                              {translated.text}
                            </div>
                            {translated.sub && (
                              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.4, marginTop: '1px' }}>
                                {translated.sub}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  : <span style={{ fontSize: '13px', color: 'var(--color-text-tertiary)' }}>No especificadas</span>
                }
              </div>
            </div>

            {/* Preparación */}
            <div style={{ padding: '16px 18px' }}>
              <p style={{
                fontSize: '11px', fontWeight: 500,
                textTransform: 'uppercase', letterSpacing: '0.09em',
                color: 'var(--color-text-tertiary)', margin: '0 0 12px',
              }}>
                Cómo prepararlo
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {sections.preparation && sections.preparation.length > 0
                  ? sections.preparation.map((step: string, i: number) => (
                      <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                        <span style={{
                          minWidth: '22px', height: '22px', borderRadius: '50%',
                          background: '#dbeafe', color: '#1d4ed8',
                          fontSize: '12px', fontWeight: 500,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          flexShrink: 0, marginTop: '1px',
                        }}>
                          {i + 1}
                        </span>
                        <span style={{ fontSize: '14px', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>
                          {step}
                        </span>
                      </div>
                    ))
                  : <span style={{ fontSize: '13px', color: 'var(--color-text-tertiary)' }}>No especificada</span>
                }
              </div>
            </div>
          </div>

          {/* Advertencias */}
          {((sections.contraindications && sections.contraindications.length > 0) ||
            (sections.warnings && sections.warnings.length > 0) ||
            plantReports.length > 0) && (
            <div style={{
              padding: '10px 16px',
              background: '#fffbeb',
              borderTop: '0.5px solid rgba(0,0,0,0.06)',
              borderBottom: '0.5px solid #fde68a',
              display: 'flex', gap: '10px', alignItems: 'flex-start',
            }}>
              <span style={{ fontSize: '15px', flexShrink: 0, marginTop: '1px' }}>⚠️</span>
              <p style={{ fontSize: '13px', color: '#92400e', lineHeight: 1.6, margin: 0 }}>
                {[
                  ...(sections.contraindications || []),
                  ...(sections.warnings || []),
                  ...(plantReports.length > 0
                    ? [`Efectos reportados por usuarios: ${plantReports.slice(0, 2).join(', ')}`]
                    : []),
                ].join(' · ')}
              </p>
            </div>
          )}

          {/* Nota legal */}
          <div style={{
            padding: '9px 16px',
            background: 'var(--color-background-secondary)',
            display: 'flex', gap: '8px', alignItems: 'center',
          }}>
            <span style={{ fontSize: '14px', flexShrink: 0 }}>ℹ️</span>
            <p style={{ fontSize: '12px', color: 'var(--color-text-tertiary)', margin: 0, lineHeight: 1.4 }}>
              Información con fines educativos. No sustituye la consulta con un profesional de la salud.
            </p>
          </div>

        </div>
      </div>
    );
  };

  // ─── RENDER MESSAGE ────────────────────────────────────────────────────────

  const renderMessage = (msg: Message) => {
    if (msg.isRecommendations && msg.recommendations)
      return renderRecommendationsCard(msg.recommendations, msg.systemInfo, msg.message,);

    
    if (msg.message.includes('🌿') || msg.message.includes('Preparación:')) {
      // Extraer nombre de planta para el comentario
      const plantMatch = msg.message.match(/\*\*([A-ZÁÉÍÓÚÑ\s]+)\*\*/);
      const plantName = plantMatch ? plantMatch[1] : 'esta planta';
      
      return (
        <div>
          {/* Comentario humano antes de la prescripción */}
          <div className="flex justify-start mb-2">
            <div className="max-w-[98%] bg-gradient-to-br from-sky-50 to-blue-50 border border-sky-200 rounded-xl p-3 shadow-sm">
              <div className="flex items-start gap-2">
                <div className="w-8 h-8 rounded-full bg-white flex-shrink-0 shadow-sm flex items-center justify-center overflow-hidden">
                  <BotHeadIcon className="w-full h-full" />
                </div>
                <div className="flex-1">
                  <div className="text-xs font-medium mb-1 text-emerald-600">Fauno</div>
                  <div className="text-sm text-slate-700 leading-relaxed">
                    {msg.preMessage || `Aquí tienes la información completa sobre ${plantName}. Sigue las indicaciones con cuidado y recuerda que si los síntomas persisten más de lo indicado, es mejor consultar con un médico. 🌿`}
                  </div>
                </div>
              </div>
            </div>
          </div>
          {/* La prescripción */}
          {renderPlantPreparation(msg.message)}
        </div>
      );
    }

    const isIntelligentOutOfScope =
      !msg.isUser &&
      (msg.message.includes('😔') ||
        msg.message.includes('🤕') ||
        msg.message.includes('💪') ||
        msg.message.includes('🏥') ||
        msg.message.includes('🤧') ||
        msg.message.includes('🌡️') ||
        msg.message.includes('✨ **Pero sí puedo ayudarte con:**'));

    if (isIntelligentOutOfScope) {
      return (
        <div className="flex justify-start mb-3">
          <div className="max-w-[98%] bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 shadow-sm">
            <div className="flex items-start gap-2">
              <div className="w-8 h-8 rounded-full bg-white flex-shrink-0 shadow-sm flex items-center justify-center overflow-hidden">
                <BotHeadIcon className="w-full h-full" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium mb-2 text-amber-600">Fauno</div>
                <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {msg.message.split('\n').map((line, idx) => (
                    <div key={idx} className="mb-1">{line}</div>
                  ))}
                </div>
                {msg.timestamp && (
                  <div className="text-xs mt-3 text-amber-400">
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }

    const currentUserName = getUserDisplayName('chat');

    return (
      <div className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'} mb-3`}>
        <div
          className={`${msg.isUser ? 'max-w-[85%]' : 'max-w-[98%]'} rounded-xl p-3 ${
            msg.isUser
              ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-md'
              : 'bg-gradient-to-br from-sky-50 to-blue-50 border border-sky-200 shadow-sm'
          }`}
        >
          <div className="flex items-start gap-2">
            {!msg.isUser ? (
              <div className="w-8 h-8 rounded-full bg-white flex-shrink-0 shadow-sm flex items-center justify-center overflow-hidden">
                <BotHeadIcon className="w-full h-full" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex-shrink-0 shadow-sm flex items-center justify-center text-white font-bold text-sm overflow-hidden">
                {userProfile?.profile_picture_url ? (
                  <img
                    src={userProfile.profile_picture_url}
                    alt={currentUserName}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      const t = e.target as HTMLImageElement;
                      t.style.display = 'none';
                    }}
                  />
                ) : (
                  currentUserName.charAt(0).toUpperCase()
                )}
              </div>
            )}
            <div className="flex-1">
              <div
                className={`text-xs font-medium mb-0.5 ${
                  msg.isUser ? 'text-emerald-100' : 'text-emerald-600'
                }`}
              >
                {msg.isUser ? currentUserName : 'Fauno'}
              </div>
              <div
                className={`${
                  msg.isUser ? 'text-white' : 'text-slate-700'
                } leading-relaxed text-sm`}
              >
                {msg.message}
              </div>
              {msg.timestamp && (
                <div
                  className={`text-xs mt-1 ${
                    msg.isUser ? 'text-emerald-100' : 'text-slate-400'
                  }`}
                >
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ─── STATUS INDICATOR ─────────────────────────────────────────────────────

  const renderStatusIndicator = () => {
    const steps = [
      { label: 'Síntomas', state: conversationState.hasSymptoms, icon: '🩺' },
      { label: 'Duración', state: conversationState.hasDuration, icon: '⏱️' },
      { label: 'Intensidad', state: conversationState.hasIntensity, icon: '📊' },
      { label: 'Ambiental', state: conversationState.hasCausaAmbiental, icon: '🌡️' },
      { label: 'Emocional', state: conversationState.hasCausaEmocional, icon: '😊' },
      { label: 'Dietética', state: conversationState.hasCausaDietetica, icon: '🍽️' },
      {
        label: 'Alergias',
        state:
          conversationState.hasAllergies ||
          (patientInfo.allergies !== undefined && patientInfo.allergies !== '') ||
          (messages.slice(-1)[0]?.isUser &&
            messages.slice(-1)[0]?.message.toLowerCase().includes('no') &&
            conversationState.hasCausaDietetica),
        icon: '🚫',
      },
    ];

    const completedSteps = steps.filter((s) => s.state).length;
    const progressPercentage = (completedSteps / steps.length) * 100;

    return (
      <div className="bg-white rounded-xl p-3 mb-3 shadow-sm border border-slate-200">
        <div className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white p-3 rounded-lg mb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
                <span className="text-base">📋</span>
              </div>
              <div>
                <h4 className="font-bold text-white text-sm">Progreso de consulta</h4>
                <div className="text-xs text-emerald-100">
                  {completedSteps}/{steps.length} completados
                </div>
              </div>
            </div>
            <div className="text-xl font-bold text-white bg-white/20 px-3 py-1 rounded-full">
              {Math.round(progressPercentage)}%
            </div>
          </div>
        </div>

        <div className="grid grid-cols-4 md:grid-cols-7 gap-2">
          {steps.map((step, idx) => (
            <div
              key={idx}
              className="relative group"
              title={`${step.label}: ${step.state ? 'Completado' : 'Pendiente'}`}
            >
              {step.state && (
                <div className="absolute -top-1 -right-1 w-5 h-5 bg-emerald-500 text-white rounded-full flex items-center justify-center shadow-sm z-10 border border-white">
                  <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
              <div
                className={`flex flex-col items-center justify-center p-2 rounded-lg transition-all duration-200 min-h-[70px] ${
                  step.state
                    ? 'bg-emerald-50 border border-emerald-300 shadow-sm'
                    : 'bg-slate-50 border border-slate-200'
                } group-hover:scale-105`}
              >
                <div className={`text-xl mb-1 ${step.state ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {step.icon}
                </div>
                <div
                  className={`text-xs font-medium text-center leading-tight ${
                    step.state ? 'text-emerald-700' : 'text-slate-500'
                  }`}
                >
                  {step.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ─── CHAT COMPONENT ───────────────────────────────────────────────────────

  const ChatComponent = () => {
    const inputRef = useRef<HTMLInputElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const messagesContainerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!showFeedbackForm && inputRef.current) inputRef.current.focus();
    }, []);

    useEffect(() => {
      if (
        showFeedbackForm &&
        textareaRef.current &&
        (feedbackStep === 1 || feedbackStep === 2 || feedbackStep === 3)
      ) {
        textareaRef.current.focus();
        setTimeout(() => {
          if (textareaRef.current) {
            const l = textareaRef.current.value.length;
            textareaRef.current.setSelectionRange(l, l);
          }
        }, 10);
      }
    }, []);

    useEffect(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTo({
          top: messagesContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    }, []);

    const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInputValue(e.target.value);
    };

    const renderFeedbackStep = (step: number) => {
      switch (step) {
        case 1:
          return (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">¿Experimentó algún efecto secundario?</p>
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={handleTextareaChange}
                className="w-full p-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
                placeholder="Describa cualquier efecto secundario observado"
                rows={4}
              />
              <button
                onClick={() => handleFeedbackSubmit({ sideEffects: inputValue })}
                className="mt-2 px-6 py-2.5 bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 transition-all"
              >
                Continuar
              </button>
            </div>
          );
        case 2:
          return (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">¿Cuánto tiempo tardó en notar mejoría?</p>
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={handleTextareaChange}
                className="w-full p-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
                placeholder="Ejemplo: 2 días, 1 semana, etc."
                rows={4}
              />
              <button
                onClick={() => handleFeedbackSubmit({ timeToImprovement: inputValue })}
                className="mt-2 px-6 py-2.5 bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 transition-all"
              >
                Continuar
              </button>
            </div>
          );
        case 3:
          return (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">Comentarios adicionales:</p>
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={handleTextareaChange}
                className="w-full p-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
                placeholder="Comparta cualquier observación adicional"
                rows={4}
              />
              <button
                onClick={() => handleFeedbackSubmit({ additionalComments: inputValue })}
                className="mt-2 px-6 py-2.5 bg-emerald-500 text-white rounded-xl hover:bg-emerald-600 transition-all"
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
      <div className="flex flex-col h-full bg-white rounded-2xl shadow-lg border-2 border-slate-200">
        {/* Header fijo */}
        <div className="border-b-2 border-slate-100 p-4 bg-white flex-shrink-0">
          {!showFeedbackForm && !conversationState.isComplete && renderStatusIndicator()}
        </div>

        {/* Área de mensajes */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4"
        >
          {messages.map((msg) => (
            <div key={msg.id}>{renderMessage(msg)}</div>
          ))}

          {isProcessing && (
            <div className="flex justify-start mb-3">
              <div className="bg-gradient-to-br from-sky-50 to-blue-50 border border-sky-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-start gap-2">
                  <div className="w-8 h-8 rounded-full bg-white flex-shrink-0 shadow-sm flex items-center justify-center overflow-hidden">
                    <BotHeadIcon className="w-full h-full" />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs font-medium mb-2 text-emerald-600">
                      Fauno está pensando...
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                    <div className="text-xs mt-2 text-slate-400">
                      {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input fijo */}
        <div className="border-t-2 border-slate-100 p-4 bg-white rounded-b-2xl flex-shrink-0">
          {!showFeedbackForm ? (
            <div className="flex gap-2">
              <div className="flex-grow relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={isProcessing}
                  className="w-full p-3 pr-10 border border-slate-300 rounded-lg focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all bg-white text-slate-700 placeholder-slate-400 text-sm"
                  placeholder={
                    awaitingPlantSelection
                      ? 'Escribe el nombre o número de la planta...'
                      : 'Escribe tu respuesta aquí...'
                  }
                />
              </div>
              <button
                onClick={handleSendMessage}
                disabled={isProcessing || !inputValue.trim()}
                className={`px-4 py-3 rounded-lg text-white font-medium transition-all ${
                  isProcessing || !inputValue.trim()
                    ? 'bg-slate-300 cursor-not-allowed'
                    : 'bg-emerald-500 hover:bg-emerald-600 active:scale-95 shadow-sm'
                }`}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          ) : (
            <div className="mt-4 p-5 bg-white border-2 border-slate-200 rounded-2xl">
              <h3 className="font-semibold mb-4 text-slate-800 text-lg">
                Evaluación del Tratamiento
              </h3>
              {feedbackStep === 4 ? (
                <div className="p-5 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl border-2 border-emerald-200">
                  <p className="text-center font-medium text-emerald-700">
                    ¡Gracias por compartir tu experiencia! Tu evaluación ha sido registrada.
                  </p>
                </div>
              ) : (
                <>
                  {feedbackStep === 0 && (
                    <div className="space-y-4">
                      <p className="text-sm text-slate-600">
                        ¿Qué tan efectivo fue el tratamiento en aliviar tus síntomas?
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
                        {[
                          { value: 'Muy deficiente', emoji: '😞' },
                          { value: 'Deficiente', emoji: '😕' },
                          { value: 'Regular', emoji: '😐' },
                          { value: 'Bueno', emoji: '😊' },
                          { value: 'Muy bueno', emoji: '😄' },
                        ].map((option) => (
                          <button
                            key={option.value}
                            onClick={() => handleFeedbackSubmit({ effectiveness: option.value })}
                            className={`flex flex-col items-center justify-center p-3 rounded-xl font-semibold transition-all shadow-sm min-h-[80px] ${
                              feedbackData.effectiveness === option.value
                                ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white scale-105'
                                : 'bg-slate-100 hover:bg-slate-200 text-slate-700 hover:scale-105'
                            }`}
                          >
                            <div className="text-2xl mb-1">{option.emoji}</div>
                            <div className="text-xs text-center leading-tight">{option.value}</div>
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
      </div>
    );
  };

  // ─── PROTECTED CHAT ───────────────────────────────────────────────────────

  const ProtectedChat = () => {
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    return (
      <Layout
        isAuthenticated={true}
        userDisplayName={getUserDisplayName('header')}
        userProfile={userProfile}
        onLogout={handleLogout}
        onNewConsultation={() => resetConsultation(true)}
        toast={toast}
        setToast={setToast}
        showUserMenu={true}
        hideNavigation={true}
      >
        <div className="w-full px-4 py-4" style={{ height: 'calc(100vh - 100px)' }}>
          <div className="container mx-auto max-w-5xl h-full">
            <div className="h-full rounded-2xl overflow-hidden shadow-xl border border-emerald-100 bg-white">
              <ChatComponent />
            </div>
          </div>
        </div>
      </Layout>
    );
  };

  // ─── ROUTER ───────────────────────────────────────────────────────────────

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <Layout
                isAuthenticated={false}
                toast={toast}
                setToast={setToast}
                showUserMenu={false}
                hideNavigation={false}
              >
                <div className="min-h-screen relative">
                  <div className="relative z-10">
                    <div className="container mx-auto px-4 py-8">
                      <div className="max-w-6xl mx-auto">
                        <div className="text-center mb-12 px-4">
                          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-black text-white mb-6 leading-tight px-2">
                            Sistema Multi-Agente de
                            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-emerald-300 to-teal-300">
                              Apoyo en Prescripción Herbolaria
                            </span>
                          </h1>
                          <p className="text-xl md:text-2xl text-white/90 max-w-3xl mx-auto mb-8 leading-relaxed">
                            Asistencia inteligente para profesionales de la salud.
                          </p>
                          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
                            <Link
                              to="/register"
                              className="px-8 py-4 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold rounded-xl hover:shadow-2xl hover:scale-105 transition-all text-lg"
                            >
                              Registrarse
                            </Link>
                            <Link
                              to="/login"
                              className="px-8 py-4 bg-white/10 backdrop-blur-md text-white font-bold rounded-xl border-2 border-white/30 hover:bg-white/20 hover:scale-105 transition-all text-lg"
                            >
                              Iniciar Sesión
                            </Link>
                          </div>
                        </div>

                        <div className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 mb-12">
                          <h2 className="text-3xl font-bold text-center text-white mb-8">
                            ¿Cómo funciona el sistema?
                          </h2>
                          <div className="grid md:grid-cols-4 gap-4">
                            {[
                              { icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', title: '1. Recolección', desc: 'Captura síntomas, duración, intensidad, causas y alergias' },
                              { icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', title: '2. Validación', desc: 'Agente validador filtra datos inconsistentes y genera registros estructurados' },
                              { icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z', title: '3. Análisis Híbrido', desc: 'RNA Perceptrón + RAG generan recomendaciones con el sistema de mayor precisión' },
                              { icon: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z', title: '4. Prescripción', desc: 'Entrega planta seleccionada con preparación detallada, dosis y precauciones' },
                            ].map((item, i) => (
                              <div key={i} className="text-center">
                                <div className="w-16 h-16 bg-white/10 rounded-full mx-auto mb-4 flex items-center justify-center border-2 border-white/30">
                                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                                  </svg>
                                </div>
                                <h4 className="font-bold text-white mb-2">{item.title}</h4>
                                <p className="text-white/70 text-sm">{item.desc}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 mb-12">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                            {[
                              { num: '150+', label: 'Plantas Base INS', color: 'text-emerald-300' },
                              { num: '2', label: 'Niveles de Agentes', color: 'text-teal-300' },
                              { num: 'RNA+RAG', label: 'Sistema Híbrido', color: 'text-blue-300' },
                              { num: '7', label: 'Variables de Entrada', color: 'text-purple-300' },
                            ].map((stat, i) => (
                              <div key={i} className="text-center">
                                <div className={`text-4xl font-black ${stat.color} mb-2`}>{stat.num}</div>
                                <div className="text-white/70 text-sm">{stat.label}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </Layout>
            )
          }
        />

        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <Layout isAuthenticated={false} toast={toast} setToast={setToast} showUserMenu={false} hideNavigation={true}>
                <div className="container mx-auto px-4 max-w-md mt-8 mb-16 py-8">
                  <LoginForm onLoginSuccess={handleLoginSuccess} />
                </div>
              </Layout>
            )
          }
        />

        <Route
          path="/register"
          element={
            isAuthenticated ? (
              <Navigate to="/chat" replace />
            ) : (
              <Layout isAuthenticated={false} toast={toast} setToast={setToast} showUserMenu={false} hideNavigation={true}>
                <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-4 py-8">
                  <RegisterForm onRegisterSuccess={() => <Navigate to="/login" replace />} />
                </div>
              </Layout>
            )
          }
        />

      

        <Route
          path="/editar-perfil"
          element={
            isAuthenticated ? (
              <Layout isAuthenticated={true} userDisplayName={getUserDisplayName('header')} userProfile={userProfile} onLogout={handleLogout} toast={toast} setToast={setToast} showUserMenu={true} hideNavigation={true}>
                <div className="container mx-auto px-4 max-w-2xl mt-6 mb-16 py-8">
                  <div className="bg-white rounded-2xl shadow-xl border border-emerald-100 p-6">
                    <EditProfilePage />
                  </div>
                </div>
              </Layout>
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        <Route path="/chat" element={<ProtectedChat />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
};

// ─── STYLES ───────────────────────────────────────────────────────────────────

const styles = document.createElement('style');
styles.textContent = `
  @keyframes slide-in-right {
    from { opacity: 0; transform: translateX(100%); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes shimmer {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  @keyframes bounce-once {
    0%, 100% { transform: scale(1); }
    50%       { transform: scale(1.2); }
  }
  .animate-slide-in-right { animation: slide-in-right 0.3s ease-out; }
  .animate-shimmer        { animation: shimmer 2s infinite; }
  .animate-bounce-once    { animation: bounce-once 0.5s ease-in-out; }
`;
if (typeof document !== 'undefined') document.head.appendChild(styles);

export default App;