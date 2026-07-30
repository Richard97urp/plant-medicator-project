import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import psycopg2
from datetime import datetime
from tensorflow.keras.callbacks import EarlyStopping
import pickle
import os

class RecommenderModel:
    def __init__(self, db_config, model_dir='./models'):
        self.db_config = db_config
        self.model = None
        self.plant_encoder = LabelEncoder()
        self.symptom_vectorizer = TfidfVectorizer(max_features=50)
        self.duration_encoder = LabelEncoder()
        self.intensity_encoder = LabelEncoder()
        self.model_trained = False
        self.scaler = StandardScaler()
        self.model_dir = model_dir
        
        os.makedirs(self.model_dir, exist_ok=True)
        self.load_model()

    def get_data_from_db(self):
        """Extrae datos de la tabla training_dataset con TODAS las variables"""
        query = """
        SELECT 
            age AS edad,
            weight AS peso,
            zone AS zona,
            gender AS genero,
            symptoms AS sintomas,
            symptoms_duration AS duracion_sintomas,
            symptoms_intensity AS intensidad_sintomas,
            environmental_cause AS causa_ambiental,
            emotional_cause AS causa_emocional,
            dietary_cause AS causa_dietetica,
            recommended_plant AS planta,
            effectiveness_rating AS rating
        FROM training_dataset
        WHERE recommended_plant IS NOT NULL 
        AND age IS NOT NULL
        AND gender IS NOT NULL
        """
        try:
            # ✅ CORREGIDO: Más logging y manejo de errores
            print(f"\n🔍 DEBUG get_data_from_db - db_config recibido:")
            print(f"   Tipo: {type(self.db_config)}")
            print(f"   Contenido: {self.db_config}")
            
            # Verificar si dbname tiene una URL completa
            if isinstance(self.db_config, dict) and 'dbname' in self.db_config:
                dbname_value = self.db_config['dbname']
                if isinstance(dbname_value, str) and '://' in dbname_value:
                    print(f"⚠️ WARNING: dbname contiene URL completa: {dbname_value}")
                    print("🔄 Intentando convertir URL a configuración de dict...")
                    
                    from urllib.parse import urlparse
                    parsed = urlparse(dbname_value)
                    
                    # Crear nueva configuración correcta
                    corrected_config = {
                        'host': parsed.hostname or 'localhost',
                        'port': parsed.port or '5432',
                        'user': parsed.username or 'postgres',
                        'password': parsed.password or 'Mascota3',
                        'dbname': parsed.path.lstrip('/') or 'databasePlantMedicator'
                    }
                    
                    print(f"✅ Configuración corregida: {corrected_config}")
                    conn = psycopg2.connect(**corrected_config)
                else:
                    conn = psycopg2.connect(**self.db_config)
            else:
                conn = psycopg2.connect(**self.db_config)
                
            data = pd.read_sql(query, conn)
            conn.close()
            print(f"✅ Successfully retrieved {len(data)} records from training_dataset")
            return data
        except Exception as e:
            print(f"❌ Error retrieving data from database: {str(e)}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            print(f"   DB Config: {self.db_config}")
            
            # ✅ INTENTAR CONEXIÓN ALTERNATIVA
            print("\n🔄 Intentando conexión alternativa...")
            try:
                # Configuración hardcodeada como fallback
                fallback_config = {
                    'host': 'localhost',
                    'port': '5432',
                    'user': 'postgres',
                    'password': 'Mascota3',
                    'dbname': 'databasePlantMedicator'
                }
                print(f"   Fallback config: {fallback_config}")
                conn = psycopg2.connect(**fallback_config)
                data = pd.read_sql(query, conn)
                conn.close()
                print(f"✅ ✅ CONEXIÓN EXITOSA CON FALLBACK: {len(data)} registros")
                return data
            except Exception as e2:
                print(f"❌❌ Fallback también falló: {e2}")
                raise

    def preprocess_data(self, data):
        """Preprocesa los datos con TODAS las nuevas variables - CAUSAS COMO TEXTO LIBRE"""
        X = data[[
            'edad', 'peso', 'zona', 'genero', 'sintomas',
            'duracion_sintomas', 'intensidad_sintomas',
            'causa_ambiental', 'causa_emocional', 'causa_dietetica'
        ]].copy()
        
        # 1. VARIABLES NUMÉRICAS BÁSICAS
        if X['peso'].isna().any():
            X['peso'] = X['peso'].fillna(X['peso'].median() if not X['peso'].isna().all() else 70)
        
        # 2. GÉNERO (binario)
        X['genero'] = X['genero'].map({
            'Masculino': 0, 'masculino': 0, 'M': 0, 'm': 0,
            'Femenino': 1, 'femenino': 1, 'F': 1, 'f': 1
        })
        X['genero'] = X['genero'].fillna(0)
        
        # 3. ZONA (categorical)
        X['zona'] = pd.factorize(X['zona'])[0]
        
        # 4. SÍNTOMAS (texto -> TF-IDF)
        X['sintomas'] = X['sintomas'].fillna('')
        
        # 5. DURACIÓN DE SÍNTOMAS (ordinal encoding)
        X['duracion_sintomas'] = X['duracion_sintomas'].fillna('No especificada')
        duration_mapping = {
            'Menos de 1 día': 1,
            '1-3 días': 2,
            '4-7 días': 3,
            '1-2 semanas': 4,
            '2-4 semanas': 5,
            'Más de 1 mes': 6,
            'No especificada': 0
        }
        X['duracion_sintomas'] = X['duracion_sintomas'].map(duration_mapping).fillna(0)
        
        # 6. INTENSIDAD DE SÍNTOMAS (ordinal encoding)
        X['intensidad_sintomas'] = X['intensidad_sintomas'].fillna('No especificada')
        intensity_mapping = {
            'Leve': 1,
            'Moderada': 2,
            'Severa': 3,
            'No especificada': 0
        }
        X['intensidad_sintomas'] = X['intensidad_sintomas'].map(intensity_mapping).fillna(0)
        
        # 7. CAUSAS (texto libre -> TF-IDF individual para cada causa) - CORREGIDO
        for col in ['causa_ambiental', 'causa_emocional', 'causa_dietetica']:
            X[col] = X[col].fillna('No especificada')
            # Mantener como texto para vectorización individual

        # 8. NORMALIZAR VARIABLES NUMÉRICAS
        numeric_features = ['edad', 'peso']
        X[numeric_features] = self.scaler.fit_transform(X[numeric_features])

        # 9. VECTORIZAR SÍNTOMAS
        X_symptoms = self.symptom_vectorizer.fit_transform(X['sintomas']).toarray()
        
        # 10. VECTORIZAR CAUSAS TEXTUALES INDIVIDUALMENTE - CORREGIDO: stop_words=None
        self.causa_ambiental_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
        self.causa_emocional_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
        self.causa_dietetica_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
        
        X_causa_ambiental = self.causa_ambiental_vectorizer.fit_transform(X['causa_ambiental']).toarray()
        X_causa_emocional = self.causa_emocional_vectorizer.fit_transform(X['causa_emocional']).toarray()
        X_causa_dietetica = self.causa_dietetica_vectorizer.fit_transform(X['causa_dietetica']).toarray()
        
        # 11. COMBINAR TODAS LAS CARACTERÍSTICAS - CORREGIDO
        feature_columns = [
            'edad', 'peso', 'genero', 'zona',
            'duracion_sintomas', 'intensidad_sintomas'
        ]
        X_final = np.hstack((
            X[feature_columns].values, 
            X_symptoms,
            X_causa_ambiental,
            X_causa_emocional, 
            X_causa_dietetica
        ))

        # SALIDA: Planta recomendada
        y_planta = self.plant_encoder.fit_transform(data['planta'])

        print(f"✅ Features procesadas: {X_final.shape}")
        print(f"   - Variables categóricas/numéricas: {len(feature_columns)}")
        print(f"   - Síntomas vectorizados (TF-IDF): {X_symptoms.shape[1]}")
        print(f"   - Causa ambiental vectorizada: {X_causa_ambiental.shape[1]}")
        print(f"   - Causa emocional vectorizada: {X_causa_emocional.shape[1]}")
        print(f"   - Causa dietética vectorizada: {X_causa_dietetica.shape[1]}")
        print(f"   - Total features: {X_final.shape[1]}")

        return X_final, y_planta

    def build_model(self, input_dim, num_plants):
        """Red neuronal con arquitectura ajustada para más features"""
        inputs = tf.keras.Input(shape=(input_dim,))
        x = tf.keras.layers.Dense(512, activation='relu')(inputs)
        x = tf.keras.layers.Dropout(0.4)(x)
        x = tf.keras.layers.Dense(256, activation='relu')(x)
        x = tf.keras.layers.Dropout(0.3)(x)
        x = tf.keras.layers.Dense(128, activation='relu')(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        x = tf.keras.layers.Dense(64, activation='relu')(x)
        
        planta_output = tf.keras.layers.Dense(num_plants, activation='softmax')(x)

        self.model = tf.keras.Model(inputs=inputs, outputs=planta_output)
        optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
        self.model.compile(
            optimizer=optimizer,
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

    def train(self, epochs=50, batch_size=32):
        """Entrena el modelo con datos de training_dataset"""
        data = self.get_data_from_db()
        if len(data) == 0:
            print("⚠️ No data available for training")
            return None, None
            
        X, y = self.preprocess_data(data)
        num_plants = len(self.plant_encoder.classes_)

        if self.model is None:
            self.build_model(X.shape[1], num_plants)

        early_stopping = EarlyStopping(
            monitor='val_loss', 
            patience=5, 
            restore_best_weights=True
        )
        
        print(f"🚀 Training model with {len(data)} samples...")
        print(f"   Features shape: {X.shape}")
        print(f"   Number of unique plants: {num_plants}")
        
        history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=1
        )
        
        evaluation = self.model.evaluate(X, y, verbose=0)
        self.model_trained = True
        
        print(f"✅ Training completed - Loss: {evaluation[0]:.4f}, Accuracy: {evaluation[1]:.4f}")
        
        self.save_model()
        
        return history, evaluation

    def save_model(self):
        """Guarda el modelo y TODOS los encoders - ACTUALIZADO"""
        try:
            model_path = os.path.join(self.model_dir, 'model.keras')
            self.model.save(model_path)
            print(f"✅ Modelo guardado en: {model_path}")
            
            with open(os.path.join(self.model_dir, 'plant_encoder.pkl'), 'wb') as f:
                pickle.dump(self.plant_encoder, f)
            
            with open(os.path.join(self.model_dir, 'symptom_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.symptom_vectorizer, f)
            
            # Guardar los 3 vectorizers de causas - NUEVO
            with open(os.path.join(self.model_dir, 'causa_ambiental_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.causa_ambiental_vectorizer, f)
            
            with open(os.path.join(self.model_dir, 'causa_emocional_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.causa_emocional_vectorizer, f)
            
            with open(os.path.join(self.model_dir, 'causa_dietetica_vectorizer.pkl'), 'wb') as f:
                pickle.dump(self.causa_dietetica_vectorizer, f)
            
            with open(os.path.join(self.model_dir, 'scaler.pkl'), 'wb') as f:
                pickle.dump(self.scaler, f)
            
            metadata = {
                'model_trained': self.model_trained,
                'num_plants': len(self.plant_encoder.classes_),
                'plants': list(self.plant_encoder.classes_),
                'last_training': datetime.now().isoformat(),
                'features': [
                    'edad', 'peso', 'genero', 'zona',
                    'duracion_sintomas', 'intensidad_sintomas',
                    'sintomas_vectorizados', 
                    'causa_ambiental_vectorizada', 'causa_emocional_vectorizada', 'causa_dietetica_vectorizada'
                ]
            }
            with open(os.path.join(self.model_dir, 'metadata.pkl'), 'wb') as f:
                pickle.dump(metadata, f)
            
            print("✅ Todos los componentes guardados exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error guardando modelo: {str(e)}")
            return False

    def load_model(self):
        """Carga el modelo y componentes desde disco - ACTUALIZADO"""
        try:
            model_path = os.path.join(self.model_dir, 'model.keras')
            
            if not os.path.exists(model_path):
                print("⚠️ No se encontró modelo guardado. Se entrenará uno nuevo.")
                return False
            
            self.model = tf.keras.models.load_model(model_path)
            print(f"✅ Modelo cargado desde: {model_path}")
            
            with open(os.path.join(self.model_dir, 'plant_encoder.pkl'), 'rb') as f:
                self.plant_encoder = pickle.load(f)
            
            with open(os.path.join(self.model_dir, 'symptom_vectorizer.pkl'), 'rb') as f:
                self.symptom_vectorizer = pickle.load(f)
            
            # Cargar los 3 vectorizers de causas - NUEVO
            try:
                with open(os.path.join(self.model_dir, 'causa_ambiental_vectorizer.pkl'), 'rb') as f:
                    self.causa_ambiental_vectorizer = pickle.load(f)
                
                with open(os.path.join(self.model_dir, 'causa_emocional_vectorizer.pkl'), 'rb') as f:
                    self.causa_emocional_vectorizer = pickle.load(f)
                
                with open(os.path.join(self.model_dir, 'causa_dietetica_vectorizer.pkl'), 'rb') as f:
                    self.causa_dietetica_vectorizer = pickle.load(f)
            except FileNotFoundError as e:
                print(f"⚠️ Vectorizers de causas no encontrados: {e}")
                print("   Se entrenarán nuevos vectorizers en el próximo entrenamiento")
                # Inicializar nuevos vectorizers
                self.causa_ambiental_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
                self.causa_emocional_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
                self.causa_dietetica_vectorizer = TfidfVectorizer(max_features=15, stop_words=None)
            
            with open(os.path.join(self.model_dir, 'scaler.pkl'), 'rb') as f:
                self.scaler = pickle.load(f)
            
            with open(os.path.join(self.model_dir, 'metadata.pkl'), 'rb') as f:
                metadata = pickle.load(f)
                self.model_trained = metadata['model_trained']
            
            print(f"✅ Modelo cargado exitosamente. Plantas conocidas: {len(self.plant_encoder.classes_)}")
            print(f"   Última actualización: {metadata.get('last_training', 'Desconocida')}")
            return True
            
        except Exception as e:
            print(f"⚠️ Error cargando modelo: {str(e)}")
            print("   Se entrenará un nuevo modelo.")
            return False

    def predict(self, patient_info):
        """Realiza predicción con TODAS las variables - CAUSAS COMO TEXTO LIBRE"""
        if not self.model_trained:
            print("❌ Model not trained yet")
            return None
            
        # 1. GÉNERO
        gender_map = {
            'Masculino': 0, 'masculino': 0, 'M': 0, 'm': 0,
            'Femenino': 1, 'femenino': 1, 'F': 1, 'f': 1
        }
        gender_value = gender_map.get(patient_info.get('gender', 'Masculino'), 0)
        
        # 2. ZONA
        try:
            zone_factorized = pd.factorize([patient_info.get('zone', 'Lima')])[0][0]
        except:
            zone_factorized = 0
        
        # 3. EDAD Y PESO (normalizados)
        age = float(patient_info.get('age', 30))
        weight = float(patient_info.get('weight', 70))
        age, weight = self.scaler.transform([[age, weight]])[0]
        
        # 4. DURACIÓN DE SÍNTOMAS
        duration_mapping = {
            'Menos de 1 día': 1, '1-3 días': 2, '4-7 días': 3,
            '1-2 semanas': 4, '2-4 semanas': 5, 'Más de 1 mes': 6
        }
        duration_value = duration_mapping.get(patient_info.get('duration', 'No especificada'), 0)
        
        # 5. INTENSIDAD DE SÍNTOMAS
        intensity_mapping = {'Leve': 1, 'Moderada': 2, 'Severa': 3}
        intensity_value = intensity_mapping.get(patient_info.get('intensity', 'Moderada'), 2)
        
        # 6. CONSTRUIR VECTOR BASE (6 features)
        X = np.array([[
            age, weight, gender_value, zone_factorized,
            duration_value, intensity_value
        ]])
        
        try:
            # 7. VECTORIZAR SÍNTOMAS
            symptoms_text = patient_info.get('symptoms', '')
            symptom_vector = self.symptom_vectorizer.transform([symptoms_text]).toarray()
            
            symptom_sum = symptom_vector.sum()
            if symptom_sum == 0:
                print(f"⚠️ WARNING: Síntoma '{symptoms_text}' NO está en el vocabulario")
            
            # 8. VECTORIZAR CAUSAS TEXTUALES INDIVIDUALMENTE - CORREGIDO
            causa_ambiental_text = str(patient_info.get('causa_ambiental', ''))
            causa_emocional_text = str(patient_info.get('causa_emocional', ''))
            causa_dietetica_text = str(patient_info.get('causa_dietetica', ''))
            
            print(f"🔍 Texto de causas:")
            print(f"   - Ambiental: '{causa_ambiental_text}'")
            print(f"   - Emocional: '{causa_emocional_text}'") 
            print(f"   - Dietética: '{causa_dietetica_text}'")
            
            # Vectorizar cada causa por separado
            causa_ambiental_vector = self.causa_ambiental_vectorizer.transform([causa_ambiental_text]).toarray()
            causa_emocional_vector = self.causa_emocional_vectorizer.transform([causa_emocional_text]).toarray()
            causa_dietetica_vector = self.causa_dietetica_vectorizer.transform([causa_dietetica_text]).toarray()
            
            # 9. COMBINAR TODAS LAS CARACTERÍSTICAS - CORREGIDO
            X = np.hstack((
                X, 
                symptom_vector,
                causa_ambiental_vector,
                causa_emocional_vector,
                causa_dietetica_vector
            ))
            
            print(f"🔍 DEBUG - Feature vector shape: {X.shape}")
            print(f"   Base features (6): edad, peso, genero, zona, duracion, intensidad")
            print(f"   Symptom features ({symptom_vector.shape[1]}): TF-IDF vectorizado")
            print(f"   Causa ambiental features ({causa_ambiental_vector.shape[1]}): TF-IDF vectorizado")
            print(f"   Causa emocional features ({causa_emocional_vector.shape[1]}): TF-IDF vectorizado")
            print(f"   Causa dietética features ({causa_dietetica_vector.shape[1]}): TF-IDF vectorizado")

            # 10. PREDICCIÓN
            predictions = self.model.predict(X, verbose=0)
            top_3_indices = np.argsort(predictions[0])[-3:][::-1]
            top_3_plants = self.plant_encoder.inverse_transform(top_3_indices)
            top_3_probs = predictions[0][top_3_indices]

            return {
                'top_3_plants': list(zip(top_3_plants, top_3_probs)),
                'confidence': float(top_3_probs[0])
            }
        except Exception as e:
            print(f"❌ Error in prediction: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def get_detailed_info(self, selected_plant):
        """Obtener información detallada de la planta"""
        plant_details = {
            "muña": {
                "dosis": "1 taza de infusión (1 cucharadita por taza)",
                "frecuencia": "2-3 veces al día después de las comidas",
                "comentarios": "Excelente para problemas digestivos y respiratorios"
            },
            "manzanilla": {
                "dosis": "1 taza de infusión (1 cucharadita por taza)",
                "frecuencia": "2-3 veces al día",
                "comentarios": "Ideal para problemas digestivos y relajación"
            },
            "hierba luisa": {
                "dosis": "1 taza de infusión (3-4 hojas por taza)",
                "frecuencia": "2-3 veces al día después de las comidas",
                "comentarios": "Excelente para digestiones pesadas y relajación"
            },
            "salvia": {
                "dosis": "1 taza de infusión (3-4 hojas por taza)",
                "frecuencia": "1-2 veces al día",
                "comentarios": "Para problemas respiratorios y circulatorios"
            },
            "eucalipto": {
                "dosis": "Inhalaciones o infusión (2-3 hojas por taza)",
                "frecuencia": "2-3 veces al día",
                "comentarios": "Ideal para problemas respiratorios y congestión"
            },
            "llantén": {
                "dosis": "Infusión (3-4 hojas por taza) o cataplasma",
                "frecuencia": "2-3 veces al día",
                "comentarios": "Para problemas respiratorios y de piel"
            },
            "uña de gato": {
                "dosis": "Infusión (1 cucharadita de corteza por taza)",
                "frecuencia": "1-2 veces al día",
                "comentarios": "Potente antiinflamatorio y para el sistema inmune"
            }
        }
        
        plant_info = plant_details.get(selected_plant.lower(), {
            "dosis": "1-2 tazas de infusión al día",
            "frecuencia": "2-3 veces al día después de las comidas",
            "comentarios": "Consultar con especialista para dosis personalizada"
        })
        
        return {
            'planta': selected_plant,
            'dosis': plant_info["dosis"],
            'frecuencia_administracion': plant_info["frecuencia"],
            'comentarios': plant_info["comentarios"]
        }

    def add_new_training_data(self, patient_data, recommended_plant, feedback_rating):
        """Añade nuevos datos de entrenamiento CON TODAS LAS VARIABLES"""
        if feedback_rating < 3:
            return False
            
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
            INSERT INTO training_dataset (
                age, weight, zone, gender, symptoms, 
                symptoms_duration, symptoms_intensity,
                environmental_cause, emotional_cause, dietary_cause,
                recommended_plant, effectiveness_rating, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                patient_data.get('age', 30),
                patient_data.get('weight', 70),
                patient_data.get('zone', 'Lima'),
                patient_data.get('gender', 'Masculino'),
                patient_data.get('symptoms', ''),
                patient_data.get('duration', 'No especificada'),
                patient_data.get('intensity', 'Moderada'),
                patient_data.get('environmental_cause', 'None'),
                patient_data.get('emotional_cause', 'None'),
                patient_data.get('dietary_cause', 'None'),
                recommended_plant,
                str(feedback_rating),
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Nuevo registro agregado a training_dataset")
            print("🔄 Reentrenando modelo con nuevo feedback...")
            self.train(epochs=5, batch_size=32)
            return True
            
        except Exception as e:
            print(f"❌ Error adding new training data: {str(e)}")
            return False

    def save_training_metrics(self, metrics):
        """Guarda métricas del entrenamiento"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
            INSERT INTO model_training_history (
                training_date, model_version, loss, plant_accuracy,
                drain_accuracy, freeworth_accuracy, training_parameters
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now(),
                "3.0.0",  # Nueva versión con más features
                float(metrics[0]),
                float(metrics[1]),
                0.0,
                0.0,
                '{"epochs": 50, "optimizer": "Adam", "batch_size": 32, "features": 10}'
            ))
            
            conn.commit()
            conn.close()
            print("✅ Training metrics saved successfully")
        except Exception as e:
            print(f"❌ Error saving training metrics: {str(e)}")