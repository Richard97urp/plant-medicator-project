# rag_load_and_process_OLLAMA_FINAL.py
# VERSIÓN FINAL - DETECTA CORRECTAMENTE EMBEDDINGS DUMMY
import os
import sys
import asyncio
import warnings
from dotenv import load_dotenv
import requests
import psycopg2
import json
from typing import List, Dict
import logging
import re
import time
import random
import unicodedata
import subprocess
from datetime import datetime

# IMPORTACIONES PARA PDFs - SUPRIMIR ADVERTENCIAS
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import pymupdf as fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    print("ADVERTENCIA: PyMuPDF no está instalado. Ejecuta: pip install pymupdf")

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    print("ADVERTENCIA: pypdf no está instalado. Ejecuta: pip install pypdf")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'rag_loader_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class OllamaManager:
    """Clase para manejar Ollama"""
    
    @staticmethod
    def check_if_ollama_is_running():
        """Verifica si Ollama ya está ejecutándose"""
        try:
            import socket
            
            # Verificar si el puerto está en uso
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 11434))
            sock.close()
            
            if result == 0:
                # Puerto en uso, verificar si es Ollama
                try:
                    response = requests.get("http://localhost:11434/api/tags", timeout=2)
                    if response.status_code == 200:
                        logger.info("OK - Ollama ya está ejecutándose en puerto 11434")
                        return True
                except:
                    pass
            return False
        except:
            return False
    
    @staticmethod
    def check_ollama_health():
        """Verifica la salud de Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            if response.status_code == 200:
                logger.info("OK - Ollama responde correctamente")
                return True
            else:
                logger.warning(f"ADVERTENCIA - Ollama responde con código: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.warning("ADVERTENCIA - No se puede conectar a Ollama")
            return False
        except Exception as e:
            logger.warning(f"ADVERTENCIA - Error conectando a Ollama: {e}")
            return False
    
    @staticmethod
    def test_embeddings():
        """Prueba los embeddings con texto pequeño"""
        try:
            test_text = "Prueba de embeddings para Ollama"
            
            model_variants = [
                "gemma:2b",           # <-- PONER ESTE PRIMERO
                "gemma:7b",           # <-- Segundo
                "nomic-embed-text",   # <-- Tercero
                "all-minilm"
            ]
            
            for model in model_variants:
                try:
                    logger.info(f"PROBANDO - Modelo: {model}")
                    
                    response = requests.post(
                        "http://localhost:11434/api/embeddings",
                        json={"model": model, "prompt": test_text},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'embedding' in data and len(data['embedding']) > 0:
                            dims = len(data['embedding'])
                            logger.info(f"OK - Modelo {model} funciona ({dims} dimensiones)")
                            return model, True
                    
                except Exception as e:
                    logger.debug(f"  Modelo {model} falló: {str(e)[:50]}")
                    continue
            
            logger.error("ERROR - Ningún modelo de embeddings funciona")
            return None, False
            
        except Exception as e:
            logger.error(f"ERROR - Error probando embeddings: {e}")
            return None, False

class RobustOllamaEmbeddings:
    """Clase de embeddings con detección correcta de dummy"""
    
    def __init__(self, model_name: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host
        self.embedding_dims = 768
        self.max_retries = 1  # Solo 1 reintento para ir más rápido
        self.retry_delay = 2
        self._is_available = self._verify_connection()
    
    def _verify_connection(self):
        """Verifica la conexión a Ollama"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=10)
            if response.status_code == 200:
                logger.info(f"OK - Ollama disponible en {self.host}")
                
                # Detectar dimensión del modelo
                try:
                    test_response = requests.post(
                        f"{self.host}/api/embeddings",
                        json={"model": self.model_name, "prompt": "test"},
                        timeout=30
                    )
                    
                    if test_response.status_code == 200:
                        data = test_response.json()
                        if 'embedding' in data:
                            self.embedding_dims = len(data['embedding'])
                            logger.info(f"DIMENSION - Modelo usa {self.embedding_dims} dimensiones")
                            return True
                    else:
                        logger.warning(f"ADVERTENCIA - Error probando embeddings: {test_response.status_code}")
                        return False
                        
                except:
                    logger.warning("ADVERTENCIA - No se pudieron detectar dimensiones")
                    return True  # Aún así intentar
            else:
                logger.warning(f"ADVERTENCIA - Ollama responde con código {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error(f"ERROR - No se puede conectar a Ollama en {self.host}")
            return False
        except Exception as e:
            logger.error(f"ERROR - Error verificando conexión: {e}")
            return False
    
    def _optimize_text_for_ollama(self, text: str, max_length: int = 2000) -> str:
        """Optimiza el texto para Ollama"""
        if not text:
            return ""
        
        # 1. Limitar tamaño
        if len(text) > max_length:
            text = text[:max_length]
        
        # 2. Eliminar caracteres problemáticos
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', text)
        
        # 3. Normalizar espacios
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 4. Asegurar que termine con punto
        if text and not text.endswith(('.', '!', '?')):
            text = text + '.'
        
        return text
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings con detección correcta de errores"""
        if not self._is_available:
            logger.warning("ADVERTENCIA - Ollama no disponible, usando embeddings dummy")
            return self._create_dummy_embeddings(len(texts))
        
        embeddings = []
        failed_count = 0
        
        for i, text in enumerate(texts):
            try:
                # Optimizar texto
                optimized_text = self._optimize_text_for_ollama(text)
                
                if not optimized_text or len(optimized_text.strip()) < 10:
                    logger.debug(f"ADVERTENCIA - Chunk {i+1} vacío, usando embedding dummy")
                    embeddings.append(self._create_smart_dummy_embedding())
                    failed_count += 1
                    continue
                
                logger.info(f"PROCESANDO - Embedding {i+1}/{len(texts)} ({len(optimized_text)} chars)...")
                
                # Intentar con retry
                embedding = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        response = requests.post(
                            f"{self.host}/api/embeddings",
                            json={
                                "model": self.model_name,
                                "prompt": optimized_text
                            },
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            if 'embedding' not in data:
                                raise ValueError("Respuesta sin campo 'embedding'")
                            
                            embedding = data['embedding']
                            
                            # Validar embedding
                            if not embedding or len(embedding) == 0:
                                raise ValueError("Embedding vacío")
                            
                            # Verificar dimensiones
                            if len(embedding) != self.embedding_dims:
                                # Ajustar dimensiones si es necesario
                                if len(embedding) > self.embedding_dims:
                                    embedding = embedding[:self.embedding_dims]
                                else:
                                    embedding = embedding + [0.0] * (self.embedding_dims - len(embedding))
                            
                            logger.info(f"OK - Embedding {i+1} generado (real)")
                            break
                        else:
                            error_msg = f"HTTP {response.status_code}"
                            if response.text:
                                try:
                                    error_data = response.json()
                                    if 'error' in error_data:
                                        error_msg = f"HTTP {response.status_code}: {error_data['error'][:100]}"
                                except:
                                    error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                            raise Exception(error_msg)
                            
                    except Exception as e:
                        if attempt < self.max_retries:
                            logger.warning(f"ADVERTENCIA - Intento {attempt+1} fallado, esperando {self.retry_delay}s...")
                            time.sleep(self.retry_delay)
                        else:
                            raise e
                
                if embedding is not None:
                    embeddings.append(embedding)
                else:
                    raise Exception("No se pudo generar embedding")
                    
            except Exception as e:
                logger.error(f"ERROR - Embedding {i+1} falló: {str(e)[:100]}")
                embeddings.append(self._create_smart_dummy_embedding())
                failed_count += 1
        
        # Resumen
        total = len(texts)
        successful_count = total - failed_count
        logger.info(f"RESUMEN - Embeddings: {successful_count} reales, {failed_count} dummy de {total} total")
        
        return embeddings
    
    def _create_smart_dummy_embedding(self) -> List[float]:
        """Crea embedding dummy inteligente"""
        # Crear valores pseudo-aleatorios pero consistentes
        seed = hash(self.model_name) % 1000
        random.seed(seed)
        
        embedding = []
        for _ in range(self.embedding_dims):
            # Valores muy cercanos a 0 (para distinguirlos de los reales)
            value = random.uniform(-0.001, 0.001)
            embedding.append(round(value, 6))
        
        return embedding
    
    def _create_dummy_embeddings(self, count: int) -> List[List[float]]:
        """Crea múltiples embeddings dummy"""
        return [self._create_smart_dummy_embedding() for _ in range(count)]
    
    def is_dummy_embedding(self, embedding: List[float]) -> bool:
        """Determina si un embedding es dummy (basado en sus valores)"""
        if not embedding:
            return True
        
        # Un embedding dummy tiene valores muy cercanos a 0
        # Calculamos la magnitud promedio
        if len(embedding) == 0:
            return True
        
        # Verificar si todos los valores son muy pequeños
        max_abs = max(abs(v) for v in embedding[:min(100, len(embedding))])
        return max_abs < 0.01  # Si el valor máximo absoluto es < 0.01, es dummy

# FUNCIONES DE PROCESAMIENTO DE PDF (MANTENER IGUAL)
def clean_extracted_text(text: str) -> str:
    """Limpia caracteres de control del texto manteniendo estructura"""
    if not text or not isinstance(text, str):
        return ""
    
    try:
        text = unicodedata.normalize('NFKC', text)
        cleaned_chars = []
        for char in text:
            code = ord(char)
            if code == 10 or code == 13 or code == 9:
                cleaned_chars.append(char)
            elif code >= 32 and code != 127:
                cleaned_chars.append(char)
            elif code == 160:
                cleaned_chars.append(' ')
        
        cleaned = ''.join(cleaned_chars)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = '\n'.join(line.strip() for line in cleaned.split('\n'))
        
        return cleaned.strip()
        
    except Exception as e:
        logger.error(f"ERROR - Error en limpieza de texto: {e}")
        return re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text).strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae texto de un PDF usando el mejor método disponible"""
    filename = os.path.basename(pdf_path)
    
    if not FITZ_AVAILABLE and not PYPDF_AVAILABLE:
        logger.error(f"ERROR - No hay bibliotecas PDF disponibles para {filename}")
        return ""
    
    logger.info(f"LEYENDO - Procesando PDF: {filename}")
    
    if FITZ_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    page_text = page.get_text("text") or page.get_text()
                    
                    if page_text and page_text.strip():
                        cleaned = clean_extracted_text(page_text)
                        if cleaned.strip():
                            full_text += f"\n--- Pagina {page_num + 1} ---\n{cleaned}"
                
                except Exception as page_error:
                    logger.debug(f"ADVERTENCIA - Error en pagina {page_num + 1}: {str(page_error)[:50]}")
                    continue
            
            doc.close()
            
            if len(full_text.strip()) > 100:
                plantas = len(re.findall(r'\[PLANTA_\d+\]', full_text))
                logger.info(f"OK - {filename}: {plantas} plantas, {len(full_text):,} caracteres")
                return full_text
            
        except Exception as e:
            logger.warning(f"ADVERTENCIA - PyMuPDF fallo para {filename}: {str(e)[:100]}")
    
    if PYPDF_AVAILABLE:
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                full_text = ""
                
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            cleaned = clean_extracted_text(page_text)
                            if cleaned.strip():
                                full_text += f"\n--- Pagina {page_num + 1} ---\n{cleaned}"
                    except Exception as page_error:
                        logger.debug(f"ADVERTENCIA - Error pypdf pagina {page_num + 1}: {str(page_error)[:50]}")
                        continue
                
                if len(full_text.strip()) > 50:
                    plantas = len(re.findall(r'\[PLANTA_\d+\]', full_text))
                    logger.info(f"OK - {filename}: {plantas} plantas, {len(full_text):,} caracteres (pypdf)")
                    return full_text
                    
        except Exception as e:
            logger.error(f"ERROR - pypdf tambien fallo para {filename}: {str(e)[:100]}")
    
    logger.warning(f"ADVERTENCIA - No se pudo extraer texto de {filename}")
    return ""

def create_plant_chunks(text: str, source: str) -> List[Dict]:
    """Crea chunks inteligentes que preservan plantas completas"""
    if not text or not text.strip():
        return []
    
    text = clean_extracted_text(text)
    chunks = []
    
    plant_pattern = r'(\[PLANTA_\d+\][\s\S]*?)(?=\[PLANTA_\d+\]|$)'
    plants = re.findall(plant_pattern, text, re.DOTALL)
    
    if not plants:
        logger.warning(f"ADVERTENCIA - No se encontro estructura de plantas en {source}")
        pages = re.split(r'--- Pagina \d+ ---', text)
        pages = [p.strip() for p in pages if p.strip()]
        
        for i, page in enumerate(pages):
            if len(page.strip()) > 100:
                chunks.append({
                    'text': page,
                    'source': source,
                    'chunk_id': len(chunks),
                    'type': 'pagina',
                    'page_num': i + 1
                })
        return chunks
    
    logger.info(f"INFO - {source}: {len(plants)} plantas encontradas")
    
    current_chunk = ""
    current_plants = []
    
    for plant in plants:
        plant = plant.strip()
        if not plant:
            continue
        
        plant_size = len(plant)
        
        if plant_size > 3000:
            if current_chunk:
                chunks.append({
                    'text': current_chunk,
                    'source': source,
                    'chunk_id': len(chunks),
                    'plants': current_plants.copy(),
                    'plant_count': len(current_plants)
                })
                current_chunk = ""
                current_plants = []
            
            plant_num = re.search(r'\[PLANTA_(\d+)\]', plant)
            chunks.append({
                'text': plant,
                'source': source,
                'chunk_id': len(chunks),
                'plants': [plant_num.group(1)] if plant_num else ["grande"],
                'plant_count': 1,
                'type': 'planta_grande'
            })
            continue
        
        if current_chunk and len(current_chunk) + len(plant) > 4000:
            chunks.append({
                'text': current_chunk,
                'source': source,
                'chunk_id': len(chunks),
                'plants': current_plants.copy(),
                'plant_count': len(current_plants)
            })
            current_chunk = plant
            current_plants = []
            
            plant_num = re.search(r'\[PLANTA_(\d+)\]', plant)
            if plant_num:
                current_plants = [plant_num.group(1)]
            else:
                current_plants = [f"chunk_{len(chunks)}"]
        else:
            if current_chunk:
                current_chunk += "\n\n" + plant
            else:
                current_chunk = plant
            
            plant_num = re.search(r'\[PLANTA_(\d+)\]', plant)
            if plant_num:
                current_plants.append(plant_num.group(1))
            else:
                current_plants.append(f"planta_{len(current_plants)+1}")
    
    if current_chunk:
        chunks.append({
            'text': current_chunk,
            'source': source,
            'chunk_id': len(chunks),
            'plants': current_plants,
            'plant_count': len(current_plants)
        })
    
    logger.info(f"DIVIDIDO - {len(chunks)} chunks creados para {source}")
    
    return chunks

async def process_pdfs(pdf_folder: str) -> List[Dict]:
    """Procesa todos los PDFs en la carpeta especificada"""
    all_chunks = []
    
    if not os.path.exists(pdf_folder):
        logger.error(f"ERROR - La carpeta no existe: {pdf_folder}")
        return all_chunks
    
    pdf_files = []
    for file in os.listdir(pdf_folder):
        if file.lower().endswith('.pdf'):
            pdf_files.append(file)
    
    if not pdf_files:
        logger.error(f"ERROR - No se encontraron archivos PDF en: {pdf_folder}")
        return all_chunks
    
    logger.info(f"ENCONTRADOS - {len(pdf_files)} archivos PDF")
    
    for filename in pdf_files:
        pdf_path = os.path.join(pdf_folder, filename)
        logger.info(f"\nPROCESANDO - Archivo: {filename}")
        
        text = extract_text_from_pdf(pdf_path)
        
        if text and len(text.strip()) > 100:
            chunks = create_plant_chunks(text, filename)
            
            if chunks:
                first_chunk = chunks[0]
                logger.info(f"OK - {len(chunks)} chunks creados")
                logger.info(f"   Chunk 0: {first_chunk.get('plant_count', 0)} plantas, {len(first_chunk['text'])} caracteres")
                
                if 'NOMBRE_CIENTIFICO:' in first_chunk['text'] and 'USO_TRADICIONAL:' in first_chunk['text']:
                    logger.info("   OK - Estructura de planta preservada")
                else:
                    logger.warning("   ADVERTENCIA - Estructura de planta incompleta")
                
                all_chunks.extend(chunks)
            else:
                logger.warning(f"ADVERTENCIA - No se pudieron crear chunks para {filename}")
        else:
            logger.warning(f"ADVERTENCIA - {filename}: Texto insuficiente o vacio")
    
    logger.info(f"\nTOTAL - {len(all_chunks)} chunks creados")
    
    if all_chunks:
        total_plants = sum(chunk.get('plant_count', 0) for chunk in all_chunks)
        total_chars = sum(len(chunk['text']) for chunk in all_chunks)
        logger.info(f"RESUMEN - {total_plants} plantas en total, {total_chars:,} caracteres")
    
    return all_chunks

async def save_to_database(chunks: List[Dict], embeddings: List[List[float]], 
                          collection_id: str, embedder: RobustOllamaEmbeddings) -> int:
    """Guarda chunks y embeddings en PostgreSQL"""
    try:
        db_config = {
            'dbname': os.getenv("DB_NAME", "postgres"),
            'user': os.getenv("DB_USER", "postgres"),
            'password': os.getenv("DB_PASSWORD", ""),
            'host': os.getenv("DB_HOST", "localhost"),
            'port': os.getenv("DB_PORT", "5432")
        }
        
        logger.info(f"CONECTANDO - PostgreSQL: {db_config['host']}:{db_config['port']}")
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'langchain_pg_embedding'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error("ERROR - La tabla 'langchain_pg_embedding' no existe")
            cursor.close()
            conn.close()
            return 0
        
        cursor.execute("DELETE FROM langchain_pg_embedding WHERE collection_id = %s", (collection_id,))
        deleted_count = cursor.rowcount
        logger.info(f"LIMPIEZA - Coleccion limpiada: {deleted_count} documentos eliminados")
        
        inserted = 0
        total_chunks = len(chunks)
        
        # ⬇️ YA NO CREA NUEVA INSTANCIA, USA LA QUE SE PASÓ
        logger.info(f"USANDO - Embedder con {embedder.embedding_dims} dimensiones")
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                if not chunk['text'] or len(chunk['text'].strip()) < 50:
                    logger.debug(f"ADVERTENCIA - Chunk {i} muy corto, omitiendo")
                    continue
                
                if len(embedding) == 0:
                    logger.warning(f"ADVERTENCIA - Chunk {i}: Embedding vacio")
                    continue
                
                # Verificar consistencia de dimensiones
                if len(embedding) != embedder.embedding_dims:
                    logger.error(f"ERROR - Chunk {i}: embedding tiene {len(embedding)} dims pero esperaba {embedder.embedding_dims}")
                    continue
                
                # DETERMINAR SI ES DUMMY CORRECTAMENTE
                is_dummy = embedder.is_dummy_embedding(embedding)
                embedding_type = "dummy" if is_dummy else "real"
                
                metadata = {
                    "source": chunk['source'],
                    "chunk_id": chunk['chunk_id'],
                    "plant_count": chunk.get('plant_count', 0),
                    "plants": chunk.get('plants', []),
                    "type": chunk.get('type', 'planta_completa'),
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "embedding_type": embedding_type,
                    "embedding_quality": "low" if is_dummy else "high",
                    "embedding_dims": len(embedding)  # ⬅️ GUARDAR DIMENSIÓN REAL
                }
                
                cursor.execute("""
                    INSERT INTO langchain_pg_embedding 
                        (collection_id, embedding, document, cmetadata)
                    VALUES 
                        (%s, %s::vector, %s, %s)
                """, (
                    collection_id,
                    embedding,
                    chunk['text'][:10000],
                    json.dumps(metadata, ensure_ascii=False)
                ))
                inserted += 1
                
                if (i + 1) % 5 == 0 or (i + 1) == total_chunks:
                    logger.info(f"INSERTANDO - Progreso: {i + 1}/{total_chunks} ({embedding_type})")
                    
            except Exception as e:
                logger.error(f"ERROR - Error insertando chunk {i}: {str(e)[:100]}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"GUARDADO - {inserted}/{total_chunks} chunks insertados exitosamente")
        return inserted
        
    except psycopg2.OperationalError as e:
        logger.error(f"ERROR - Error de conexion a PostgreSQL: {e}")
        return 0
    except Exception as e:
        logger.error(f"ERROR - Error de base de datos: {e}")
        import traceback
        traceback.print_exc()
        return 0

async def verify_database(collection_id: str):
    """Verifica que los datos se hayan insertado correctamente"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = %s", (collection_id,))
        count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT vector_dims(embedding) as dims 
            FROM langchain_pg_embedding 
            WHERE collection_id = %s 
            LIMIT 1
        """, (collection_id,))
        dim_result = cursor.fetchone()
        dims = dim_result[0] if dim_result else "N/A"
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN cmetadata->>'embedding_type' = 'dummy' THEN 1 ELSE 0 END) as dummy_count
            FROM langchain_pg_embedding 
            WHERE collection_id = %s
        """, (collection_id,))
        
        quality_result = cursor.fetchone()
        total_docs = quality_result[0] if quality_result else 0
        dummy_docs = quality_result[1] if quality_result else 0
        
        cursor.execute("""
            SELECT 
                LEFT(document, 150) as preview,
                cmetadata->>'source' as source,
                cmetadata->>'plant_count' as plants,
                cmetadata->>'embedding_type' as embedding_type,
                cmetadata->>'embedding_quality' as quality
            FROM langchain_pg_embedding 
            WHERE collection_id = %s 
            ORDER BY RANDOM() 
            LIMIT 3
        """, (collection_id,))
        
        samples = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        logger.info("VERIFICACION - Base de datos:")
        logger.info(f"   Documentos en coleccion: {count}")
        logger.info(f"   Dimension embeddings: {dims}")
        logger.info(f"   Calidad embeddings: {total_docs - dummy_docs} reales, {dummy_docs} dummy")
        
        if samples:
            logger.info("   Muestras aleatorias:")
            for preview, source, plants, emb_type, quality in samples:
                clean_preview = preview.replace('\n', ' ').strip()
                logger.info(f"     {source} ({plants} plantas): {emb_type} ({quality}) - {clean_preview[:80]}...")
        
        return count, dummy_docs
        
    except Exception as e:
        logger.error(f"ERROR - Error en verificacion: {e}")
        return 0, 0

async def main():
    """Función principal"""
    print("\n" + "="*70)
    print("CARGADOR DE PLANTAS MEDICINALES - VERSIÓN FINAL")
    print("="*70)
    
    pdf_folder = "C:/Users/Fytli/OneDrive/Escritorio/plant_medicator_venv/plant-medicator/pdf-books"
    collection_id = '9e74cfee-6339-4551-aca3-154a2066cd38'
    
    logger.info("\nVERIFICANDO - Dependencias...")
    
    if not FITZ_AVAILABLE and not PYPDF_AVAILABLE:
        logger.error("ERROR - No hay bibliotecas PDF disponibles")
        return
    
    logger.info("\nVERIFICANDO - Estado de Ollama...")
    
    if not OllamaManager.check_if_ollama_is_running():
        logger.error("ERROR - Ollama no está ejecutándose")
        logger.info("CONSEJO: Abre otra terminal y ejecuta: ollama serve")
        logger.info("Continuando con embeddings dummy...")
        embeddings_available = False
        working_model = None
    else:
        embeddings_available = OllamaManager.check_ollama_health()
        
        if embeddings_available:
            working_model, test_ok = OllamaManager.test_embeddings()
            if not test_ok:
                logger.warning("ADVERTENCIA - Ollama está ejecutándose pero embeddings fallan")
                embeddings_available = False
        else:
            working_model = None
    
    logger.info("\nEXTRAYENDO - Textos de PDFs...")
    chunks = await process_pdfs(pdf_folder)
    
    if not chunks:
        logger.error("ERROR - No se pudieron crear chunks")
        return
    
    logger.info(f"\nOK - {len(chunks)} chunks listos para procesar")
    
    logger.info("\nGENERANDO - Embeddings...")
    
    if embeddings_available and working_model:
        logger.info(f"USANDO - Modelo: {working_model}")
        embedder = RobustOllamaEmbeddings(model_name=working_model)
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = embedder.embed_documents(chunk_texts)
    else:
        logger.warning("ADVERTENCIA - Usando embeddings dummy")
        embedder = RobustOllamaEmbeddings()
        embeddings = embedder._create_dummy_embeddings(len(chunks))
    
    if len(embeddings) != len(chunks):
        logger.warning(f"ADVERTENCIA - Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
        while len(embeddings) < len(chunks):
            embeddings.append(embedder._create_smart_dummy_embedding())
    
    logger.info("\nGUARDANDO - Base de datos PostgreSQL...")
    inserted = await save_to_database(chunks, embeddings, collection_id, embedder)
    
    if inserted > 0:
        logger.info(f"\n" + "="*60)
        logger.info(f"ÉXITO - Proceso completado!")
        logger.info(f"="*60)
        
        logger.info("\nVERIFICANDO - Verificación final...")
        db_count, dummy_count = await verify_database(collection_id)
        
        logger.info(f"\nRESUMEN FINAL:")
        logger.info(f"  • Documentos totales: {db_count}")
        logger.info(f"  • Embeddings reales: {db_count - dummy_count}")
        logger.info(f"  • Embeddings dummy: {dummy_count}")
        
        if dummy_count > 0:
            logger.info("\n[ADVERTENCIA] Hay embeddings dummy")
            logger.info("Para mejorar los embeddings:")
            logger.info("1. Asegúrate de que Ollama esté ejecutándose ('ollama serve')")
            logger.info("2. Verifica que el modelo esté descargado ('ollama pull nomic-embed-text')")
            logger.info("3. Ejecuta este script nuevamente")
        else:
            logger.info("\n[TODO OK] Todos los embeddings son reales!")
        
        logger.info("\n[LISTO] Sistema RAG listo para usar!")
        
    else:
        logger.error("ERROR - No se insertaron documentos")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("SISTEMA RAG - CARGADOR FINAL")
    print("="*70)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Directorio: {os.getcwd()}")
    print(f"PyMuPDF: {'SI' if FITZ_AVAILABLE else 'NO'}")
    print(f"pypdf: {'SI' if PYPDF_AVAILABLE else 'NO'}")
    print("="*70)
    
    print("\nINSTRUCCIONES PARA EMBEDDINGS REALES:")
    print("1. En una terminal SEPARADA ejecuta: ollama serve")
    print("2. Si no tienes el modelo: ollama pull nomic-embed-text")
    print("3. Luego ejecuta este script")
    print("\nPresiona Enter para comenzar o Ctrl+C para cancelar...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nCANCELADO")
        sys.exit(0)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nCANCELADO")
    except Exception as e:
        logger.error(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("PROCESO FINALIZADO")
    print("="*70)