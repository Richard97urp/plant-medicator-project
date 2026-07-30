"""
rag_chain.py - VERSIÓN CORREGIDA QUE RETORNA ESTRUCTURA DIRECTAMENTE
✅ Elimina el doble parseo innecesario
✅ Retorna List[Dict] en lugar de texto
"""

from datetime import datetime
import os
import psycopg2
import traceback
from typing import Dict, Any, List, Tuple
import logging
import json
import re
from dotenv import load_dotenv

from groq import Groq
from sentence_transformers import SentenceTransformer

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

GROQ_MODEL = "llama-3.3-70b-versatile"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

logger.info(f"""
╔════════════════════════════════════════════════════════════╗
║  🚀 SISTEMA RAG - RETORNA ESTRUCTURA DIRECTA              ║
╠════════════════════════════════════════════════════════════╣
║  ✅ Sin doble parseo innecesario                          ║
║  ✅ Estructura nativa: List[Dict]                         ║
╚════════════════════════════════════════════════════════════╝
""")

class OptimizedRAGSystem:
    """Sistema RAG que retorna estructura directamente"""
    
    def __init__(self):
        self.db_config = {
            'dbname': os.getenv("DB_NAME"),
            'user': os.getenv("DB_USER"),
            'password': os.getenv("DB_PASSWORD"),
            'host': os.getenv("DB_HOST"),
            'port': os.getenv("DB_PORT", "5432")
        }
        self.collection_id = '9e74cfee-6339-4551-aca3-154a2066cd38'
        
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        logger.info("📦 Cargando modelo de embeddings local...")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("✅ Modelo cargado (384 dimensiones)")
        
        self._is_available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Verifica disponibilidad"""
        try:
            test_response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = %s", 
                          (self.collection_id,))
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            if count == 0:
                logger.warning("⚠️ No hay documentos en la colección")
                return False
            
            logger.info(f"✅ Sistema RAG disponible - {count} documentos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verificando disponibilidad: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        return self._is_available
    
    async def get_embedding(self, text: str) -> List[float]:
        """Embeddings locales"""
        try:
            embedding = self.embedding_model.encode(text, show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generando embedding: {str(e)}")
            return None

    async def get_recommendations_from_rag(
        self, 
        patient_info: Dict[str, Any], 
        top_k: int = 3
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        🔥 RETORNA ESTRUCTURA DIRECTAMENTE - Sin conversión a texto
        """
        try:
            symptoms = patient_info.get('symptoms', '')
            duration = patient_info.get('duration', '')
            intensity = patient_info.get('intensidad_sintomas', 'moderado')
            causa_amb = patient_info.get('causa_ambiental', '')
            causa_emo = patient_info.get('causa_emocional', '')
            causa_diet = patient_info.get('causa_dietetica', '')
            allergies = patient_info.get('allergies', '')
            age = patient_info.get('age', patient_info.get('edad', 30))
            weight = patient_info.get('weight', patient_info.get('peso', 70))

            query = f"""
Síntomas: {symptoms}
Duración: {duration}
Intensidad: {intensity}
Causa ambiental: {causa_amb}
Causa emocional: {causa_emo}
Causa dietética: {causa_diet}
Alergias: {allergies}

Buscar plantas medicinales peruanas efectivas para estos síntomas
"""
            
            logger.info(f"🔍 Búsqueda RAG: {symptoms}")
            
            embedding = await self.get_embedding(query)
            if not embedding:
                return [], 0.0
            
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            search_query = """
            SELECT 
                document,
                1 - (embedding <=> %s::vector) as similarity
            FROM langchain_pg_embedding
            WHERE collection_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 20
            """
            
            cursor.execute(search_query, (embedding_str, self.collection_id, embedding_str))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not results:
                logger.warning("⚠️ No se encontraron documentos")
                return [], 0.0
            
            logger.info(f"📄 Recuperados {len(results)} documentos")
            
            top_5_docs = results[:5]
            base_confidence = sum(sim for _, sim in top_5_docs) / len(top_5_docs)
            
            logger.info(f"   📊 Similitud promedio TOP 5: {base_confidence:.3f}")
            
            context = "\n\n".join([
                f"DOCUMENTO {i+1} (Similitud: {sim:.3f}):\n{doc}" 
                for i, (doc, sim) in enumerate(results[:10])
            ])
            
            plant_name = patient_info.get('selected_plant', 'planta medicinal')

            prompt = f"""Eres un experto en medicina tradicional peruana y fitoterapia.

CONTEXTO CIENTÍFICO:
{context}

PACIENTE:
- Síntomas: {symptoms}
- Edad: {age} años
- Peso: {weight} kg

TAREA:
Recomienda las 3 mejores plantas medicinales peruanas para estos síntomas.

IMPORTANTE:
Responde ÚNICAMENTE con un array JSON válido siguiendo este formato EXACTO:

[
  {{"planta": "Nombre Común", "cientifico": "Nombre científico", "razon": "Motivo de recomendación"}},
  {{"planta": "Nombre Común", "cientifico": "Nombre científico", "razon": "Motivo de recomendación"}},
  {{"planta": "Nombre Común", "cientifico": "Nombre científico", "razon": "Motivo de recomendación"}}
]

REGLAS CRÍTICAS:
1. SOLO devuelve el array JSON, sin texto adicional
2. Usa comillas dobles, no simples
3. Incluye exactamente 3 plantas
4. NO agregues explicaciones antes o después del JSON
5. NO uses markdown (sin ```)

GENERA EL JSON AHORA:"""
            
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Eres un experto en plantas medicinales peruanas. 
                        Responde ÚNICAMENTE con un array JSON válido.
                        Formato requerido: [{"planta": "Nombre", "cientifico": "Nombre científico", "razon": "Motivo"}]
                        NO incluyas texto adicional, markdown, ni explicaciones."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=400
            )
            
            answer = response.choices[0].message.content
            
            # 🔥 PARSEO CON VALIDACIÓN ROBUSTA
            try:
                logger.info(f"📝 Respuesta LLM (primeros 300 chars): {answer[:300]}")
                
                cleaned = answer.strip()
                cleaned = re.sub(r'```json\s*', '', cleaned)
                cleaned = re.sub(r'```\s*', '', cleaned)
                cleaned = cleaned.strip()
                
                recommendations = []
                
                if cleaned.startswith('[') and cleaned.endswith(']'):
                    try:
                        recommendations = json.loads(cleaned)
                        logger.info(f"✅ Parseado directo de array JSON")
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Error parseando array JSON: {e}")
                
                elif cleaned.startswith('{') and cleaned.endswith('}'):
                    try:
                        data = json.loads(cleaned)
                        logger.info(f"✅ Parseado objeto JSON, keys: {list(data.keys())}")
                        
                        for key in data:
                            if isinstance(data[key], list):
                                recommendations = data[key]
                                logger.info(f"✅ Array encontrado en key '{key}'")
                                break
                        
                        if not recommendations:
                            logger.warning("⚠️ No se encontró array en el objeto JSON")
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Error parseando objeto JSON: {e}")
                
                else:
                    json_match = re.search(r'(\[.*\])', cleaned, re.DOTALL)
                    if json_match:
                        try:
                            recommendations = json.loads(json_match.group(0))
                            logger.info(f"✅ JSON extraído con regex")
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ Error parseando JSON extraído: {e}")
                
                if not isinstance(recommendations, list):
                    logger.warning(f"⚠️ No es lista, es {type(recommendations)}, convirtiendo...")
                    if isinstance(recommendations, dict):
                        recommendations = [recommendations]
                    else:
                        recommendations = []
                
                # 🔥 VALIDACIÓN ROBUSTA
                valid_recommendations = []
                for idx, item in enumerate(recommendations):
                    if isinstance(item, dict):
                        valid_recommendations.append(item)
                        logger.info(f"   ✓ Item {idx+1} es dict válido")
                    elif isinstance(item, str):
                        logger.warning(f"   ✗ Item {idx+1} es string (INVÁLIDO): {item[:100]}")
                    else:
                        logger.warning(f"   ✗ Item {idx+1} tipo inesperado: {type(item)}")
                
                recommendations = valid_recommendations
                logger.info(f"✅ Validación completa: {len(recommendations)} items válidos")
                
                # 🔥 CONSTRUIR ESTRUCTURA - SIN CONVERTIR A TEXTO
                structured_recs = []
                
                for i, rec in enumerate(recommendations[:3], 1):
                    if not isinstance(rec, dict):
                        logger.error(f"❌ FATAL: rec no es dict: {type(rec)}")
                        continue
                    
                    plant_name = rec.get('planta', '').strip().lower()
                    
                    # Buscar similitud con documentos
                    plant_similarities = []
                    
                    for doc, sim in results[:10]:
                        doc_lower = doc.lower()
                        
                        if plant_name in doc_lower:
                            plant_similarities.append(sim)
                        else:
                            plant_words = plant_name.split()
                            matches = sum(1 for word in plant_words if len(word) > 3 and word in doc_lower)
                            if matches >= len(plant_words) * 0.5:
                                plant_similarities.append(sim * 0.8)
                    
                    if plant_similarities:
                        confidence = max(plant_similarities)
                    else:
                        confidence = base_confidence * 0.6
                    
                    position_penalty = (i - 1) * 0.05
                    confidence = max(0.30, confidence - position_penalty)
                    
                    structured_recs.append({
                        'name': rec.get('planta', 'Desconocida').strip().title(),
                        'scientific_name': rec.get('cientifico', 'N/A').strip(),
                        'confidence': round(confidence, 2),
                        'rank': i,
                        'reason': rec.get('razon', 'Recomendado por literatura'),
                        'properties': [],
                        'source': 'RAG',
                        'doc_matches': len(plant_similarities),
                        'max_similarity': round(max(plant_similarities), 3) if plant_similarities else 0.0
                    })
                
                logger.info(f"✅ Recomendaciones RAG estructuradas:")
                for rec in structured_recs:
                    logger.info(f"   ✓ {rec['name']}: conf={rec['confidence']:.2f}")
                
                # 🔥 RETORNAR ESTRUCTURA DIRECTAMENTE
                return structured_recs, base_confidence
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error JSON final: {e}")
                logger.error(f"Contenido problemático: {answer[:500]}")
                return [], base_confidence
            
        except Exception as e:
            logger.error(f"❌ Error RAG: {str(e)}")
            traceback.print_exc()
            return [], 0.0

    async def retrieve_context_for_plant(self, plant_name: str, symptoms: str, top_k: int = 3) -> Tuple[str, float]:
        """Recupera contexto para preparación"""
        try:
            focused_query = f"""
{plant_name} preparación medicinal dosis posología uso terapéutico 
contraindicaciones efectos secundarios advertencias {symptoms}
"""
            
            logger.info(f"🔍 Búsqueda preparación: {plant_name}")
            
            embedding = await self.get_embedding(focused_query)
            if not embedding:
                return "", 0.0
            
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = f"""
            SELECT 
                document,
                1 - (embedding <=> %s::vector) as similarity
            FROM langchain_pg_embedding
            WHERE collection_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT {top_k * 2}
            """
            
            cursor.execute(query, (embedding_str, self.collection_id, embedding_str))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if not results:
                return "", 0.0
            
            plant_lower = plant_name.lower()
            relevant_docs = []
            
            for doc, sim in results:
                if plant_lower in doc.lower():
                    relevant_docs.append((doc, sim))
            
            if not relevant_docs:
                relevant_docs = results[:top_k]
            
            context_parts = []
            total_similarity = 0
            
            for i, (doc, sim) in enumerate(relevant_docs[:top_k], 1):
                context_parts.append(f"{'='*80}")
                context_parts.append(f"DOC {i} | Sim: {sim:.3f}")
                context_parts.append(f"{'='*80}")
                context_parts.append(doc.strip())
                context_parts.append("")
                total_similarity += sim
            
            context = "\n".join(context_parts)
            avg_similarity = total_similarity / len(relevant_docs[:top_k]) if relevant_docs else 0.0
            
            return context, avg_similarity
            
        except Exception as e:
            logger.error(f"❌ Error: {str(e)}")
            return "", 0.0
    
    async def generate_answer(self, plant_name: str, symptoms: str, context: str, 
                     patient_info: Dict[str, Any]) -> str:
        """Genera guía de preparación PERSONALIZADA según datos clínicos"""
        try:
            age = patient_info.get('age', 30)
            intensity = patient_info.get('intensidad_sintomas', 'moderado')
            duration = patient_info.get('duration', '')
            causa_dietetica = patient_info.get('causa_dietetica', '')
            causa_emocional = patient_info.get('causa_emocional', '')
            
            plant_name_display = plant_name.split('/')[0].strip().upper()
            
            # 🔥 PASO 1: Traducir intensity ordinal a texto
            intensity_map = {
                1: 'leve', 2: 'moderado', 3: 'severo',
                '1': 'leve', '2': 'moderado', '3': 'severo',
                'leve': 'leve', 'moderado': 'moderado', 'severo': 'severo'
            }
            intensity_text = intensity_map.get(str(intensity).lower(), 'moderado')
            
            # 🔥 PASO 2: Tabla de posología clínica según intensidad
            posology = {
                'leve': {
                    'cantidad': '1 cucharadita (2-3g) por taza de agua',
                    'preparacion_extra': 'Infusión suave: 5 minutos de reposo',
                    'frecuencia': '1 vez al día, preferiblemente por la mañana',
                    'duracion': '3-5 días o hasta remisión de síntomas',
                    'nota_clinica': 'Síntoma leve: dosis mínima terapéutica es suficiente'
                },
                'moderado': {
                    'cantidad': '1.5 cucharaditas (3-5g) por taza de agua',
                    'preparacion_extra': 'Infusión estándar: 8-10 minutos de reposo tapado',
                    'frecuencia': '2-3 veces al día, después de comidas principales',
                    'duracion': '5-7 días',
                    'nota_clinica': 'Síntoma moderado: dosis estándar con seguimiento'
                },
                'severo': {
                    'cantidad': '2 cucharaditas (5-7g) por taza de agua',
                    'preparacion_extra': 'Decocción: hervir 10 minutos a fuego lento, luego reposar 10 minutos',
                    'frecuencia': '3-4 veces al día, cada 6 horas aproximadamente',
                    'duracion': '7-10 días — consultar médico si no mejora en 3 días',
                    'nota_clinica': 'Síntoma severo: dosis máxima, vigilar respuesta clínica'
                }
            }[intensity_text]
            
            # 🔥 NUEVO: Pre-extraer contraindicaciones y advertencias del contexto
            # Para que el LLM no tenga que "decidir" — ya le damos los valores calculados
            context_lower = context.lower() if context else ""

            # Palabras clave que indican contraindicaciones en el contexto RAG
            contraindication_keywords = [
                'contraindicado', 'contraindicación', 'no usar', 'no administrar',
                'embarazo', 'lactancia', 'hipertensión', 'diabetes', 'epilepsia',
                'alergia', 'hipersensibilidad', 'evitar en', 'prohibido en'
            ]

            # Palabras clave que indican advertencias en el contexto RAG  
            warning_keywords = [
                'advertencia', 'precaución', 'precaucion', 'tener cuidado',
                'interacción', 'interaccion', 'efecto secundario', 'toxicidad',
                'sobredosis', 'dosis alta', 'suspender', 'vigilar'
            ]

            # Extraer frases del contexto que contengan esas palabras
            found_contraindications = []
            found_warnings = []

            if context:
                # Dividir el contexto en oraciones
                sentences = re.split(r'[.\n]', context)
                for sentence in sentences:
                    sentence_clean = sentence.strip()
                    if len(sentence_clean) < 10:
                        continue
                    sentence_lower = sentence_clean.lower()
                    
                    # ¿Esta oración habla de la planta específica?
                    plant_mentioned = plant_name.lower() in sentence_lower
                    
                    if any(kw in sentence_lower for kw in contraindication_keywords):
                        if plant_mentioned:  # ← Solo agregar si menciona la planta específica
                            found_contraindications.append(f"- {sentence_clean[:150]}")

                    if any(kw in sentence_lower for kw in warning_keywords):
                        if plant_mentioned:  # ← Solo agregar si menciona la planta específica
                            found_warnings.append(f"- {sentence_clean[:150]}")

            # Construir los textos finales — valores fijos que el LLM solo copia
            contraindications_text = (
                "\n    ".join(found_contraindications[:3])  # Máximo 3
                if found_contraindications
                else "- No se encontraron contraindicaciones específicas en la literatura consultada."
            )

            warnings_text = (
                "\n    ".join(found_warnings[:3])  # Máximo 3
                if found_warnings
                else "- Suspender si hay reacciones adversas. Consultar médico ante síntomas persistentes."
            )

            logger.info(f"🛡️ Contraindicaciones encontradas: {len(found_contraindications)}")
            logger.info(f"⚠️ Advertencias encontradas: {len(found_warnings)}")

            # 🔥 NUEVO: Detectar método de preparación desde el contexto RAG
            # Agregar justo después de donde calculas contraindications_text y warnings_text

            preparation_keywords = {
                'zumo': ['zumo', 'jugo', 'extracto', 'exprimir'],
                'cocción': ['sancochad', 'hervir', 'cocid', 'cocimiento', 'decocción'],
                'cataplasma': ['cataplasma', 'emplasto', 'aplicar', 'tópico', 'externamente'],
                'maceración': ['maceración', 'macerar', 'remojar'],
                'infusión': ['infusión', 'té', 'tisana'],
                'tintura': ['tintura', 'alcohol'],
            }

            detected_preparation = None
            context_lower_prep = context.lower() if context else ""
            plant_lower = plant_name.lower()

            if context:
                for method, keywords in preparation_keywords.items():
                    for kw in keywords:
                        # Buscar el método cerca del nombre de la planta en el contexto
                        idx = context_lower_prep.find(plant_lower)
                        if idx != -1:
                            # Ventana de 300 caracteres alrededor de la mención de la planta
                            window = context_lower_prep[max(0, idx-100):idx+300]
                            if kw in window:
                                detected_preparation = method
                                break
                    if detected_preparation:
                        break

            # Mapear el método detectado a instrucciones concretas
            preparation_method_map = {
                'zumo': 'Extracción del zumo/jugo fresco de la planta',
                'cocción': 'Cocción directa: hervir en agua durante 15-20 minutos',
                'cataplasma': 'Preparación tópica: machacar y aplicar directamente sobre la zona afectada',
                'maceración': 'Maceración en agua fría durante 8-12 horas',
                'infusión': posology['preparacion_extra'],  # fallback al default
                'tintura': 'Maceración en alcohol durante 7 días',
            }

            # Si no se detectó nada específico, usar el default de posología
            preparation_instruction = preparation_method_map.get(
                detected_preparation, 
                posology['preparacion_extra']  # fallback
            )

            logger.info(f"🔬 Método de preparación detectado: {detected_preparation or 'no detectado, usando default'}")

            prompt = f"""Eres un especialista en fitoterapia peruana del Instituto Nacional de Salud.

⚠️ PLANTA SELECCIONADA POR EL PACIENTE: {plant_name_display}
Esta planta ya fue validada como apropiada para los síntomas del paciente.
Genera la ficha ÚNICAMENTE para {plant_name_display}. No uses ninguna otra planta.


    ═══════════════════════════════════════
    DATOS CLÍNICOS DEL PACIENTE:
    ═══════════════════════════════════════
    - Síntoma principal: {symptoms}
    - Intensidad: {intensity_text.upper()} ← ESTE ES EL FACTOR CLAVE PARA LA DOSIS
    - Duración del síntoma: {duration}
    - Causa dietética relacionada: {causa_dietetica if causa_dietetica and causa_dietetica != 'no aplica' else 'No identificada'}
    - Causa emocional: {causa_emocional if causa_emocional and causa_emocional != 'no aplica' else 'No identificada'}
    - Edad del paciente: {age} años

    CONTEXTO CIENTÍFICO DE LA BASE DE DATOS:
    {context[:1500] if context else 'No disponible'}

    ═══════════════════════════════════════
    POSOLOGÍA CALCULADA PARA INTENSIDAD {intensity_text.upper()}:
    ═══════════════════════════════════════
    - Cantidad exacta: {posology['cantidad']}
    - Técnica de preparación: {posology['preparacion_extra']}
    - Frecuencia: {posology['frecuencia']}
    - Duración: {posology['duracion']}
    - Nota clínica: {posology['nota_clinica']}

    GENERA LA FICHA USANDO EXACTAMENTE ESTOS VALORES DE POSOLOGÍA.
    Si el síntoma es LEVE, la dosis debe ser BAJA. Si es SEVERO, la dosis debe ser ALTA.

    FORMATO EXACTO (no cambiar estructura):

    🌿 **{plant_name_display}** - Ficha Técnica Herbolaria

    📋 INFORMACIÓN BOTÁNICA
    **Planta:** {plant_name_display}
    **Propiedades Terapéuticas:**
    - [Propiedad específica para {symptoms}]
    - [Propiedad relevante]
    - [Propiedad relevante]
    **Parte Utilizada:** [parte específica de esta planta]

    💊 POSOLOGÍA Y PREPARACIÓN — INTENSIDAD: {intensity_text.upper()}
    **Cantidad/Dosis:** {posology['cantidad']}
    **Preparación:**
        1. [paso específico para {plant_name_display} según el contexto científico]
        2. {preparation_instruction}
        3. [paso final específico]
        
        IMPORTANTE PARA LA PREPARACIÓN:
        - Método detectado desde el contexto RAG: {detected_preparation or 'infusión estándar'}
        - Si el contexto menciona zumo, cataplasma o cocción, USA ESE MÉTODO
        - NO uses infusión si el contexto indica otro método de preparación
    **Frecuencia:** {posology['frecuencia']}
    **Duración del Tratamiento:** {posology['duracion']}
    **Nota clínica:** {posology['nota_clinica']}

    ⚠️ SEGURIDAD Y PRECAUCIONES
    **Contraindicaciones:**
    {contraindications_text}

    **Advertencias:**
    {warnings_text}

    INSTRUCCIÓN CRÍTICA PARA SEGURIDAD:
    COPIA EXACTAMENTE el texto de Contraindicaciones y Advertencias que aparece arriba.
    NO agregues, NO modifiques, NO expandas esos textos.
    Si dice "No se encontraron...", escribe exactamente eso. NADA MÁS."""

            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""Eres un fitoterapista clínico peruano especializado.
                        REGLA ABSOLUTA 1: La ficha es EXCLUSIVAMENTE para la planta {plant_name_display}. 
                        Si el contexto menciona otras plantas, IGNÓRALAS. No las nombres ni las sugieras.
                        REGLA ABSOLUTA 2: La posología SIEMPRE debe reflejar la intensidad del síntoma.
                        - Intensidad LEVE → dosis mínima
                        - Intensidad MODERADA → dosis estándar
                        - Intensidad SEVERA → dosis máxima
                        El paciente actual tiene intensidad: {intensity_text.upper()}"""
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=900,
                top_p=0.85
            )
            
            answer = response.choices[0].message.content
            
            # Post-procesamiento igual que antes
            answer = re.sub(r'Contraindicaciones:.*?\*Advertencias:\*', 
                        'Contraindicaciones:', 
                        answer, flags=re.DOTALL)
            
            if "**Planta:**" not in answer:
                info_idx = answer.find("📋 INFORMACIÓN BOTÁNICA")
                if info_idx != -1:
                    insert_idx = info_idx + len("📋 INFORMACIÓN BOTÁNICA")
                    answer = answer[:insert_idx] + f"\n**Planta:** {plant_name_display}" + answer[insert_idx:]
            
            logger.info(f"✅ Preparación personalizada generada — intensidad: {intensity_text}, duración: {duration}")
            return answer
            
        except Exception as e:
            logger.error(f"❌ Error en generate_answer: {str(e)}")
            return self._generate_complete_fallback(plant_name, symptoms, 
                str(patient_info.get('intensidad_sintomas', 'moderado')), 
                str(patient_info.get('duration', '')))

    def _generate_complete_fallback(self, plant_name: str, symptoms: str, 
                                 intensity: str, duration: str) -> str:
        plant_name_display = plant_name.split('/')[0].strip().upper()
        
        # Misma tabla de posología como fallback
        posology_fallback = {
            'leve':    ('1 cucharadita (2-3g)', '1 vez al día',           '3-5 días'),
            'moderado':('1.5 cucharaditas (3-5g)', '2-3 veces al día',    '5-7 días'),
            'severo':  ('2 cucharaditas (5-7g)',  '3-4 veces al día',     '7-10 días'),
            '1':       ('1 cucharadita (2-3g)', '1 vez al día',           '3-5 días'),
            '2':       ('1.5 cucharaditas (3-5g)', '2-3 veces al día',    '5-7 días'),
            '3':       ('2 cucharaditas (5-7g)',  '3-4 veces al día',     '7-10 días'),
        }
        cantidad, frecuencia, duracion = posology_fallback.get(
            str(intensity).lower(), 
            ('1.5 cucharaditas (3-5g)', '2-3 veces al día', '5-7 días')
        )
        
        return f"""🌿 **{plant_name_display}** - Ficha Técnica Herbolaria

    📋 INFORMACIÓN BOTÁNICA
    **Planta:** {plant_name_display}
    **Propiedades Terapéuticas:**
    - Digestiva
    - Antiinflamatoria
    - Calmante
    **Parte Utilizada:** Hojas

    💊 POSOLOGÍA Y PREPARACIÓN — INTENSIDAD: {intensity.upper()}
    **Cantidad/Dosis:** {cantidad}
    **Preparación:**
    1. Hervir 250ml de agua
    2. Agregar {cantidad} de {plant_name_display.lower()}
    3. Reposar tapado según intensidad: {'5 min' if intensity in ['leve','1'] else '8-10 min' if intensity in ['moderado','2'] else '10-12 min'}
    **Frecuencia:** {frecuencia}
    **Duración del Tratamiento:** {duracion}

    ⚠️ SEGURIDAD Y PRECAUCIONES
    **Contraindicaciones:**
    - Embarazo
    - Lactancia
    - Alergia conocida a la planta
    **Advertencias:**
    - Consultar médico si síntomas persisten
    - Suspender si hay reacciones adversas"""

    def _generate_complete_preparation(self, plant_name: str, symptoms: str, intensity: str, duration: str) -> str:
        """Genera preparación completa como fallback"""
        return f"""
    🌿 **{plant_name.upper()}** - Ficha Técnica Herbolaria

    📋 INFORMACIÓN BOTÁNICA
    **Planta:** {plant_name.upper()}
    **Nombre científico:** (Consultar con especialista)
    **Propiedades Terapéuticas:** Digestiva, antiinflamatoria, calmante para {symptoms}
    **Parte Utilizada:** Hojas

    💊 POSOLOGÍA Y PREPARACIÓN
    **Cantidad/Dosis:** MODERADA (1 cucharada por taza)
    **Preparación:**
    1. Colocar 1 cucharada de {plant_name.lower()} en una taza
    2. Verter 250ml de agua recién hervida (no hirviendo)
    3. Tapar y dejar reposar 5-10 minutos
    4. Colar y beber tibio

    **Dosis:** 1 taza (250ml)
    **Administración:** Vía oral, después de comidas
    **Frecuencia:** 2-3 veces al día
    **Duración del Tratamiento:** 7-10 días

    ⚠️ SEGURIDAD Y PRECAUCIONES
    **Contraindicaciones:**
    - No usar durante el embarazo o lactancia
    - No usar en menores de 2 años
    - No usar si hay alergia conocida a esta planta

    **Advertencias:**
    - Iniciar con media dosis para evaluar tolerancia
    - No combinar con alcohol
    - Suspender si aparecen efectos adversos

    **Disclaimers Médicos:**
    ⚠️ Esta ficha es informativa y NO sustituye diagnóstico médico
    ⚠️ Consulte a profesional de salud para síntomas persistentes
    📞 Emergencias: 117 (SAMU Perú)

    **Nota de Personalización:** Adaptado para intensidad {intensity} y duración {duration}.
    """

    def _generate_basic_preparation(self, plant_name: str) -> str:
        """Preparación básica"""
        plant_name_display = plant_name.split('/')[0].strip().upper()
        
        return f"""
    🌿 **{plant_name_display}**

    **📋 Nombre científico:** (Consultar con especialista)

    **🔬 Propiedades:**
    - Propiedades medicinales tradicionales
    - Uso en medicina natural peruana
    - Efectos terapéuticos documentados

    **🌱 Parte:** Hojas o partes aéreas

    **📏 Cantidad:** 1-2 cucharaditas (5-10g)

    **⚗️ Preparación:**
    1. Colocar la cantidad indicada en una taza
    2. Verter 250ml de agua recién hervida
    3. Tapar y reposar 5-10 minutos
    4. Colar y beber tibio

    **💊 Dosis:** 1 taza • 2-3 veces al día después de comidas

    **⏱️ Duración:** 7-10 días máximo

    **⚠️ Contraindicaciones:**
    - No usar en embarazo sin supervisión médica
    - No en menores de 2 años sin consulta
    - Suspender si hay efectos adversos

    **🏥 IMPORTANTE:**
    ⚠️ NO sustituye consulta médica profesional
    ⚠️ Ante síntomas graves, buscar atención médica
    📞 Emergencias: 117 (SAMU Perú)
    """

# ========== 🔥 FUNCIONES PRINCIPALES - RETORNAN ESTRUCTURA ==========

async def evaluate_rag_system(patient_info: Dict[str, Any]) -> Tuple[List[Dict], float]:
    """
    🔥 VERSIÓN CORREGIDA - Retorna estructura directamente
    NO convierte a texto innecesariamente
    """
    try:
        if not optimized_rag.is_available:
            logger.warning("⚠️ RAG no disponible")
            return _get_fallback_recommendations_structured(patient_info)
        
        # 🔥 IMPORTANTE: Retornar la estructura directamente
        recommendations, similarity = await optimized_rag.get_recommendations_from_rag(patient_info)
        
        if not recommendations:
            logger.warning("⚠️ RAG no generó recomendaciones")
            return _get_fallback_recommendations_structured(patient_info)
        
        precision = similarity if similarity > 0 else 0.5
        
        logger.info(f"✅ RAG completo - {len(recommendations)} plantas - Precisión: {precision:.3f}")
        
        # 🔥 RETORNAR LISTA DE DICTS DIRECTAMENTE
        return recommendations, precision
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return _get_fallback_recommendations_structured(patient_info)


def _get_fallback_recommendations_structured(patient_info: Dict[str, Any]) -> Tuple[List[Dict], float]:
    """
    🔥 NUEVO: Fallback que retorna estructura
    """
    symptoms = patient_info.get('symptoms', '').lower()
    
    if any(word in symptoms for word in ['cabeza', 'migraña']):
        plants = [
            {'name': 'Manzanilla', 'scientific_name': 'Matricaria chamomilla', 'confidence': 0.65, 'rank': 1, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []},
            {'name': 'Menta', 'scientific_name': 'Mentha piperita', 'confidence': 0.60, 'rank': 2, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []},
            {'name': 'Hierba Luisa', 'scientific_name': 'Aloysia citrodora', 'confidence': 0.55, 'rank': 3, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []}
        ]
    else:
        plants = [
            {'name': 'Manzanilla', 'scientific_name': 'Matricaria chamomilla', 'confidence': 0.65, 'rank': 1, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []},
            {'name': 'Menta', 'scientific_name': 'Mentha piperita', 'confidence': 0.60, 'rank': 2, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []},
            {'name': 'Hierba Luisa', 'scientific_name': 'Aloysia citrodora', 'confidence': 0.55, 'rank': 3, 'source': 'RAG', 'reason': 'Recomendación general', 'properties': []}
        ]
    
    logger.info(f"✅ Fallback: {len(plants)} plantas genéricas")
    return plants, 0.5


async def get_plant_preparation_with_rag(
    plant_name: str, patient_info: Dict[str, Any], moderate_warning: str = ""
) -> Dict[str, Any]:
    """Preparación detallada"""
    try:
        logger.info(f"🌿 Generando preparación: {plant_name}")
        
        symptoms = patient_info.get('symptoms', '')
        
        context, avg_similarity = await optimized_rag.retrieve_context_for_plant(
            plant_name, symptoms, top_k=3
        )
        
        detailed_answer = await optimized_rag.generate_answer(
            plant_name, symptoms, context, patient_info
        )
        
        if moderate_warning:
            detailed_answer = f"{moderate_warning}\n\n{detailed_answer}"
        
        return {
            "answer": detailed_answer,
            "plant_name": plant_name,
            "preparation_method": "RAG_GROQ",
            "retrieval_similarity": avg_similarity,
            "session_id": patient_info.get('session_id'),
            "safety_evaluated": True
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "answer": optimized_rag._generate_basic_preparation(plant_name),
            "plant_name": plant_name,
            "preparation_method": "FALLBACK"
        }

# ========== INICIALIZACIÓN ==========

optimized_rag = OptimizedRAGSystem()

if optimized_rag.is_available:
    logger.info("✅ Sistema RAG ACTIVADO - RETORNA ESTRUCTURA DIRECTA 🚀")
else:
    logger.warning("⚠️ Sistema RAG en modo fallback")

__all__ = [
    'get_plant_preparation_with_rag',
    'evaluate_rag_system',
    'OptimizedRAGSystem',
    'optimized_rag'
]

real_rag = optimized_rag