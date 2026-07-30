import re
import pdfplumber
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from datetime import datetime

def extract_plants_complete(pdf_path):
    """
    Extrae TODAS las 39 plantas del PDF con mayor precisión.
    """
    
    print("="*60)
    print("EXTRACCIÓN COMPLETA DE 39 PLANTAS MEDICINALES")
    print("="*60)
    
    # 1. Extraer texto completo
    all_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            print(f"Procesando página {page_num + 1}...")
            text = page.extract_text()
            if text:
                all_text += f"\n--- PÁGINA {page_num + 1} ---\n" + text
    
    # 2. Limpiar encabezados y pies de página
    all_text = clean_headers_footers(all_text)
    
    # 3. Dividir por plantas usando múltiples estrategias
    plants = []
    
    # Estrategia 1: Buscar nombres científicos seguidos de número de página
    pattern1 = r'([A-Z][a-z]+\s+[a-z]+(?:\s+[A-Za-z\.\(\)&]+)*)\s+(\d+)\s*\n'
    matches = list(re.finditer(pattern1, all_text))
    
    print(f"\nEncontrados {len(matches)} patrones de nombres científicos")
    
    # Procesar cada bloque
    for i in range(len(matches)):
        start = matches[i].start()
        if i < len(matches) - 1:
            end = matches[i + 1].start()
        else:
            end = len(all_text)
        
        block = all_text[start:end].strip()
        plant = extract_plant_from_block(block)
        
        if plant and plant.get('nombre_cientifico'):
            # Verificar si no es duplicado
            if not is_duplicate(plant, plants):
                plants.append(plant)
    
    # Estrategia 2: Buscar plantas que no tienen número de página
    # (como la primera: Aloysia citrodora)
    missing_plants = find_missing_plants(all_text, plants)
    plants.extend(missing_plants)
    
    # 3. Ordenar por nombre científico para consistencia
    plants.sort(key=lambda x: x.get('nombre_cientifico', ''))
    
    return plants

def clean_headers_footers(text):
    """
    Elimina encabezados, pies de página y elementos no deseados.
    """
    
    # Patrones a eliminar
    patterns_to_remove = [
        r'Catálogo florístico de plantas medicinales peruanas',
        r'Centro Nacional de Salud Intercultural\s*\(CENSI\)',
        r'Centro Nacional de Salud Intercultural(?!\s*\()',
        r'Foto:\s*J\.\s*Cabrera',
        r'CENSI(?!\w)',
        r'--- PÁGINA \d+ ---',
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Limpiar líneas vacías múltiples
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def extract_plant_from_block(block):
    """
    Extrae información de una planta desde un bloque de texto.
    """
    
    plant = {
        'nombre_cientifico': '',
        'nombre_comun': '',
        'familia': '',
        'lugar_colecta': '',
        'uso_tradicional': '',
        'advertencias': ''
    }
    
    lines = [line.strip() for line in block.split('\n') if line.strip()]
    
    if not lines:
        return None
    
    # Extraer nombre científico (primera línea, limpiando número de página)
    first_line = lines[0]
    sci_name_match = re.match(r'^([A-Z][a-z]+\s+[a-z]+(?:\s+[A-Za-z\.\(\)&]+)*)', first_line)
    if sci_name_match:
        plant['nombre_cientifico'] = sci_name_match.group(1).strip()
    
    # Convertir bloque a texto único para búsquedas
    block_text = '\n'.join(lines)
    
    # Nombre común
    nombre_match = re.search(
        r'Nombre común:\s*([^\n]+?)(?=\s*(?:Familia:|Lugar de colecta:|Uso tradicional:|$))',
        block_text, re.IGNORECASE
    )
    if nombre_match:
        plant['nombre_comun'] = clean_field(nombre_match.group(1))
    
    # Familia
    familia_match = re.search(
        r'Familia:\s*([^\n]+?)(?=\s*(?:Lugar de colecta:|Uso tradicional:|$))',
        block_text, re.IGNORECASE
    )
    if familia_match:
        plant['familia'] = clean_field(familia_match.group(1))
    
    # Lugar de colecta
    lugar_match = re.search(
        r'Lugar de colecta:\s*([^\n]+?)(?=\s*(?:Uso tradicional:|$))',
        block_text, re.IGNORECASE
    )
    if lugar_match:
        plant['lugar_colecta'] = clean_field(lugar_match.group(1))
    
    # Uso tradicional (multilínea, hasta encontrar "Advertencia" o fin)
    uso_match = re.search(
        r'Uso tradicional:\s*(.+?)(?=(?:\s*Advertencia|\s*$))',
        block_text, re.IGNORECASE | re.DOTALL
    )
    if uso_match:
        uso_text = uso_match.group(1).strip()
        plant['uso_tradicional'] = clean_field(uso_text)
    
    # Advertencias
    adv_match = re.search(
        r'Advertencia[:\s]*(.+?)(?=\s*$)',
        block_text, re.IGNORECASE | re.DOTALL
    )
    if adv_match:
        plant['advertencias'] = clean_field(adv_match.group(1))
    
    return plant

def find_missing_plants(text, existing_plants):
    """
    Busca plantas que pueden haberse perdido en la primera extracción.
    Específicamente busca Aloysia citrodora y otras posibles.
    """
    
    missing = []
    existing_names = {p['nombre_cientifico'] for p in existing_plants}
    
    # Buscar todas las ocurrencias de "Nombre común:" sin número de página previo
    pattern = r'([A-Z][a-z]+\s+[a-z]+(?:\s+[A-Za-z\.\(\)&]+)*)\s*\n\s*Nombre común:'
    matches = re.finditer(pattern, text)
    
    for match in matches:
        sci_name = match.group(1).strip()
        
        # Si no está en la lista existente
        if sci_name not in existing_names:
            # Extraer el bloque completo
            start = match.start()
            # Buscar el final (siguiente nombre científico o fin)
            next_match = re.search(
                r'\n\s*[A-Z][a-z]+\s+[a-z]+(?:\s+[A-Za-z\.\(\)&]+)*\s*\n\s*Nombre común:',
                text[start + 50:]
            )
            
            if next_match:
                end = start + 50 + next_match.start()
            else:
                end = len(text)
            
            block = text[start:end]
            plant = extract_plant_from_block(block)
            
            if plant and plant.get('nombre_cientifico'):
                missing.append(plant)
                existing_names.add(plant['nombre_cientifico'])
    
    return missing

def clean_field(text):
    """
    Limpia un campo de texto individual.
    """
    
    if not text:
        return ""
    
    # Eliminar números de página sueltos al final
    text = re.sub(r'\s+\d+\s*$', '', text)
    
    # Eliminar "()" vacíos
    text = re.sub(r'\s*\(\s*\)\s*', '', text)
    
    # Eliminar espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    
    # Eliminar saltos de línea dentro del texto
    text = text.replace('\n', ' ')
    
    # Eliminar números de superíndice comunes (referencias)
    text = re.sub(r'(\d+,)*\d+\s*\.?\s*$', '', text)
    
    return text.strip()

def is_duplicate(plant, plants_list):
    """
    Verifica si una planta ya existe en la lista.
    """
    
    sci_name = plant.get('nombre_cientifico', '').lower()
    
    for existing in plants_list:
        if existing.get('nombre_cientifico', '').lower() == sci_name:
            return True
    
    return False

def validate_extraction(plants):
    """
    Valida que se extrajeron las 39 plantas esperadas.
    """
    
    expected_count = 39
    actual_count = len(plants)
    
    print(f"\n{'='*60}")
    print(f"VALIDACIÓN DE EXTRACCIÓN")
    print(f"{'='*60}")
    print(f"Plantas esperadas: {expected_count}")
    print(f"Plantas extraídas: {actual_count}")
    
    if actual_count == expected_count:
        print("✓ ÉXITO: Se extrajeron todas las plantas")
    elif actual_count < expected_count:
        print(f"⚠ ADVERTENCIA: Faltan {expected_count - actual_count} plantas")
    else:
        print(f"⚠ ADVERTENCIA: Se extrajeron {actual_count - expected_count} plantas de más")
    
    # Verificar plantas conocidas
    known_plants = [
        "Aloysia citrodora",
        "Annona muricata",
        "Passiflora edulis",
        "Xanthium spinosum"
    ]
    
    print(f"\nVerificación de plantas clave:")
    for known in known_plants:
        found = any(known in p['nombre_cientifico'] for p in plants)
        status = "✓" if found else "✗"
        print(f"  {status} {known}")

def save_results(plants, output_txt, output_json):
    """
    Guarda los resultados en formato limpio para Ollama.
    """
    
    # Guardar JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(plants, f, ensure_ascii=False, indent=2)
    
    # Guardar TXT optimizado para vector database
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("CATÁLOGO DE PLANTAS MEDICINALES PERUANAS\n")
        f.write("Base de datos limpia para embeddings vectoriales\n")
        f.write("="*80 + "\n\n")
        
        for i, plant in enumerate(plants, 1):
            # Formato optimizado para embeddings
            f.write(f"[PLANTA_{i:03d}]\n")
            f.write(f"NOMBRE_CIENTÍFICO: {plant.get('nombre_cientifico', 'N/A')}\n")
            f.write(f"NOMBRE_COMÚN: {plant.get('nombre_comun', 'N/A')}\n")
            f.write(f"FAMILIA: {plant.get('familia', 'N/A')}\n")
            f.write(f"UBICACIÓN: {plant.get('lugar_colecta', 'N/A')}\n")
            
            # Uso tradicional (el más importante para búsquedas)
            uso = plant.get('uso_tradicional', 'N/A')
            f.write(f"USO_TRADICIONAL: {uso}\n")
            
            # Advertencias si existen
            if plant.get('advertencias'):
                f.write(f"ADVERTENCIAS: {plant['advertencias']}\n")
            
            f.write("\n" + "-"*80 + "\n\n")
    
    print(f"\n✓ Archivos guardados:")
    print(f"  - JSON: {output_json}")
    print(f"  - TXT: {output_txt}")

def save_to_pdf(plants, output_pdf):
    """
    Guarda las plantas extraídas en un PDF con solo el contenido esencial.
    """
    
    print(f"\n📄 Generando PDF con contenido esencial: {output_pdf}")
    
    # Crear documento PDF con márgenes mínimos
    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    # Obtener estilos básicos
    styles = getSampleStyleSheet()
    
    # Crear estilo simple para texto plano
    plain_style = ParagraphStyle(
        'PlainStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',  # Fuente simple
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=6
    )
    
    # Crear contenido SOLO con las plantas
    story = []
    
    # Agregar cada planta directamente
    for i, plant in enumerate(plants, 1):
        # Encabezado simple de planta
        story.append(Paragraph(f"[PLANTA_{i:03d}]", plain_style))
        story.append(Spacer(1, 5))
        
        # Información de la planta
        story.append(Paragraph(f"NOMBRE_CIENTÍFICO: {plant.get('nombre_cientifico', 'N/A')}", plain_style))
        story.append(Paragraph(f"NOMBRE_COMÚN: {plant.get('nombre_comun', 'N/A')}", plain_style))
        story.append(Paragraph(f"FAMILIA: {plant.get('familia', 'N/A')}", plain_style))
        story.append(Paragraph(f"UBICACIÓN: {plant.get('lugar_colecta', 'N/A')}", plain_style))
        
        # Uso tradicional
        uso = plant.get('uso_tradicional', 'N/A')
        # Mantener el texto en líneas largas, el PDF se encargará del wrap automático
        story.append(Paragraph(f"USO_TRADICIONAL: {uso}", plain_style))
        
        # Advertencias si existen
        if plant.get('advertencias'):
            adv = plant['advertencias']
            story.append(Paragraph(f"ADVERTENCIAS: {adv}", plain_style))
        
        # Separador simple entre plantas
        if i < len(plants):  # No agregar separador después de la última planta
            story.append(Spacer(1, 10))
    
    # Construir PDF (sin encabezados ni pies de página automáticos)
    doc.build(story)
    print(f"✓ PDF con contenido esencial generado exitosamente: {output_pdf}")

def main():
    """
    Función principal.
    """
    
    # Rutas de archivos
    pdf_path = "C:/Users/Fytli/OneDrive/Escritorio/libros de plantas para mi tesis/1 libros a usarse/RECORTADO catalogo_floristico_plantas_medicinales-9-47.pdf"
    output_txt = "C:/Users/Fytli/OneDrive/Escritorio/libros de plantas para mi tesis/1 libros a usarse/plantas_completas_39.txt"
    output_json = "C:/Users/Fytli/OneDrive/Escritorio/libros de plantas para mi tesis/1 libros a usarse/plantas_completas_39.json"
    output_pdf = "C:/Users/Fytli/OneDrive/Escritorio/libros de plantas para mi tesis/1 libros a usarse/plantas_completas_39.pdf"
    
    try:
        # 1. Extraer plantas
        print("\n🔍 Extrayendo plantas del PDF...\n")
        plants = extract_plants_complete(pdf_path)
        
        # 2. Validar extracción
        validate_extraction(plants)
        
        # 3. Guardar resultados en JSON y TXT
        print("\n💾 Guardando resultados...")
        save_results(plants, output_txt, output_json)
        
        # 4. Guardar resultados en PDF (solo contenido esencial)
        save_to_pdf(plants, output_pdf)
        
        # 5. Mostrar muestra
        print(f"\n{'='*80}")
        print("MUESTRA DE PLANTAS EXTRAÍDAS")
        print(f"{'='*80}\n")
        
        for i, plant in enumerate(plants[:3], 1):
            print(f"{i}. {plant['nombre_cientifico']}")
            print(f"   Nombre común: {plant['nombre_comun']}")
            print(f"   Familia: {plant['familia']}")
            print(f"   Uso tradicional (primeras 100 chars): {plant['uso_tradicional'][:100]}...")
            print()
        
        if len(plants) > 3:
            print(f"... y {len(plants) - 3} plantas más\n")
        
        print("="*80)
        print("✓ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"✓ Archivos generados:")
        print(f"  - JSON: {output_json}")
        print(f"  - TXT:  {output_txt}")
        print(f"  - PDF:  {output_pdf} (solo contenido esencial)")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()