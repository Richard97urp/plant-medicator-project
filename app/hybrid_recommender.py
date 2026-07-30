"""
hybrid_recommender.py - VERSIÓN CORREGIDA
✅ Maneja estructura directa desde RAG (sin doble parseo)
✅ Compatible con ambos formatos (estructura o texto)
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import logging
import re
from app.ml.recommender_model import RecommenderModel
import asyncio
import os
import json 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentHybridRecommender:
    """
    🧠 Sistema Híbrido CORREGIDO - Sin doble parseo
    
    FLUJO CORRECTO:
    1. RNA predice plantas (fuente primaria)
    2. RAG predice plantas (fuente primaria) ✅ Estructura directa
    3. Validador de seguridad verifica contraindicaciones
    4. Fusión inteligente entre RNA y RAG
    """
    
    def __init__(self, db_config: Dict[str, Any]):
        logger.info("🧠 Inicializando Hybrid Recommender SIN DOBLE PARSEO")
        
        # Instanciar RNA
        self.rna_model = RecommenderModel(db_config)
        
        # Entrenar RNA
        try:
            logger.info("Entrenando RNA...")
            history, evaluation = self.rna_model.train(epochs=50, batch_size=32)
            if evaluation:
                logger.info(f"RNA entrenada. Loss: {evaluation[0]:.4f}, Accuracy: {evaluation[1]:.4f}")
        except Exception as e:
            logger.warning(f"No se pudo entrenar RNA: {e}")
        
        # Base de conocimiento para seguridad
        self._init_safety_knowledge_base()
        
        # Inicializar RAG
        self.rag_module = None
        self.RAG_AVAILABLE = False
        self._init_rag_module()
    
    def _init_safety_knowledge_base(self):
        """Base de conocimiento solo para validación de seguridad"""
        self.safety_constraints = {
            'manzanilla': {
                'age_range': (0, 100),
                'contraindications': ['embarazo avanzado', 'alergia a asteráceas']
            },
            'menta': {
                'age_range': (3, 100),
                'contraindications': ['reflujo gastroesofágico', 'niños menores 3 años']
            },
            'hierba luisa': {
                'age_range': (2, 100),
                'contraindications': ['embarazo', 'lactancia']
            },
            'eucalipto': {
                'age_range': (2, 100),
                'contraindications': ['epilepsia', 'hipertensión severa']
            },
            'muña': {
                'age_range': (2, 100),
                'contraindications': ['embarazo']
            },
            'uña de gato': {
                'age_range': (12, 100),
                'contraindications': ['embarazo', 'trasplantados', 'autoinmunes', 'niños']
            },
            'salvia': {
                'age_range': (12, 100),
                'contraindications': ['embarazo', 'lactancia', 'epilepsia']
            }
        }
    
    def _init_rag_module(self):
        """Inicializa módulo RAG"""
        try:
            from app import rag_chain
            
            if hasattr(rag_chain, 'optimized_rag') and hasattr(rag_chain.optimized_rag, 'is_available'):
                self.rag_module = rag_chain
                self.rag_instance = rag_chain.optimized_rag
                self.RAG_AVAILABLE = rag_chain.optimized_rag.is_available
                logger.info(f"✅ RAG disponible: {self.RAG_AVAILABLE}")
            else:
                logger.warning("⚠️ RAG no disponible")
                self.RAG_AVAILABLE = False
        except Exception as e:
            logger.error(f"❌ Error inicializando RAG: {e}")
            self.RAG_AVAILABLE = False
    
    async def _normalize_patient_info(self, patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza información del paciente — usa LLM para duración e intensidad"""
        normalized = patient_info.copy()
        
        normalized['age'] = int(patient_info.get('age', 30))
        normalized['weight'] = float(patient_info.get('weight', 70.0))
        normalized['gender'] = str(patient_info.get('gender', 'Not specified'))
        normalized['zone'] = str(patient_info.get('zone', 'Lima'))
        normalized['symptoms'] = str(patient_info.get('symptoms', ''))
        
        # Causas
        normalized['causa_ambiental'] = str(patient_info.get('causa_ambiental', ''))
        normalized['causa_emocional'] = str(patient_info.get('causa_emocional', ''))
        normalized['causa_dietetica'] = str(patient_info.get('causa_dietetica', ''))
        
        # 🔥 LLM normaliza duración e intensidad semánticamente
        llm_norms = await self._normalize_with_llm(patient_info)
        normalized['duration_ordinal'] = llm_norms.get('duration_ordinal', 2)
        normalized['intensidad_sintomas'] = llm_norms.get('intensity_ordinal', 2)
        
        logger.info(f"📋 Paciente normalizado:")
        logger.info(f"   - Edad: {normalized['age']} años")
        logger.info(f"   - Síntomas: {normalized['symptoms']}")
        logger.info(f"   - Intensidad: {normalized['intensidad_sintomas']}")
        logger.info(f"   - Duración ordinal: {normalized['duration_ordinal']}")
        
        return normalized
    
    def _convert_duration_to_ordinal(self, duration_str: str) -> int:
        """Convierte duración a ordinal (0-6)"""
        if not duration_str:
            return 2
        
        duration_lower = duration_str.lower()
        
        if 'hora' in duration_lower:
            return 0
        if '1 día' in duration_lower or '2 días' in duration_lower or '3 días' in duration_lower:
            return 1
        if any(d in duration_lower for d in ['4', '5', '6', '7']) and 'día' in duration_lower:
            return 2
        if '1 semana' in duration_lower:
            return 2
        if '2 semanas' in duration_lower:
            return 3
        if '1 mes' in duration_lower:
            return 4
        if '2 meses' in duration_lower or '3 meses' in duration_lower:
            return 5
        if 'año' in duration_lower:
            return 6
        
        return 2
    
    def _convert_intensity_to_ordinal(self, intensity_str: str) -> int:
        """Convierte intensidad a ordinal (0-3)"""
        if not intensity_str:
            return 2
        
        intensity_lower = intensity_str.lower()
        
        if 'leve' in intensity_lower:
            return 1
        elif 'severo' in intensity_lower or 'fuerte' in intensity_lower:
            return 3
        else:
            return 2
    
    async def get_hybrid_recommendations_async(self, patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        🧠 MÉTODO PRINCIPAL CORREGIDO - Sin doble parseo
        """
        symptoms = patient_info.get('symptoms', '')
        logger.info(f"🧠 Generando recomendaciones para: {symptoms}")
        logger.info(f"📋 patient_info recibido completo: {json.dumps(patient_info, ensure_ascii=False, default=str)}")
        logger.info(f"🤖 RNA entrenada: {self.rna_model.model_trained}")
        logger.info(f"📚 RAG disponible: {self.RAG_AVAILABLE}")
        
        # Normalizar información
        normalized_info = await self._normalize_patient_info(patient_info)
        
        # 🤖 PASO 1: RNA (FUENTE PRIMARIA)
        rna_recommendations = []
        rna_precision = 0.0
        
        if self.rna_model.model_trained:
            rna_tuples = self._get_rna_predictions(normalized_info)
            rna_recommendations = self._convert_tuples_to_dicts(rna_tuples)
            rna_precision = self._calculate_rna_precision(rna_tuples)
            logger.info(f"   🤖 RNA: {len(rna_recommendations)} plantas, precisión={rna_precision:.3f}")
        else:
            logger.warning("⚠️ RNA no entrenada, solo usará RAG")
        
        # 📚 PASO 2: RAG (FUENTE PRIMARIA) - 🔥 SIN DOBLE PARSEO
        rag_recommendations = []
        rag_precision = 0.0
        
        if self.RAG_AVAILABLE and self.rag_module:
            try:
                logger.info("🔍 Llamando a evaluate_rag_system()...")
                
                # 🔥 CORRECCIÓN: evaluate_rag_system ahora retorna estructura directamente
                rag_result, rag_precision = await self.rag_module.evaluate_rag_system(normalized_info)
                
                logger.info(f"📦 RAG devolvió: {type(rag_result)}")
                logger.info(f"📊 RAG precision: {rag_precision}")
                
                # 🔥 MANEJAR ESTRUCTURA DIRECTA (sin parseo)
                if isinstance(rag_result, list):
                    # ✅ Ya es una lista de diccionarios - NO PARSEAR
                    rag_recommendations = rag_result
                    logger.info(f"✅ RAG devolvió estructura directa: {len(rag_recommendations)} plantas")
                    
                    # Log de las plantas recibidas
                    for rec in rag_recommendations:
                        logger.info(f"   ✓ {rec['name']}: conf={rec['confidence']:.2f}")
                    
                elif isinstance(rag_result, str):
                    # ⚠️ Caso legacy - Si por alguna razón aún viene texto
                    logger.warning("⚠️ RAG devolvió texto (caso legacy), parseando...")
                    rag_recommendations = self._parse_rag_text_if_needed(rag_result)
                else:
                    logger.warning(f"⚠️ RAG devolvió tipo inesperado: {type(rag_result)}")
                
                logger.info(f"   📚 RAG: {len(rag_recommendations)} plantas, precisión={rag_precision:.3f}")
                
            except Exception as e:
                logger.error(f"❌ Error en RAG: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("⚠️ RAG no disponible, solo usará RNA")
        
        # 🛡️ PASO 3: VALIDACIÓN DE SEGURIDAD
        safe_rna = self._filter_unsafe_plants(rna_recommendations, normalized_info)
        safe_rag = self._filter_unsafe_plants(rag_recommendations, normalized_info)
        
        logger.info(f"   🛡️ Filtrado de seguridad:")
        logger.info(f"      RNA: {len(rna_recommendations)} → {len(safe_rna)}")
        logger.info(f"      RAG: {len(rag_recommendations)} → {len(safe_rag)}")
        
        # 🎯 PASO 4: FUSIÓN INTELIGENTE
        final_recommendations = self._fuse_rna_rag(safe_rna, safe_rag, rna_precision, rag_precision)
        
        # Calcular precisión global
        if rna_precision > 0 and rag_precision > 0:
            global_precision = (rna_precision * 0.6 + rag_precision * 0.4)
        elif rna_precision > 0:
            global_precision = rna_precision
        elif rag_precision > 0:
            global_precision = rag_precision
        else:
            global_precision = 0.5
        
        selected_system = self._determine_system(rna_precision, rag_precision)
        
        logger.info(f"✅ Sistema seleccionado: {selected_system}")
        logger.info(f"   Plantas finales: {[p['name'] for p in final_recommendations[:3]]}")
        
        answer = await self._format_response_with_llm(
            final_recommendations[:3],
            patient_info,
            selected_system,
            global_precision
        )
        return {
            "session_id": patient_info.get('session_id', ''),
            "selected_system": selected_system,
            "selection_reason": f"Fusión RNA-RAG (precisión: {global_precision:.3f})",
            "rna_precision": round(rna_precision, 4),
            "rag_precision": round(rag_precision, 4),
            "intelligent_precision": round(global_precision, 4),
            "final_recommendations": final_recommendations[:3],
            "patient_symptoms": symptoms,
            "rag_available": self.RAG_AVAILABLE,
            "answer": answer
        }
    
    def _parse_rag_text_if_needed(self, rag_text: str) -> List[Dict[str, Any]]:
        """
        🔥 PARSER DE EMERGENCIA - Solo para caso legacy
        Busca patrón: "PLANTA_1: Nombre (Científico) | Confianza: 0.42 | Razón"
        """
        if not rag_text or len(rag_text) < 10:
            logger.warning("⚠️ Texto RAG vacío")
            return []
        
        logger.info(f"🔍 Parseando texto RAG (primeros 200 chars): {rag_text[:200]}")
        
        recommendations = []
        
        # Patrón correcto para el formato actual
        pattern = r'PLANTA_(\d+):\s+([^(]+)\s*\(([^)]+)\)\s*\|\s*Confianza:\s*([\d.]+)\s*\|\s*(.+?)(?=PLANTA_|\Z)'
        
        matches = re.finditer(pattern, rag_text, re.DOTALL)
        
        for match in matches:
            rank = int(match.group(1))
            name = match.group(2).strip()
            scientific = match.group(3).strip()
            confidence = float(match.group(4))
            reason = match.group(5).strip()
            
            recommendations.append({
                'name': name,
                'scientific_name': scientific,
                'confidence': confidence,
                'rank': rank,
                'reason': reason,
                'source': 'RAG',
                'properties': []
            })
        
        logger.info(f"✅ Parser legacy: {len(recommendations)} plantas encontradas")
        return recommendations
    
    def _filter_unsafe_plants(
        self, 
        recommendations: List[Dict], 
        patient_info: Dict[str, Any]
    ) -> List[Dict]:
        """Filtro de seguridad"""
        if not recommendations:
            return []
        
        safe_plants = []
        age = patient_info.get('age', 30)
        allergies = patient_info.get('allergies', '').lower()
        
        for plant in recommendations:
            plant_name = plant['name'].lower()
            
            if plant_name not in self.safety_constraints:
                safe_plants.append(plant)
                continue
            
            safety_info = self.safety_constraints[plant_name]
            
            # Verificar edad
            age_min, age_max = safety_info['age_range']
            if not (age_min <= age <= age_max):
                logger.warning(f"   ⚠️ {plant_name}: edad {age} fuera de rango")
                continue
            
            # Verificar contraindicaciones
            has_contraindication = False
            for contraindication in safety_info['contraindications']:
                if contraindication in allergies:
                    logger.warning(f"   ⚠️ {plant_name}: contraindicación {contraindication}")
                    has_contraindication = True
                    break
            
            if not has_contraindication:
                safe_plants.append(plant)
        
        return safe_plants
    
    def _fuse_rna_rag(
        self,
        rna: List[Dict],
        rag: List[Dict],
        rna_precision: float,
        rag_precision: float
    ) -> List[Dict[str, Any]]:
        """Fusión inteligente RNA + RAG"""
        fusion = {}
        
        # Calcular pesos dinámicos
        total_precision = rna_precision + rag_precision
        if total_precision > 0:
            rna_weight = rna_precision / total_precision
            rag_weight = rag_precision / total_precision
        else:
            rna_weight = 0.5
            rag_weight = 0.5
        
        logger.info(f"🎯 Pesos de fusión: RNA={rna_weight:.2f}, RAG={rag_weight:.2f}")
        
        # Agregar plantas de RNA
        for plant in rna:
            name = plant['name'].lower()
            fusion[name] = {
                **plant,
                'fusion_score': plant['confidence'] * rna_weight,
                'sources': ['RNA']
            }
        
        # Agregar plantas de RAG
        for plant in rag:
            name = plant['name'].lower()
            if name in fusion:
                fusion[name]['fusion_score'] += plant['confidence'] * rag_weight
                fusion[name]['confidence'] = max(fusion[name]['confidence'], plant['confidence'])
                fusion[name]['sources'].append('RAG')
            else:
                fusion[name] = {
                    **plant,
                    'fusion_score': plant['confidence'] * rag_weight,
                    'sources': ['RAG']
                }
        
        # Ordenar por fusion_score
        sorted_fusion = sorted(fusion.values(), key=lambda x: x['fusion_score'], reverse=True)
        
        # Reindexar ranks
        for i, plant in enumerate(sorted_fusion, 1):
            plant['rank'] = i
        
        logger.info(f"🎯 Fusión completada: {len(sorted_fusion)} plantas totales")
        logger.info("🔍 Resultados de fusión:")
        for i, plant in enumerate(sorted_fusion[:5], 1):
            logger.info(f"   {i}. {plant['name']} - Score: {plant['fusion_score']:.3f}")
            logger.info(f"      Sources: {plant.get('sources', [])}")
            logger.info(f"      Conf: {plant.get('confidence', 0):.3f}")
            
        return sorted_fusion
    
    def _determine_system(self, rna_prec: float, rag_prec: float) -> str:
        """Determina qué sistema fue más efectivo"""
        if rna_prec > 0 and rag_prec > 0:
            if rna_prec > rag_prec * 1.2:
                return "RNA_PRIMARY"
            elif rag_prec > rna_prec * 1.2:
                return "RAG_PRIMARY"
            else:
                return "HYBRID_BALANCED"
        elif rna_prec > 0:
            return "RNA_ONLY"
        elif rag_prec > 0:
            return "RAG_ONLY"
        else:
            return "FALLBACK"
    
    async def _format_response_with_llm(
        self,
        recommendations: List[Dict],
        patient_info: Dict[str, Any],
        system: str,
        precision: float
    ) -> str:
        """
        LLM genera la respuesta final personalizada para el paciente.
        Reemplaza _format_user_friendly_response().
        """
        plants_summary = []
        for i, p in enumerate(recommendations[:3], 1):
            plants_summary.append(
                f"{i}. {p['name']} ({p.get('scientific_name','')}) "
                f"- confianza: {p.get('confidence',0):.0%} "
                f"- fuente: {'+'.join(p.get('sources',['N/A']))}"
            )
        
        prompt = f"""Eres Fauno, un asistente empático de plantas medicinales peruanas.

    Paciente con: {patient_info.get('symptoms', 'síntomas digestivos')}
    Duración: {patient_info.get('duration', 'no especificada')}
    Intensidad: {patient_info.get('intensidad_sintomas', 'moderada')}
    Plantas recomendadas por el sistema híbrido RNA+RAG:
    {chr(10).join(plants_summary)}

    Redacta una respuesta cálida y clara para el paciente en español peruano:
    - Presenta las 3 plantas con sus nombres
    - Menciona brevemente por qué cada una ayuda con su síntoma específico
    - Indica que puede elegir una escribiendo 1, 2 o 3
    - Máximo 120 palabras
    - Sin markdown ni bullets, solo texto natural

    Responde SOLO el mensaje para el paciente:"""

        try:
            response = await self._call_groq_async(prompt, temperature=0.7)
            if response:
                logger.info("✅ Respuesta final generada por LLM")
                return response.strip()
        except Exception as e:
            logger.error(f"❌ Error generando respuesta final: {e}")
        
        # Fallback al template hardcoded
        return self._format_user_friendly_response(system, recommendations, precision)
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _convert_tuples_to_dicts(self, tuples_list: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
        """Convierte tuplas a diccionarios"""
        result = []
        for i, (plant_name, confidence) in enumerate(tuples_list, 1):
            result.append({
                'name': plant_name.title(),
                'scientific_name': self._get_scientific_name_from_db(plant_name),
                'confidence': float(confidence),
                'rank': i,
                'properties': [],
                'source': 'RNA'
            })
        return result
    
    def _get_scientific_name_from_db(self, common_name: str) -> str:
        """Obtiene nombre científico"""
        scientific_names = {
            'manzanilla': 'Matricaria chamomilla',
            'menta': 'Mentha piperita',
            'hierba luisa': 'Aloysia citrodora',
            'eucalipto': 'Eucalyptus globulus',
            'muña': 'Minthostachys mollis',
            'uña de gato': 'Uncaria tomentosa',
            'salvia': 'Salvia officinalis',
            'matico': 'Buddleja globosa',
            'boldo': 'Peumus boldus',
            'jengibre': 'Zingiber officinale',
            'sauco': 'Sambucus nigra',
            'llantén': 'Plantago major',
            'cedrón': 'Aloysia citrodora',
            'hinojo': 'Foeniculum vulgare',
            'anís': 'Pimpinella anisum'
        }
        return scientific_names.get(common_name.lower(), 'N/A')
    
    def _get_rna_predictions(self, patient_info: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Obtiene predicciones RNA"""
        try:
            predictions = self.rna_model.predict(patient_info)
            if predictions and 'top_3_plants' in predictions:
                return [(plant, float(prob)) for plant, prob in predictions['top_3_plants']]
            return []
        except Exception as e:
            logger.error(f"Error RNA: {e}")
            return []
    
    def _calculate_rna_precision(self, rna_result):
        """Calcula precisión RNA"""
        if not rna_result:
            return 0.0
        if isinstance(rna_result, list) and len(rna_result) > 0:
            if isinstance(rna_result[0], tuple):
                return float(rna_result[0][1])
        return 0.0
    
    # ========== MÉTODOS DE COMPATIBILIDAD ==========
    
    def get_hybrid_recommendations(self, patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """Método síncrono"""
        try:
            return asyncio.run(self.get_hybrid_recommendations_async(patient_info))
        except Exception as e:
            logger.error(f"Error: {e}")
            return {"error": str(e)}
    
    def recommend(self, symptoms: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """Método simple"""
        patient_info = {"symptoms": symptoms}
        result = self.get_hybrid_recommendations(patient_info)
        return result.get('final_recommendations', [])[:top_n]
    
    async def _normalize_with_llm(self, patient_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        USA EL LLM para normalizar campos clínicos ambiguos.
        Reemplaza _convert_duration_to_ordinal y _convert_intensity_to_ordinal.
        """
        prompt = f"""Eres un asistente clínico. Normaliza estos datos del paciente a valores numéricos.

    Datos del paciente:
    - Duración: "{patient_info.get('duration', '')}"
    - Intensidad: "{patient_info.get('intensidad_sintomas', patient_info.get('intensity', ''))}"
    - Síntomas: "{patient_info.get('symptoms', '')}"

    Reglas:
    - duration_ordinal: 0=horas, 1=1-3 días, 2=4-7 días, 3=2 semanas, 4=1 mes, 5=2-3 meses, 6=más de 6 meses. Infiere desde el texto.
    - intensity_ordinal: 1=leve, 2=moderado, 3=severo. Infiere desde el contexto (ej: "bastante fuerte"=3, "un poco"=1).

    Responde SOLO JSON válido:
    {{"duration_ordinal": 2, "intensity_ordinal": 2, "normalization_notes": "brevísima explicación"}}"""

        try:
            # Necesitamos versión sync aquí — usar asyncio si es posible
            import asyncio
            result = self.rna_model  # placeholder — ver nota abajo
            
            response = await self._call_groq_async(prompt)
            if response:
                clean = response.strip().replace("```json","").replace("```","").strip()
                data = json.loads(clean)
                logger.info(f"✅ LLM normalizó: duration={data['duration_ordinal']}, intensity={data['intensity_ordinal']}")
                return data
        except Exception as e:
            logger.error(f"❌ Error normalizando con LLM: {e}")
        
        # Fallback a los métodos hardcoded si LLM falla
        return {
            "duration_ordinal": self._convert_duration_to_ordinal(patient_info.get('duration', '')),
            "intensity_ordinal": self._convert_intensity_to_ordinal(patient_info.get('intensidad_sintomas', ''))
        }

    async def _call_groq_async(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """Cliente Groq para el recommender"""
        try:
            from groq import Groq
            import os
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Groq error en recommender: {e}")
            return None
    
# ========== ALIAS ==========
HybridRecommender = IntelligentHybridRecommender