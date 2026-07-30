"""
natural_conversation_agent.py - VERSIÓN CORREGIDA
✅ Fix: duración no se reconocía ("3 dias", "hace 3 dias", variantes sin tilde)
✅ Fix: LLM extraía info pero estado no se actualizaba (bucle infinito de preguntas)
✅ Fix: inClarificationMode sobreescribía extracted antes de procesar duración/intensidad
✅ Fix: prompt del LLM mejorado con más ejemplos y normalización de tildes
✅ Fix: _is_vague_duration ahora acepta variantes sin tilde
✅ Fix: actualización de estado más robusta con logging detallado
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"


class ConversationState(BaseModel):
    hasSymptoms: bool = False
    hasDuration: bool = False
    hasAllergies: bool = False
    hasIntensity: bool = False
    hasCausaAmbiental: bool = False
    hasCausaEmocional: bool = False
    hasCausaDietetica: bool = False
    isComplete: bool = False
    needsEmergencyCheck: bool = False
    inClarificationMode: bool = False
    clarificationStep: int = 0
    hasReceivedRecommendations: bool = False
    selectedPlant: Optional[str] = None


class ExtractedInfo(BaseModel):
    symptoms: Optional[str] = None
    duration: Optional[str] = None
    allergies: Optional[str] = None
    intensity: Optional[str] = None
    causa_ambiental: Optional[str] = None
    causa_emocional: Optional[str] = None
    causa_dietetica: Optional[str] = None
    selected_plant: Optional[str] = None


class ProcessChatRequest(BaseModel):
    session_id: str
    message: str
    conversation_history: List[Dict[str, str]]
    current_state: ConversationState
    patient_info: Dict[str, Optional[str]]


class ProcessChatResponse(BaseModel):
    assistant_response: str
    conversation_state: ConversationState
    extracted_info: Optional[Dict[str, Any]] = None
    patient_info: Optional[Dict[str, Any]] = None
    is_emergency: bool = False
    has_recommendations: bool = False
    recommendations: Optional[Dict[str, Any]] = None


EMERGENCY_KEYWORDS = [
    "dolor de pecho", "no puedo respirar", "sangrado abundante",
    "pérdida de conciencia", "convulsiones", "infarto"
]


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDAD: normalizar texto (quitar tildes, minúsculas) para comparaciones
# ─────────────────────────────────────────────────────────────────────────────
def _normalize(text: str) -> str:
    """Convierte a minúsculas y elimina tildes para comparaciones robustas."""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u',
        'ü': 'u', 'ñ': 'n', 'Ñ': 'n',
    }
    result = text.lower()
    for accented, plain in replacements.items():
        result = result.replace(accented, plain)
    return result


class NaturalConversationAgent:

    def __init__(self):
        self.model = GROQ_MODEL
        self.client = GROQ_CLIENT
        self.failed_symptom_attempts = {}

    # ─────────────────────────────────────────────────────────────────────────
    # OUT-OF-SCOPE
    # ─────────────────────────────────────────────────────────────────────────
    def _generate_intelligent_out_of_scope_response(self, detected_part: str, category: str) -> str:
        import random
        
        # Respuestas humanizadas según la parte detectada
        responses = {
            'nuca': "Ay, la nuca duele bastante, lo sé. Pero mi especialidad es el sistema digestivo — para eso de la nuca o cervical te vendría mejor ver un traumatólogo o hacerte un masaje terapéutico. Lo que sí puedo hacer por ti es ayudarte si tienes alguna molestia en el estómago, la barriga o la digestión. ¿Tienes algo así?",
            'cabeza': "Entiendo que un dolor de cabeza puede ser muy molesto. Pero eso escapa de mi área — yo me especializo en plantas para el sistema digestivo. Si tienes algo en el estómago, náuseas, o problemas digestivos, ahí sí te puedo orientar bien.",
            'espalda': "La espalda es cosa de huesos y músculos, y para eso te conviene más un fisioterapeuta o traumatólogo. Yo me muevo en el mundo digestivo — estómago, barriga, intestinos. ¿Tienes alguna molestia por ahí?",
            'gripe': "La gripe y el resfriado son cosa del sistema respiratorio, fuera de mi alcance como herbolario digestivo. Pero si además tienes malestar estomacal o náuseas, eso sí lo puedo atender.",
            'fiebre': "La fiebre necesita atención médica, no me arriesgo a orientarte mal en eso. Lo que sí domino son las plantas para el sistema digestivo. ¿Hay algo en el estómago que también te esté molestando?",
        }
        
        # Buscar respuesta específica
        detected_lower = detected_part.lower()
        for key, response in responses.items():
            if key in detected_lower:
                return response
        
        # Respuesta genérica humanizada
        generics = [
            f"Mmm, lo de {detected_part} no es mi área, la verdad. Yo me especializo en plantas medicinales para el sistema digestivo — estómago, barriga, náuseas, eso sí lo manejo bien. ¿Tienes alguna molestia digestiva?",
            f"Para {detected_part} necesitarías otro especialista, yo soy herbolario digestivo. Cuéntame si tienes algo en el estómago o la digestión y te ayudo.",
        ]
        return random.choice(generics)



    def _detect_sensitive_conditions(self, user_message: str, patient_info: Dict) -> Optional[str]:
        """
        Detecta condiciones sensibles que afectan las recomendaciones.
        Retorna un mensaje especial si detecta algo crítico, None si todo normal.
        """
        norm = _normalize(user_message)
        
        sensitive_conditions = {
            'embarazo': ['embarazada', 'embarazo', 'gestante', 'gestacion', 'estoy esperando', 'encinta'],
            'lactancia': ['lactando', 'dando de lactar', 'amamantando', 'lactancia'],
            'diabetes': ['diabetica', 'diabetico', 'diabetes', 'insulina'],
            'hipertension': ['hipertensa', 'hipertenso', 'hipertension', 'presion alta'],
            'ninos': ['mi bebe', 'mi hijo', 'para mi hijo', 'tiene 2 anos', 'tiene 3 anos', 'tiene 4 anos'],
        }
        
        detected = None
        for condition, keywords in sensitive_conditions.items():
            if any(kw in norm for kw in keywords):
                detected = condition
                break
        
        if not detected:
            return None
        
        # Guardar en patient_info para que el recommender lo considere
        patient_info['sensitive_condition'] = detected
        
        messages = {
            'embarazo': (
                "¡Eso es muy importante que me lo digas! El embarazo cambia todo — "
                "muchas plantas que normalmente recomendaría pueden no ser seguras en esta etapa. "
                "Voy a ser muy cuidadoso/a con lo que te sugiera. "
                "De todas formas te recomendaré opciones suaves y seguras, "
                "pero siempre consultando con tu médico o ginecólogo antes de tomar cualquier cosa. ¿De acuerdo?"
            ),
            'lactancia': (
                "Gracias por decirme que estás lactando, eso es clave. "
                "Varias plantas pasan a la leche materna, así que tengo que ser muy selectivo/a. "
                "Te daré opciones muy suaves y seguras, pero siempre con supervisión médica."
            ),
            'diabetes': (
                "Entendido, la diabetes es importante tenerla en cuenta. "
                "Algunas plantas pueden interactuar con la glucosa o con medicamentos. "
                "Voy a considerar eso en mis recomendaciones."
            ),
            'hipertension': (
                "Anotado, la presión alta es un factor importante. "
                "Hay plantas que pueden afectar la presión, así que seré cuidadoso/a. "
                "Te daré opciones seguras para tu condición."
            ),
            'ninos': (
                "Para niños pequeños hay que tener mucho cuidado con las plantas y las dosis. "
                "¿Cuántos años tiene? Así puedo orientarte mejor sobre qué es seguro."
            ),
        }
        
        return messages.get(detected, 
            f"Gracias por decirme eso sobre {detected}, lo tendré muy en cuenta para recomendarte algo seguro."
        )
    # ─────────────────────────────────────────────────────────────────────────
    # EXTRACCIÓN CON LLM  ← CORREGIDO
    # ─────────────────────────────────────────────────────────────────────────
    async def _extract_with_llm(
        self,
        user_message: str,
        patient_info: Dict[str, Optional[str]],
        last_assistant_message: str
    ) -> dict:
        prompt = f"""Eres un asistente médico especializado en sistema digestivo peruano.

    Última pregunta del asistente: "{last_assistant_message}"
    Mensaje del paciente: "{user_message}"
    Información ya recopilada: {json.dumps(patient_info, ensure_ascii=False)}

    Tu tarea: extraer TODA la información del mensaje actual con máxima inteligencia.

    === REGLA PRINCIPAL: CONTEXTO DE LA PREGUNTA ===
    Siempre interpreta la respuesta del paciente EN FUNCIÓN de lo que se le preguntó.

    Si se le preguntó sobre causa AMBIENTAL y responde "no", "tampoco", "nada", "para nada" → causa_ambiental: "no aplica"
    Si se le preguntó sobre causa EMOCIONAL y responde "no", "tampoco", "nada" → causa_emocional: "no aplica"  
    Si se le preguntó sobre causa DIETÉTICA y responde "no", "nada", "tampoco" → causa_dietetica: "no aplica"
    Si se le preguntó sobre ALERGIAS y responde "no", "ninguna", "no lo sé", "no creo" → allergies: "ninguna"

    === MENSAJES MIXTOS — MUY IMPORTANTE ===
    El paciente puede dar múltiples datos en un solo mensaje. Extrae TODO:

    Ejemplos:
    - "no lo sé, solo estoy embarazada" 
    → allergies: "ninguna", sensitive_condition: "embarazo"
    
    - "tampoco tengo estrés, pero sí comí chicharrón"
    → causa_emocional: "no aplica", causa_dietetica: "chicharrón"
    
    - "no tengo alergias y soy diabético"
    → allergies: "ninguna", sensitive_condition: "diabetes"

    - "no, aunque tengo presión alta"
    → [campo preguntado]: "no aplica", sensitive_condition: "hipertension"

    === CONDICIONES SENSIBLES ===
    Detecta y extrae en "sensitive_condition" si menciona:
    - embarazada, gestante, embarazo → "embarazo"
    - lactando, dando de lactar → "lactancia"  
    - diabético/a, diabetes → "diabetes"
    - presión alta, hipertensión → "hipertension"
    - niño pequeño, bebé, hijo de X años (menor de 12) → "nino"

    === NEGACIONES VÁLIDAS ===
    Estas palabras son respuestas VÁLIDAS a preguntas de causa/alergia:
    "no", "tampoco", "nada", "para nada", "no creo", "no tengo", 
    "ninguna", "no que yo sepa", "no lo sé", "no sé", "desconozco"

    NUNCA marques is_confusion: true cuando el paciente niega algo en respuesta
    a una pregunta directa. "no" es siempre una respuesta válida.

    === CONFUSIÓN REAL ===
    is_confusion: true SOLO cuando:
    - El paciente pregunta "¿qué?", "¿cómo?", "no entiendo", "¿a qué te refieres?"
    - El mensaje no tiene relación con ningún campo conocido
    - El paciente pide que le expliques algo

    === SÍNTOMAS DIGESTIVOS ===
    Extrae SOLO síntomas del sistema digestivo.
    Si menciona síntoma NO digestivo → is_out_of_scope: true, out_of_scope_part: [parte]

    === DURACIÓN ===
    Normaliza a "N unidad(es)": "3 dias" → "3 días", "como 1 hora" → "1 hora"
    Vago ("hace poco", "recientemente") → null

    === INTENSIDAD ===
    Infiere desde contexto:
    "mucho", "bastante", "muy fuerte" → "severo"
    "más o menos", "masomenos", "regular", "medio" → "moderado"  
    "un poco", "leve", "tolerable", "nomás" → "leve"

    === EMERGENCIA ===
    is_emergency: true SOLO para: dolor de pecho intenso, no puede respirar,
    pérdida de conciencia, convulsiones.

    === RESPONDE ÚNICAMENTE CON JSON VÁLIDO ===
    {{
    "symptoms": null,
    "duration": null,
    "intensity": null,
    "causa_ambiental": null,
    "causa_emocional": null,
    "causa_dietetica": null,
    "allergies": null,
    "sensitive_condition": null,
    "is_out_of_scope": false,
    "is_emergency": false,
    "is_confusion": false,
    "out_of_scope_part": null
    }}"""

        try:
            result = await self._call_groq(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=350
            )

            if not result:
                logger.warning("⚠️ LLM no respondió, usando fallback")
                return self._extract_by_rules_fallback_static(user_message, patient_info, last_assistant_message)

            clean = result.strip().replace("```json", "").replace("```", "").strip()
            extracted = json.loads(clean)
            logger.info(f"✅ LLM extrajo: {extracted}")
            return extracted

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON: {e}")
            return self._extract_by_rules_fallback_static(user_message, patient_info)
        except Exception as e:
            logger.error(f"❌ Error en _extract_with_llm: {e}")
            return self._extract_by_rules_fallback_static(user_message, patient_info, last_assistant_message)
        
    
    def _extract_by_rules_fallback_static(
        self,
        user_message: str,
        patient_info: Dict[str, Optional[str]],
        last_assistant_message: str = ""       # ← agregar este parámetro
    ) -> dict:
        """
        Fallback SOLO cuando el LLM falla por error de red o JSON inválido.
        No debe usarse como lógica principal.
        """
        logger.warning("🔄 FALLBACK POR REGLAS ACTIVADO (LLM no disponible)")
        norm = _normalize(user_message)
        result = {
            "symptoms": None,
            "duration": None,
            "intensity": None,
            "causa_ambiental": None,
            "causa_emocional": None,
            "causa_dietetica": None,
            "allergies": None,
            "is_out_of_scope": False,
            "is_emergency": False,
            "out_of_scope_part": None
        }

        # Emergencia básica
        emergency_keywords = ["dolor de pecho", "no puedo respirar", "perdi el conocimiento", "convulsion"]
        if any(kw in norm for kw in emergency_keywords):
            result["is_emergency"] = True
            return result

        # Síntomas digestivos básicos
        digestive_keywords = [
            "estomago", "vientre", "barriga", "abdomen", "panza",
            "nausea", "nauseas", "vomito", "vomitar", "diarrea",
            "acidez", "reflujo", "gases", "flatulencia", "colico",
            "indigestion", "estrenimiento", "dolor abdominal"
        ]
        non_digestive_keywords = [
            "cabeza", "migrana", "espalda", "brazo", "pierna",
            "pecho", "garganta", "tos", "gripe", "fiebre", "oido"
        ]

        has_digestive = any(kw in norm for kw in digestive_keywords)
        has_non_digestive = any(kw in norm for kw in non_digestive_keywords)

        if has_non_digestive and not has_digestive:
            for kw in non_digestive_keywords:
                if kw in norm:
                    result["is_out_of_scope"] = True
                    result["out_of_scope_part"] = kw
                    break
            return result

        if has_digestive:
            result["symptoms"] = user_message

        # Duración por regex
        duration = self._detect_duration_fallback(user_message)
        if duration:
            result["duration"] = duration

        # Intensidad por regex
        intensity = self._detect_intensity(user_message)
        if intensity:
            result["intensity"] = intensity

        # Causas básicas
        if any(kw in norm for kw in ["frio", "calor", "lluvia", "clima"]):
            result["causa_ambiental"] = user_message
        if any(kw in norm for kw in ["estres", "ansiedad", "nervios"]):
            result["causa_emocional"] = user_message
        if any(kw in norm for kw in ["comi", "comida", "tome", "bebi"]):
            result["causa_dietetica"] = user_message

        # Condiciones sensibles
        sensitive_keywords = {
            'embarazo': ['embarazada', 'embarazo', 'gestante'],
            'lactancia': ['lactando', 'lactar', 'amamantando'],
            'diabetes': ['diabetica', 'diabetico', 'diabetes'],
            'hipertension': ['hipertensa', 'hipertenso', 'presion alta'],
        }
        for condition, keywords in sensitive_keywords.items():
            if any(kw in norm for kw in keywords):
                result["sensitive_condition"] = condition
                break

        # Negaciones contextuales — si la última pregunta era sobre causas
        last_msg_norm = _normalize(last_assistant_message) if last_assistant_message else ""
        neg_words = ['no', 'tampoco', 'nada', 'ninguna', 'no creo', 'no tengo', 'no lo se']
        is_negation = any(norm.strip() == neg or norm.startswith(neg + ' ') for neg in neg_words)

        if is_negation:
            if any(kw in last_msg_norm for kw in ['clima', 'temperatura', 'frio', 'calor', 'ambiente']):
                result["causa_ambiental"] = "no aplica"
            elif any(kw in last_msg_norm for kw in ['estres', 'ansiedad', 'nervios', 'emocional']):
                result["causa_emocional"] = "no aplica"
            elif any(kw in last_msg_norm for kw in ['comida', 'comiste', 'bebida', 'dieta', 'comi']):
                result["causa_dietetica"] = "no aplica"
            elif any(kw in last_msg_norm for kw in ['alergia', 'alergias', 'medicamento']):
                result["allergies"] = "ninguna"
            # is_confusion = False porque es una negación válida
            result["is_confusion"] = False
            
        # Alergias básicas
        if any(neg in norm for neg in ["no tengo", "ninguna", "nada", "^no$"]):
            result["allergies"] = "ninguna"

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # GENERACIÓN DE RESPUESTA
    # ─────────────────────────────────────────────────────────────────────────
    async def _generate_response(
        self,
        new_state: ConversationState,
        patient_info: Dict[str, Optional[str]],
        current_duration: Optional[str],
        last_user_message: str = "",
        last_assistant_message: str = ""
    ) -> str:

        # Verificar si hay condición sensible recién detectada
        sensitive = patient_info.get('sensitive_condition', '')
        sensitive_just_mentioned = sensitive and last_user_message and any(
            kw in _normalize(last_user_message) 
            for kw in ['embarazada', 'embarazo', 'gestante', 'lactando', 
                        'diabetic', 'diabetes', 'presion alta', 'hipertens']
        )

        if sensitive_just_mentioned:
            sensitive_responses = {
                'embarazo': (
                    "Gracias por decirme que estás embarazada, es muy importante saberlo. "
                    "Voy a ser muy cuidadoso con lo que te recomiende — solo plantas seguras para esta etapa. "
                ),
                'lactancia': (
                    "Entendido, estás lactando — eso cambia lo que puedo recomendarte. "
                    "Seré muy selectivo para proteger a tu bebé también. "
                ),
                'diabetes': (
                    "Anotado que tienes diabetes, lo tendré muy en cuenta. "
                ),
                'hipertension': (
                    "Entendido, la presión alta es un factor importante que consideraré. "
                ),
            }
            sensitive_intro = sensitive_responses.get(sensitive, "Gracias por ese dato importante. ")
        else:
            sensitive_intro = ""
            
        current_symptoms = patient_info.get('symptoms', '')

        # ── Determinar qué falta ──
        if not new_state.hasSymptoms:
            missing_topic = "síntoma digestivo"
        elif not new_state.hasDuration or self._is_vague_duration(current_duration):
            missing_topic = "duración"
        elif not new_state.hasIntensity:
            missing_topic = "intensidad"
        elif not new_state.hasCausaAmbiental:
            missing_topic = "causa_ambiental"
        elif not new_state.hasCausaEmocional:
            missing_topic = "causa_emocional"
        elif not new_state.hasCausaDietetica:
            missing_topic = "causa_dietetica"
        elif not new_state.hasAllergies:
            missing_topic = "alergias"
        else:
            return "Perfecto, ya tengo toda la información que necesito."

        topic_instructions = {
            "síntoma digestivo": "Pregunta qué molestia digestiva tiene (estómago, náuseas, diarrea, etc.)",
            "duración": "Pregunta cuánto tiempo lleva con esos síntomas. Sé específico: horas, días, semanas.",
            "intensidad": "Pregunta qué tan fuerte es el malestar, si es tolerable o muy molesto.",
            "causa_ambiental": "Pregunta si estuvo expuesto a frío, calor, lluvia u otro cambio de clima.",
            "causa_emocional": "Pregunta si ha tenido estrés, nervios o preocupaciones últimamente.",
            "causa_dietetica": "Pregunta si comió o bebió algo que pueda haber causado la molestia.",
            "alergias": (
                "Pregunta si tiene alergias a plantas o medicamentos. "
                "Indica que es la ÚLTIMA pregunta antes de dar la recomendación."
            ),
        }

        instruction = topic_instructions.get(missing_topic, "Continúa la conversación naturalmente.")


        prompt = f"""Eres Fauno, un herbolario peruano profesional y empático con años de experiencia.
Tu estilo es cálido y cercano pero SIEMPRE profesional — como un médico naturista de confianza.

SÍNTOMAS DEL PACIENTE HASTA AHORA: {current_symptoms or 'aún no definidos'}
ÚLTIMO MENSAJE DEL PACIENTE: "{last_user_message}"
ÚLTIMA PREGUNTA QUE HICISTE: "{last_assistant_message}"

REGLAS DE ORO:
1. Primero REACCIONA brevemente a lo que dijo el paciente (1 frase empática).
2. Luego haz UNA SOLA pregunta sobre: {instruction}
3. NO uses listas, NO uses bullets, NO suenes clínico.
4. Máximo 2-3 oraciones en total.
5. NUNCA uses palabras como: "hermano", "pues", "pe", "causa", "brother".
   Sé cálido pero profesional — como un naturista respetado.
6. Si la respuesta fue confusa, pide aclaración amablemente.

EJEMPLOS CORRECTOS:
- "Entiendo, ese cólico en la parte baja puede ser bastante molesto. ¿Cuánto tiempo llevas así, desde esta mañana o ya hace más días?"
- "Bien, descartamos el estrés entonces. ¿Comiste algo diferente hoy que pueda haber causado esta molestia?"
- "No te preocupes, con esa información ya puedo orientarte mejor. ¿Tienes alguna alergia a plantas o medicamentos?"

EJEMPLOS INCORRECTOS (nunca hacer esto):
- "¿Cuántos días llevas sintiendo esta acidez en los intestinos, hermano?" ❌
- "Dale pues, cuéntame más" ❌

Responde SOLO con el mensaje para el paciente:"""

        try:
            response = await self._call_groq(
                [{"role": "user", "content": prompt}],
                temperature=0.75,
                max_tokens=120
            )
            if response:
                logger.info(f"✅ LLM generó respuesta humana: {response[:80]}...")
                return response.strip()
        except Exception as e:
            logger.error(f"❌ Error en _generate_response: {e}")

        # Fallbacks humanizados
        fallbacks = {
            "síntoma digestivo": "Cuéntame, ¿qué molestia en el estómago o la barriga estás sintiendo?",
            "duración": "¿Y cuánto tiempo llevas así, desde hace unas horas o ya varios días?",
            "intensidad": "¿Qué tan fuerte es el malestar? ¿Puedes aguantarlo o está bastante molesto?",
            "causa_ambiental": "¿Has estado expuesto a frío, calor o algún cambio de clima últimamente?",
            "causa_emocional": "¿Y emocionalmente cómo andas? ¿Mucho estrés o preocupaciones?",
            "causa_dietetica": "¿Comiste algo diferente hoy, algo que te pueda haber caído mal?",
            "alergias": "Última pregunta: ¿tienes alergia a alguna planta o medicamento que deba tomar en cuenta?",
        }
        return fallbacks.get(missing_topic, "¿Puedes contarme un poco más sobre cómo te sientes?")

    

    # ─────────────────────────────────────────────────────────────────────────
    # DETECCIÓN DE EMERGENCIA
    # ─────────────────────────────────────────────────────────────────────────
    def _detect_emergency(self, message: str) -> bool:
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in EMERGENCY_KEYWORDS)

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDACIÓN DE DURACIÓN  ← CORREGIDA
    # ─────────────────────────────────────────────────────────────────────────
    def _is_vague_duration(self, duration: Optional[str]) -> bool:
        """
        Retorna True si la duración es demasiado vaga para usarse.
        
        CORRECCIÓN: ahora usa _normalize() para aceptar variantes sin tilde
        como "dias", "horas", "semanas", etc.
        """
        if not duration:
            return True  # Sin duración = inválida

        norm = _normalize(duration)

        # Expresiones aproximadas que SÍ son válidas
        acceptable_approximate = [
            'unas horas', 'un dia', 'unos dias', 'una semana',
            'un par de dias', 'desde ayer', 'desde hoy',
            # Con tilde (por si el LLM normaliza)
            'un día', 'unos días', 'un par de días',
        ]
        if any(_normalize(expr) in norm for expr in acceptable_approximate):
            return False

        # Patrones verdaderamente vagos
        vague_patterns = ['desde que', 'hace poco', 'recientemente', 'hace tiempo']
        is_vague = any(pattern in norm for pattern in vague_patterns)

        # Unidades de tiempo válidas (normalizadas, sin tilde)
        time_units = ['hora', 'horas', 'dia', 'dias', 'semana', 'semanas', 'mes', 'meses']
        has_time_unit = any(unit in norm for unit in time_units)

        # Tener la unidad de tiempo es suficiente (no exigir número)
        return is_vague or not has_time_unit

    # ─────────────────────────────────────────────────────────────────────────
    # DETECCIÓN DE SÍNTOMAS (reglas)
    # ─────────────────────────────────────────────────────────────────────────
    def _detect_symptoms(self, message: str) -> Optional[str]:
        message_lower = _normalize(message)

        digestive_symptoms = {
            'dolor abdominal': [
                'estomago', 'vientre', 'barriga', 'abdomen', 'panza',
                'abdominal', 'gastritis', 'colitis', 'intestino', 'tripas'
            ],
            'dolor pelvico': ['pelvico', 'pelvis', 'bajo vientre', 'zona pelvica'],
            'nauseas': [
                'nausea', 'nauseas', 'mareo estomacal',
                'ganas de vomitar', 'asco', 'malestar estomacal'
            ],
            'vomito': ['vomito', 'vomitar', 'devolver', 'arrojar'],
            'acidez': ['acidez', 'agruras', 'reflujo', 'ardor estomacal', 'acido'],
            'flatulencia': [
                'flatulencia', 'gases', 'inflado', 'hinchado', 'distension',
                'inflamacion abdominal', 'abdomen hinchado'
            ],
            'diarrea': [
                'diarrea', 'suelta', 'descompostura', 'evacuaciones liquidas',
                'deposiciones frecuentes'
            ],
            'estrenimiento': [
                'estrenimiento', 'estrenido', 'constipacion', 'no evacuo',
                'dificultad para defecar'
            ],
            'incontinencia fecal': ['incontinencia fecal', 'no controlo', 'escape de heces'],
            'sonidos intestinales': [
                'ruidos', 'borborigmos', 'sonidos intestinales', 'gruñe la panza',
                'estomago hace ruido'
            ],
            'indigestion': ['indigestion', 'digestion pesada', 'empachado', 'pesadez']
        }

        detected = []
        for symptom_type, keywords in digestive_symptoms.items():
            if any(kw in message_lower for kw in keywords):
                detected.append(symptom_type)

        if not detected:
            return None

        if len(detected) == 1:
            return detected[0]
        elif len(detected) == 2:
            return f"{detected[0]} y {detected[1]}"
        else:
            return ", ".join(detected[:-1]) + f" y {detected[-1]}"

    # ─────────────────────────────────────────────────────────────────────────
    # OUT-OF-SCOPE (reglas)
    # ─────────────────────────────────────────────────────────────────────────
    def _is_out_of_scope(self, message: str) -> Tuple[bool, Optional[str]]:
        message_lower = _normalize(message)

        non_digestive_body_parts = {
            'cabeza y cara': ['cabeza', 'migrana', 'cefalea', 'jaqueca', 'oreja', 'oido', 'ojo', 'vista', 'nariz', 'diente', 'muela', 'encia'],
            'extremidades superiores': ['brazo', 'mano', 'muneca', 'dedo', 'codo', 'hombro'],
            'extremidades inferiores': ['pierna', 'rodilla', 'tobillo', 'pie', 'cadera', 'muslo', 'pantorrilla'],
            'espalda y columna': ['espalda', 'columna', 'lumbar', 'cervical'],
            'pecho y respiratorio': ['pecho', 'pulmon', 'corazon', 'costilla'],
            'piel': ['piel', 'sarpullido', 'picazon', 'ronchas', 'dermatitis', 'mancha'],
            'otros': ['articulacion', 'hueso', 'musculo', 'tendon']
        }

        non_digestive_symptoms = {
            'respiratorio': ['gripe', 'resfriado', 'tos', 'garganta', 'catarro', 'congestion', 'mocos', 'flema'],
            'fiebre': ['fiebre', 'calentura', 'temperatura alta'],
            'otros': ['mareo general', 'vertigo', 'desmayo', 'cansancio extremo', 'debilidad']
        }

        detected_category = None
        detected_part = None

        for category, parts in non_digestive_body_parts.items():
            for part in parts:
                if part in message_lower:
                    detected_category = category
                    detected_part = part
                    break
            if detected_category:
                break

        if not detected_category:
            for category, symptoms in non_digestive_symptoms.items():
                for symptom in symptoms:
                    if symptom in message_lower:
                        detected_category = category
                        detected_part = symptom
                        break
                if detected_category:
                    break

        if detected_category and detected_part:
            intelligent_response = self._generate_intelligent_out_of_scope_response(detected_part, detected_category)
            return True, intelligent_response

        return False, None

    # ─────────────────────────────────────────────────────────────────────────
    # DETECCIÓN DE DURACIÓN (reglas — backup)
    # ─────────────────────────────────────────────────────────────────────────
    def _detect_duration_fallback(self, message: str) -> Optional[str]:
        """
        Extracción por regex como respaldo al LLM.
        Normaliza antes de buscar para aceptar variantes sin tilde.
        """
        norm = _normalize(message)

        patterns = [
            (r'hace\s+(\d+)\s*(hora|horas|dia|dias|semana|semanas|mes|meses)', '{} {}'),
            (r'(\d+)\s*(hora|horas|dia|dias|semana|semanas|mes|meses)', '{} {}'),
            (r'desde\s+ayer', '1 día'),
            (r'desde\s+hoy', 'unas horas'),
            (r'desde\s+esta\s+ma[ñn]ana', 'unas horas'),
            (r'un\s+par\s+de\s+dias', '2 días'),
            (r'unas\s+horas', 'unas horas'),
        ]

        for pattern, template in patterns:
            match = re.search(pattern, norm)
            if match:
                if '{}' in template:
                    # Normalizar unidades al plural con tilde
                    unit_map = {
                        'hora': 'hora', 'horas': 'horas',
                        'dia': 'día', 'dias': 'días',
                        'semana': 'semana', 'semanas': 'semanas',
                        'mes': 'mes', 'meses': 'meses',
                    }
                    number = match.group(1)
                    unit_raw = match.group(2)
                    unit = unit_map.get(unit_raw, unit_raw)
                    return f"{number} {unit}"
                else:
                    return template

        return None

    def _detect_intensity(self, message: str) -> Optional[str]:
        norm = _normalize(message)

        if any(word in norm for word in ['masomenos', 'mas o menos', 'regular', 'medio']):
            return 'moderado'

        intensity_patterns = {
            'leve': ['leve', 'poco', 'tolerable', 'suave', 'ligero'],
            'moderado': ['moderado'],
            'severo': ['severo', 'fuerte', 'intenso', 'insoportable', 'mucho', 'bastante']
        }

        for intensity, patterns in intensity_patterns.items():
            if any(pattern in norm for pattern in patterns):
                return intensity

        return None

    def _detect_plant_selection_after_recommendations(self, message: str, current_state: ConversationState) -> bool:
        if not current_state.hasReceivedRecommendations:
            return False
        message_lower = message.lower().strip()
        known_plants = [
            'menta', 'manzanilla', 'hierba luisa', 'muña', 'uña de gato',
            'eucalipto', 'matico', 'boldo', 'salvia'
        ]
        for plant in known_plants:
            if message_lower == plant or message_lower == f"la {plant}":
                return True
        return message_lower in ['1', '2', '3']

    def _extract_plant_name(self, message: str) -> Optional[str]:
        message_lower = message.lower().strip()
        if message_lower in ["luisa", "la luisa"]:
            return "hierba luisa"
        known_plants = [
            'menta', 'manzanilla', 'hierba luisa', 'muña', 'uña de gato',
            'eucalipto', 'matico', 'boldo', 'salvia'
        ]
        for plant in known_plants:
            if message_lower == plant or message_lower == f"la {plant}":
                return plant
        return None

    def _validate_allergy_response(self, message: str) -> Tuple[bool, Optional[str]]:
        message_lower = _normalize(message).strip()

        negative_patterns = [
            r'^no$', r'^nop$', r'^nope$', r'^ninguna$', r'^nada$',
            r'^no tengo$', r'^no aplica$', r'^no hay$', r'^no\s*$',
            r'^sin alergias$', r'^ninguna alergia$', r'^no\.$', r'^nop\.$'
        ]
        for pattern in negative_patterns:
            if re.match(pattern, message_lower):
                return True, "ninguna"

        if message_lower.startswith('no ') and len(message_lower) < 20:
            return True, "ninguna"

        if message_lower in ['no.', 'nop.', 'nope.']:
            return True, "ninguna"

        yes_patterns = [
            r'soy alergico a (.+)',
            r'tengo alergia a (.+)',
            r'alergia a (.+)',
            r'alergico a (.+)',
            r'soy sensible a (.+)',
            r'reacciono a (.+)'
        ]
        for pattern in yes_patterns:
            match = re.search(pattern, message_lower)
            if match:
                allergy = match.group(1).strip().rstrip('.')
                return True, allergy

        short_allergies = ['penicilina', 'aspirina', 'ibuprofeno', 'paracetamol', 'sulfas', 'latex', 'polen']
        for allergy in short_allergies:
            if allergy in message_lower:
                return True, allergy

        if len(message_lower) < 20 and not any(word in message_lower for word in ['si', 'tengo']):
            logger.info(f"   ⚠️ Respuesta corta no reconocida, tratando como 'ninguna': '{message_lower}'")
            return True, "ninguna"

        logger.warning(f"   ❌ Respuesta de alergias no reconocida: '{message_lower}'")
        return False, None

    def _validate_cause_response(self, message: str, cause_type: str) -> Tuple[bool, Optional[str]]:
        message_lower = _normalize(message).strip()

        affirmative_patterns = [
            'si', 'yes', 'claro', 'exacto', 'correcto', 'afirmativo',
            'sep', 'see', 'simon', 'aja', 'dale'
        ]
        if message_lower in affirmative_patterns:
            return True, "sí"

        if any([
            message_lower.startswith('no'),
            message_lower in ['nel', 'nah', 'ninguno', 'ninguna', 'nada'],
            'no aplica' in message_lower,
            'no creo' in message_lower,
            'creo que no' in message_lower
        ]):
            return True, "no aplica"

        if 'no te dije' in message_lower or 'ya te dije' in message_lower:
            return True, "no aplica"

        if message_lower.startswith('si '):
            return True, message_lower.strip()

        cause_keywords = {
            'ambiental': ['frio', 'calor', 'clima', 'mojado', 'lluvia', 'sol', 'temperatura', 'aire', 'viento',
                          'expuesto', 'exposicion', 'cambio', 'helado', 'congelado',
                          'solo sentia', 'sentia frio', 'hacia frio'],
            'emocional': ['estres', 'ansiedad', 'nervios', 'preocupado', 'triste', 'angustia', 'tension', 'presion'],
            'dietetica': ['comida', 'comi', 'tome', 'picante', 'bebi', 'cena', 'almuerzo', 'desayuno',
                          'lactea', 'helado', 'grasa', 'alcohol']
        }

        for keyword in cause_keywords.get(cause_type, []):
            if keyword in message_lower:
                return True, message_lower.strip()

        if len(message_lower) > 10 and not any(neg in message_lower for neg in ['no', 'ninguna', 'ninguno', 'nada']):
            return True, message_lower.strip()

        logger.warning(f"   ⚠️ Causa {cause_type}: respuesta no reconocida '{message}'")
        return False, None

    # ─────────────────────────────────────────────────────────────────────────
    # LLAMADA A GROQ
    # ─────────────────────────────────────────────────────────────────────────
    async def _call_groq(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 150
    ) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Error con Groq: {str(e)}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # PROCESO PRINCIPAL  ← CORREGIDO
    # ─────────────────────────────────────────────────────────────────────────
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        current_state: ConversationState,
        patient_info: Dict[str, Optional[str]]
    ) -> ProcessChatResponse:

        try:
            logger.info("=" * 80)
            logger.info(f"🗣️ MENSAJE: '{user_message}'")
            logger.info(f"📊 ESTADO ACTUAL: symptoms={current_state.hasSymptoms} "
                        f"duration={current_state.hasDuration} intensity={current_state.hasIntensity} "
                        f"ambiental={current_state.hasCausaAmbiental} emocional={current_state.hasCausaEmocional} "
                        f"dietetica={current_state.hasCausaDietetica} alergias={current_state.hasAllergies} "
                        f"clarif={current_state.inClarificationMode}(step={current_state.clarificationStep})")
            logger.info("=" * 80)

            # 1. OBTENER ÚLTIMO MENSAJE DEL BOT
            last_assistant_message = ""
            if conversation_history:
                for msg in reversed(conversation_history):
                    if msg.get("role") == "assistant":
                        last_assistant_message = msg.get("content", "")
                        break

            # 2. EXTRAER CON LLM PRIMERO — siempre, para todo
            llm_extracted = await self._extract_with_llm(
                user_message,
                patient_info,
                last_assistant_message
            )

            # 3. EMERGENCIA
            if llm_extracted.get("is_emergency"):
                return ProcessChatResponse(
                    assistant_response="🚨 ALERTA: Llama al 117 (SAMU) inmediatamente.",
                    conversation_state=current_state,
                    is_emergency=True
                )

            # 4. OUT OF SCOPE — solo si no estamos en medio de una consulta activa
            if llm_extracted.get("is_out_of_scope") and not current_state.hasSymptoms:
                part = llm_extracted.get("out_of_scope_part", "ese síntoma")
                response = self._generate_intelligent_out_of_scope_response(part, "general")
                return ProcessChatResponse(
                    assistant_response=response,
                    conversation_state=current_state
                )
            
            # 4.5 MANEJAR CONFUSIÓN DEL USUARIO
            if llm_extracted.get("is_confusion"):
                logger.info("💬 Usuario confundido, explicando...")
                
                # Generar explicación basada en el último mensaje del bot
                confusion_prompt = f"""Eres Fauno, un herbolario peruano empático.

            El paciente no entendió tu último mensaje: "{last_assistant_message}"
            El paciente respondió: "{user_message}"

            Explica de forma más simple y clara lo que preguntaste antes.
            - Máximo 2 oraciones
            - Muy sencillo y directo
            - Si no había pregunta clara antes, explica brevemente qué información necesitas

            Responde SOLO con el mensaje:"""

                try:
                    explanation = await self._call_groq(
                        [{"role": "user", "content": confusion_prompt}],
                        temperature=0.6,
                        max_tokens=80
                    )
                    if explanation:
                        return ProcessChatResponse(
                            assistant_response=explanation.strip(),
                            conversation_state=current_state,
                            extracted_info=None,
                            patient_info=patient_info,
                            is_emergency=False
                        )
                except Exception as e:
                    logger.error(f"Error manejando confusión: {e}")
                
                # Fallback si falla el LLM
                return ProcessChatResponse(
                    assistant_response="Perdona si no me expliqué bien. Lo que necesito saber es: ¿qué molestia digestiva tienes? Por ejemplo, dolor de estómago, náuseas, diarrea, acidez...",
                    conversation_state=current_state,
                    extracted_info=None,
                    patient_info=patient_info,
                    is_emergency=False
                )
        
            # 5. POBLAR ExtractedInfo
            extracted = ExtractedInfo(
                symptoms=llm_extracted.get("symptoms"),
                duration=llm_extracted.get("duration"),
                intensity=llm_extracted.get("intensity"),
                causa_ambiental=llm_extracted.get("causa_ambiental"),
                causa_emocional=llm_extracted.get("causa_emocional"),
                causa_dietetica=llm_extracted.get("causa_dietetica"),
                allergies=llm_extracted.get("allergies"),
            )

            session_id = patient_info.get('session_id', 'unknown')

            # 5.5 PROCESAR CONDICIÓN SENSIBLE DETECTADA POR LLM
            sensitive_condition = llm_extracted.get("sensitive_condition")
            if sensitive_condition:
                patient_info['sensitive_condition'] = sensitive_condition
                logger.info(f"⚠️ Condición sensible detectada por LLM: {sensitive_condition}")
                
                # Si además trajo datos de alergias u otros campos, los procesamos igual
                # No interrumpimos el flujo — simplemente guardamos y continuamos
                # El mensaje sensible se generará en _generate_response si corresponde
                
            # 6. PRIMER SÍNTOMA — ahora validado por LLM, no por reglas
            if not current_state.hasSymptoms:
                if not extracted.symptoms:
                    # LLM no encontró síntoma digestivo
                    if session_id not in self.failed_symptom_attempts:
                        self.failed_symptom_attempts[session_id] = 0
                    self.failed_symptom_attempts[session_id] += 1
                    attempts = self.failed_symptom_attempts[session_id]

                    logger.warning(f"⚠️ Intento #{attempts} sin síntoma digestivo (validado por LLM)")

                    if attempts >= 2:
                        return ProcessChatResponse(
                            assistant_response=(
                                "⚠️ **Parece que no mencionas síntomas digestivos**\n\n"
                                "Solo puedo ayudarte con síntomas del sistema digestivo.\n\n"
                                "¿Tienes dolor de estómago, náuseas, diarrea, acidez, gases u otro síntoma digestivo?"
                            ),
                            conversation_state=current_state,
                            is_emergency=False
                        )
                    else:
                        return ProcessChatResponse(
                            assistant_response=(
                                "Hola, para poder ayudarte necesito que me cuentes sobre **síntomas digestivos**.\n\n"
                                "Por ejemplo: dolor de estómago, náuseas, acidez, diarrea, gases, etc.\n\n"
                                "¿Qué molestia digestiva tienes?"
                            ),
                            conversation_state=current_state,
                            is_emergency=False
                        )
                else:
                    # LLM confirmó síntoma digestivo — iniciar clarificación
                    if session_id in self.failed_symptom_attempts:
                        del self.failed_symptom_attempts[session_id]

                    detail_prompt = f"""Eres un asistente médico empático especializado en plantas medicinales peruanas.

    El paciente acaba de decir que tiene: {extracted.symptoms}

    Genera UNA sola pregunta muy corta para saber únicamente:
    ¿DÓNDE exactamente siente la molestia?

    Ejemplos de respuesta esperada: "en la parte baja", "arriba del estómago", "al lado derecho"

    Máximo 1 oración, muy conversacional, en español peruano.
    Responde SOLO la pregunta:"""

                    detail_question = await self._call_groq(
                        [{"role": "user", "content": detail_prompt}],
                        temperature=0.7,
                        max_tokens=80
                    )

                    if not detail_question:
                        detail_question = (
                            "¿Puedes describirme dónde exactamente sientes la molestia "
                            "(parte alta, baja, lado derecho)?"
                        )

                    extracted_info_early = {'symptoms': extracted.symptoms}
                    complete_patient_info_early = patient_info.copy()
                    complete_patient_info_early.update(extracted_info_early)

                    early_state = ConversationState(
                        hasSymptoms=True,
                        hasDuration=current_state.hasDuration,
                        hasAllergies=current_state.hasAllergies,
                        hasIntensity=current_state.hasIntensity,
                        hasCausaAmbiental=current_state.hasCausaAmbiental,
                        hasCausaEmocional=current_state.hasCausaEmocional,
                        hasCausaDietetica=current_state.hasCausaDietetica,
                        isComplete=False,
                        hasReceivedRecommendations=current_state.hasReceivedRecommendations,
                        needsEmergencyCheck=current_state.needsEmergencyCheck,
                        inClarificationMode=True,
                        clarificationStep=0,
                        selectedPlant=current_state.selectedPlant
                    )

                    logger.info(f"✅ Síntoma detectado por LLM: '{extracted.symptoms}', iniciando clarificación...")
                    return ProcessChatResponse(
                        assistant_response=detail_question,
                        conversation_state=early_state,
                        extracted_info=extracted_info_early,
                        patient_info=complete_patient_info_early,
                        is_emergency=False,
                        has_recommendations=False,
                        recommendations=None
                    )

            # 7. FALLBACK DE DURACIÓN si LLM no extrajo
            if not extracted.duration:
                fallback_duration = self._detect_duration_fallback(user_message)
                if fallback_duration:
                    extracted.duration = fallback_duration
                    logger.info(f"✅ Duración por FALLBACK regex: '{fallback_duration}'")

            # 8. FALLBACK DE INTENSIDAD si LLM no extrajo
            if not extracted.intensity:
                fallback_intensity = self._detect_intensity(user_message)
                if fallback_intensity:
                    extracted.intensity = fallback_intensity
                    logger.info(f"✅ Intensidad por FALLBACK regex: '{fallback_intensity}'")

            # 8.5 DETECTAR CONDICIONES SENSIBLES (embarazo, lactancia, etc.)
            sensitive_msg = self._detect_sensitive_conditions(user_message, patient_info)
            if sensitive_msg:
                logger.info(f"⚠️ Condición sensible detectada: {patient_info.get('sensitive_condition')}")
                return ProcessChatResponse(
                    assistant_response=sensitive_msg,
                    conversation_state=current_state,   # ← usar current_state, no new_state
                    extracted_info=None,                # ← no hay extracted_info aún
                    patient_info=patient_info,          # ← usar patient_info directo
                    is_emergency=False,
                    has_recommendations=False,
                    recommendations=None
                )

            # 9. ACUMULACIÓN DE SÍNTOMAS EN MODO CLARIFICACIÓN — con validación
            if current_state.inClarificationMode:
                current_symptoms = patient_info.get('symptoms', '')
                detail_text = llm_extracted.get("symptoms")

                # ── Validar que la respuesta del usuario tiene sentido ──
                user_msg_clean = user_message.strip()
                is_meaningful = (
                    len(user_msg_clean) >= 3 and          # al menos 3 caracteres
                    detail_text is not None and            # LLM extrajo algo
                    not llm_extracted.get("is_out_of_scope", False)  # no es fuera de alcance
                )

                if is_meaningful:
                    # Acumular solo si es info nueva
                    if current_symptoms and detail_text and detail_text.lower() not in current_symptoms.lower():
                        extracted.symptoms = f"{current_symptoms}, {detail_text}"
                    else:
                        extracted.symptoms = current_symptoms or detail_text
                    logger.info(f"✅ Síntomas enriquecidos (step {current_state.clarificationStep}): '{extracted.symptoms}'")
                else:
                    # Respuesta sin sentido — mantener síntomas anteriores sin acumular basura
                    extracted.symptoms = current_symptoms
                    logger.warning(f"⚠️ Respuesta poco clara '{user_message}', manteniendo síntomas anteriores: '{current_symptoms}'")

            # 10. CALCULAR SIGUIENTE ESTADO DE CLARIFICACIÓN
            if current_state.inClarificationMode:
                next_step = current_state.clarificationStep + 1
                still_clarifying = next_step < 4
                next_clarification_step = next_step if still_clarifying else 0
            else:
                still_clarifying = False
                next_clarification_step = 0

            # 11. ACTUALIZAR ESTADO
            merged_duration = (
                extracted.duration
                or patient_info.get('duration')
                or patient_info.get('duracion')
            )
            duration_is_valid = bool(merged_duration) and not self._is_vague_duration(merged_duration)

            new_state = ConversationState(
                hasSymptoms=current_state.hasSymptoms or bool(extracted.symptoms),
                hasDuration=current_state.hasDuration or duration_is_valid,
                hasAllergies=(
                    current_state.hasAllergies or
                    (extracted.allergies is not None and extracted.allergies != "")
                ),
                hasIntensity=current_state.hasIntensity or bool(extracted.intensity),
                hasCausaAmbiental=current_state.hasCausaAmbiental or (extracted.causa_ambiental is not None),
                hasCausaEmocional=current_state.hasCausaEmocional or (extracted.causa_emocional is not None),
                hasCausaDietetica=current_state.hasCausaDietetica or (extracted.causa_dietetica is not None),
                isComplete=False,
                hasReceivedRecommendations=current_state.hasReceivedRecommendations,
                needsEmergencyCheck=current_state.needsEmergencyCheck,
                inClarificationMode=still_clarifying,
                clarificationStep=next_clarification_step,
                selectedPlant=current_state.selectedPlant
            )

            if extracted.allergies is not None:
                new_state.hasAllergies = True
                logger.info(f"✅ Alergias CONFIRMADAS por LLM: '{extracted.allergies}'")

            # 12. VALIDAR COMPLETITUD
            merged_duration = (
                extracted.duration
                or patient_info.get('duration')
                or patient_info.get('duracion')
            )
            current_allergies = patient_info.get('allergies') or extracted.allergies
            allergies_valid = new_state.hasAllergies and current_allergies is not None and current_allergies != ""

            logger.info(
                f"🔍 COMPLETITUD:\n"
                f"   hasSymptoms={new_state.hasSymptoms}\n"
                f"   hasDuration={new_state.hasDuration} (valor='{merged_duration}', válida={duration_is_valid})\n"
                f"   hasIntensity={new_state.hasIntensity}\n"
                f"   hasCausaAmbiental={new_state.hasCausaAmbiental}\n"
                f"   hasCausaEmocional={new_state.hasCausaEmocional}\n"
                f"   hasCausaDietetica={new_state.hasCausaDietetica}\n"
                f"   hasAllergies={new_state.hasAllergies} (válida={allergies_valid})"
            )

            new_state.isComplete = (
                new_state.hasSymptoms and
                new_state.hasDuration and
                new_state.hasIntensity and
                new_state.hasCausaAmbiental and
                new_state.hasCausaEmocional and
                new_state.hasCausaDietetica and
                new_state.hasAllergies
            )

            # 13. GENERAR RESPUESTA
            if new_state.isComplete:
                assistant_response = (
                    "Perfecto, ya tengo toda la información. "
                    "Voy a buscar las mejores plantas medicinales para ti. 🌿"
                )
                new_state.hasReceivedRecommendations = True
            else:
                assistant_response = await self._generate_response(
                    new_state,
                    patient_info,
                    merged_duration,
                    last_user_message=user_message,           # ← NUEVO
                    last_assistant_message=last_assistant_message  # ← NUEVO
                )

            # 14. PREPARAR extracted_info
            extracted_info: Dict[str, Any] = {}

            if extracted.symptoms:
                extracted_info['symptoms'] = extracted.symptoms
            if extracted.duration and not self._is_vague_duration(extracted.duration):
                extracted_info['duration'] = extracted.duration
            if extracted.allergies is not None:
                extracted_info['allergies'] = extracted.allergies
                logger.info(f"✅ Enviando alergias: '{extracted.allergies}'")
            if extracted.intensity:
                extracted_info['intensidad_sintomas'] = extracted.intensity
            if extracted.causa_ambiental is not None:
                extracted_info['causa_ambiental'] = extracted.causa_ambiental
            if extracted.causa_emocional is not None:
                extracted_info['causa_emocional'] = extracted.causa_emocional
            if extracted.causa_dietetica is not None:
                extracted_info['causa_dietetica'] = extracted.causa_dietetica

            # 15. CONSTRUIR patient_info COMPLETO
            complete_patient_info = patient_info.copy()
            if extracted_info:
                complete_patient_info.update(extracted_info)

            defaults = {
                'symptoms': '', 'duration': '', 'allergies': '',
                'intensidad_sintomas': '', 'causa_ambiental': '',
                'causa_emocional': '', 'causa_dietetica': ''
            }
            for field, default in defaults.items():
                if field not in complete_patient_info or complete_patient_info[field] is None:
                    complete_patient_info[field] = default

            if new_state.isComplete:
                if not complete_patient_info.get('allergies'):
                    complete_patient_info['allergies'] = 'ninguna'
                if not complete_patient_info.get('intensidad_sintomas'):
                    complete_patient_info['intensidad_sintomas'] = 'moderado'
                for field in ['symptoms', 'duration', 'causa_ambiental', 'causa_emocional', 'causa_dietetica']:
                    if not complete_patient_info.get(field):
                        complete_patient_info[field] = 'no especificado'
                logger.info(f"📋 Patient info COMPLETO: {complete_patient_info}")

            logger.info(f"📦 Extraído: {extracted_info}")
            logger.info(f"💬 Respuesta: '{assistant_response}'")

            return ProcessChatResponse(
                assistant_response=assistant_response,
                conversation_state=new_state,
                extracted_info=extracted_info if extracted_info else None,
                patient_info=complete_patient_info,
                is_emergency=False,
                has_recommendations=new_state.isComplete,
                recommendations=None
            )

        except Exception as e:
            logger.error(f"❌ ERROR: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return ProcessChatResponse(
                assistant_response="Error procesando tu mensaje. ¿Puedes repetir?",
                conversation_state=current_state,
                is_emergency=False
            )

    async def _generate_pre_recommendation_message(
        self, 
        patient_info: Dict,
        last_user_message: str = ""
    ) -> str:
        """
        Genera un mensaje humano ANTES de las recomendaciones,
        considerando el contexto del paciente.
        """
        symptoms = patient_info.get('symptoms', '')
        intensity = patient_info.get('intensidad_sintomas', 'moderado')
        sensitive = patient_info.get('sensitive_condition', '')
        
        # Contexto especial por condición sensible
        sensitivity_note = ""
        if sensitive == 'embarazo':
            sensitivity_note = "Recuerda que estás embarazada, así que voy a priorizarte plantas completamente seguras para esta etapa. Aun así, siempre consulta con tu médico antes de tomar cualquier cosa."
        elif sensitive == 'lactancia':
            sensitivity_note = "Considerando que estás lactando, te sugeriré opciones muy suaves y seguras."
        elif sensitive == 'diabetes':
            sensitivity_note = "Teniendo en cuenta tu diabetes, las opciones que te doy son compatibles con esa condición."
            
        intensity_comment = {
            'leve': "como tu malestar es leve, con algo suave debería bastar",
            'moderado': "con un tratamiento adecuado deberías sentirte mejor pronto",
            'severo': "entiendo que estás bastante incómodo/a, vamos a atacar esto bien"
        }.get(str(intensity).lower(), "vamos a ver qué te viene mejor")

        prompt = f"""Eres Fauno, un herbolario peruano empático y sabio.

    SÍNTOMAS DEL PACIENTE: {symptoms}
    INTENSIDAD: {intensity}
    ÚLTIMO MENSAJE DEL PACIENTE: "{last_user_message}"
    CONDICIÓN ESPECIAL: {sensitive or 'ninguna'}
    NOTA DE SEGURIDAD: {sensitivity_note or 'ninguna'}

    Genera un mensaje corto (2-3 oraciones) que:
    1. Haga un breve comentario empático sobre lo que el paciente acaba de decir o sobre su situación general
    2. Anuncie de forma natural que vas a dar las recomendaciones de plantas
    3. Si hay condición especial (embarazo, etc.), menciona brevemente que lo tuviste en cuenta
    4. NO menciones las plantas aún — eso viene después
    5. Tono: cálido, como un herbolario de confianza, no clínico

    Ejemplos del tono correcto:
    - "Gracias por contarme todo eso. Con lo que me describes — ese cólico constante de 3 horas — ya tengo claro qué plantas pueden ayudarte. Déjame mostrarte las mejores opciones para tu caso."
    - "Perfecto, ya tengo todo lo que necesito saber. Y tranquila con lo del embarazo, voy a elegir solo lo que es seguro para ti y tu bebé."
    - "Bien, con esa información ya puedo orientarte. {intensity_comment.capitalize()}, así que te traigo lo mejor."

    Responde SOLO con el mensaje, sin etiquetas ni explicaciones:"""

        try:
            response = await self._call_groq(
                [{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=100
            )
            if response:
                return response.strip()
        except Exception as e:
            logger.error(f"Error generando pre-recomendación: {e}")
        
        # Fallback humanizado
        if sensitive == 'embarazo':
            return "Ya tengo todo lo que necesito. Y no te preocupes — voy a elegir solo plantas seguras para esta etapa de tu embarazo. Aquí están mis recomendaciones:"
        
        return f"Listo, ya tengo una idea clara de lo que te pasa. {intensity_comment.capitalize()}, aquí están las plantas que te recomiendo:"

    async def generate_welcome_message(self) -> str:
        prompt = """Eres Fauno, un herbolario peruano cercano y empático.

    Genera UN mensaje de bienvenida corto para un paciente nuevo.
    REGLAS ESTRICTAS:
    - Máximo 2 oraciones, no más
    - Preséntate como Fauno, herbolario especializado en plantas digestivas
    - Invita a que cuente su malestar
    - Tono cálido y simple, nada filosófico ni poético
    - NO uses palabras como "equilibrio", "armonía", "espíritu", "raíz del problema"

    Ejemplo del tono correcto:
    "¡Hola! Soy Fauno, tu herbolario de confianza. Cuéntame qué molestia en el estómago o la digestión te trae por acá."

    Responde SOLO con el mensaje:"""

        try:
            response = await self._call_groq(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=60,  # limitado para forzar brevedad
            )
            if response and len(response.strip()) > 10:
                return response.strip()
        except Exception as e:
            logger.error(f"Error generando bienvenida: {e}")

        import random
        fallbacks = [
            "¡Hola! Soy Fauno, tu herbolario de confianza. ¿Qué molestia en el estómago o la digestión te trae por acá?",
            "¡Hola! Me llamo Fauno y me especializo en plantas digestivas. ¿Qué síntoma tienes hoy?",
            "¡Buenas! Soy Fauno, herbolario peruano. Cuéntame qué molestia digestiva tienes.",
        ]
        return random.choice(fallbacks)

conversation_agent = NaturalConversationAgent()