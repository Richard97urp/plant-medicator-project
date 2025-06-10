import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import psycopg2
from datetime import datetime
from tensorflow.keras.callbacks import EarlyStopping

class RecommenderModel:
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = None
        self.plant_encoder = LabelEncoder()
        self.symptom_vectorizer = TfidfVectorizer(max_features=50)
        self.model_trained = False
        self.scaler = StandardScaler()

    def get_data_from_db(self):
        query = """
        SELECT 
            pi.zone AS zona,
            pi.age AS edad,
            pi.weight AS peso,
            pi.height AS talla,
            pi.gender AS genero,
            pc.symptoms AS sintomas,
            pc.recommended_plant AS planta,
            tf.effectiveness_rating AS rating
        FROM personal_information pi
        JOIN patient_consultations pc ON pi.id::TEXT = pc.user_id
        LEFT JOIN treatment_feedback tf ON pc.id = tf.id
        WHERE pc.recommended_plant IS NOT NULL
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            data = pd.read_sql(query, conn)
            conn.close()
            print(f"Successfully retrieved {len(data)} records")
            return data
        except Exception as e:
            print(f"Error retrieving data from database: {str(e)}")
            raise

    def preprocess_data(self, data):
        # Entradas
        X = data[['edad', 'peso', 'talla', 'genero', 'zona', 'sintomas']].copy()
        X['genero'] = X['genero'].map({'Masculino': 0, 'Femenino': 1})
        X['zona'] = pd.factorize(X['zona'])[0]
        X['sintomas'] = X['sintomas'].fillna('')  # Manejo de datos faltantes

        # Normalizar características numéricas
        X[['edad', 'peso', 'talla']] = self.scaler.fit_transform(X[['edad', 'peso', 'talla']])

        # Vectorizar síntomas
        X_symptoms = self.symptom_vectorizer.fit_transform(X['sintomas']).toarray()
        X = np.hstack((X[['edad', 'peso', 'talla', 'genero', 'zona']].values, X_symptoms))

        # Solo salida de plantas
        y_planta = self.plant_encoder.fit_transform(data['planta'])

        return X, y_planta

    def build_model(self, input_dim, num_plants):
        inputs = tf.keras.Input(shape=(input_dim,))
        x = tf.keras.layers.Dense(256, activation='relu')(inputs)
        x = tf.keras.layers.Dropout(0.4)(x)
        x = tf.keras.layers.Dense(128, activation='relu')(x)
        x = tf.keras.layers.Dropout(0.3)(x)
        x = tf.keras.layers.Dense(64, activation='relu')(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        
        # Salida para plantas
        planta_output = tf.keras.layers.Dense(num_plants, activation='softmax')(x)

        self.model = tf.keras.Model(inputs=inputs, outputs=planta_output)
        optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
        self.model.compile(
            optimizer=optimizer,
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

    def train(self, epochs=50, batch_size=32):
        data = self.get_data_from_db()
        if len(data) == 0:
            print("No data available for training")
            return None, None
            
        X, y = self.preprocess_data(data)
        num_plants = len(self.plant_encoder.classes_)

        if self.model is None:
            self.build_model(X.shape[1], num_plants)

        early_stopping = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
        
        history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[early_stopping]
        )
        evaluation = self.model.evaluate(X, y, verbose=0)
        self.model_trained = True
        return history, evaluation

    def predict(self, patient_info):
        if not self.model_trained:
            print("Model not trained yet")
            return None
            
        # Preprocesar entrada
        gender_map = {'Masculino': 0, 'M': 0, 'Femenino': 1, 'F': 1}
        gender_value = gender_map.get(patient_info['gender'], 0)
        
        try:
            zone_factorized = pd.factorize([patient_info['zone']])[0][0]
        except:
            zone_factorized = 0
            
        # Normalizar características numéricas
        age = float(patient_info['age'])
        weight = float(patient_info.get('weight', 70))
        height = float(patient_info.get('height', 170))
        age, weight, height = self.scaler.transform([[age, weight, height]])[0]
        
        X = np.array([[age, weight, height, gender_value, zone_factorized]])
        
        try:
            # Asegurar que el vectorizador esté entrenado
            if not hasattr(self.symptom_vectorizer, 'vocabulary_'):
                data = self.get_data_from_db()
                _, _ = self.preprocess_data(data)
                
            symptom_vector = self.symptom_vectorizer.transform([patient_info['symptoms']]).toarray()
            X = np.hstack((X, symptom_vector))

            # Obtener predicciones solo para plantas
            predictions = self.model.predict(X)
            top_3_indices = np.argsort(predictions[0])[-3:][::-1]
            top_3_plants = self.plant_encoder.inverse_transform(top_3_indices)
            top_3_probs = predictions[0][top_3_indices]

            return {
                'top_3_plants': list(zip(top_3_plants, top_3_probs))
            }
        except Exception as e:
            print(f"Error in prediction: {str(e)}")
            return None

    def get_detailed_info(self, selected_plant):
        """Obtener información detallada de la planta seleccionada."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
            SELECT 
                pc.dosage AS dosis,
                pc.administration_frequency AS frecuencia_administracion,
                pc.comments AS comentarios
            FROM patient_consultations pc
            WHERE pc.recommended_plant = %s
            ORDER BY pc.created_at DESC
            LIMIT 1
            """
            
            cursor.execute(query, (selected_plant,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'planta': selected_plant,
                    'dosis': result[0] or 'No especificada',
                    'frecuencia_administracion': result[1] or 'No especificada',
                    'comentarios': result[2] or 'Sin comentarios'
                }
            
            return {
                'planta': selected_plant,
                'dosis': 'Información no disponible',
                'frecuencia_administracion': 'Información no disponible',
                'comentarios': 'Sin comentarios disponibles'
            }
        except Exception as e:
            print(f"Error getting plant details: {str(e)}")
            return {
                'planta': selected_plant,
                'dosis': 'Error al obtener información',
                'frecuencia_administracion': 'Error al obtener información',
                'comentarios': f'Error: {str(e)}'
            }

    def add_new_training_data(self, patient_data, recommended_plant, feedback_rating):
        """
        Añade nuevos datos de entrenamiento al modelo basado en feedback del usuario
        """
        if feedback_rating < 3:  # Si el feedback es menor a 3 (en escala de 1-5), no lo usamos para entrenamiento
            return False
            
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Verificar si el usuario existe
            cursor.execute("SELECT id FROM personal_information WHERE id = %s", (patient_data['user_id'],))
            user_exists = cursor.fetchone()
            
            if not user_exists:
                # Crear usuario si no existe
                cursor.execute("""
                INSERT INTO personal_information (id, age, weight, height, gender, zone)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    patient_data['user_id'],
                    patient_data['age'],
                    patient_data.get('weight', 70),
                    patient_data.get('height', 170),
                    patient_data['gender'],
                    patient_data['zone']
                ))
            
            # Añadir consulta con la planta recomendada que resultó efectiva
            cursor.execute("""
            INSERT INTO patient_consultations 
            (user_id, symptoms, symptoms_duration, allergies, recommended_plant, feedback_rating)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                patient_data['user_id'],
                patient_data['symptoms'],
                patient_data.get('duration', 'No especificada'),
                patient_data.get('allergies', 'Ninguna'),
                recommended_plant,
                feedback_rating
            ))
            
            conn.commit()
            conn.close()
            
            # Reentrenar el modelo con los nuevos datos
            self.train(epochs=5, batch_size=32)
            return True
            
        except Exception as e:
            print(f"Error adding new training data: {str(e)}")
            return False

    def save_training_metrics(self, metrics):
        # Guardar métricas de entrenamiento
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insertar en la tabla model_training_history
            cursor.execute("""
            INSERT INTO model_training_history (
                training_date, model_version, loss, plant_accuracy,
                drain_accuracy, freeworth_accuracy, training_parameters
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now(),  # training_date (fecha y hora actual)
                "1.0.0",         # model_version (puedes cambiarlo si es dinámico)
                metrics[0],      # loss (primer valor en la lista metrics)
                metrics[1],      # plant_accuracy (segundo valor en la lista metrics)
                0.0,             # drain_accuracy (valor por defecto, ajusta si es necesario)
                0.0,             # freeworth_accuracy (valor por defecto, ajusta si es necesario)
                '{"epochs": 50, "optimizer": "Adam", "batch_size": 32, "loss_function": "sparse_categorical_crossentropy"}'  # training_parameters (ajusta según tus necesidades)
            ))
            
            conn.commit()
            conn.close()
            print("Training metrics saved successfully in model_training_history.")
        except Exception as e:
            print(f"Error saving training metrics: {str(e)}")