
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
import psycopg2
from datetime import datetime, timedelta
import traceback
import uuid
import importlib.util
import sys
import os
import logging
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from urllib.parse import urlparse


# Configurar logging más detallado
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Para mostrar en consola
    ]
)
logger = logging.getLogger(__name__)

# Comprobar las rutas del proyecto para los imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Importar dependencias con try/except para manejar errores
try:
    from app.rag_chain import process_consultation_with_safety
    from app.hybrid_recommender import HybridRecommender
except ImportError:
    # Si falla, intentar importar de manera relativa
    try:
        from .rag_chain import process_consultation_with_safety
        from .hybrid_recommender import HybridRecommender
    except ImportError:
        # Si ambos fallan, importar directamente (considerando que estamos en el directorio app)
        try:
            import rag_chain
            from hybrid_recommender import HybridRecommender
            process_consultation_with_safety = rag_chain.process_consultation_with_safety
        except ImportError as e:
            print(f"Error de importación crítico: {e}")
            raise

# Importar bcrypt para el hash de contraseñas
try:
    import bcrypt
except ImportError:
    print("WARNING: bcrypt not installed. Installing...")
    import pip
    pip.main(['install', 'bcrypt'])
    import bcrypt

# Importar passlib.hash para compatibilidad
try:
    from passlib.hash import bcrypt as passlib_bcrypt
except ImportError:
    print("WARNING: passlib not installed. Some functionality may be limited.")
    passlib_bcrypt = None

# Importar jose para JWT
try:
    from jose import JWTError, jwt
except ImportError:
    print("WARNING: python-jose not installed. Installing...")
    import pip
    pip.main(['install', 'python-jose[cryptography]'])
    from jose import JWTError, jwt

# Inicializar el recomendador híbrido
hybrid_recommender = HybridRecommender()

# Configuración del JWT
SECRET_KEY = os.getenv("SECRET_KEY", "GROF*_*09")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 8  # 4 horas de validez (ajustable)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

# Configurar CORS
origins = [
    "http://localhost:3000",  # Para desarrollo local
    "http://localhost:3001",  # Para desarrollo local alternativo
    "https://plant-medicator-project-red.vercel.app",  # Tu dominio de Vercel
    "https://plant-medicator-project-pvin1pbxd-richard97chzs-projects.vercel.app",  # Tu dominio de deployment
    "https://*.vercel.app",  # Permitir todos los subdominios de Vercel
]

# Si estás en producción, agregar dinámicamente los dominios de Vercel
if os.getenv("NODE_ENV") == "production":
    # Agregar dominios de preview de Vercel
    origins.extend([
        "https://plant-medicator-project-git-main-richard97chzs-projects.vercel.app",
        # Puedes agregar más dominios aquí según sea necesario
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Usar 'origins' en lugar de 'CORS_ORIGINS'
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],  # Agregado HEAD
    allow_headers=["*"],
)

class PatientInfo(BaseModel):
    symptoms: str
    duration: str
    allergies: str
    user_id: Optional[str] = None

class PatientConsultation(BaseModel):
    session_id: Optional[str] = None
    patient_info: Dict[str, Any]
    selected_plant: Optional[str] = None

# Modelo de datos para el feedback
class FeedbackRequest(BaseModel):
    session_id: str
    effectiveness_rating: Optional[int] = None
    side_effects: Optional[str] = None
    improvement_time: Optional[str] = None
    additional_comments: Optional[str] = None

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def print_terminal_separator():
    """Imprime un separador visual en la terminal"""
    print("\n" + "="*80)

def detect_consultation_state(selected_plant: Optional[str], session_id: Optional[str]) -> tuple[str, str]:
    """
    Detecta el estado de la consulta basado en si hay una planta seleccionada
    """
    if selected_plant:
        return "PLANT_SELECTION", "Continuando consulta existente - Preparación detallada"
    else:
        return "INITIAL_CONSULTATION", "Nueva consulta iniciada - Análisis y recomendaciones"

def get_previous_recommendations_from_session(session_id: str) -> Dict[str, Any]:
    """
    Recupera las recomendaciones previas de una sesión para validar la planta seleccionada
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # CAMBIO: consultations -> patient_consultations
        query = """
        SELECT rna_recommendations, rag_recommendations, selected_system
        FROM patient_consultations 
        WHERE session_id = %s 
        ORDER BY created_at DESC 
        LIMIT 1
        """
        
        cursor.execute(query, (session_id,))
        result = cursor.fetchone()
        
        if result:
            return {
                'rna_recommendations': result[0],
                'rag_recommendations': result[1], 
                'selected_system': result[2]
            }
        else:
            return {}
            
    except Exception as e:
        logger.error(f"❌ Error recuperando recomendaciones previas: {str(e)}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def validate_plant_selection(selected_plant: str, session_id: str) -> tuple[bool, str]:
    """
    Valida que la planta seleccionada esté en las opciones previas
    """
    if not session_id:
        return False, "Session ID requerido para validación"
    
    previous_recs = get_previous_recommendations_from_session(session_id)
    
    if not previous_recs:
        logger.warning(f"⚠️  No se encontraron recomendaciones previas para session: {session_id}")
        return True, "Validación omitida - no hay recomendaciones previas"
    
    # Verificar en recomendaciones RAG (formato texto)
    rag_recs = previous_recs.get('rag_recommendations', '')
    if selected_plant.lower() in rag_recs.lower():
        return True, f"Planta '{selected_plant}' encontrada en recomendaciones RAG previas"
    
    # Verificar en recomendaciones RNA (si están disponibles)
    rna_recs = previous_recs.get('rna_recommendations', '')
    if selected_plant.lower() in rna_recs.lower():
        return True, f"Planta '{selected_plant}' encontrada en recomendaciones RNA previas"
    
    return False, f"Planta '{selected_plant}' no encontrada en opciones previas"

def print_consultation_header(state: str, session_id: str, selected_plant: Optional[str] = None):
    """
    Imprime el encabezado apropiado según el estado de la consulta
    """
    print_terminal_separator()
    
    if state == "PLANT_SELECTION":
        print("🔄 CONTINUANDO CONSULTA EXISTENTE")
        print_terminal_separator()
        print("=== FASE 6: PREPARACIÓN DETALLADA ===")
        print(f"📋 Contexto: Continuación de Session ID: {session_id}")
        print(f"🌱 Usuario seleccionó: {selected_plant}")
        print("📄 Generando preparación personalizada...")
    else:
        print("🌿 NUEVA CONSULTA INICIADA")
        print_terminal_separator()
        print("=== FASES 1-5: ANÁLISIS Y RECOMENDACIONES ===")
        print(f"📋 Session ID: {session_id}")
        print("🔄 Iniciando evaluación dual RNA + RAG...")

def print_precision_analysis(response: Dict[str, Any]):
    """Imprime análisis detallado de precisión en la terminal"""
    print_terminal_separator()
    print("🧠 ANÁLISIS DE PRECISIÓN DEL SISTEMA")
    print_terminal_separator()
    
    # Información básica
    print(f"📊 Session ID: {response.get('session_id', 'N/A')}")
    print(f"🎯 Sistema Elegido: {response.get('selected_system', 'N/A')}")
    print(f"💡 Razón de Selección: {response.get('selection_reason', 'N/A')}")
    print()
    
    # Precisiones
    rna_precision = response.get('rna_precision', 0)
    rag_precision = response.get('rag_precision', 0)
    
    print("📈 PRECISIÓN DE SISTEMAS:")
    print(f"   🤖 RNA (Red Neuronal): {rna_precision:.4f} ({rna_precision*100:.2f}%)")
    print(f"   📚 RAG (Retrieval-Aug): {rag_precision:.4f} ({rag_precision*100:.2f}%)")
    print(f"   📊 Diferencia: {abs(rna_precision - rag_precision):.4f}")
    
    # Determinar ganador
    if rna_precision > rag_precision:
        winner = "RNA"
        margin = rna_precision - rag_precision
    elif rag_precision > rna_precision:
        winner = "RAG"
        margin = rag_precision - rna_precision
    else:
        winner = "EMPATE"
        margin = 0
    
    print(f"   🏆 Ganador: {winner}" + (f" (margen: {margin:.4f})" if margin > 0 else ""))
    print()
    
    # Recomendaciones RNA
    rna_recs = response.get('rna_recommendations', [])
    if rna_recs:
        print("🤖 RECOMENDACIONES RNA:")
        for i, plant in enumerate(rna_recs, 1):
            print(f"   {i}. {plant.get('name', 'N/A')} ({plant.get('scientific_name', 'N/A')})")
            print(f"      Confianza: {plant.get('confidence', 0):.3f}")
    
    print()
    
    # Recomendaciones RAG
    rag_recs = response.get('rag_recommendations', '')
    if rag_recs:
        print("📚 RECOMENDACIONES RAG:")
        # Mostrar solo las primeras líneas para no saturar
        rag_lines = rag_recs.split('\n')[:3]
        for line in rag_lines:
            if line.strip():
                print(f"   {line.strip()}")
        if len(rag_lines) > 3:
            print("   ...")
    
    print_terminal_separator()

def print_detailed_preparation_summary(selected_plant: str, response: Dict[str, Any], session_id: str):
    """
    Imprime resumen de la preparación detallada generada
    """
    print_terminal_separator()
    print("💊 PREPARACIÓN DETALLADA COMPLETADA")
    print_terminal_separator()
    print(f"🌱 Planta seleccionada: {selected_plant.title()}")
    print(f"📋 Session ID: {session_id}")
    print(f"📄 Método utilizado: RAG (Preparación detallada)")
    print(f"📝 Longitud de respuesta: {len(response.get('answer', ''))} caracteres")
    print(f"✅ Estado: Preparación generada exitosamente")
    print()
    print("📋 Contenido incluye:")
    print("   • Nombre científico y propiedades")
    print("   • Parte de la planta a utilizar")  
    print("   • Forma de preparación detallada")
    print("   • Dosis y frecuencia recomendada")
    print("   • Duración del tratamiento")
    print("   • Precauciones y efectos secundarios")
    print_terminal_separator()

async def get_user_data_from_db(username: str) -> Optional[Dict[str, Any]]:
    """
    Recupera los datos del usuario desde la base de datos usando el username
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Consulta para obtener datos del usuario
        query = """
        SELECT full_name, email, username, dni, phone_number, age, gender, 
               weight, height, zone, occupation, education_level
        FROM personal_information 
        WHERE username = %s
        """
        
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        
        if result:
            # Mapear resultado a diccionario
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
                'education_level': result[11]
            }
            logger.info(f"📋 Datos del usuario {username} recuperados exitosamente")
            return user_data
        else:
            logger.warning(f"⚠️  Usuario {username} no encontrado en la base de datos")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error consultando datos del usuario {username}: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Agregar endpoint HEAD para la ruta raíz
@app.head("/")
async def head_welcome():
    """
    Endpoint HEAD para verificación de estado
    """
    return {}
            
@app.post("/rag/chat")
async def chat_endpoint(
    consultation: PatientConsultation,
    current_user: str = Depends(get_current_user)
):
    try:
        # Asegurarse de que el user_id en patient_info coincida con el usuario autenticado
        consultation.patient_info['user_id'] = current_user
        # DETECTAR ESTADO DE LA CONSULTA
        consultation_state, state_description = detect_consultation_state(
            consultation.selected_plant, 
            consultation.session_id
        )
        
        # IMPRIMIR ENCABEZADO APROPIADO
        print_consultation_header(
            consultation_state, 
            consultation.session_id, 
            consultation.selected_plant
        )
        
        # LOGGING CONTEXTUAL
        logger.info(f"📥 Session ID: {consultation.session_id}")
        logger.info(f"🔄 Estado: {consultation_state}")
        logger.info(f"👤 User ID: {consultation.patient_info.get('user_id', 'N/A')}")
        logger.info(f"🩺 Síntomas: {consultation.patient_info.get('symptoms', 'N/A')}")
        
        if consultation_state == "PLANT_SELECTION":
            logger.info(f"🌱 Planta seleccionada: {consultation.selected_plant}")
            
            # VALIDAR PLANTA SELECCIONADA
            is_valid, validation_msg = validate_plant_selection(
                consultation.selected_plant, 
                consultation.session_id
            )
            
            if not is_valid:
                logger.error(f"❌ Validación falló: {validation_msg}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Planta inválida: {validation_msg}"
                )
            else:
                logger.info(f"✅ Validación exitosa: {validation_msg}")
        else:
            logger.info("🔍 Iniciando análisis dual RNA + RAG")
        
        # Recuperar información del usuario desde la base de datos
        user_id = consultation.patient_info.get('user_id')
        if user_id:
            user_data = await get_user_data_from_db(user_id)
            if user_data:
                # Actualizar patient_info con datos reales del usuario
                consultation.patient_info.update({
                    'age': user_data.get('age', 30),
                    'gender': user_data.get('gender', 'Not specified'),
                    'zone': user_data.get('zone', 'Lima'),
                    'weight': user_data.get('weight'),
                    'height': user_data.get('height'),
                    'full_name': user_data.get('full_name'),
                    'phone_number': user_data.get('phone_number')
                })
                logger.info(f"✅ Datos del usuario recuperados: Edad: {user_data.get('age')}, Género: {user_data.get('gender')}, Zona: {user_data.get('zone')}")
            else:
                logger.warning(f"⚠️  No se encontraron datos para el usuario: {user_id}")
                # Solo asignar defaults si no se encontró el usuario
                consultation.patient_info.setdefault('age', 30)
                consultation.patient_info.setdefault('gender', 'Not specified')
                consultation.patient_info.setdefault('zone', 'Lima')
        else:
            logger.warning("⚠️  No se proporcionó user_id, usando valores por defecto")
            # Solo asignar defaults si no hay user_id
            consultation.patient_info.setdefault('age', 30)
            consultation.patient_info.setdefault('gender', 'Not specified')
            consultation.patient_info.setdefault('zone', 'Lima')
        
        # Si hay una session_id, asegurarse de que esté incluida en patient_info
        if consultation.session_id:
            consultation.patient_info['session_id'] = consultation.session_id
        
        print("\n🔄 INICIANDO PROCESAMIENTO...")
        
        # Llamar directamente a process_consultation_with_safety con la planta seleccionada
        response = await process_consultation_with_safety(
            patient_info=consultation.patient_info,
            selected_plant=consultation.selected_plant
        )
        
        if "error" in response:
            logger.error(f"❌ Error en process_consultation_with_safety: {response['error']}")
            raise HTTPException(status_code=500, detail=response["error"])
        
        # Asegurarse de que la respuesta contiene todos los campos necesarios
        if "answer" not in response and "rag_answer" in response:
            response["answer"] = response["rag_answer"]
        
        # MOSTRAR ANÁLISIS SEGÚN EL ESTADO
        if consultation_state == "INITIAL_CONSULTATION":
            # Mostrar análisis de precisión para nuevas consultas
            print_precision_analysis(response)
        else:
            # Mostrar resumen de preparación detallada
            print_detailed_preparation_summary(
                consultation.selected_plant, 
                response, 
                consultation.session_id
            )

        # =====================================================================
        # CÓDIGO MEJORADO PARA GUARDAR CONSULTA - VERSIÓN COMPLETA
        # =====================================================================
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Obtener todos los datos necesarios para la consulta
            symptoms = consultation.patient_info.get('symptoms', '')
            duration = consultation.patient_info.get('duration', '')
            allergies = consultation.patient_info.get('allergies', '')
            recommended_plant = consultation.selected_plant or ''
            
            # Preparar recomendaciones según el tipo de consulta
            rna_recommendations = str(response.get('rna_recommendations', [])) if consultation_state == "INITIAL_CONSULTATION" else ''
            rag_recommendations = response.get('rag_recommendations', '')
            selected_system = response.get('selected_system', '')
            answer = response.get('answer', '')
            
            # Consulta SQL completa con todos los campos
            insert_query = """
            INSERT INTO patient_consultations (
                user_id, 
                session_id, 
                symptoms, 
                symptoms_duration, 
                allergies, 
                recommended_plant,
                consultation_date,
                status,
                mac_recommendations,
                rag_recommendations,
                selected_system,
                recon
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (session_id) DO UPDATE SET
                symptoms = EXCLUDED.symptoms,
                symptoms_duration = EXCLUDED.symptoms_duration,
                allergies = EXCLUDED.allergies,
                recommended_plant = EXCLUDED.recommended_plant,
                status = EXCLUDED.status,
                mac_recommendations = EXCLUDED.mac_recommendations,
                rag_recommendations = EXCLUDED.rag_recommendations,
                selected_system = EXCLUDED.selected_system,
                recon = EXCLUDED.recon,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, session_id
            """
            
            # Ejecutar la consulta con todos los parámetros
            cursor.execute(insert_query, (
                current_user,
                consultation.session_id,
                symptoms,
                duration,
                allergies,
                recommended_plant,
                datetime.now(),  # consultation_date
                consultation_state,  # status
                rna_recommendations,  # mac_recommendations
                rag_recommendations,
                selected_system,
                answer  # recon
            ))
            
            # Obtener los datos insertados/actualizados
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                logger.info(f"✅ Consulta guardada correctamente. ID: {result[0]}, Session ID: {result[1]}")
            else:
                logger.warning("⚠️  Consulta guardada pero no se obtuvieron datos de retorno")
            
        except psycopg2.Error as db_error:
            logger.error(f"❌ Error de base de datos al guardar consulta: {db_error}")
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error crítico al guardar la consulta en la base de datos: {db_error}"
            )
        except Exception as e:
            logger.error(f"❌ Error inesperado al guardar consulta: {str(e)}")
            if conn:
                conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al guardar la consulta: {str(e)}"
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        # =====================================================================
        # FIN DEL CÓDIGO MEJORADO
        # =====================================================================
        
        logger.info("✅ CONSULTA PROCESADA Y GUARDADA EXITOSAMENTE")
        return response
        
    except HTTPException as e:
        logger.error(f"❌ HTTPException: {e.detail}")
        print_terminal_separator()
        print(f"❌ ERROR HTTP: {e.detail}")
        print_terminal_separator()
        raise e
    except Exception as e:
        logger.error(f"❌ Error inesperado: {str(e)}")
        print_terminal_separator()
        print(f"❌ ERROR INESPERADO: {str(e)}")
        print_terminal_separator()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback")
async def save_feedback(feedback: FeedbackRequest):
    conn = None
    cursor = None
    try:
        print_terminal_separator()
        print("📝 GUARDANDO FEEDBACK")
        print_terminal_separator()
        
        # Validar que session_id es un UUID válido
        try:
            session_uuid = uuid.UUID(feedback.session_id)
            logger.info(f"📋 Session ID válido: {session_uuid}")
        except ValueError:
            logger.error(f"❌ Session ID inválido: {feedback.session_id}")
            raise HTTPException(
                status_code=400,
                detail="Formato de session_id inválido"
            )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # PRIMERO: Verificar si existe la consulta
        cursor.execute(
            """
            SELECT id, user_id FROM patient_consultations 
            WHERE session_id = %s
            LIMIT 1
            """,
            (str(session_uuid),)
        )
        consultation_data = cursor.fetchone()
        
        if not consultation_data:
            logger.warning(f"⚠️ Session ID no encontrado en patient_consultations: {session_uuid}")
            
            # Crear una entrada mínima en patient_consultaciones usando los campos correctos
            try:
                logger.info("🆕 Creando entrada mínima en patient_consultations")
                cursor.execute(
                    """
                    INSERT INTO patient_consultations 
                        (session_id, consultation_date, status)
                    VALUES 
                        (%s, %s, %s)
                    RETURNING id
                    """,
                    (
                        str(session_uuid),
                        datetime.now(),  # Usamos consultation_date en lugar de created_at
                        'FEEDBACK_ONLY'  # Estado especial para feedback sin consulta completa
                    )
                )
                consultation_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"✅ Entrada mínima creada (ID: {consultation_id}) para feedback")
            except Exception as create_error:
                logger.error(f"❌ Error creando entrada mínima: {str(create_error)}")
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontró la consulta y no se pudo crear una entrada mínima: {feedback.session_id}"
                )
        else:
            consultation_id = consultation_data[0]
            logger.info(f"✅ Consulta encontrada (ID: {consultation_id})")
        
        # [Resto del código para guardar el feedback...]
        # Verificar si ya existe feedback para esta sesión
        cursor.execute(
            """
            SELECT id, created_at FROM treatment_feedback 
            WHERE session_id = %s
            """,
            (str(session_uuid),)
        )
        existing_feedback = cursor.fetchone()
        
        if existing_feedback:
            logger.info(f"🔄 Actualizando feedback existente (ID: {existing_feedback[0]})")
            update_query = """
            UPDATE treatment_feedback 
            SET effectiveness_rating = %s,
                side_effects = %s,
                improvement_time = %s,
                additional_comments = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, session_id, effectiveness_rating
            """
            cursor.execute(update_query, (
                feedback.effectiveness_rating,
                feedback.side_effects,
                feedback.improvement_time,
                feedback.additional_comments,
                existing_feedback[0]
            ))
            
            # Obtener los datos actualizados
            updated_feedback = cursor.fetchone()
        else:
            logger.info("➕ Creando nuevo feedback")
            insert_query = """
            INSERT INTO treatment_feedback 
                (session_id, effectiveness_rating, side_effects, improvement_time, 
                 additional_comments, created_at)
            VALUES 
                (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, session_id, effectiveness_rating
            """
            cursor.execute(insert_query, (
                str(session_uuid),
                feedback.effectiveness_rating,
                feedback.side_effects,
                feedback.improvement_time,
                feedback.additional_comments
            ))
            
            # Obtener los datos recién insertados
            updated_feedback = cursor.fetchone()
        
        conn.commit()
        
        if updated_feedback:
            logger.info(f"✅ Feedback {'actualizado' if existing_feedback else 'creado'} exitosamente (ID: {updated_feedback[0]})")
            
            # Registrar métricas adicionales
            cursor.execute(
                """
                SELECT COUNT(*) FROM treatment_feedback 
                WHERE session_id = %s
                """,
                (str(session_uuid),)
            )
            total_feedbacks = cursor.fetchone()[0]
            logger.info(f"📊 Total feedbacks para esta sesión: {total_feedbacks}")
        
        print_terminal_separator()
        print("✅ FEEDBACK GUARDADO EXITOSAMENTE")
        print(f"📋 Session ID: {session_uuid}")
        if updated_feedback:
            print(f"⭐ Calificación: {updated_feedback[2]}/5")
        print_terminal_separator()
        
        return {
            "status": "success",
            "message": "Feedback guardado correctamente",
            "session_id": str(session_uuid),
            "feedback_id": updated_feedback[0] if updated_feedback else None,
            "action": "updated" if existing_feedback else "created",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException as e:
        logger.error(f"❌ Error HTTP en feedback: {e.detail}")
        print_terminal_separator()
        print(f"❌ ERROR EN FEEDBACK: {e.detail}")
        print_terminal_separator()
        raise e
    except Exception as e:
        logger.error(f"❌ Error guardando feedback: {str(e)}")
        print_terminal_separator()
        print(f"❌ ERROR INESPERADO: {str(e)}")
        print_terminal_separator()
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar el feedback: {str(e)}"
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# FUNCIÓN ADICIONAL: Endpoint para verificar session_id
@app.get("/debug/session/{session_id}")
async def debug_session(session_id: str):
    """
    Endpoint para debugging - verificar si un session_id existe en patient_consultations
    """
    conn = None
    cursor = None
    try:
        # Validar UUID
        session_uuid = uuid.UUID(session_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # CAMBIO: consultations -> patient_consultations
        cursor.execute(
            """
            SELECT session_id, created_at, user_id 
            FROM patient_consultations 
            WHERE session_id = %s
            """,
            (str(session_uuid),)
        )
        consultation = cursor.fetchone()
        
        # Verificar en treatment_feedback
        cursor.execute(
            """
            SELECT id, created_at, effectiveness_rating 
            FROM treatment_feedback 
            WHERE CAST(session_id AS VARCHAR) = %s
            """,
            (str(session_uuid),)
        )
        feedback = cursor.fetchone()
        
        return {
            "session_id": str(session_uuid),
            "exists_in_patient_consultations": consultation is not None,
            "consultation_data": {
                "created_at": consultation[1].isoformat() if consultation else None,
                "user_id": consultation[2] if consultation else None
            } if consultation else None,
            "exists_in_feedback": feedback is not None,
            "feedback_data": {
                "id": feedback[0],
                "created_at": feedback[1].isoformat(),
                "effectiveness_rating": feedback[2]
            } if feedback else None
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# FUNCIÓN ADICIONAL: Limpiar sessions huérfanas (opcional)
@app.post("/debug/cleanup-orphaned-feedback")
async def cleanup_orphaned_feedback():
    """
    Endpoint para limpiar feedback sin sesiones válidas (solo para debugging)
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # CAMBIO: consultations -> patient_consultations
        cursor.execute("""
            SELECT tf.id, tf.session_id 
            FROM treatment_feedback tf
            LEFT JOIN patient_consultations pc ON CAST(tf.session_id AS VARCHAR) = pc.session_id
            WHERE pc.session_id IS NULL
        """)
        orphaned = cursor.fetchall()
        
        if orphaned:
            logger.info(f"🧹 Encontrados {len(orphaned)} feedbacks huérfanos")
            # Opcionalmente, podrías eliminarlos aquí
            # cursor.execute("DELETE FROM treatment_feedback WHERE id IN %s", (tuple(row[0] for row in orphaned),))
            # conn.commit()
        
        return {
            "orphaned_count": len(orphaned),
            "orphaned_sessions": [row[1] for row in orphaned]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
            
@app.post("/api/register")
async def register_user(user: UserRegistration):
    connection = None
    cursor = None
    try:
        print_terminal_separator()
        print("👤 REGISTRO DE NUEVO USUARIO")
        print_terminal_separator()
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        logger.info(f"📝 Registrando usuario: {user.username} ({user.email})")
        
        # Verificaciones de usuario existente
        cursor.execute("SELECT username FROM personal_information WHERE username = %s", (user.username,))
        if cursor.fetchone():
            logger.warning(f"⚠️  Username ya existe: {user.username}")
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
            
        cursor.execute("SELECT email FROM personal_information WHERE email = %s", (user.email,))
        if cursor.fetchone():
            logger.warning(f"⚠️  Email ya existe: {user.email}")
            raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
            
        cursor.execute("SELECT dni FROM personal_information WHERE dni = %s", (user.dni,))
        if cursor.fetchone():
            logger.warning(f"⚠️  DNI ya existe: {user.dni}")
            raise HTTPException(status_code=400, detail="El DNI ya está registrado")
            
        cursor.execute("SELECT phone_number FROM personal_information WHERE phone_number = %s", (user.phoneNumber,))
        if cursor.fetchone():
            logger.warning(f"⚠️  Teléfono ya existe: {user.phoneNumber}")
            raise HTTPException(status_code=400, detail="El número de teléfono ya está registrado")

        # Hash de la contraseña
        password_bytes = user.password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        INSERT_USER = """
        INSERT INTO personal_information (
            full_name, email, username, password_hash, dni, phone_number,
            age, gender, weight, height, zone, education_level,
            occupation, created_at, last_login
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        cursor.execute(INSERT_USER, (
            user.fullName,
            user.email,
            user.username,
            hashed_password,
            user.dni,
            user.phoneNumber,
            user.age,
            user.gender,
            user.weight,
            user.height,
            user.zone,
            user.occupation or 'No especificada',
            'No especificada',
            datetime.now(),
            None
        ))

        connection.commit()
        logger.info(f"✅ Usuario registrado exitosamente: {user.username}")
        
        print_terminal_separator()
        print(f"✅ USUARIO REGISTRADO: {user.username}")
        print_terminal_separator()
        
        return {"message": "Usuario registrado exitosamente"}

    except HTTPException as e:
        logger.error(f"❌ Error en registro: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"❌ Error registrando usuario: {str(e)}")
        print(f"❌ Error registering user: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al registrar usuario: {str(e)}")
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

@app.post("/api/login")
async def login(credentials: LoginCredentials):
    connection = None
    cursor = None
    try:
        print_terminal_separator()
        print("🔐 INTENTO DE LOGIN")
        print_terminal_separator()
        
        connection = get_db_connection()
        cursor = connection.cursor()

        logger.info(f"👤 Intento de login para: {credentials.identifier}")

        cursor.execute(
            "SELECT username, password_hash FROM personal_information WHERE username = %s",
            (credentials.identifier,)
        )
        user = cursor.fetchone()

        if not user:
            logger.warning(f"⚠️  Usuario no encontrado: {credentials.identifier}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos"
            )

        username, stored_hash = user

        # Check if password matches using bcrypt
        password_bytes = credentials.password.encode('utf-8')
        stored_hash_bytes = stored_hash.encode('utf-8')
        
        # Check if password matches
        if not bcrypt.checkpw(password_bytes, stored_hash_bytes):
            logger.warning(f"⚠️  Contraseña incorrecta para: {credentials.identifier}")
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

        logger.info(f"✅ Login exitoso para: {username}")
        
        print_terminal_separator()
        print(f"✅ LOGIN EXITOSO: {username}")
        print_terminal_separator()

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": username
        }

    except HTTPException as e:
        logger.error(f"❌ Error en login: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"❌ Error inesperado en login: {str(e)}")
        print(f"❌ Error in login: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el servidor: {str(e)}"
        )
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

# Agregar este endpoint para verificar el estado del servidor
@app.get("/health")
async def health_check():
    """
    Endpoint para verificar el estado del servidor y la base de datos
    """
    try:
        # Probar conexión a la base de datos
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return {
                "status": "healthy",
                "database": "connected",
                "message": "Server and database are running correctly"
            }
        except Exception as db_error:
            logger.error(f"Database connection error: {db_error}")
            return {
                "status": "healthy",
                "database": "disconnected",
                "message": "Server is running but database connection failed",
                "error": str(db_error)
            }, 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503
    finally:
        if connection:
            connection.close()

def get_db_connection():
    """Conexión robusta que intenta DATABASE_URL primero, luego variables individuales"""
    try:
        # 1️⃣ PRIMERA OPCIÓN: Intenta con DATABASE_URL (Render/Producción)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            logger.info(f"🔗 Intentando conectar con DATABASE_URL")
            
            # Corrección para Render (cambia postgres:// a postgresql://)
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            # Usar la URL completa directamente con psycopg2
            conn = psycopg2.connect(database_url)
            logger.info("✅ Conexión exitosa via DATABASE_URL")
            return conn

        # 2️⃣ SEGUNDA OPCIÓN: Fallback a variables individuales (Desarrollo local)
        logger.info("🔗 DATABASE_URL no encontrada, usando variables individuales")
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )

    except Exception as e:
        logger.error(f"❌ Error de conexión: {str(e)}")
        raise RuntimeError(f"No se pudo conectar a PostgreSQL: {str(e)}")
        
# Endpoint para verificar variables de entorno (útil para debugging)
@app.get("/debug/env")
async def debug_env():
    """
    Endpoint para verificar las variables de entorno (solo para debugging)
    """
    return {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PORT": os.getenv("DB_PORT"),
        "NODE_ENV": os.getenv("NODE_ENV"),
        "PORT": os.getenv("PORT"),
        "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL")),
        # No mostrar valores sensibles como passwords
    }

@app.get("/", response_class=HTMLResponse)
async def welcome_page():
    """
    Página de bienvenida HTML para el servidor
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PlantMedicator API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c5530; text-align: center; }
            .status { background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin: 20px 0; }
            .endpoint { background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .tech { display: inline-block; background: #e9ecef; padding: 5px 10px; margin: 5px; border-radius: 15px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 PlantMedicator API</h1>
            <div class="status">
                ✅ Servidor en línea y funcionando correctamente
            </div>
            
            <h2>📋 Endpoints Disponibles</h2>
            <div class="endpoint">
                <strong>GET /health</strong> - Estado del servidor y base de datos
            </div>
            <div class="endpoint">
                <strong>POST /rag/chat</strong> - Consultas médicas con IA
            </div>
            <div class="endpoint">
                <strong>POST /feedback</strong> - Envío de feedback de tratamientos
            </div>
            <div class="endpoint">
                <strong>POST /api/register</strong> - Registro de nuevos usuarios
            </div>
            <div class="endpoint">
                <strong>POST /api/login</strong> - Autenticación de usuarios
            </div>
            <div class="endpoint">
                <strong>GET /docs</strong> - Documentación automática de la API
            </div>
            
            <h2>🔧 Tecnologías</h2>
            <div>
                <span class="tech">FastAPI</span>
                <span class="tech">PostgreSQL</span>
                <span class="tech">Neural Networks</span>
                <span class="tech">RAG System</span>
                <span class="tech">JWT Auth</span>
            </div>
            
            <h2>📚 Documentación</h2>
            <p>Visita <a href="/docs">/docs</a> para ver la documentación interactiva de la API.</p>
            
            <p style="text-align: center; margin-top: 30px; color: #666;">
                Sistema de recomendación de plantas medicinales con IA híbrida
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

def run():
    import uvicorn
    print_terminal_separator()
    print("🚀 INICIANDO SERVIDOR PlantMedicator")
    print("🌿 Sistema de Recomendación de Plantas Medicinales")
    print("📊 Con análisis dual RNA + RAG")
    print_terminal_separator()

    # Para Render: usar puerto dinámico
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    run()
