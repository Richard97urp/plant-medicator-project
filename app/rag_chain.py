from datetime import datetime
import os
import uuid
import asyncio
import json
import psycopg2
import traceback
from typing import Dict, Any, Optional, List, Tuple
import logging
import re
from dotenv import load_dotenv
import os

load_dotenv()  # Carga el contenido de .env automáticamente

openai_api_key = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ========== NUEVAS FUNCIONES DE EVALUACIÓN DE RIESGO ==========

def evaluar_riesgo_critico(patient_info: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    🚨 EVALUACIÓN CRÍTICA DE RIESGO - PRIMERA LÍNEA DE DEFENSA
    
    Returns:
        (es_critico, nivel_riesgo, mensaje_derivacion)
    """
    symptoms = patient_info.get('symptoms', '').lower()
    age = patient_info.get('age', 0)
    duration = patient_info.get('duration', '').lower()
    gender = patient_info.get('gender', '')
    allergies = patient_info.get('allergies', '').lower()
    
    # 🚨 SÍNTOMAS CRÍTICOS - DERIVACIÓN INMEDIATA
    critical_symptoms = [
        # Cardiovasculares
        r'dolor.*pecho.*irradia|dolor.*brazo.*izquierdo|opresión.*pecho',
        r'dolor.*mandíbula.*sudoración|dolor.*cuello.*mareo',
        
        # Respiratorios
        r'dificultad.*respirar.*sever|falta.*aire.*reposo|ahogo.*extremo',
        r'labios.*azules|cianosis|respiración.*muy.*rápida',
        
        # Neurológicos
        r'pérdida.*conciencia|desmayo.*repetido|convulsiones?',
        r'dolor.*cabeza.*súbito.*intenso|cefalea.*trueno',
        r'confusión.*mental.*aguda|desorientación.*severa',
        
        # Gastrointestinales
        r'vómito.*sangre|heces.*negras.*alquitranadas',
        r'sangrado.*que.*no.*para|hemorragia',
        
        # Febriles críticos
        r'fiebre.*39|temperatura.*39|40.*grados',
        r'rigidez.*cuello.*fiebre|manchas.*piel.*fiebre'
    ]
    
    for pattern in critical_symptoms:
        if re.search(pattern, symptoms, re.IGNORECASE):
            return True, "CRÍTICO", f"""
🚨 **ATENCIÓN MÉDICA INMEDIATA NECESARIA** 🚨

Los síntomas que describes requieren evaluación médica urgente.
**NO es seguro usar plantas medicinales en este momento.**

**Por favor:**
- Acude INMEDIATAMENTE a emergencias
- Llama al 117 (SAMU) si es necesario
- No retrases la atención médica

**Este sistema no puede ayudarte con síntomas que pueden ser de emergencia.**
            """
    
    # 👥 POBLACIONES DE ALTO RIESGO
    try:
        age_int = int(age) if str(age).isdigit() else 0
    except:
        age_int = 0
    
    # Menores de 2 años - BLOQUEO ABSOLUTO
    if age_int < 2 and age_int > 0:
        return True, "ALTO_RIESGO", f"""
👶 **ATENCIÓN: MENOR DE 2 AÑOS**

**Las plantas medicinales NO son seguras para menores de 2 años.**

**Por favor:**
- Consulta SIEMPRE con pediatra
- Llama al centro de salud más cercano
- No uses remedios caseros en bebés

**Este sistema no puede proporcionar recomendaciones para esta edad.**
        """
    
    # Embarazadas con síntomas complejos
    if 'embaraza' in patient_info.get('additional_info', '').lower() or 'gestante' in symptoms:
        high_risk_pregnancy = any([
            'sangrado' in symptoms, 'dolor' in symptoms and 'abdomen' in symptoms,
            'fiebre' in symptoms, 'vómito' in symptoms and 'severo' in symptoms
        ])
        
        if high_risk_pregnancy:
            return True, "EMBARAZO_RIESGO", f"""
🤱 **EMBARAZO CON SÍNTOMAS DE RIESGO**

**Durante el embarazo, estos síntomas requieren atención médica.**

**Por favor:**
- Contacta a tu obstetra inmediatamente
- Acude a control prenatal urgente
- Evita automedicación con plantas

**Este sistema no puede ayudarte durante el embarazo con estos síntomas.**
            """
    
    # Adultos mayores con síntomas múltiples
    if age_int > 75:
        complex_symptoms = len([s for s in ['dolor', 'fiebre', 'mareo', 'debilidad', 'confusión'] 
                               if s in symptoms]) >= 2
        if complex_symptoms:
            return True, "ADULTO_MAYOR_RIESGO", f"""
👴 **ADULTO MAYOR CON SÍNTOMAS MÚLTIPLES**

**Los síntomas combinados en adultos mayores requieren evaluación médica.**

**Por favor:**
- Consulta con tu médico de cabecera
- Considera acudir a emergencias si empeora
- Las plantas pueden interactuar con medicamentos

**Recomendamos evaluación médica antes de usar plantas medicinales.**
            """
    
    # ⏰ DURACIÓN PROLONGADA SIN MEJORA
    duration_patterns = [
        r'(\d+).*semanas?', r'(\d+).*meses?', r'más.*de.*(\d+).*días?',
        r'hace.*(\d+).*semanas?', r'desde.*hace.*(\d+).*días?'
    ]
    
    days_duration = 0
    for pattern in duration_patterns:
        match = re.search(pattern, duration)
        if match:
            num = int(match.group(1))
            if 'semana' in pattern:
                days_duration = num * 7
            elif 'mes' in pattern:  
                days_duration = num * 30
            else:
                days_duration = num
            break
    
    if days_duration > 14:
        return True, "CRONICO", f"""
⏰ **SÍNTOMAS PROLONGADOS (>{days_duration} días)**

**Los síntomas que duran más de 2 semanas sin mejora necesitan evaluación médica.**

**Posibles razones:**
- Condición que requiere tratamiento específico
- Complicaciones no detectadas
- Necesidad de diagnóstico preciso

**Por favor consulta con un médico antes de continuar con plantas medicinales.**
        """
    
    # 💊 INTERACCIONES PELIGROSAS
    dangerous_interactions = [
        r'anticoagulante|warfarina|sintrom',
        r'medicamento.*corazón|digoxina|cardiotónico',
        r'quimioterapia|tratamiento.*cáncer',
        r'inmunosupresor|transplante'
    ]
    
    medications = patient_info.get('medications', '') + ' ' + patient_info.get('additional_info', '')
    for pattern in dangerous_interactions:
        if re.search(pattern, medications.lower()):
            return True, "INTERACCION_PELIGROSA", f"""
💊 **MEDICAMENTOS CON INTERACCIONES PELIGROSAS**

**Las plantas medicinales pueden tener interacciones graves con tus medicamentos.**

**Por favor:**
- Consulta con tu médico tratante
- Lleva la lista de todos tus medicamentos
- No suspendas ni agregues nada sin supervisión médica

**Tu seguridad es prioritaria.**
            """
    
    return False, "BAJO_RIESGO", ""

def evaluar_riesgo_moderado(patient_info: Dict[str, Any]) -> Tuple[bool, str]:
    """
    ⚠️ EVALUACIÓN DE RIESGO MODERADO - PRECAUCIONES ADICIONALES
    """
    symptoms = patient_info.get('symptoms', '').lower()
    age = patient_info.get('age', 0)
    
    try:
        age_int = int(age) if str(age).isdigit() else 0
    except:
        age_int = 0
    
    warnings = []
    
    # Niños pequeños (2-12 años)
    if 2 <= age_int <= 12:
        warnings.append("👶 **NIÑO:** Usar solo plantas muy suaves, dosis reducidas")
    
    # Embarazo (sin síntomas críticos)
    if 'embaraza' in patient_info.get('additional_info', '').lower():
        warnings.append("🤱 **EMBARAZO:** Evitar plantas emenagogas, consultar dosis")
    
    # Adultos mayores
    if age_int > 65:
        warnings.append("👴 **ADULTO MAYOR:** Vigilar interacciones, empezar con dosis bajas")
    
    # Alergias conocidas
    allergies = patient_info.get('allergies', '').lower()
    if allergies and 'ninguna' not in allergies and 'no' not in allergies:
        warnings.append("⚠️ **ALERGIAS:** Verificar reacciones cruzadas con plantas")
    
    if warnings:
        warning_text = "\n".join([f"- {w}" for w in warnings])
        return True, f"""
⚠️ **PRECAUCIONES ESPECIALES REQUERIDAS:**

{warning_text}

**Continúa con precaución extra y considera consulta médica si empeora.**
        """
    
    return False, ""

async def process_consultation_with_safety(
    patient_info: Dict[str, Any],
    selected_plant: Optional[str] = None
) -> Dict[str, Any]:
    """
    NUEVO FLUJO CON EVALUACIÓN DE SEGURIDAD INTEGRADA Y MANTENIENDO LA EVALUACIÓN DUAL
    """
    try:
        logger.info("\n=== INICIANDO EVALUACIÓN DE SEGURIDAD ===")
        
        # 🚨 FASE 0: EVALUACIÓN CRÍTICA DE RIESGO
        is_critical, risk_level, critical_message = evaluar_riesgo_critico(patient_info)
        
        if is_critical:
            logger.warning(f"RIESGO CRÍTICO DETECTADO: {risk_level}")
            return {
                "answer": critical_message,
                "risk_level": risk_level,
                "medical_referral_required": True,
                "plant_recommendation_blocked": True,
                "session_id": patient_info.get('session_id', str(uuid.uuid4()))
            }
        
        # ⚠️ EVALUACIÓN DE RIESGO MODERADO
        has_moderate_risk, moderate_warning = evaluar_riesgo_moderado(patient_info)
        
        logger.info("=== EVALUACIÓN DE SEGURIDAD COMPLETADA - CONTINUANDO ===")
        
        # Continuar con la lógica de evaluación dual
        session_id = patient_info.get('session_id', str(uuid.uuid4()))
        symptoms = patient_info.get('symptoms', '')
        
        has_selected_plant = selected_plant is not None and selected_plant.strip() != ""
        
        if has_selected_plant:
            # FASE 6 con advertencias de seguridad
            result = await get_plant_preparation_safe(selected_plant, patient_info, moderate_warning)
            
            # Guardar consulta
            await save_consultation(
                user_id=patient_info.get('user_id', 'anonymous'),
                session_id=session_id,
                symptoms=symptoms,
                symptoms_duration=patient_info.get('duration', ''),
                allergies=patient_info.get('allergies', 'ninguna'),
                recommended_plant=selected_plant,
                risk_level=risk_level
            )
            
            return result
        else:
            # FASES 1-5 con evaluación de seguridad
            logger.info("=== CONTINUANDO CON EVALUACIÓN DUAL ===")
            
            # Evaluación dual RNA/RAG
            rna_recommendations, rna_precision = await evaluate_rna_system(symptoms)
            rag_recommendations, rag_precision = await evaluate_rag_system(patient_info)
            
            selected_system, selection_reason = select_optimal_system(
                rna_precision, rag_precision, symptoms
            )
            
            # Formatear respuesta con advertencias de seguridad
            formatted_response = format_user_response_safe(
                selected_system, 
                rna_recommendations, 
                rag_recommendations,
                rna_precision,
                rag_precision,
                selection_reason, 
                moderate_warning
            )
            
            return {
                "answer": formatted_response,
                "selected_system": selected_system,
                "rna_recommendations": rna_recommendations,
                "rag_recommendations": rag_recommendations,
                "rna_precision": rna_precision,
                "rag_precision": rag_precision,
                "selection_reason": selection_reason,
                "risk_level": risk_level,
                "has_moderate_risk": has_moderate_risk,
                "session_id": session_id,
                "medical_referral_required": False,
                "plant_recommendation_blocked": False
            }
        
    except Exception as e:
        logger.error(f"Error in process_consultation_with_safety: {str(e)}")
        traceback.print_exc()
        return {"error": f"Error processing consultation: {str(e)}"}

async def get_plant_preparation_safe(plant_name: str, patient_info: Dict[str, Any], 
                                   moderate_warning: str = "") -> Dict[str, Any]:
    """
    FASE 6 MEJORADA: Preparación con advertencias de seguridad
    """
    try:
        logger.info(f"Generando preparación SEGURA para: {plant_name}")
        
        # Prompt modificado con consideraciones de seguridad
        prompt = prepare_safe_rag_prompt(patient_info, plant_name, moderate_warning)
        
        response = await get_completion(prompt)
        detailed_answer = extract_answer(response)
        
        # Agregar disclaimer legal obligatorio
        safety_disclaimer = generate_safety_disclaimer()
        final_answer = f"{detailed_answer}\n\n{safety_disclaimer}"
        
        if moderate_warning:
            final_answer = f"{moderate_warning}\n\n{final_answer}"
        
        return {
            "answer": final_answer,
            "plant_name": plant_name,
            "preparation_method": "RAG_SAFE",
            "session_id": patient_info.get('session_id'),
            "safety_evaluated": True
        }
    except Exception as e:
        logger.error(f"Error generating safe plant preparation: {str(e)}")
        return {"answer": f"Error al procesar la preparación: {str(e)}"}

def format_user_response_safe(
    selected_system: str, 
    rna_recommendations: List[Dict], 
    rag_recommendations: str, 
    rna_precision: float,
    rag_precision: float,
    reason: str,
    moderate_warning: str = ""
) -> str:
    """
    FASE 4 MEJORADA: Formateo con advertencias de seguridad y manteniendo la información de precisión
    """
    lines = []
    
    # Advertencias de seguridad moderada al inicio
    if moderate_warning:
        lines.append(moderate_warning)
        lines.append("")
    
    # Encabezado con información de precisión
    lines.append("🌿 **RECOMENDACIONES DE PLANTAS MEDICINALES** 🌿")
    lines.append("")
    lines.append(f"**Sistema elegido:** {selected_system}")
    lines.append(f"**Precisión estimada:** {(rna_precision if selected_system == 'RNA' else rag_precision)*100:.1f}%")
    lines.append(f"**Motivo de selección:** {reason}")
    lines.append("")
    
    if selected_system == "RNA":
        # Mostrar recomendaciones RNA estructuradas
        lines.append("🤖 **Recomendaciones basadas en patrones aprendidos (RNA):**")
        for i, plant in enumerate(rna_recommendations, 1):
            confidence_level = "Alta" if plant['confidence'] > 0.7 else "Media" if plant['confidence'] > 0.4 else "Baja"
            
            lines.append(f"**PLANTA_{i}: {plant['name'].title()} ({plant['scientific_name']})**")
            lines.append(f"- Efectividad: {confidence_level} (Confianza: {plant['confidence']:.2f})")
            lines.append(f"- Descripción: Recomendada para sus síntomas específicos")
            lines.append("")
    else:
        # Mostrar recomendaciones RAG
        lines.append("📚 **Recomendaciones basadas en conocimiento médico (RAG):**")
        lines.append(rag_recommendations)
        lines.append("")
    
    # Comparativa de sistemas
    lines.append("📊 **Comparativa de sistemas:**")
    lines.append(f"- Precisión RNA: {rna_precision*100:.1f}%")
    lines.append(f"- Precisión RAG: {rag_precision*100:.1f}%")
    lines.append("")
    
    # Disclaimer de seguridad obligatorio
    lines.append("---")
    lines.append(generate_safety_disclaimer())
    lines.append("")
    lines.append("📋 **Por favor, elija una de estas plantas para recibir la preparación detallada.**")
    
    return "\n".join(lines)

def prepare_safe_rag_prompt(patient_info: Dict[str, Any], selected_plant: str, 
                           moderate_warning: str = "") -> str:
    """
    Prompt mejorado con consideraciones de seguridad
    """
    symptoms = patient_info.get('symptoms', '')
    duration = patient_info.get('duration', 'No especificado')
    allergies = patient_info.get('allergies', 'Ninguna')
    age = patient_info.get('age', 'No especificado')
    
    plant_name = selected_plant.split('(')[0].strip() if '(' in selected_plant else selected_plant
    
    safety_considerations = ""
    if moderate_warning:
        safety_considerations = f"\n\nCONSIDERACIONES ESPECIALES DE SEGURIDAD:\n{moderate_warning}"
    
    prompt = f"""
    INFORMACIÓN DEL PACIENTE:
    - Síntomas: "{symptoms}" (Duración: {duration})
    - Edad: {age}
    - Alergias: {allergies}
    - Planta seleccionada: {plant_name}
    {safety_considerations}
    
    Por favor proporciona un plan de tratamiento SEGURO que incluya:
    
    1. **Verificación de seguridad específica para esta edad/condición**
    2. **Nombre completo** (común y científico)
    3. **Propiedades medicinales** específicas
    4. **Preparación detallada** paso a paso
    5. **Dosis CONSERVADORA y frecuencia**
    6. **Duración máxima recomendada**
    7. **CONTRAINDICACIONES específicas**
    8. **Señales de alarma** para suspender uso
    9. **Cuándo buscar ayuda médica**
    
    IMPORTANTE: Sé conservador con las dosis y enfatiza la supervisión médica cuando sea necesario.
    """
    
    return prompt

def generate_safety_disclaimer() -> str:
    """
    Genera disclaimer legal obligatorio
    """
    return """
🏥 **IMPORTANTE - DISCLAIMER MÉDICO:**

⚠️ **Este sistema NO sustituye la consulta médica profesional.**
- En caso de emergencia, contacta servicios médicos (117 - SAMU)
- Si los síntomas empeoran o persisten, busca atención médica
- Las plantas medicinales pueden tener efectos secundarios e interacciones
- Siempre informa a tu médico sobre remedios herbales que uses

**🔒 Tu seguridad es nuestra prioridad principal.**
    """

# Modificar la función save_consultation para incluir risk_level
async def save_consultation(
    user_id: str,
    session_id: str,
    symptoms: str,
    symptoms_duration: str,
    allergies: str,
    recommended_plant: str = None,
    risk_level: str = "BAJO_RIESGO"
) -> bool:
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DATABASE_URL") or os.getenv("DB_NAME"), 
            user=os.getenv("DB_USER"),            
            password=os.getenv("DB_PASSWORD"),    
            host=os.getenv("DB_HOST"),            
            port=os.getenv("DB_PORT", "5432")         
        )
        register_uuid()
        cursor = conn.cursor()
        
        # Query modificada para incluir risk_level
        insert_query = """
        INSERT INTO patient_consultations 
            (user_id, session_id, symptoms, symptoms_duration, allergies, 
             recommended_plant, consultation_date, risk_level)
        VALUES 
            (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        
        if not user_id:
            user_id = str(uuid.uuid4())
            
        try:
            user_id_uuid = uuid.UUID(user_id)
            session_id_uuid = uuid.UUID(session_id)
        except ValueError as e:
            logger.error(f"Error converting UUIDs: {e}")
            user_id_uuid = uuid.uuid4()
            session_id_uuid = uuid.uuid4()
        
        cursor.execute(insert_query, (
            user_id_uuid,
            session_id_uuid,
            symptoms,
            symptoms_duration,
            allergies,
            recommended_plant,
            risk_level  # Nueva columna
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving consultation: {str(e)}")
        if conn is not None:
            conn.rollback()
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# ========== FUNCIONES DE EVALUACIÓN DUAL ==========

async def evaluate_rna_system(symptoms: str) -> tuple[List[Dict], float]:
    """FASE 2.1: Evaluación del sistema RNA con manejo de casos límite mejorado"""
    try:
        if not symptoms.strip():
            return [], 0.0
            
        # Obtener recomendaciones del sistema híbrido (RNA)
        recommendations = hybrid_recommender.recommend(symptoms, top_n=3)
        
        if not recommendations or len(recommendations) == 0:
            logger.warning(f"El sistema RNA no devolvió recomendaciones para: '{symptoms}'")
            # Devuelve precisión base más baja cuando no hay recomendaciones
            return [], 0.2
        
        # Calcular factores de precisión con valores mínimos
        precision_factors = []
        
        # Factor 1: Confianza promedio (mínimo 0.2)
        avg_confidence = max(0.2, sum(p['confidence'] for p in recommendations) / len(recommendations))
        precision_factors.append(avg_confidence)
        
        # Resto de factores (mantén los mismos)
        historical_similarity = max(0.2, calculate_historical_similarity(symptoms))
        precision_factors.append(historical_similarity)
        
        symptom_frequency = max(0.2, calculate_symptom_frequency(symptoms))
        precision_factors.append(symptom_frequency)
        
        recommendation_coherence = max(0.2, calculate_recommendation_coherence(recommendations))
        precision_factors.append(recommendation_coherence)
        
        # Pesos para cada factor
        weights = [0.4, 0.25, 0.2, 0.15]
        
        # Calcular precisión ponderada (asegurar mínimo 0.2)
        rna_precision = min(1.0, max(0.2, sum(f*w for f,w in zip(precision_factors, weights))))
        
        logger.info(f"Factores RNA: {precision_factors} → Precisión: {rna_precision:.3f}")
        return recommendations, rna_precision
        
    except Exception as e:
        logger.error(f"Error en evaluate_rna_system: {str(e)}")
        return [], 0.2  # Precisión base más baja en caso de error

async def evaluate_rag_system(patient_info: Dict[str, Any]) -> tuple[str, float]:
    """
    FASE 2.2: Evaluación del sistema RAG con manejo de casos límite
    """
    try:
        rag_response = await get_rag_recommendations(patient_info)
        
        if not rag_response or len(rag_response.strip()) < 30:
            logger.warning("Respuesta RAG demasiado corta o vacía")
            return "", 0.5  # Precisión base
        
        # Calcular factores con valores mínimos
        precision_factors = []
        
        # Factor 1: Relevancia semántica (mínimo 0.3)
        semantic_relevance = max(0.3, calculate_semantic_relevance(
            patient_info.get('symptoms', ''), rag_response
        ))
        precision_factors.append(semantic_relevance)
        
        # Factor 2: Calidad literaria (mínimo 0.3)
        literature_quality = max(0.3, calculate_literature_quality(rag_response))
        precision_factors.append(literature_quality)
        
        # Factor 3: Cobertura (mínimo 0.3)
        information_coverage = max(0.3, calculate_information_coverage(rag_response))
        precision_factors.append(information_coverage)
        
        # Factor 4: Coherencia (mínimo 0.3)
        information_coherence = max(0.3, calculate_information_coherence(rag_response))
        precision_factors.append(information_coherence)
        
        weights = [0.35, 0.3, 0.2, 0.15]
        rag_precision = min(1.0, max(0.3, sum(f*w for f,w in zip(precision_factors, weights))))
        
        logger.info(f"Factores RAG: {precision_factors} → Precisión: {rag_precision:.3f}")
        return rag_response, rag_precision
        
    except Exception as e:
        logger.error(f"Error en evaluate_rag_system: {str(e)}")
        return "", 0.5  # Precisión base en caso de error

def select_optimal_system(rna_precision: float, rag_precision: float, symptoms: str) -> tuple[str, str]:
    """
    FASE 3: Selección del sistema óptimo basado en criterios de decisión
    """
    # Diferencia mínima para considerar empate
    min_difference = 0.05
    
    if abs(rna_precision - rag_precision) <= min_difference:
        # Empate - usar criterio adicional basado en tipo de síntomas
        if is_common_symptom(symptoms):
            return "RNA", f"Empate (RNA: {rna_precision:.3f}, RAG: {rag_precision:.3f}) - Síntomas comunes favorecen RNA"
        else:
            return "RAG", f"Empate (RNA: {rna_precision:.3f}, RAG: {rag_precision:.3f}) - Síntomas específicos favorecen RAG"
    
    elif rna_precision > rag_precision:
        return "RNA", f"RNA superior (RNA: {rna_precision:.3f} > RAG: {rag_precision:.3f}) - Patrones conocidos/frecuentes"
    
    else:
        return "RAG", f"RAG superior (RAG: {rag_precision:.3f} > RNA: {rna_precision:.3f}) - Casos complejos/inusuales"

async def get_rag_recommendations(patient_info: Dict[str, Any]) -> str:
    """Obtiene recomendaciones usando el sistema RAG"""
    try:
        prompt = prepare_rag_prompt(patient_info, plant_selected=False)
        response = await get_completion(prompt)
        return extract_answer(response)
    except Exception as e:
        logger.error(f"Error getting RAG recommendations: {str(e)}")
        return ""

def prepare_rag_prompt(patient_info: Dict[str, Any], selected_plant: Optional[str] = None, plant_selected: bool = False) -> str:
    """Prepara el prompt para el RAG"""
    symptoms = patient_info.get('symptoms', '')
    duration = patient_info.get('duration', 'No especificado')
    allergies = patient_info.get('allergies', 'Ninguna')
    age = patient_info.get('age', 'No especificado')
    gender = patient_info.get('gender', 'No especificado')
    
    plant_name = selected_plant
    if selected_plant and plant_selected:
        if '(' in selected_plant:
            plant_name = selected_plant.split('(')[0].strip()
        logger.info(f"Nombre de planta normalizado para el prompt: {plant_name}")
    
    if plant_selected:
        prompt = f"""
        El paciente presenta los siguientes síntomas: "{symptoms}" desde hace {duration}.
        Alergias: {allergies}. Edad: {age}. Género: {gender}.
        
        La planta seleccionada es: {plant_name}
        
        Por favor proporciona un detallado plan de tratamiento con esta planta que incluya:
        1. Nombre completo de la planta (común y científico)
        2. Propiedades medicinales específicas para estos síntomas
        3. Parte de la planta utilizada
        4. Forma de preparación (infusión, decocción, cataplasma, etc.)
        5. Dosis recomendada y frecuencia
        6. Duración del tratamiento
        7. Precauciones específicas y posibles efectos secundarios
        
        Proporciona instrucciones paso a paso muy claras y específicas.
        """
    else:
        prompt = f"""
        El paciente presenta los siguientes síntomas: "{symptoms}" desde hace {duration}.
        Alergias: {allergies}. Edad: {age}. Género: {gender}.
        
        Sugiere 3 plantas medicinales peruanas para tratar estos síntomas usando exactamente este formato:
        
        PLANTA_1: [Nombre común (Nombre científico)] | [Breve descripción de beneficios] | Efectividad: [Alta/Media/Baja]
        PLANTA_2: [Nombre común (Nombre científico)] | [Breve descripción de beneficios] | Efectividad: [Alta/Media/Baja]
        PLANTA_3: [Nombre común (Nombre científico)] | [Breve descripción de beneficios] | Efectividad: [Alta/Media/Baja]
        
        Finaliza indicando que debe elegir una planta para recibir preparación detallada.
        """
    
    return prompt

async def get_completion(prompt: str) -> Dict:
    """Obtiene completion para el prompt usando OpenAI"""
    try:
        if not api_key:
            logger.error("ERROR: No OpenAI API key available")
            return None
            
        if use_new_client:
            response = await client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en medicina tradicional peruana especializado en plantas medicinales. Tu objetivo es proporcionar información precisa y útil sobre remedios herbales para síntomas específicos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800
            )
            logger.info('HTTP Request: OpenAI chat completions API call successful')
            return response
        else:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Eres un experto en medicina tradicional peruana especializado en plantas medicinales. Tu objetivo es proporcionar información precisa y útil sobre remedios herbales para síntomas específicos."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800
            )
            logger.info('HTTP Request: OpenAI chat completions API call successful')
            return response
    except Exception as e:
        logger.error(f"Error obteniendo completion: {str(e)}")
        return None

def extract_answer(completion_response) -> str:
    """Extrae y formatea la respuesta del RAG"""
    if not completion_response:
        return "No se pudo generar una respuesta."
    
    try:
        if use_new_client:
            if not hasattr(completion_response, 'choices') or not completion_response.choices:
                return "No se encontraron recomendaciones adecuadas."
            content = completion_response.choices[0].message.content
        else:
            if 'choices' not in completion_response or not completion_response['choices']:
                return "No se encontraron recomendaciones adecuadas."
            content = completion_response['choices'][0]['message']['content']
        
        if not content:
            return "La respuesta generada está vacía."
            
        return content.strip()
    except Exception as e:
        logger.error(f"Error extrayendo respuesta: {str(e)}")
        return "Error procesando la respuesta."

# Funciones auxiliares para cálculo de precisión
def calculate_historical_similarity(symptoms: str) -> float:
    """Simula similitud con casos históricos exitosos"""
    common_symptoms = ["dolor", "fiebre", "tos", "digestión", "cabeza", "estómago"]
    symptoms_lower = symptoms.lower()
    matches = sum(1 for symptom in common_symptoms if symptom in symptoms_lower)
    return min(0.9, matches / len(common_symptoms) + 0.3)

def calculate_symptom_frequency(symptoms: str) -> float:
    """Simula frecuencia de síntomas en dataset de entrenamiento"""
    symptom_frequencies = {
        "dolor": 0.8, "cabeza": 0.7, "estómago": 0.75, "fiebre": 0.6,
        "tos": 0.65, "digestión": 0.7, "piel": 0.4, "respiratorio": 0.5
    }
    symptoms_lower = symptoms.lower()
    total_frequency = 0
    count = 0
    for symptom, freq in symptom_frequencies.items():
        if symptom in symptoms_lower:
            total_frequency += freq
            count += 1
    return total_frequency / count if count > 0 else 0.3

def calculate_recommendation_coherence(recommendations: List[Dict]) -> float:
    """Calcula coherencia entre recomendaciones"""
    if len(recommendations) < 2:
        return 0.5
    confidences = [plant['confidence'] for plant in recommendations]
    is_ordered = all(confidences[i] >= confidences[i+1] for i in range(len(confidences)-1))
    confidence_range = max(confidences) - min(confidences)
    good_range = 0.2 <= confidence_range <= 0.5
    coherence = 0.5
    if is_ordered:
        coherence += 0.3
    if good_range:
        coherence += 0.2
    return min(1.0, coherence)

def calculate_semantic_relevance(symptoms: str, rag_response: str) -> float:
    """Simula relevancia semántica entre síntomas y respuesta RAG"""
    symptoms_words = set(symptoms.lower().split())
    response_words = set(rag_response.lower().split())
    medical_keywords = {
        "dolor", "fiebre", "inflamación", "tos", "digestión", "cabeza", "estómago",
        "piel", "respiratorio", "tratamiento", "medicinal", "planta", "hierba"
    }
    symptom_medical = symptoms_words.intersection(medical_keywords)
    response_medical = response_words.intersection(medical_keywords)
    if not symptom_medical:
        return 0.4
    overlap = len(symptom_medical.intersection(response_medical))
    return min(0.95, overlap / len(symptom_medical) + 0.3)

def calculate_literature_quality(rag_response: str) -> float:
    """Simula calidad de matches en literatura médica/botánica"""
    quality_indicators = [
        "nombre científico", "propiedades", "preparación", "dosis",
        "efectos", "contraindicaciones", "infusión", "decocción"
    ]
    response_lower = rag_response.lower()
    matches = sum(1 for indicator in quality_indicators if indicator in response_lower)
    return min(0.9, matches / len(quality_indicators) + 0.2)

def calculate_information_coverage(rag_response: str) -> float:
    """Calcula cobertura de información en la respuesta"""
    coverage_aspects = [
        "planta", "síntoma", "preparación", "uso", "cantidad", "tiempo"
    ]
    response_lower = rag_response.lower()
    covered = sum(1 for aspect in coverage_aspects if aspect in response_lower)
    return covered / len(coverage_aspects)

def calculate_information_coherence(rag_response: str) -> float:
    """Calcula coherencia de la información recuperada"""
    lines = rag_response.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    has_structure = len(non_empty_lines) >= 3
    good_length = 100 <= len(rag_response) <= 1000
    has_plant_format = "PLANTA_" in rag_response or "planta" in rag_response.lower()
    coherence = 0.3
    if has_structure:
        coherence += 0.25
    if good_length:
        coherence += 0.25
    if has_plant_format:
        coherence += 0.2
    return min(1.0, coherence)

def is_common_symptom(symptoms: str) -> bool:
    """Determina si los síntomas son comunes o específicos"""
    common_symptoms = [
        "dolor de cabeza", "dolor", "fiebre", "tos", "resfriado", "gripe",
        "digestión", "estómago", "malestar", "cansancio", "fatiga"
    ]
    symptoms_lower = symptoms.lower()
    return any(common in symptoms_lower for common in common_symptoms)

def register_uuid():
    """Register UUID type with psycopg2"""
    import psycopg2.extras
    psycopg2.extras.register_uuid()

# Configuración de la base de datos
"""
db_config = {
    'dbname': 'databasePlantMedicator',
    'user': 'postgres',
    'password': 'Mascota3',
    'host': 'localhost'
}
"""
# Inicialización del recomendador híbrido y cliente OpenAI
try:
    from hybrid_recommender import HybridRecommender
    hybrid_recommender = HybridRecommender()
except ImportError:
    class HybridRecommender:
        def recommend(self, symptoms, top_n=3):
            return []
    hybrid_recommender = HybridRecommender()

try:
    from openai import AsyncOpenAI as OpenAIClient
    use_new_client = True
    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    try:
        import openai
        use_new_client = False
        openai.api_key = os.getenv("OPENAI_API_KEY")
    except ImportError:
        print("ERROR: OpenAI library not installed")
        use_new_client = False

api_key = os.getenv("OPENAI_API_KEY")