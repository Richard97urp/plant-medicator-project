import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

def prepare_chat_input(chat_data, user_data):
    """
    Prepara los datos del chat y usuario para el modelo
    """
    return {
        # Datos demográficos
        'zona': user_data.get('zona'),
        'edad': user_data.get('edad'),
        'peso': user_data.get('peso'),
        'talla': user_data.get('talla'),
        'genero': user_data.get('genero'),
        'ocupacion': user_data.get('ocupacion'),
        
        # Datos del chat
        'sintomas': chat_data.get('symptoms'),
        'tiempo_sintomas': chat_data.get('symptoms_duration'),
        'alergias': chat_data.get('allergies'),
        
        # Datos de feedback (iniciales)
        'efectividad': 0,
        'efectos_secundarios': 'ninguno',
        'comentarios': ''
    }