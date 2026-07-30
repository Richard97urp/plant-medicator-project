import psycopg2

try:
    connection = psycopg2.connect(
        host="localhost",
        user="postgres",
        password="Mascota3",
        dbname="databasePlantMedicator"
    )
    connection.autocommit = True
    cursor = connection.cursor()

    # Agregar la columna para la ruta de la foto de perfil
    ADD_PROFILE_PICTURE_COLUMN = """
    ALTER TABLE personal_information 
    ADD COLUMN profile_picture_path VARCHAR(255);
    """
    
    cursor.execute(ADD_PROFILE_PICTURE_COLUMN)
    print("✅ Columna 'profile_picture_path' agregada exitosamente")
    
    # (Opcional) Agregar un índice para búsquedas rápidas
    ADD_INDEX = """
    CREATE INDEX idx_profile_picture_path 
    ON personal_information (profile_picture_path) 
    WHERE profile_picture_path IS NOT NULL;
    """
    
    cursor.execute(ADD_INDEX)
    print("✅ Índice creado para 'profile_picture_path'")

except psycopg2.Error as e:
    print(f"❌ Error de base de datos: {e}")

finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'connection' in locals() and connection:
        connection.close()
    print("✅ Conexión a la base de datos cerrada")