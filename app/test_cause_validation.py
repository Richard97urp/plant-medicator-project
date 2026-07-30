"""
Script de diagnóstico para validar la extracción de causas
Ejecutar: python test_cause_validation.py
"""

import sys
import re

def validate_cause_response(message: str, cause_type: str):
    """Versión simplificada de _validate_cause_response para testing"""
    message_lower = message.lower().strip()
    
    # Respuestas EXPLÍCITAS negativas
    negative_patterns = [
        r'^\bno\b$', r'^\bno nada\b$', r'^\bnada\b$'
    ]
    
    for pattern in negative_patterns:
        if re.search(pattern, message_lower):
            return True, ""  # Causa explícita pero vacía
    
    # Palabras clave que indican causa
    cause_keywords = {
        'ambiental': ['frío', 'frio', 'calor', 'mojado', 'polo', 'dormí', 'dormi'],
        'emocional': ['estrés', 'estres', 'ansiedad', 'nervios'],
        'dietética': ['comida', 'comí', 'comi', 'picante']
    }
    
    keywords = cause_keywords.get(cause_type, [])
    has_keywords = any(keyword in message_lower for keyword in keywords)
    words_count = len(message_lower.split())
    
    if has_keywords and words_count >= 2:
        # Extraer texto
        cause_text = extract_cause_text(message, cause_type)
        return True, cause_text
    
    return False, None

def extract_cause_text(message: str, cause_type: str) -> str:
    """Extrae el texto descriptivo de la causa"""
    message_lower = message.lower().strip()
    
    # Si el mensaje es descriptivo, usar completo
    words = message_lower.split()
    if len(words) >= 4 and len(message_lower) < 100:
        cleaned = message_lower
        for prefix in ['sí,', 'si,', 'sí', 'si', 'claro,']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned[:80]
    
    return "exposición ambiental" if cause_type == 'ambiental' else "causa detectada"

# ========================================
# PRUEBAS
# ========================================

test_cases = [
    ("me dormí con el polo mojado", "ambiental"),
    ("sí, por el frío", "ambiental"),
    ("no", "ambiental"),
    ("estaba estresado por el examen", "emocional"),
    ("comí picante ayer", "dietética"),
]

print("="*80)
print("🧪 PRUEBAS DE VALIDACIÓN DE CAUSAS")
print("="*80)

for message, cause_type in test_cases:
    print(f"\n📝 Mensaje: '{message}'")
    print(f"🎯 Tipo de causa: {cause_type}")
    
    is_valid, cause_text = validate_cause_response(message, cause_type)
    
    print(f"✅ Es válido: {is_valid}")
    print(f"📄 Texto extraído: '{cause_text}'")
    print(f"🔍 Tipo de dato: {type(cause_text)}")
    
    # Simular lo que hace extracted_info
    extracted_info = {}
    if is_valid and cause_text is not None:
        key = f"{cause_type}_cause"
        extracted_info[key] = str(cause_text)
        print(f"💾 Se guardaría: {key} = '{extracted_info[key]}'")
    
    print("-" * 80)

print("\n" + "="*80)
print("✅ DIAGNÓSTICO COMPLETO")
print("="*80)