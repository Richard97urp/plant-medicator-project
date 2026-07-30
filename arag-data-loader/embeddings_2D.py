import psycopg2
import numpy as np
import ast
import plotly.express as px
from sklearn.manifold import TSNE

# 1. Configuración de la conexión
try:
    conn = psycopg2.connect(
        dbname="databasePlantMedicator",
        user="postgres",
        password="Mascota3",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    # 2. Consulta: Traemos el texto (document) para poder identificar los puntos
    print("Extrayendo datos de la base de datos...")
    cursor.execute("""
        SELECT document, embedding FROM public.langchain_pg_embedding LIMIT 200
    """)
    rows = cursor.fetchall()

    if not rows:
        print("No se encontraron datos en la tabla.")
    else:
        documents = [row[0] for row in rows]
        # Convertimos el string del embedding a una lista de floats de numpy
        embeddings = np.array([ast.literal_eval(row[1]) for row in rows])

        print(f"Procesando {len(embeddings)} embeddings...")

        # 3. Reducción de dimensionalidad con t-SNE
        # t-SNE es superior a PCA para visualizar "clusters" o grupos semánticos
        tsne = TSNE(
            n_components=2, 
            perplexity=min(30, len(embeddings) - 1), 
            random_state=42, 
            init='pca', 
            learning_rate='auto'
        )
        reduced = tsne.fit_transform(embeddings)

        # 4. Creación del gráfico interactivo
        fig = px.scatter(
            x=reduced[:, 0], 
            y=reduced[:, 1],
            hover_name=[doc[:100] + "..." for doc in documents], # Muestra los primeros 100 caracteres al pasar el mouse
            title="Mapa Semántico de Plant Medicator (t-SNE)",
            labels={'x': 'Dimensión t-SNE 1', 'y': 'Dimensión t-SNE 2'},
            template="plotly_white",
            color_discrete_sequence=['#2ecc71'] # Un verde acorde al proyecto botánico
        )

        fig.update_traces(marker=dict(size=12, opacity=0.7, line=dict(width=1, color='DarkSlateGrey')))
        
        print("Abriendo visualización en el navegador...")
        fig.show()

except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        cursor.close()
        conn.close()