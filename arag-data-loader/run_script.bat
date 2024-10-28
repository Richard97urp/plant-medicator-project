@echo off
REM Activar el entorno virtual
call C:\Users\Fytli\OneDrive\Escritorio\plant_medicator_venv\Scripts\activate.bat

    
REM Ejecutar el script Python
python C:\Users\Fytli\OneDrive\Escritorio\plant_medicator_venv\plant-medicator\arag-data-loader\rag_load_and_process.py
        
REM Desactivar el entorno virtual (opcional)
deactivate
