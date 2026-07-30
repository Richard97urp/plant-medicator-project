from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
import psycopg2
from datetime import datetime, timedelta
import traceback
import uuid
import os
import logging
import json

import re
import unicodedata 
from fastapi.security import OAuth2PasswordBearer

from app.natural_conversation_agent import (
    conversation_agent,
    ConversationState,
    ProcessChatRequest,
    ProcessChatResponse,
    ExtractedInfo
)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

try:
    from app.hybrid_recommender import HybridRecommender
except ImportError:
    from hybrid_recommender import HybridRecommender

try:
    import bcrypt
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'bcrypt'])
    import bcrypt

try:
    from jose import JWTError, jwt
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'python-jose[cryptography]'])
    from jose import JWTError, jwt

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME") or "databasePlantMedicator",
    "user": os.getenv("DB_USER") or "postgres",
    "password": os.getenv("DB_PASSWORD") or "Mascota3",
    "host": os.getenv("DB_HOST") or "localhost",
    "port": os.getenv("DB_PORT") or "5432"
}

hybrid_recommender = HybridRecommender(DB_CONFIG)

SECRET_KEY = "GROF*_*09"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

session_recommendations_cache: Dict[str, list] = {}
session_cache_timestamps: Dict[str, datetime] = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# 📌 Configurar directorio para imágenes
UPLOAD_DIR = "app/uploads/profile_pictures"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Crear si no existe


def get_connection():
    """Función auxiliar para obtener conexión a BD"""
    return psycopg2.connect(**DB_CONFIG)
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

# 📌 Montar directorio estático para servir imágenes
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://*.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class PatientInfo(BaseModel):
    symptoms: str
    duration: str
    intensity: str
    allergies: str
    causa_ambiental: Optional[str] = None
    causa_emocional: Optional[str] = None
    causa_dietetica: Optional[str] = None
    user_id: Optional[str] = None

class PatientConsultation(BaseModel):
    session_id: Optional[str] = None
    patient_info: Dict[str, Any]
    selected_plant: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    effectiveness_rating: Optional[int] = None
    side_effects: Optional[str] = None
    improvement_time: Optional[str] = None
    additional_comments: Optional[str] = None
    plant_name: Optional[str] = None  # ← AGREGAR

class UserRegistration(BaseModel):
    fullName: str
    email: str
    username: str
    password: str
    dni: str
    phoneNumber: str
    age: int
    gender: str
    weight: float
    height: float
    zone: str
    occupation: Optional[str] = None

class LoginCredentials(BaseModel):
    identifier: str
    password: str


def normalize_text(text: str) -> str:
    """Normaliza texto removiendo acentos y convirtiendo a minúsculas"""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    return text.lower().strip()

def clean_plant_name(plant_name: str) -> str:
    """Limpia nombre de planta removiendo caracteres especiales"""
    cleaned = plant_name.strip()
    cleaned = re.sub(r'^\*+', '', cleaned)
    cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
    return cleaned.strip()

def calculate_similarity(text1: str, text2: str) -> float:
    """Calcula similitud simple entre dos textos"""
    if not text1 or not text2:
        return 0.0
    
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return 1.0
    
    matches = sum(1 for a, b in zip(text1_lower, text2_lower) if a == b)
    return matches / max(len(text1_lower), len(text2_lower))

def fuzzy_match_plant(selected: str, available_plants: List[str]) -> Optional[str]:
    """Busca coincidencia flexible entre planta seleccionada y plantas disponibles - MEJORADA"""
    if not selected or not available_plants:
        return None
    
    selected_normalized = normalize_text(selected)
    selected_cleaned = clean_plant_name(selected_normalized)
    
    logger.info(f"🔍 Buscando match para: '{selected}' → '{selected_cleaned}'")
    logger.info(f"   Plantas disponibles: {available_plants}")
    
    # CASO 1: Número
    try:
        index = int(selected_cleaned) - 1
        if 0 <= index < len(available_plants):
            matched = available_plants[index]
            logger.info(f"✅ Número detectado → '{matched}'")
            return matched
    except ValueError:
        pass
    
    # CASO 2: Coincidencia exacta
    for plant in available_plants:
        if selected_cleaned == plant.lower().strip():
            logger.info(f"✅ Coincidencia exacta: '{plant}'")
            return plant
    
    # CASO 3: Coincidencia parcial
    for plant in available_plants:
        plant_lower = plant.lower().strip()
        if (selected_cleaned in plant_lower or 
            plant_lower in selected_cleaned or
            selected_cleaned.split()[0] == plant_lower.split()[0]):
            logger.info(f"✅ Coincidencia parcial: '{plant}'")
            return plant
    
    # CASO 4: Confirmaciones ("sí", "ok", "esa")
    confirmation_words = ['si', 'sí', 'yes', 'ok', 'dale', 'confirmo', 'esa', 'exacto', 'claro']
    is_confirmation = any(word in selected_cleaned for word in confirmation_words)
    
    if is_confirmation and len(available_plants) == 1:
        matched = available_plants[0]
        logger.info(f"✅ Confirmación detectada → '{matched}'")
        return matched
    
    logger.warning(f"❌ No se encontró coincidencia para: '{selected}'")
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def cleanup_old_sessions():
    """Limpia sesiones más antiguas de 1 hora"""
    current_time = datetime.now()
    expired_sessions = [
        session_id for session_id, timestamp in session_cache_timestamps.items()
        if current_time - timestamp > timedelta(hours=1)
    ]
    
    for session_id in expired_sessions:
        if session_id in session_recommendations_cache:
            del session_recommendations_cache[session_id]
        del session_cache_timestamps[session_id]


def _detect_plant_selection_after_recommendations(message: str, current_state: ConversationState) -> bool:
    """
    Detecta si el usuario está seleccionando una planta después de haber recibido recomendaciones
    """
    if not current_state.hasReceivedRecommendations:
        return False
    
    message_lower = message.lower().strip()
    
    # Plantas conocidas
    known_plants = [
        'menta', 'manzanilla', 'hierba luisa', 'muña', 'uña de gato', 
        'eucalipto', 'matico', 'boldo', 'caléndula', 'salvia', 'jengibre',
        'maca', 'sangre de grado', 'sauco', 'llantén', 'ruda', 'yacón'
    ]
    
    # Verificar si es una selección de planta
    for plant in known_plants:
        if message_lower == plant or message_lower == f"la {plant}":
            return True
    
    # También números (1, 2, 3)
    if message_lower in ['1', '2', '3', 'uno', 'dos', 'tres']:
        return True
    
    # Patrones de selección
    selection_patterns = [
        r'^(quiero|quisiera|dame|dime|muestra|ver|info|información|detalles)\s+(la\s+)?(\w+)',
        r'^(\w+)$',
        r'^(la\s+)?(\w+)\s+(por favor|plis|please)',
    ]
    
    for pattern in selection_patterns:
        match = re.search(pattern, message_lower)
        if match:
            return True
    
    return False

def _extract_plant_name(message: str) -> Optional[str]:
    """
    Extrae el nombre de la planta del mensaje del usuario
    """
    message_lower = message.lower().strip()
    
    # Mapeo de números a plantas (asumiendo el orden de recomendación)
    number_to_plant = {
        '1': 'manzanilla', 'uno': 'manzanilla',
        '2': 'menta', 'dos': 'menta', 
        '3': 'hierba luisa', 'tres': 'hierba luisa'
    }
    
    # Verificar si es un número
    if message_lower in number_to_plant:
        return number_to_plant[message_lower]
    
    # Lista de plantas conocidas
    known_plants = [
        'menta', 'manzanilla', 'hierba luisa', 'muña', 'uña de gato', 
        'eucalipto', 'matico', 'boldo', 'caléndula', 'salvia', 'jengibre',
        'maca', 'sangre de grado', 'sauco', 'llantén', 'ruda', 'yacón'
    ]
    
    # Verificar nombre exacto
    for plant in known_plants:
        if (message_lower == plant or 
            message_lower == f"la {plant}" or 
            message_lower == f"quiero {plant}" or
            message_lower == f"dame {plant}" or
            message_lower == f"selecciono {plant}"):
            return plant
    
    # Verificar si contiene el nombre de planta
    for plant in known_plants:
        if plant in message_lower:
            return plant
    
    return None

async def get_user_data_from_db(username: str) -> Optional[Dict[str, Any]]:
    """Recupera los datos del usuario desde la base de datos INCLUYENDO FOTO"""
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
        SELECT full_name, email, username, dni, phone_number, age, gender, 
               weight, height, zone, occupation, education_level, profile_picture_path
        FROM personal_information 
        WHERE username = %s
        """
        
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        
        if result:
            user_data = {
                'full_name': result[0],
                'email': result[1],
                'username': result[2],
                'dni': result[3],
                'phone_number': result[4],
                'age': result[5],
                'gender': result[6],
                'weight': result[7],
                'height': result[8],
                'zone': result[9],
                'occupation': result[10],
                'education_level': result[11],
                'profile_picture_url': f"http://localhost:8000{result[12]}" if result[12] else None
            }
            logger.info(f"Datos del usuario {username} recuperados")
            return user_data
        else:
            logger.warning(f"Usuario {username} no encontrado")
            return None
            
    except Exception as e:
        logger.error(f"Error consultando usuario {username}: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def save_consultation(
    user_id: str,
    session_id: str,
    symptoms: str,
    symptoms_duration: str,
    symptoms_intensity: str,  
    allergies: str,
    causa_ambiental: Optional[str] = None,
    causa_emocional: Optional[str] = None,
    causa_dietetica: Optional[str] = None,
    recommended_plant: str = None,
    risk_level: str = "BAJO_RIESGO"
):
    """Guarda la consulta en la base de datos con las 3 causas"""
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        causa_amb_str = str(causa_ambiental) if causa_ambiental is not None else ''
        causa_emo_str = str(causa_emocional) if causa_emocional is not None else ''
        causa_diet_str = str(causa_dietetica) if causa_dietetica is not None else ''
        
        query = """
        INSERT INTO consultations 
            (user_id, session_id, symptoms, symptoms_duration, symptoms_intensity,
             allergies, causa_ambiental, causa_emocional, causa_dietetica,
             recommended_plant, risk_level, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """
        
        cursor.execute(query, (
            user_id, session_id, symptoms, symptoms_duration, symptoms_intensity,
            allergies, causa_amb_str, causa_emo_str, causa_diet_str,
            recommended_plant, risk_level
        ))
        
        conn.commit()
        logger.info(f"Consulta guardada: {session_id}")
        
    except Exception as e:
        logger.error(f"Error guardando consulta: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ============================================================================
# 📸 FUNCIONES PARA MANEJAR FOTOS DE PERFIL
# ============================================================================

async def save_profile_picture(file: UploadFile) -> Optional[str]:
    """
    Guarda la imagen de perfil en el servidor y retorna la ruta
    """
    try:
        # Validar que sea una imagen
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            logger.warning(f"Tipo de archivo no permitido: {file.content_type}")
            return None
        
        # Leer contenido
        contents = await file.read()
        
        # Validar tamaño (5MB máximo)
        if len(contents) > 5 * 1024 * 1024:
            logger.warning(f"Archivo demasiado grande: {len(contents)} bytes")
            return None
        
        # Generar nombre único
        file_extension = file.filename.split('.')[-1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Guardar archivo
        await file.seek(0)  # Resetear cursor
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Retornar ruta relativa (para guardar en la DB)
        return f"/uploads/profile_pictures/{unique_filename}"
        
    except Exception as e:
        logger.error(f"Error guardando imagen: {str(e)}")
        return None

# ============================================================================
# ENDPOINTS PRINCIPALES
# ============================================================================

@app.post("/chat/process", response_model=ProcessChatResponse)
async def process_natural_conversation(request: ProcessChatRequest):
    try:
        logger.info(f"📨 Procesando mensaje - Session: {request.session_id}")
        logger.info(f"   Mensaje: '{request.message}'")
        
        # ✅ AGREGAR: Incluir user_id del frontend si está disponible
        if not request.patient_info.get('user_id') and hasattr(request, 'user_id'):
            request.patient_info['user_id'] = request.user_id
        
        if not request.message or request.message.strip() == "":
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
        
        # ✅ NUEVO: Si ya hay recomendaciones y el usuario selecciona una planta
        if (request.current_state.hasReceivedRecommendations and 
            conversation_agent._detect_plant_selection_after_recommendations(
                request.message, request.current_state
            )):
            
            selected_plant = conversation_agent._extract_plant_name(request.message)
            logger.info(f"🌿 SELECCIÓN DE PLANTA DETECTADA: '{selected_plant}'")
            
            if selected_plant:
                return ProcessChatResponse(
                    assistant_response=f"🌿 **Perfecto, has seleccionado {selected_plant.title()}**\n\nVoy a preparar la información detallada de preparación y uso medicinal. Un momento por favor...",
                    conversation_state=request.current_state,
                    extracted_info={"selected_plant": selected_plant},
                    patient_info=request.patient_info,
                    is_emergency=False,
                    has_recommendations=True,
                    recommendations=None
                )
            else:
                return ProcessChatResponse(
                    assistant_response="❌ No reconozco esa planta. Por favor selecciona una de las plantas recomendadas usando el número (1, 2, 3) o escribe el nombre completo.",
                    conversation_state=request.current_state,
                    extracted_info=None,
                    patient_info=request.patient_info,
                    is_emergency=False,
                    has_recommendations=True,
                    recommendations=None
                )
        
        # 1. PROCESAR CONVERSACIÓN CON AGENTE NATURAL
        logger.info("1️⃣ Llamando conversation_agent...")
        response = await conversation_agent.process_message(
            user_message=request.message,
            conversation_history=request.conversation_history,
            current_state=request.current_state,
            patient_info=request.patient_info
        )
        
        if response.is_emergency:
            logger.warning("🚨 EMERGENCIA DETECTADA")
            return response
        
        # 🔍 DEBUG: Imprimir estado completo ANTES de verificar
        logger.info("\n" + "="*80)
        logger.info("🔍 DEBUG: Verificando response.patient_info")
        logger.info("="*80)
        logger.info(f"response.patient_info es: {response.patient_info}")
        logger.info(f"type(response.patient_info): {type(response.patient_info)}")
        if response.patient_info:
            logger.info(f"Contenido de patient_info:")
            for key, value in response.patient_info.items():
                logger.info(f"  {key}: {repr(value)}")
        else:
            logger.info("❌ patient_info es None o False")
            logger.info(f"\nVerificando states:")
            logger.info(f"  hasSymptoms: {response.conversation_state.hasSymptoms}")
            logger.info(f"  hasDuration: {response.conversation_state.hasDuration}")
            logger.info(f"  hasIntensity: {response.conversation_state.hasIntensity}")
            logger.info(f"  hasCausaAmbiental: {response.conversation_state.hasCausaAmbiental}")
            logger.info(f"  hasCausaEmocional: {response.conversation_state.hasCausaEmocional}")
            logger.info(f"  hasCausaDietetica: {response.conversation_state.hasCausaDietetica}")
            logger.info(f"  hasAllergies: {response.conversation_state.hasAllergies}")
            logger.info(f"  isComplete: {response.conversation_state.isComplete}")
            logger.info(f"  hasReceivedRecommendations: {response.conversation_state.hasReceivedRecommendations}")
            
            all_true = all([
                response.conversation_state.hasSymptoms,
                response.conversation_state.hasDuration,
                response.conversation_state.hasIntensity,
                response.conversation_state.hasCausaAmbiental,
                response.conversation_state.hasCausaEmocional,
                response.conversation_state.hasCausaDietetica,
                response.conversation_state.hasAllergies
            ])
            logger.info(f"  all([...]) = {all_true}")
        logger.info("="*80 + "\n")
        
        # 2. VALIDACIÓN MANUAL - No confiar en isComplete del agente
        should_get_recommendations = False

        if response.patient_info:
            symptoms = response.patient_info.get('symptoms', '').strip()
            duration = response.patient_info.get('duration', '').strip()
            intensity = response.patient_info.get('intensidad_sintomas', '').strip()
            cause_env = response.patient_info.get('causa_ambiental', '').strip()
            cause_emo = response.patient_info.get('causa_emocional', '').strip()
            cause_diet = response.patient_info.get('causa_dietetica', '').strip()
            allergies_raw = response.patient_info.get('allergies')
            if allergies_raw is None:
                allergies = ''
            elif isinstance(allergies_raw, str):
                allergies = allergies_raw.strip()
            else:
                allergies = str(allergies_raw).strip()
            
            # ✅ CORRECCIÓN CRÍTICA: "no aplica" y "false" son respuestas VÁLIDAS
            cause_env_valid = cause_env and cause_env.lower() not in ['', 'none', 'null']
            cause_emo_valid = cause_emo and cause_emo.lower() not in ['', 'none', 'null'] 
            cause_diet_valid = cause_diet and cause_diet.lower() not in ['', 'none', 'null']
            
            # Alergias válidas: cualquier valor que no sea vacío o "incierta"
            allergies_valid = allergies and allergies.lower() not in ['incierta', '', 'none', 'null']
            
            manually_complete = (
                bool(symptoms) and 
                bool(duration) and
                bool(intensity) and
                cause_env_valid and
                cause_emo_valid and
                cause_diet_valid and
                allergies_valid
            )
            
            logger.info(f"🔍 VALIDACIÓN MANUAL MEJORADA:")
            logger.info(f"   symptoms: {bool(symptoms)} ('{symptoms}')")
            logger.info(f"   duration: {bool(duration)} ('{duration}')")
            logger.info(f"   intensity: {bool(intensity)} ('{intensity}')")
            logger.info(f"   cause_env: {cause_env_valid} ('{cause_env}')")
            logger.info(f"   cause_emo: {cause_emo_valid} ('{cause_emo}')")
            logger.info(f"   cause_diet: {cause_diet_valid} ('{cause_diet}')")
            logger.info(f"   allergies: {allergies_valid} ('{allergies}')")
            logger.info(f"   → RESULTADO: {manually_complete}")
            
            should_get_recommendations = manually_complete
        else:
            manually_complete = False
            should_get_recommendations = False

        # 🔥 CORRECCIÓN: Confiar en el agente si dice isComplete=True
        if response.conversation_state.isComplete and not should_get_recommendations:
            logger.warning("⚠️ Agente dice isComplete=True pero validación manual dice False")
            logger.warning("🔄 CONFIANDO EN EL AGENTE - Forzando recomendaciones")
            should_get_recommendations = True

        # 3. SI ESTÁ COMPLETO, GENERAR RECOMENDACIONES
        if should_get_recommendations and response.patient_info:
            logger.info("\n✅ CONSULTA COMPLETA - Llamando HYBRID RECOMMENDER...\n")
            
            try:
                patient_data = response.patient_info.copy()
                patient_data['session_id'] = request.session_id
                
                # Obtener datos del usuario si es necesario
                user_id = patient_data.get('user_id')
                if user_id and user_id != 'test_user':
                    try:
                        user_data = await get_user_data_from_db(user_id)
                        if user_data:
                            patient_data.update({
                                'age': user_data.get('age', 30),
                                'gender': user_data.get('gender', 'Not specified'),
                                'zone': user_data.get('zone', 'Lima'),
                                'weight': user_data.get('weight', 70.0),
                            })
                            logger.info(f"✅ Datos del usuario {user_id} cargados")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudieron obtener datos del usuario: {e}")
                        patient_data.update({
                            'age': 30,
                            'gender': 'Not specified',
                            'zone': 'Lima',
                            'weight': 70.0,
                        })
                else:
                    patient_data.update({
                        'age': 30,
                        'gender': 'Not specified',
                        'zone': 'Lima',
                        'weight': 70.0,
                    })
                
                logger.info(f"📋 Datos para hybrid_recommender:")
                logger.info(f"   - symptoms: {patient_data.get('symptoms')}")
                logger.info(f"   - duration: {patient_data.get('duration')}")
                logger.info(f"   - intensidad: {patient_data.get('intensidad_sintomas')}")
                logger.info(f"   - allergies: {patient_data.get('allergies')}")
                logger.info(f"   - causa_ambiental: {patient_data.get('causa_ambiental')}")
                logger.info(f"   - causa_emocional: {patient_data.get('causa_emocional')}")
                logger.info(f"   - causa_dietetica: {patient_data.get('causa_dietetica')}")
                
                # 🔥 LLAMAR HYBRID RECOMMENDER
                logger.info("\n🔄 Ejecutando hybrid_recommender.get_hybrid_recommendations_async()...\n")
                recommendations = await hybrid_recommender.get_hybrid_recommendations_async(patient_data)

                
                
                logger.info(f"\n✅ RECOMENDACIONES GENERADAS:")
                logger.info(f"   - Sistema: {recommendations.get('selected_system')}")
                logger.info(f"   - Precisión RNA: {recommendations.get('rna_precision')}")
                logger.info(f"   - Precisión RAG: {recommendations.get('rag_precision')}")
                logger.info(f"   - Plantas: {[p['name'] for p in recommendations.get('final_recommendations', [])[:3]]}\n")
            
                # 🔥 NUEVO: Generar mensaje pre-recomendación humanizado
                pre_rec_message = await conversation_agent._generate_pre_recommendation_message(
                    patient_info=response.patient_info,
                    last_user_message=request.message
                )

                # Cachear plantas
                if request.session_id and 'final_recommendations' in recommendations:
                    final_recs = recommendations['final_recommendations']
                    if final_recs and len(final_recs) >= 3:
                        recommended_names = [plant['name'] for plant in final_recs[:3]]
                        session_recommendations_cache[request.session_id] = recommended_names
                        session_cache_timestamps[request.session_id] = datetime.now()
                        logger.info(f"✅ Plantas cacheadas: {recommended_names}")
                
                # 🔥 ACTUALIZAR LA RESPUESTA CON LAS RECOMENDACIONES
                response.recommendations = recommendations
                response.has_recommendations = True
                response.conversation_state.hasReceivedRecommendations = True
                
                 # 🔥 Usar el mensaje humanizado en lugar del frío anterior
                response.assistant_response = pre_rec_message
                
                logger.info("✅ RECOMENDACIONES INTEGRADAS EN RESPUESTA")
                
            except Exception as rec_error:
                logger.error(f"❌ Error generando recomendaciones: {rec_error}")
                import traceback
                traceback.print_exc()
                response.has_recommendations = False
                response.recommendations = None
                response.assistant_response = "¡Gracias! He recopilado toda la información. Hubo un error generando las recomendaciones, pero puedes contarme más detalles."

        else:
            logger.info("⏳ Consulta incompleta - continuando recopilación de información\n")

        return response
        
    except HTTPException as e:
        logger.error(f"HTTP Error: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"❌ Error fatal: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return ProcessChatResponse(
            assistant_response="Lo siento, hubo un error inesperado. ¿Podrías repetir tu respuesta?",
            conversation_state=request.current_state,
            extracted_info=None,
            patient_info=None,
            is_emergency=False,
            has_recommendations=False,
            recommendations=None
        )
    

@app.post("/chat/process-stream")
async def process_natural_conversation_stream(request: ProcessChatRequest):
    """
    🔥 VERSIÓN CON STREAMING - Envía tokens uno por uno
    Compatible con Server-Sent Events (SSE)
    """
    
    async def generate():
        try:
            logger.info(f"📨 STREAMING - Session: {request.session_id}")
            logger.info(f"   Mensaje: '{request.message}'")
            
            # Incluir user_id si está disponible
            if not request.patient_info.get('user_id') and hasattr(request, 'user_id'):
                request.patient_info['user_id'] = request.user_id
            
            if not request.message or request.message.strip() == "":
                yield f"data: {json.dumps({'type': 'error', 'content': 'Mensaje vacío'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 🔥 LLAMAR AL AGENTE CON STREAMING
            async for chunk in conversation_agent.process_message_streaming(
                user_message=request.message,
                conversation_history=request.conversation_history,
                current_state=request.current_state,
                patient_info=request.patient_info
            ):
                # Enviar cada chunk como Server-Sent Event
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # Pequeña pausa para simular escritura natural
                await asyncio.sleep(0.001)
            
            # Señal de finalización
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"❌ Error en streaming: {str(e)}")
            import traceback
            traceback.print_exc()
            
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.post("/chat/welcome")
async def generate_welcome_message():
    """Genera un mensaje de bienvenida variado"""
    try:
        welcome_message = await conversation_agent.generate_welcome_message()
        return {"message": welcome_message}
    except Exception as e:
        logger.error(f"Error generating welcome: {e}")
        # Fallback variado
        import random
        fallbacks = [
            "¡Hola! Soy Fauno, tu asistente de salud natural. ¿Qué síntomas o molestias tienes hoy?",
            "Hola, soy Fauno. Estoy aquí para ayudarte con remedios naturales. ¿Cómo te sientes?",
            "¡Bienvenido! Soy Fauno, especialista en herbolaria. ¿Qué molestia tienes?",
            "Hola, me llamo Fauno. Puedo recomendarte plantas medicinales. ¿Qué síntomas presentas?",
            "¡Saludos! Soy Fauno, tu guía en medicina natural. ¿En qué puedo ayudarte hoy?"
        ]
        return {"message": random.choice(fallbacks)}

@app.get("/debug-session/{session_id}")
async def debug_session(session_id: str):
    """Endpoint para debug de sesiones"""
    return {
        "session_id": session_id,
        "cached_plants": session_recommendations_cache.get(session_id, []),
        "cache_timestamp": session_cache_timestamps.get(session_id),
        "cache_size": len(session_recommendations_cache),
        "all_sessions": list(session_recommendations_cache.keys())
    }

@app.get("/test-rag-format")
async def test_rag_format():
    """Prueba directa del formato RAG"""
    test_patient = {
        'symptoms': 'dolor de cabeza moderado',
        'duration': '2 días', 
        'intensity': 'moderado',
        'allergies': 'ninguna',
        'age': 30,
        'weight': 70,
        'causa_ambiental': 'frío',
        'causa_emocional': 'estrés',
        'causa_dietetica': 'no'
    }
    
    from app.rag_chain import evaluate_real_rag_system
    rag_text, precision = await evaluate_real_rag_system(test_patient)
    
    from app.hybrid_recommender import HybridRecommender
    hybrid = HybridRecommender(db_config)
    parsed = hybrid._parse_rag_to_structured(rag_text)
    
    return {
        "rag_raw_response": rag_text,
        "rag_precision": precision,
        "parsed_plants": parsed,
        "plant_count": len(parsed),
        "diagnosis": "OK" if len(parsed) == 3 else f"ERROR: Solo {len(parsed)} plantas"
    }

@app.post("/rag/chat")
async def chat_endpoint(consultation: PatientConsultation):
    try:
        cleanup_old_sessions()
        
        logger.info("="*80)
        logger.info(f"📨 REQUEST /rag/chat")
        logger.info(f"   Session: {consultation.session_id}")
        logger.info(f"   Selected Plant: {consultation.selected_plant}")
        logger.info("="*80)
        
        # ============================================================
        # CASO 1: SELECCIÓN DE PLANTA → GENERAR PREPARACIÓN
        # ============================================================
        if consultation.selected_plant:
            logger.info(f"🌿 CASO 1: Selección de planta")
            
            selected_normalized = normalize_text(consultation.selected_plant)
            selected_cleaned = clean_plant_name(selected_normalized)
            
            logger.info(f"   Original: '{consultation.selected_plant}'")
            logger.info(f"   Limpio: '{selected_cleaned}'")
            
            # ============================================================
            # PASO 1: OBTENER PLANTAS RECOMENDADAS
            # ============================================================
            recommended_plants_names = []
            
            # 1.1 Desde patient_info
            if consultation.patient_info and 'recommended_plants' in consultation.patient_info:
                recommended_plants_names = consultation.patient_info['recommended_plants']
                logger.info(f"   ✅ Plantas desde patient_info: {recommended_plants_names}")
            
            # 1.2 Desde caché
            if not recommended_plants_names and consultation.session_id:
                cached = session_recommendations_cache.get(consultation.session_id, [])
                if cached:
                    recommended_plants_names = cached
                    logger.info(f"   ✅ Plantas desde caché: {recommended_plants_names}")
            
            # 1.3 Desde último mensaje
            if not recommended_plants_names and consultation.patient_info:
                last_rec = consultation.patient_info.get('last_recommendations', '')
                if last_rec:
                    pattern = r'\*\*\d+\.\s+([^*]+?)\*\*'
                    matches = re.findall(pattern, last_rec)
                    if matches:
                        recommended_plants_names = [m.strip() for m in matches]
                        logger.info(f"   ✅ Plantas desde mensaje: {recommended_plants_names}")
            
            # 1.4 Fallback: todas las plantas conocidas
            if not recommended_plants_names:
                logger.warning("   ⚠️ Sin plantas previas, usando todas")
                from app.hybrid_recommender import IntelligentHybridRecommender
                temp = IntelligentHybridRecommender({})
                recommended_plants_names = list(temp.safety_constraints.keys())
            
            # Limpiar nombres
            cleaned_recommended = [
                clean_plant_name(normalize_text(p)) 
                for p in recommended_plants_names
            ]
            
            logger.info(f"   📋 {len(cleaned_recommended)} plantas disponibles")
            logger.info(f"   {cleaned_recommended}")
            
            # ============================================================
            # PASO 2: BUSCAR COINCIDENCIA MEJORADA
            # ============================================================
            def fuzzy_match_plant_improved(selected: str, available_plants: List[str]) -> Optional[str]:
                if not selected or not available_plants:
                    return None
                
                selected_lower = selected.lower().strip()
                
                # ESTRATEGIA 1: Número
                try:
                    index = int(selected_lower) - 1
                    if 0 <= index < len(available_plants):
                        matched = available_plants[index]
                        logger.info(f"✅ Match NÚMERO → '{matched}'")
                        return matched
                except ValueError:
                    pass
                
                # ESTRATEGIA 2: Coincidencia exacta
                for plant in available_plants:
                    if selected_lower == plant.lower():
                        logger.info(f"✅ Match EXACTO → '{plant}'")
                        return plant
                
                # ESTRATEGIA 3: Substring
                for plant in available_plants:
                    plant_lower = plant.lower()
                    if selected_lower in plant_lower or plant_lower in selected_lower:
                        logger.info(f"✅ Match SUBSTRING → '{plant}'")
                        return plant
                
                # ESTRATEGIA 4: Primera palabr
                selected_words = selected_lower.split()
                if selected_words and len(selected_words[0]) >= 4:
                    first_word = selected_words[0]
                    for plant in available_plants:
                        plant_words = plant.lower().split()
                        if plant_words and first_word == plant_words[0]:
                            logger.info(f"✅ Match PRIMERA PALABRA → '{plant}'")
                            return plant
                
                # ESTRATEGIA 5: Similitud textual
                max_similarity = 0.0
                best_match = None
                
                for plant in available_plants:
                    plant_lower = plant.lower()
                    similarity = calculate_similarity(selected_lower, plant_lower)
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match = plant
                
                if max_similarity >= 0.6:
                    logger.info(f"✅ Match SIMILITUD ({max_similarity:.2f}) → '{best_match}'")
                    return best_match
                
                # ESTRATEGIA 6: Confirmación genérica
                confirmation_words = {'si', 'sí', 'yes', 'ok', 'dale', 'claro', 'esa', 'confirmo'}
                if any(word in selected_lower for word in confirmation_words) and len(available_plants) == 1:
                    logger.info(f"✅ CONFIRMACIÓN → '{available_plants[0]}'")
                    return available_plants[0]
                
                logger.warning(f"❌ Sin match para: '{selected}'")
                return None
            
            matched_plant = fuzzy_match_plant_improved(
                selected_cleaned, 
                cleaned_recommended
            )
            
            if not matched_plant:
                logger.error(f"   ❌ NO MATCH para '{consultation.selected_plant}'")
                
                plants_list = "\n".join([
                    f"**{i+1}. {p.title()}**" 
                    for i, p in enumerate(cleaned_recommended[:5])
                ])
                
                return {
                    "answer": f"""❌ No reconozco **'{consultation.selected_plant}'**

**Plantas disponibles:**
{plants_list}

💡 Escribe el número (1, 2, 3) o el nombre completo
""",
                    "requires_selection": True,
                    "recommended_plants": cleaned_recommended[:5],
                    "session_id": consultation.session_id,
                    "result_type": "invalid_selection"
                }
            
            validated_plant = matched_plant.strip()
            logger.info(f"   ✅✅✅ PLANTA VALIDADA: '{validated_plant}'")
            
            # ============================================================
            # PASO 3: PREPARAR INFO DEL PACIENTE
            # ============================================================
            if not consultation.patient_info:
                consultation.patient_info = {}
            
            defaults = {
                'symptoms': 'Síntomas no especificados',
                'duration': 'No especificada',
                'intensidad_sintomas': 'Moderada',
                'allergies': 'Ninguna',
                'causa_ambiental': 'No especificada',
                'causa_emocional': 'No especificada',
                'causa_dietetica': 'No especificada',
                'age': 30,
                'gender': 'No especificado',
                'zone': 'Lima',
                'weight': 70.0
            }
            
            for key, value in defaults.items():
                if key not in consultation.patient_info or not consultation.patient_info[key]:
                    consultation.patient_info[key] = value
            
            # Cargar datos del usuario si existe
            user_id = consultation.patient_info.get('user_id')
            if user_id and user_id not in ['anonymous', 'test_user', '', None]:
                try:
                    user_data = await get_user_data_from_db(user_id)
                    if user_data:
                        consultation.patient_info.update({
                            'age': user_data.get('age', 30),
                            'gender': user_data.get('gender', 'No especificado'),
                            'zone': user_data.get('zone', 'Lima'),
                            'weight': user_data.get('weight', 70.0),
                        })
                        logger.info(f"   ✅ Datos usuario {user_id} cargados")
                except Exception as e:
                    logger.warning(f"   ⚠️ Error cargando usuario: {e}")
            
            logger.info(f"   📊 Paciente:")
            logger.info(f"      Síntomas: {consultation.patient_info.get('symptoms')}")
            logger.info(f"      Edad: {consultation.patient_info.get('age')}")
            
            # ============================================================
            # PASO 4: 🔥 GENERAR PREPARACIÓN CON RAG
            # ============================================================
            try:
                logger.info("   🔥🔥🔥 LLAMANDO RAG PARA PREPARACIÓN 🔥🔥🔥")
                
                from app.rag_chain import get_plant_preparation_with_rag
                
                result = await get_plant_preparation_with_rag(
                    plant_name=validated_plant,
                    patient_info=consultation.patient_info,
                    moderate_warning=""
                )
                
                logger.info(f"   ✅ RAG ejecutado")
                logger.info(f"      Método: {result.get('preparation_method')}")
                logger.info(f"      Similitud: {result.get('retrieval_similarity', 0):.3f}")
                logger.info(f"      Respuesta: {len(result.get('answer', ''))} chars")
                
                # Guardar consulta en BD
                if user_id and user_id not in ['anonymous', 'test_user', '', None]:
                    try:
                        await save_consultation(
                            user_id=user_id,
                            session_id=consultation.session_id or 'unknown',
                            symptoms=consultation.patient_info.get('symptoms', ''),
                            symptoms_duration=consultation.patient_info.get('duration', ''),
                            symptoms_intensity=consultation.patient_info.get('intensidad_sintomas', 'Moderada'),
                            allergies=consultation.patient_info.get('allergies', 'ninguna'),
                            causa_ambiental=consultation.patient_info.get('causa_ambiental'),
                            causa_emocional=consultation.patient_info.get('causa_emocional'),
                            causa_dietetica=consultation.patient_info.get('causa_dietetica'),
                            recommended_plant=validated_plant,
                            risk_level="BAJO_RIESGO"
                        )
                        logger.info("   ✅ Consulta guardada en BD")
                    except Exception as e:
                        logger.error(f"   ❌ Error guardando: {e}")
                
                # Verificar respuesta válida
                final_answer = result.get('answer', '')
                
                if final_answer and len(final_answer.strip()) > 150:
                    logger.info(f"   ✅✅✅ PREPARACIÓN LISTA ({len(final_answer)} chars)")
                    
                    return {
                        "answer": final_answer,
                        "selected_plant": validated_plant,
                        "session_id": consultation.session_id,
                        "preparation_method": result.get('preparation_method', 'RAG_SYSTEM'),
                        "phase": "DETAILED_PREPARATION",
                        "retrieval_similarity": result.get('retrieval_similarity', 0.0),
                        "user_info_used": user_id is not None,
                        "success": True
                    }
                else:
                    logger.warning(f"   ⚠️ Respuesta RAG corta ({len(final_answer)} chars)")
                    raise Exception("Respuesta RAG insuficiente")
                
            except Exception as e:
                logger.error(f"   ❌❌❌ ERROR RAG: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # FALLBACK
                logger.info("   🔄 Generando FALLBACK")
                
                fallback_answer = f"""
🌿 **{validated_plant.title()}**

**Preparación básica:**
1. Colocar 1-2 cucharaditas en una taza
2. Verter 250ml de agua recién hervida
3. Tapar y reposar 5-10 minutos
4. Colar y beber tibio

**Dosis:**
- 2-3 tazas al día
- Después de comidas

**Duración:**
- 7-10 días máximo

**Precauciones:**
⚠️ No usar en embarazo sin supervisión
⚠️ Suspender si hay efectos adversos
⚠️ No sustituye tratamiento médico

🏥 **IMPORTANTE:** Consulta con un especialista para tratamiento personalizado.

---
*Error técnico: {str(e)[:100]}... - Información básica generada*
"""
                
                return {
                    "answer": fallback_answer,
                    "selected_plant": validated_plant,
                    "session_id": consultation.session_id,
                    "preparation_method": "FALLBACK",
                    "error": str(e),
                    "success": False
                }
        
        # ============================================================
        # CASO 2: GENERAR RECOMENDACIONES INICIALES
        # ============================================================
        logger.info("🔄 CASO 2: Generando recomendaciones")
        
        if not consultation.patient_info:
            consultation.patient_info = {}
        
        # Completar info usuario
        user_id = consultation.patient_info.get('user_id')
        if user_id and user_id not in ['anonymous', 'test_user', '', None]:
            user_data = await get_user_data_from_db(user_id)
            if user_data:
                consultation.patient_info.update({
                    'age': user_data.get('age', 30),
                    'gender': user_data.get('gender', 'No especificado'),
                    'zone': user_data.get('zone', 'Lima'),
                    'weight': user_data.get('weight', 70.0),
                })
        
        if consultation.session_id:
            consultation.patient_info['session_id'] = consultation.session_id
        
        logger.info("   🤖 Llamando hybrid_recommender...")
        response = await hybrid_recommender.get_hybrid_recommendations_async(
            consultation.patient_info
        )
        
        if "error" in response:
            raise HTTPException(status_code=500, detail=response["error"])
        
        # Cachear plantas
        if consultation.session_id and 'final_recommendations' in response:
            final_recs = response['final_recommendations']
            if final_recs and len(final_recs) >= 3:
                recommended_names = [plant['name'] for plant in final_recs[:3]]
                session_recommendations_cache[consultation.session_id] = recommended_names
                session_cache_timestamps[consultation.session_id] = datetime.now()
                logger.info(f"   ✅ Cacheadas: {recommended_names}")
        
        logger.info(f"✅✅✅ RECOMENDACIONES GENERADAS")
        return response
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"❌❌❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/hybrid-status")
async def get_hybrid_status():
    """Endpoint para diagnosticar el estado del hybrid recommender"""
    try:
        rag_status = hybrid_recommender.get_rag_status()
        
        # Probar con datos de ejemplo
        test_patient_info = {
            'symptoms': 'dolor de cabeza',
            'duration': '2 días',
            'intensity': 'moderado',
            'allergies': 'ninguna',
            'causa_ambiental': 'exposición al sol',
            'causa_emocional': 'estrés',
            'causa_dietetica': 'no desayuné',
            'session_id': 'test-session'
        }
        
        test_result = await hybrid_recommender.get_hybrid_recommendations_async(test_patient_info)
        
        return {
            "hybrid_system_working": True,
            "rag_status": rag_status,
            "test_result": {
                "selected_system": test_result.get('selected_system'),
                "rna_precision": test_result.get('rna_precision'),
                "rag_precision": test_result.get('rag_precision'),
                "selection_reason": test_result.get('selection_reason')
            }
        }
    except Exception as e:
        logger.error(f"Error en hybrid-status: {e}")
        return {
            "hybrid_system_working": False,
            "error": str(e)
        }
    

@app.post("/hybrid_recommender")
async def hybrid_recommender_endpoint(request: dict):
    try:
        session_id = request.get("session_id")
        patient_info = request.get("patient_info", {})
        
        # 🔥 AGREGAR: Enriquecer con datos del usuario ANTES de llamar al recommender
        user_id = patient_info.get('user_id')
        if user_id and user_id not in ['anonymous', 'test_user', '', None]:
            try:
                user_data = await get_user_data_from_db(user_id)
                if user_data:
                    patient_info.update({
                        'age': user_data.get('age', 30),
                        'gender': user_data.get('gender', 'Not specified'),
                        'zone': user_data.get('zone', 'Lima'),
                        'weight': user_data.get('weight', 70.0),
                    })
                    logger.info(f"✅ Datos usuario {user_id} cargados para recommender")
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron cargar datos de usuario: {e}")
        
        # Valores por defecto si faltan
        patient_info.setdefault('age', 30)
        patient_info.setdefault('gender', 'Not specified')
        patient_info.setdefault('zone', 'Lima')
        patient_info.setdefault('weight', 70.0)
        
        if session_id:
            patient_info['session_id'] = session_id
        
        logger.info(f"📋 Llamando hybrid_recommender con:")
        logger.info(f"   symptoms: {patient_info.get('symptoms')}")
        logger.info(f"   intensidad: {patient_info.get('intensidad_sintomas')}")
        logger.info(f"   age: {patient_info.get('age')}")
        
        recommendations = await hybrid_recommender.get_hybrid_recommendations_async(patient_info)
        
        # 🔥 Cachear plantas
        if session_id and 'final_recommendations' in recommendations:
            final_recs = recommendations['final_recommendations']
            if final_recs:
                recommended_names = [plant['name'] for plant in final_recs[:3]]
                session_recommendations_cache[session_id] = recommended_names
                session_cache_timestamps[session_id] = datetime.now()
                logger.info(f"✅ Cacheadas: {recommended_names}")
        
        return {
            "session_id": session_id,
            "status": "success",
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ ERROR en /hybrid_recommender: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Fallback estructurado
        fallback = {
            "selected_system": "FALLBACK",
            "rna_precision": 0.5,
            "rag_precision": 0.5,
            "intelligent_precision": 0.5,
            "final_recommendations": [
                {"name": "Manzanilla", "scientific_name": "Matricaria chamomilla", 
                 "confidence": 0.70, "rank": 1, "sources": ["FALLBACK"], "properties": []},
                {"name": "Menta", "scientific_name": "Mentha piperita",
                 "confidence": 0.65, "rank": 2, "sources": ["FALLBACK"], "properties": []},
                {"name": "Hierba Luisa", "scientific_name": "Aloysia citrodora",
                 "confidence": 0.60, "rank": 3, "sources": ["FALLBACK"], "properties": []}
            ],
            "patient_symptoms": request.get("patient_info", {}).get("symptoms", ""),
            "rag_available": False,
            "answer": "Basándome en tus síntomas te recomiendo estas plantas. Escribe 1, 2 o 3 para ver la preparación."
        }
        
        return {
            "session_id": request.get("session_id"),
            "status": "fallback",
            "recommendations": fallback,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/debug-hybrid")
async def debug_hybrid_system():
    """Endpoint de diagnóstico detallado del sistema híbrido"""
    try:
        # Probar con datos similares a tu caso
        test_patient_info = {
            'symptoms': 'dolor de estomago',
            'duration': '1 día',
            'intensity': 'moderado',
            'allergies': 'ninguna',
            'causa_ambiental': 'dormir con polo mojado',
            'causa_emocional': 'no hay',
            'causa_dietetica': 'no hay',
            'session_id': 'debug-session'
        }
        
        # Probar RNA
        normalized_info = await hybrid_recommender._normalize_patient_info(test_patient_info)

        rna_recommendations = hybrid_recommender._get_rna_predictions(normalized_info)
        rna_precision = hybrid_recommender._calculate_rna_precision(rna_recommendations)
        
        # Probar RAG
        rag_text, rag_precision = await hybrid_recommender.rag_module.evaluate_rag_system(normalized_info)
        
        return {
            "test_case": test_patient_info,
            "rna_analysis": {
                "recommendations": rna_recommendations,
                "precision": rna_precision,
                "normalized_input": normalized_info
            },
            "rag_analysis": {
                "precision": rag_precision,
                "response_sample": rag_text[:200] + "..." if rag_text else "Empty"
            },
            "comparison": {
                "rna_precision": rna_precision,
                "rag_precision": rag_precision,
                "difference": rna_precision - rag_precision,
                "winner": "RNA" if rna_precision > rag_precision else "RAG"
            },
            "rag_status": hybrid_recommender.get_rag_status()
        }
    except Exception as e:
        logger.error(f"Error en debug-hybrid: {e}")
        return {"error": str(e)}

@app.get("/test-intensity-detection")
async def test_intensity_detection():
    """Endpoint para probar detección de intensidad"""
    test_cases = [
        "intnsidad media",
        "masonenos", 
        "moderado",
        "medio",
        "leve",
        "severo",
        "mas o menos",
        "intensidad media"
    ]
    
    results = {}
    agent = NaturalConversationAgent()
    
    for case in test_cases:
        intensity = agent._detect_intensity(case)
        is_valid, value = agent._validate_intensity_response(case)
        results[case] = {
            "detected_intensity": intensity,
            "validated": is_valid,
            "validated_value": value
        }
    
    return results

@app.post("/feedback")
async def save_feedback(feedback: FeedbackRequest):
    conn = None
    cursor = None
    
    try:
        try:
            session_uuid = uuid.UUID(feedback.session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session_id format")
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM treatment_feedback WHERE CAST(session_id AS VARCHAR) = %s",
            (str(session_uuid),)
        )
        existing_feedback = cursor.fetchone()
        
        if existing_feedback:
            update_query = """
            UPDATE treatment_feedback 
            SET effectiveness_rating = %s, side_effects = %s, improvement_time = %s,
                additional_comments = %s, updated_at = CURRENT_TIMESTAMP
            WHERE CAST(session_id AS VARCHAR) = %s
            """
            cursor.execute(update_query, (
                feedback.effectiveness_rating, feedback.side_effects,
                feedback.improvement_time, feedback.additional_comments, str(session_uuid)
            ))
        else:
            insert_query = """
            INSERT INTO treatment_feedback 
                (session_id, effectiveness_rating, side_effects, improvement_time, 
                additional_comments, plant_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """
            cursor.execute(insert_query, (
                str(session_uuid), feedback.effectiveness_rating, feedback.side_effects,
                feedback.improvement_time, feedback.additional_comments,
                feedback.plant_name
            ))
        
        conn.commit()
        logger.info("Feedback guardado")
        
        return {
            "status": "success",
            "message": "Feedback guardado correctamente",
            "session_id": str(session_uuid)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error guardando feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ============================================================================
# 📝 ENDPOINTS DE USUARIO CON FOTOS DE PERFIL
# ============================================================================
@app.get("/api/plant-reports/{plant_name}")
async def get_plant_user_reports(plant_name: str):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tf.side_effects, tf.effectiveness_rating
            FROM treatment_feedback tf
            JOIN consultations c ON CAST(c.session_id AS VARCHAR) = CAST(tf.session_id AS VARCHAR)
            WHERE LOWER(c.recommended_plant) = LOWER(%s)
              AND tf.side_effects IS NOT NULL
              AND TRIM(tf.side_effects) != ''
              AND LOWER(TRIM(tf.side_effects)) NOT IN 
                  ('ninguno','ninguna','no','nada','n/a','none')
            ORDER BY tf.created_at DESC
            LIMIT 5
        """, (plant_name,))
        rows = cursor.fetchall()
        reports = [
            {"side_effect": row[0].strip(), "effectiveness": row[1]}
            for row in rows if row[0] and len(row[0].strip()) > 3
        ]
        return {"plant_name": plant_name, "reports": reports}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"plant_name": plant_name, "reports": []}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.post("/api/register")
async def register_user(
    fullName: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    dni: str = Form(...),
    phoneNumber: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    weight: float = Form(...),
    height: float = Form(...),
    zone: str = Form(...),
    occupation: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None)
):
    connection = None
    cursor = None
    profile_picture_path = None  # ✅ DEFINIDA AL INICIO
    
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        logger.info(f"📝 Registrando usuario: {username}")
        
        # Validar que no exista
        cursor.execute("SELECT username FROM personal_information WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
            
        cursor.execute("SELECT email FROM personal_information WHERE email = %s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
            
        cursor.execute("SELECT dni FROM personal_information WHERE dni = %s", (dni,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El DNI ya está registrado")

        # Procesar foto de perfil si existe
        if profile_picture and profile_picture.filename:
            logger.info(f"📸 Procesando foto de perfil para {username}")
            profile_picture_path = await save_profile_picture(profile_picture)
            if profile_picture_path:
                logger.info(f"✅ Foto guardada: {profile_picture_path}")
            else:
                logger.warning(f"⚠️ Foto no válida para {username}")
                profile_picture_path = None  # Asegurar que sea None si no es válida

        # Hash de la contraseña
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        # Insertar en la base de datos
        INSERT_USER = """
        INSERT INTO personal_information (
            full_name, email, username, password_hash, dni, phone_number,
            age, gender, weight, height, zone, education_level, occupation, 
            profile_picture_path, created_at, last_login, role
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'user')
        """

        cursor.execute(INSERT_USER, (
            fullName, email, username, hashed_password, dni, phoneNumber,
            age, gender, weight, height, zone, 'No especificada',
            occupation, profile_picture_path, datetime.now(), None
        ))

        connection.commit()
        logger.info(f"✅ Usuario registrado: {username}")
        
        # Construir URL completa para la foto si existe
        photo_url = None
        if profile_picture_path:
            photo_url = f"http://localhost:8000{profile_picture_path}"
        
        return {
            "message": "Usuario registrado exitosamente",
            "username": username,
            "profile_picture_url": photo_url
        }

    except HTTPException as e:
        # ✅ CORREGIDO: profile_picture_path ahora está definida
        if profile_picture_path:
            try:
                os.remove(f"app{profile_picture_path}")
                logger.info(f"🗑️ Foto eliminada por error de registro: {profile_picture_path}")
            except Exception as delete_error:
                logger.warning(f"⚠️ No se pudo eliminar foto: {delete_error}")
        raise e
    except Exception as e:
        # También limpiar si hay otros errores
        if profile_picture_path:
            try:
                os.remove(f"app{profile_picture_path}")
                logger.info(f"🗑️ Foto eliminada por error: {profile_picture_path}")
            except:
                pass
        logger.error(f"❌ Error registrando usuario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.post("/api/login")
async def login(credentials: LoginCredentials):
    connection = None
    cursor = None
    
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        logger.info(f"🔐 Intento de login: {credentials.identifier}")

        cursor.execute(
            "SELECT username, password_hash FROM personal_information WHERE username = %s",
            (credentials.identifier,)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos"
            )

        username, stored_hash = user

        password_bytes = credentials.password.encode('utf-8')
        stored_hash_bytes = stored_hash.encode('utf-8')
        
        if not bcrypt.checkpw(password_bytes, stored_hash_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos"
            )

        cursor.execute(
            "UPDATE personal_information SET last_login = %s WHERE username = %s",
            (datetime.now(), username)
        )
        connection.commit()

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )

        logger.info(f"✅ Login exitoso: {username}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": username
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Error en login: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.get("/api/user/{username}")
async def get_user_profile(username: str):
    """
    Obtiene el perfil completo de un usuario, incluyendo la foto
    """
    connection = None
    cursor = None
    
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        query = """
        SELECT id, full_name, email, username, dni, phone_number, age, gender, 
               weight, height, zone, education_level, occupation, 
               profile_picture_path, created_at, role
        FROM personal_information 
        WHERE username = %s
        """
        
        cursor.execute(query, (username,))
        user_data = cursor.fetchone()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Construir respuesta
        user_dict = {
            "id": str(user_data[0]),
            "full_name": user_data[1],
            "email": user_data[2],
            "username": user_data[3],
            "dni": user_data[4],
            "phone_number": user_data[5],
            "age": user_data[6],
            "gender": user_data[7],
            "weight": float(user_data[8]) if user_data[8] else None,
            "height": float(user_data[9]) if user_data[9] else None,
            "zone": user_data[10],
            "education_level": user_data[11],
            "occupation": user_data[12],
            "profile_picture_url": f"http://localhost:8000{user_data[13]}" if user_data[13] else None,
            "created_at": user_data[14].isoformat() if user_data[14] else None,
            "role": user_data[15]
        }
        
        return user_dict
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Error obteniendo perfil: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Obtener usuario de la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, email, full_name, dni, phone_number, 
                   age, gender, weight, height, zone, occupation, 
                   profile_picture_path, created_at, last_login, role
            FROM personal_information 
            WHERE username = %s
        """, (username,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 🔴 REEMPLAZA ESTO:
        # return dict(user)
        
        # ✅ CON ESTO (mapear explícitamente):
        columns = [
            'id', 'username', 'email', 'full_name', 'dni', 'phone_number',
            'age', 'gender', 'weight', 'height', 'zone', 'occupation',
            'profile_picture_path', 'created_at', 'last_login', 'role'
        ]
        
        user_dict = {}
        for i, col in enumerate(columns):
            user_dict[col] = user[i] if i < len(user) else None
        
        # Asegurar tipos correctos
        if user_dict.get('age'):
            try:
                user_dict['age'] = int(user_dict['age'])
            except:
                user_dict['age'] = None
        
        if user_dict.get('weight'):
            try:
                user_dict['weight'] = float(user_dict['weight'])
            except:
                user_dict['weight'] = None
        
        if user_dict.get('height'):
            try:
                user_dict['height'] = float(user_dict['height'])
            except:
                user_dict['height'] = None
        
        if user_dict.get('profile_picture_path'):
            user_dict['profile_picture_url'] = f"http://localhost:8000{user_dict['profile_picture_path']}"
        
        logger.info(f"✅ Usuario autenticado: {username}")
        return user_dict
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Error en get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
@app.put("/api/user/{username}/update")
async def update_user_profile(
    username: str,
    full_name: str = Form(None),
    email: str = Form(None),
    dni: str = Form(None),
    phone_number: str = Form(None),
    age: int = Form(None),
    gender: str = Form(None),
    weight: float = Form(None),
    height: float = Form(None),
    zone: str = Form(None),
    occupation: str = Form(None),
    profile_picture: UploadFile = File(None),
    current_user: dict = Depends(get_current_user)
):
    try:
        logger.info(f"📝 Actualizando perfil de usuario: {username}")
        
        # Verificar que el usuario sea el propietario del perfil
        if current_user["username"] != username:
            raise HTTPException(status_code=403, detail="No autorizado para actualizar este perfil")
        
        conn = get_connection()  # ✅ Ahora existe esta función
        cursor = conn.cursor()
        
        # 1. Manejar la foto de perfil si existe
        profile_picture_path = None
        if profile_picture:
            try:
                # Guardar usando la función existente
                profile_picture_path = await save_profile_picture(profile_picture)
                if profile_picture_path:
                    logger.info(f"✅ Foto guardada: {profile_picture_path}")
            except Exception as e:
                logger.error(f"❌ Error guardando foto: {str(e)}")
                raise HTTPException(status_code=500, detail="Error al guardar la imagen")
        
        # 2. Preparar los datos para actualizar
        update_fields = []
        update_values = []
        
        # Mapeo de campos
        if full_name is not None:
            update_fields.append("full_name = %s")
            update_values.append(full_name)
        if email is not None:
            update_fields.append("email = %s")
            update_values.append(email)
        if dni is not None:
            update_fields.append("dni = %s")
            update_values.append(dni)
        if phone_number is not None:
            update_fields.append("phone_number = %s")
            update_values.append(phone_number)
        if age is not None:
            update_fields.append("age = %s")
            update_values.append(age)
        if gender is not None:
            update_fields.append("gender = %s")
            update_values.append(gender)
        if weight is not None:
            update_fields.append("weight = %s")
            update_values.append(float(weight))
        if height is not None:
            update_fields.append("height = %s")
            update_values.append(float(height))
        if zone is not None:
            update_fields.append("zone = %s")
            update_values.append(zone)
        if occupation is not None:
            update_fields.append("occupation = %s")
            update_values.append(occupation)
        if profile_picture_path is not None:
            update_fields.append("profile_picture_path = %s")
            update_values.append(profile_picture_path)
        
        # Si no hay campos para actualizar
        if not update_fields:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")
        
        # 3. Construir y ejecutar la consulta SQL
        update_values.append(username)
        query = f"""
            UPDATE personal_information 
            SET {', '.join(update_fields)}
            WHERE username = %s
            RETURNING id, username, email, full_name, dni, phone_number, 
                     age, gender, weight, height, zone, occupation, 
                     profile_picture_path, created_at, last_login, role;
        """
        
        logger.info(f"📝 Query SQL: {query}")
        
        cursor.execute(query, update_values)
        updated_user = cursor.fetchone()
        
        if not updated_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        conn.commit()
        
        # ✅ CORREGIR: Convertir tupla a diccionario correctamente
        columns = [
            'id', 'username', 'email', 'full_name', 'dni', 'phone_number',
            'age', 'gender', 'weight', 'height', 'zone', 'occupation',
            'profile_picture_path', 'created_at', 'last_login', 'role'
        ]
        
        user_dict = {}
        for i, col in enumerate(columns):
            user_dict[col] = updated_user[i] if i < len(updated_user) else None
        
        # Añadir URL de la foto si existe
        if user_dict.get('profile_picture_path'):
            user_dict['profile_picture_url'] = f"http://localhost:8000{user_dict['profile_picture_path']}"
        
        logger.info(f"✅ Perfil actualizado exitosamente: {username}")
        
        return {
            "message": "Perfil actualizado exitosamente",
            "user": user_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error actualizando perfil: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@app.post("/api/validate-token")
async def validate_token():
    """Endpoint para validar tokens - requerido por el frontend"""
    # Este endpoint es simple porque la validación real se hace en get_current_user
    return {"valid": True}

@app.put("/api/user/{username}/profile-picture")
async def update_profile_picture(
    username: str,
    profile_picture: UploadFile = File(...)
):
    """
    Actualiza la foto de perfil de un usuario
    """
    connection = None
    cursor = None
    
    try:
        # Verificar que el usuario existe
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        cursor.execute("SELECT profile_picture_path FROM personal_information WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Guardar nueva foto
        old_photo_path = user[0]
        new_photo_path = await save_profile_picture(profile_picture)
        
        if not new_photo_path:
            raise HTTPException(status_code=400, detail="Imagen no válida")
        
        # Actualizar en la base de datos
        cursor.execute(
            "UPDATE personal_information SET profile_picture_path = %s WHERE username = %s",
            (new_photo_path, username)
        )
        
        connection.commit()
        
        # Eliminar foto anterior si existe
        if old_photo_path:
            try:
                os.remove(f"app{old_photo_path}")
            except:
                logger.warning(f"⚠️ No se pudo eliminar foto anterior: {old_photo_path}")
        
        return {
            "message": "Foto de perfil actualizada",
            "profile_picture_url": f"http://localhost:8000{new_photo_path}"
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Error actualizando foto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.get("/debug-hybrid-detailed")
async def debug_hybrid_detailed():
    """Endpoint de diagnóstico detallado del sistema híbrido CORREGIDO"""
    try:
        # Probar con datos similares a tu caso de uso real
        test_patient_info = {
            'symptoms': 'dolor de estomago y fiebre',
            'duration': '2 días',
            'intensity': 'moderado',
            'allergies': 'ninguna',
            'causa_ambiental': 'dormir con polo mojado',
            'causa_emocional': 'no hay',
            'causa_dietetica': 'no hay',
            'session_id': 'debug-session-detailed',
            'age': 35,
            'weight': 70.0,
            'gender': 'masculino',
            'zone': 'Lima'
        }
        
        # Probar normalización
        normalized_info = await hybrid_recommender._normalize_patient_info(test_patient_info)

        
        # Probar RNA
        rna_recommendations = hybrid_recommender._get_rna_predictions(normalized_info)
        rna_precision = hybrid_recommender._calculate_rna_precision(rna_recommendations)
        
        # Probar RAG
        rag_text = ""
        rag_precision = 0.0
        if hybrid_recommender.RAG_AVAILABLE and hybrid_recommender.rag_module:
            try:
                rag_text, rag_precision = await hybrid_recommender.rag_module.evaluate_rag_system(normalized_info)
            except Exception as e:
                rag_text, rag_precision = hybrid_recommender._get_fallback_rag_recommendations(test_patient_info['symptoms'])
        else:
            rag_text, rag_precision = hybrid_recommender._get_fallback_rag_recommendations(test_patient_info['symptoms'])
        
        # Probar recomendación híbrida completa
        hybrid_result = await hybrid_recommender.get_hybrid_recommendations_async(test_patient_info)
        
        return {
            "test_case": test_patient_info,
            "normalized_info": normalized_info,
            "rna_analysis": {
                "recommendations": rna_recommendations,
                "precision": rna_precision,
                "precision_calculation": "BOOSTED_ALGORITHM",
                "recommendations_count": len(rna_recommendations)
            },
            "rag_analysis": {
                "available": hybrid_recommender.RAG_AVAILABLE,
                "precision": rag_precision,
                "response_sample": rag_text[:200] + "..." if rag_text else "Empty",
                "module_loaded": hybrid_recommender.rag_module is not None
            },
            "hybrid_selection": {
                "selected_system": hybrid_result.get('selected_system'),
                "selection_reason": hybrid_result.get('selection_reason'),
                "rna_precision": hybrid_result.get('rna_precision'),
                "rag_precision": hybrid_result.get('rag_precision'),
                "selection_details": hybrid_result.get('selection_details', {})
            },
            "system_status": {
                "rna_trained": hybrid_recommender.rna_model.model_trained,
                "rag_available": hybrid_recommender.RAG_AVAILABLE
            }
        }
    except Exception as e:
        logger.error(f"❌ Error en debug-hybrid-detailed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/debug-rna-training")
async def debug_rna_training():
    """Endpoint para diagnosticar el entrenamiento del RNA"""
    try:
        # Verificar estado del modelo RNA
        model_info = {
            "model_trained": hybrid_recommender.rna_model.model_trained,
            "training_metrics": hybrid_recommender.rna_model.get_training_metrics(),
            "vocabulary_size": len(hybrid_recommender.rna_model.symptom_vocabulary) if hasattr(hybrid_recommender.rna_model, 'symptom_vocabulary') else 0
        }
        
        # Probar predicción
        test_info = {
            'symptoms': 'dolor de cabeza',
            'duration': '2 días', 
            'intensity': 'moderado',
            'allergies': 'ninguna'
        }
        normalized = hybrid_recommender._normalize_patient_info(test_info)
        predictions = hybrid_recommender._get_rna_predictions(normalized)
        precision = hybrid_recommender._calculate_rna_precision(predictions)
        
        return {
            "model_info": model_info,
            "test_prediction": {
                "predictions": predictions,
                "precision": precision,
                "normalized_input": normalized
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/test-symptoms")
async def test_symptoms():
    """Endpoint para probar diferentes síntomas y ver qué sistema selecciona"""
    test_cases = [
        {
            "symptoms": "dolor de cabeza fuerte",
            "duration": "1 día",
            "intensity": "severo",
            "allergies": "ninguna"
        },
        {
            "symptoms": "fiebre y tos",
            "duration": "3 días", 
            "intensity": "moderado",
            "allergies": "penicilina"
        },
        {
            "symptoms": "problemas digestivos",
            "duration": "1 semana",
            "intensity": "leve", 
            "allergies": "ninguna"
        },
        {
            "symptoms": "síntoma raro desconocido",
            "duration": "2 semanas",
            "intensity": "moderado",
            "allergies": "ninguna"
        }
    ]
    
    results = {}
    
    for i, test_case in enumerate(test_cases):
        try:
            # Completar información requerida
            test_case.update({
                'causa_ambiental': 'test',
                'causa_emocional': 'test', 
                'causa_dietetica': 'test',
                'session_id': f'test-session-{i}',
                'age': 30,
                'weight': 70.0,
                'gender': 'masculino',
                'zone': 'Lima'
            })
            
            result = await hybrid_recommender.get_hybrid_recommendations_async(test_case)
            
            results[f"case_{i+1}"] = {
                "symptoms": test_case["symptoms"],
                "selected_system": result.get("selected_system"),
                "rna_precision": result.get("rna_precision"),
                "rag_precision": result.get("rag_precision"), 
                "selection_reason": result.get("selection_reason"),
                "recommendations_count": len(result.get("final_recommendations", [])),
                "recommendations": [plant["name"] for plant in result.get("final_recommendations", [])[:3]]
            }
            
        except Exception as e:
            results[f"case_{i+1}"] = {"error": str(e)}
    
    return {
        "test_results": results,
        "summary": {
            "total_cases": len(test_cases),
            "rna_wins": sum(1 for case in results.values() if case.get("selected_system") == "RNA"),
            "rag_wins": sum(1 for case in results.values() if case.get("selected_system") == "RAG_OPTIMIZADO")
        }
    }

def run():
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    run()