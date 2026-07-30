"""
rag_load_and_process_SENTENCE_TRANSFORMERS.py
VERSIÓN CORREGIDA - USA SENTENCE TRANSFORMERS (384 DIMS)
Compatible con el sistema RAG actual (Groq + Sentence Transformers)
"""

import os
import sys
import asyncio
import warnings
from dotenv import load_dotenv
import psycopg2
import json
from typing import List, Dict
import logging
import re
import time
import unicodedata
from datetime import datetime
from sentence_transformers import SentenceTransformer

# IMPORTACIONES PARA PDFs
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

class SentenceTransformerEmbeddings:
    """Clase de embeddings con Sentence Transformers (384 dimensiones)"""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.embedding_dims = 384
        
        logger.info(f"📦 Cargando modelo: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.info(f"✅ Modelo cargado ({self.embedding_dims} dimensiones)")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para una lista de textos"""
        embeddings = []
        total = len(texts)
        
        logger.info(f"🔄 Generando embeddings para {total} documentos...")
        
        for i, text in enumerate(texts):
            try:
                # Optimizar texto
                optimized_text = self._optimize_text(text)
                
                if not optimized_text or len(optimized_text.strip()) < 10:
                    logger.warning(f"⚠️ Chunk {i+1} vacío, omitiendo")
                    continue
                
                # Generar embedding
                embedding = self.model.encode(optimized_text, show_progress_bar=False)
                embeddings.append(embedding.tolist())
                
                if (i + 1) % 10 == 0 or (i + 1) == total:
                    logger.info(f"   ✓ Procesados {i + 1}/{total} ({(i+1)*100//total}%)")
                
            except Exception as e:
                logger.error(f"❌ Error en chunk {i+1}: {str(e)[:100]}")
                continue
        
        logger.info(f"✅ {len(embeddings)} embeddings generados exitosamente")
        return embeddings
    
    def _optimize_text(self, text: str, max_length: int = 2000) -> str:
        """Optimiza el texto para embeddings"""
        if not text:
            return ""
        
        # Limitar tamaño
        if len(text) > max_length:
            text = text[:max_length]
        
        # Eliminar caracteres problemáticos
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', text)
        
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

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
    
    logger.info(f"📄 Procesando PDF: {filename}")
    
    # Intentar con PyMuPDF primero
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
                            full_text += f"\n--- Página {page_num + 1} ---\n{cleaned}"
                
                except Exception as page_error:
                    logger.debug(f"⚠️ Error en página {page_num + 1}: {str(page_error)[:50]}")
                    continue
            
            doc.close()
            
            if len(full_text.strip()) > 100:
                plantas = len(re.findall(r'\[PLANTA_\d+\]', full_text))
                logger.info(f"✅ {filename}: {plantas} plantas, {len(full_text):,} caracteres")
                return full_text
            
        except Exception as e:
            logger.warning(f"⚠️ PyMuPDF falló para {filename}: {str(e)[:100]}")
    
    # Fallback a pypdf
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
                                full_text += f"\n--- Página {page_num + 1} ---\n{cleaned}"
                    except Exception as page_error:
                        logger.debug(f"⚠️ Error pypdf página {page_num + 1}: {str(page_error)[:50]}")
                        continue
                
                if len(full_text.strip()) > 50:
                    plantas = len(re.findall(r'\[PLANTA_\d+\]', full_text))
                    logger.info(f"✅ {filename}: {plantas} plantas, {len(full_text):,} caracteres (pypdf)")
                    return full_text
                    
        except Exception as e:
            logger.error(f"❌ pypdf también falló para {filename}: {str(e)[:100]}")
    
    logger.warning(f"⚠️ No se pudo extraer texto de {filename}")
    return ""

def create_plant_chunks(text: str, source: str) -> List[Dict]:
    """Crea chunks inteligentes que preservan plantas completas"""
    if not text or not text.strip():
        return []
    
    text = clean_extracted_text(text)
    chunks = []
    
    # Buscar estructura de plantas
    plant_pattern = r'(\[PLANTA_\d+\][\s\S]*?)(?=\[PLANTA_\d+\]|$)'
    plants = re.findall(plant_pattern, text, re.DOTALL)
    
    if not plants:
        logger.warning(f"⚠️ No se encontró estructura de plantas en {source}")
        # Dividir por páginas
        pages = re.split(r'--- Página \d+ ---', text)
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
    
    logger.info(f"📝 {source}: {len(plants)} plantas encontradas")
    
    current_chunk = ""
    current_plants = []
    
    for plant in plants:
        plant = plant.strip()
        if not plant:
            continue
        
        plant_size = len(plant)
        
        # Planta muy grande (dividir)
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
        
        # Agrupar plantas
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
            if current_chunk:
                current_chunk += "\n\n" + plant
            else:
                current_chunk = plant
            
            plant_num = re.search(r'\[PLANTA_(\d+)\]', plant)
            if plant_num:
                current_plants.append(plant_num.group(1))
    
    if current_chunk:
        chunks.append({
            'text': current_chunk,
            'source': source,
            'chunk_id': len(chunks),
            'plants': current_plants,
            'plant_count': len(current_plants)
        })
    
    logger.info(f"✂️ {len(chunks)} chunks creados para {source}")
    
    return chunks

async def process_pdfs(pdf_folder: str) -> List[Dict]:
    """Procesa todos los PDFs en la carpeta especificada"""
    all_chunks = []
    
    if not os.path.exists(pdf_folder):
        logger.error(f"❌ La carpeta no existe: {pdf_folder}")
        return all_chunks
    
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.error(f"❌ No se encontraron archivos PDF en: {pdf_folder}")
        return all_chunks
    
    logger.info(f"📚 Encontrados {len(pdf_files)} archivos PDF")
    
    for filename in pdf_files:
        pdf_path = os.path.join(pdf_folder, filename)
        logger.info(f"\n{'='*60}")
        logger.info(f"📖 Procesando: {filename}")
        logger.info(f"{'='*60}")
        
        text = extract_text_from_pdf(pdf_path)
        
        if text and len(text.strip()) > 100:
            chunks = create_plant_chunks(text, filename)
            
            if chunks:
                logger.info(f"✅ {len(chunks)} chunks creados")
                all_chunks.extend(chunks)
            else:
                logger.warning(f"⚠️ No se pudieron crear chunks para {filename}")
        else:
            logger.warning(f"⚠️ {filename}: Texto insuficiente o vacío")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📦 TOTAL: {len(all_chunks)} chunks creados")
    logger.info(f"{'='*60}")
    
    return all_chunks

async def save_to_database(chunks: List[Dict], embeddings: List[List[float]], 
                          collection_id: str, embedder: SentenceTransformerEmbeddings) -> int:
    """Guarda chunks y embeddings en PostgreSQL"""
    try:
        db_config = {
            'dbname': os.getenv("DB_NAME", "postgres"),
            'user': os.getenv("DB_USER", "postgres"),
            'password': os.getenv("DB_PASSWORD", ""),
            'host': os.getenv("DB_HOST", "localhost"),
            'port': os.getenv("DB_PORT", "5432")
        }
        
        logger.info(f"🔌 Conectando a PostgreSQL: {db_config['host']}:{db_config['port']}")
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Verificar tabla
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'langchain_pg_embedding'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.error("❌ La tabla 'langchain_pg_embedding' no existe")
            cursor.close()
            conn.close()
            return 0
        
        # Limpiar colección anterior
        cursor.execute("DELETE FROM langchain_pg_embedding WHERE collection_id = %s", (collection_id,))
        deleted_count = cursor.rowcount
        logger.info(f"🗑️ Colección limpiada: {deleted_count} documentos eliminados")
        
        inserted = 0
        total_chunks = len(chunks)
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                if not chunk['text'] or len(chunk['text'].strip()) < 50:
                    logger.debug(f"⚠️ Chunk {i} muy corto, omitiendo")
                    continue
                
                if len(embedding) != embedder.embedding_dims:
                    logger.error(f"❌ Chunk {i}: dimensión incorrecta {len(embedding)} != {embedder.embedding_dims}")
                    continue
                
                metadata = {
                    "source": chunk['source'],
                    "chunk_id": chunk['chunk_id'],
                    "plant_count": chunk.get('plant_count', 0),
                    "plants": chunk.get('plants', []),
                    "type": chunk.get('type', 'planta_completa'),
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "embedding_model": embedder.model_name,
                    "embedding_dims": embedder.embedding_dims
                }
                
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                cursor.execute("""
                    INSERT INTO langchain_pg_embedding 
                        (collection_id, embedding, document, cmetadata)
                    VALUES 
                        (%s, %s::vector, %s, %s)
                """, (
                    collection_id,
                    embedding_str,
                    chunk['text'][:10000],
                    json.dumps(metadata, ensure_ascii=False)
                ))
                inserted += 1
                
                if (i + 1) % 10 == 0 or (i + 1) == total_chunks:
                    logger.info(f"💾 Progreso: {i + 1}/{total_chunks} ({(i+1)*100//total_chunks}%)")
                    
            except Exception as e:
                logger.error(f"❌ Error insertando chunk {i}: {str(e)[:100]}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ {inserted}/{total_chunks} chunks insertados exitosamente")
        return inserted
        
    except psycopg2.OperationalError as e:
        logger.error(f"❌ Error de conexión a PostgreSQL: {e}")
        return 0
    except Exception as e:
        logger.error(f"❌ Error de base de datos: {e}")
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
                LEFT(document, 150) as preview,
                cmetadata->>'source' as source,
                cmetadata->>'plant_count' as plants
            FROM langchain_pg_embedding 
            WHERE collection_id = %s 
            ORDER BY RANDOM() 
            LIMIT 3
        """, (collection_id,))
        
        samples = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        logger.info(f"\n{'='*60}")
        logger.info("🔍 VERIFICACIÓN DE BASE DE DATOS")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Documentos en colección: {count}")
        logger.info(f"📏 Dimensión embeddings: {dims}")
        
        if samples:
            logger.info("\n📄 Muestras aleatorias:")
            for preview, source, plants in samples:
                clean_preview = preview.replace('\n', ' ').strip()
                logger.info(f"   • {source} ({plants} plantas): {clean_preview[:80]}...")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Error en verificación: {e}")
        return 0

async def main():
    """Función principal"""
    logger.info(f"\n{'='*70}")
    logger.info("🌿 CARGADOR DE PLANTAS MEDICINALES - SENTENCE TRANSFORMERS")
    logger.info(f"{'='*70}\n")
    
    pdf_folder = "C:/Users/Fytli/OneDrive/Escritorio/plant_medicator_venv/plant-medicator/pdf-books"
    collection_id = '9e74cfee-6339-4551-aca3-154a2066cd38'
    
    # Verificar dependencias
    if not FITZ_AVAILABLE and not PYPDF_AVAILABLE:
        logger.error("❌ No hay bibliotecas PDF disponibles")
        return
    
    # Inicializar embedder
    embedder = SentenceTransformerEmbeddings()
    
    # Procesar PDFs
    logger.info("📚 Extrayendo textos de PDFs...\n")
    chunks = await process_pdfs(pdf_folder)
    
    if not chunks:
        logger.error("❌ No se pudieron crear chunks")
        return
    
    logger.info(f"\n✅ {len(chunks)} chunks listos para procesar")
    
    # Generar embeddings
    logger.info("\n🔄 Generando embeddings con Sentence Transformers...")
    chunk_texts = [chunk['text'] for chunk in chunks]
    embeddings = embedder.embed_documents(chunk_texts)
    
    if len(embeddings) != len(chunks):
        logger.error(f"❌ Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
        return
    
    # Guardar en base de datos
    logger.info("\n💾 Guardando en PostgreSQL...")
    inserted = await save_to_database(chunks, embeddings, collection_id, embedder)
    
    if inserted > 0:
        logger.info(f"\n{'='*70}")
        logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
        logger.info(f"{'='*70}\n")
        
        # Verificar
        await verify_database(collection_id)
        
        logger.info(f"\n{'='*70}")
        logger.info("🎉 SISTEMA RAG LISTO PARA USAR")
        logger.info(f"{'='*70}")
        logger.info(f"📊 Documentos insertados: {inserted}")
        logger.info(f"📏 Dimensiones: 384 (compatible con tu sistema)")
        logger.info(f"✅ Embeddings: 100% reales (Sentence Transformers)")
        
    else:
        logger.error("❌ No se insertaron documentos")

if __name__ == "__main__":
    print(f"\n{'='*70}")
    print("🌿 SISTEMA RAG - CARGADOR CON SENTENCE TRANSFORMERS")
    print(f"{'='*70}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"PyMuPDF: {'SÍ' if FITZ_AVAILABLE else 'NO'}")
    print(f"pypdf: {'SÍ' if PYPDF_AVAILABLE else 'NO'}")
    print(f"{'='*70}\n")
    
    print("Este script regenerará TODOS los embeddings con Sentence Transformers (384 dims)")
    print("Esto es compatible con tu sistema RAG actual (Groq + Sentence Transformers)\n")
    print("Presiona Enter para comenzar o Ctrl+C para cancelar...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ CANCELADO")
        sys.exit(0)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n❌ CANCELADO POR USUARIO")
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("🏁 PROCESO FINALIZADO")
    print(f"{'='*70}\n")