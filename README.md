# Movie Recommendation Agent Project (not updated)

This project provides a complete pipeline for movie recommendations: data processing, high-performance vector embedding generation, and a Google ADK-powered AI agent.

## 🏗 Project Structure
* **`Emb_Rerank/Embeddings/createVectorDB`**: Scripts for data cleaning, embedding generation, and database ingestion.
* **`movieRec`**: The main AI Agent configuration, including `docker-compose.yml` and the ADK logic.
* **`ProcessedData`**: Folder for source CSV files and processed datasets.

---

## 📋 Prerequisites
* **Windows** (WSL2 enabled) or **Linux/Mac**.
* **Podman** installed and running (`podman machine start`).
* **Python 3.12+**.
* **NVIDIA GPU** (Highly recommended for embedding generation).
* **Storage**: ~20GB free for raw data, vector indexes, and the database.

---

## 🚀 Step-by-Step Setup

### 1. Clone & Environment Setup
```powershell
git clone [https://github.com/Mona212004/movie-rec-agent.git](https://github.com/Mona212004/movie-rec-agent.git)
cd movie-rec-agent

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install sentence-transformers torch torchvision torchaudio google-adk google-generativeai psycopg2-binary python-dotenv
```

### 2. Launch the Database Container
Before running the Python scripts, the PostgreSQL container must be running to receive the data:
```powershell
cd movieRec
podman-compose up -d db
```

### 3. Generate Embeddings & Populate DB
Navigate to the embedding scripts to build your database from the raw data:
```powershell
cd ../Emb_Rerank/Embeddings/createVectorDB

# 1. Update paths in db_params.ini to match your local directory
# 2. Run the cleaning and preparation script
python main.py             

# 3. Generate vectors and index the data (This takes time, uses GPU if available)
python src/index_data.py
```

### 4. Run the AI Agent
Once the database is populated, launch the agent:
```powershell
cd ../../../movieRec
podman-compose up --build agent
```
The Agent will be accessible at http://localhost:8000.

---

## Important Configuration Notes
* **Database Config**: host=`localhost`, database=`imdb`, user=`postgres`, password=`postgrespw`.
* **Path Adjustments**: Update db_params.ini and .env files to match your local absolute paths (e.g., replace C:\Users\M\... with your actual path).
* **GPU Check**: Run `python -c "import torch; print(torch.cuda.is_available())"` to ensure your GPU is being used for vector generation.

---
