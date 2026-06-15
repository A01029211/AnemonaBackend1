# Anemona - Backend

API del sistema Anemona, desarrollada con FastAPI.  
Se encarga de manejar la lógica del sistema, conexión con base de datos, autenticación, proyectos, sesiones, widgets y comunicación con el agente de inteligencia artificial.

## Tecnologías utilizadas

- Python
- FastAPI
- PostgreSQL
- Firebase
- Vertex AI
- Google Cloud Platform
- Docker
- GitHub Actions

## Instalación

Crear y activar entorno virtual:

```bash
python -m venv venv
source venv/bin/activate
```

## Descargar dependencias 

pip install -r requirements.txt

## Ejecución local

uvicorn main:app --reload

El servidor se ejecuta en:

http://127.0.0.1:8000

## Estructura del proyecto
main.py                 # Punto de entrada de la API
routes/                 # Endpoints principales del sistema
models/                 # Modelos y estructuras de datos
utils/                  # Funciones auxiliares
credentials/            # Credenciales de servicios externos
tests/                  # Pruebas del sistema
database.py             # Configuración de base de datos
requirements.txt        # Dependencias del proyecto
Dockerfile              # Configuración para contenedor
cloudbuild.yml          # Configuración de despliegue en GCP

## Funcionalidades principales

Gestión de usuarios y autenticación
Creación y administración de proyectos
Manejo de sesiones colaborativas
Consulta y modificación de widgets
Conexión con base de datos
Comunicación con agente de IA
Exportación y manejo de documentación
Deployment

El back-end se encuentra desplegado en Google Cloud Platform.
El servicio está contenerizado con Docker y se despliega mediante Cloud Build.

## Liga del back-end desplegado:

https://api-anemona-63736850775.northamerica-northeast1.run.app
Repositorios relacionados

Front-end: https://github.com/darioPM2002/Anemona
Back-end: https://github.com/A01029211/AnemonaBackend1
Agente: https://github.com/darioPM2002/agente_anemona

## Autores

Darío Cuauhtémoc Peña Mariano A01785420
Mariel González Grunspan A01198887
Santiago Córdova Molina A01029211
Angela Lizeth Aguirre Zúñiga A01286354
Ariana Isabela Espinoza López A01645270

Proyecto desarrollado por el equipo TechNova para la materia Planeación de Sistemas de Software.