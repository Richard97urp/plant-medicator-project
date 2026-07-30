import pandas as pd
from sqlalchemy import create_engine

# === CONFIGURACIÓN DE CONEXIÓN A POSTGRESQL ===
# Ajusta los valores a tu entorno
DB_USER = "postgres"
DB_PASSWORD = "Mascota3"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "databasePlantMedicator"

# Crea el motor de conexión
engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# === LECTURA DEL ARCHIVO EXCEL ===
excel_path = r"C:\Users\Fytli\OneDrive\Escritorio\chz_dataset.xlsx"  # Ruta completa a tu archivo
df = pd.read_excel(excel_path)

# === OPCIONAL: Mostrar las primeras filas para verificar ===
print("Primeras filas del Excel:")
print(df.head())

# === RENOMBRAR LAS COLUMNAS PARA COINCIDIR CON LA TABLA SQL ===
df.columns = [
    "gender",
    "age",
    "weight",
    "education_level",
    "city",
    "zone",
    "symptoms",
    "symptoms_intensity",
    "symptoms_duration",
    "environmental_cause",
    "emotional_cause",
    "dietary_cause",
    "recommended_plant",
    "plant_part",
    "plant_property",
    "preparation_method",
    "administration_route",
    "dosage",
    "administration_frequency",
    "improvement_time",
    "therapeutic_response",
    "contraindications",
    "effectiveness_rating"
]

# === INSERTAR LOS DATOS EN LA TABLA POSTGRESQL ===
df.to_sql('training_dataset', engine, if_exists='append', index=False)

print("✅ Datos insertados correctamente en la tabla training_dataset.")
