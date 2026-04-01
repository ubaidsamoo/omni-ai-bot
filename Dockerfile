FROM python:3.11-slim

WORKDIR /app

# System dependencies for FAISS, OpenCV, PyPDF etc if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the whole project
COPY . .

# Install requirements
RUN pip install --no-cache-dir -r backend/requirements.txt

# Create .env dynamically if you want (but better to use HF Secrets)
# Hugging Face Spaces will pass GOOGLE_API_KEY from Settings > Secrets

# Expose Streamlit's port (Hugging Face expects 7860)
EXPOSE 7860

# Command to run BOTH FastAPI and Streamlit in the same container
# 1. FastAPI port 8000 (background)
# 2. Streamlit port 7860 (foreground)
CMD bash -c "cd backend && uvicorn main:app --host 127.0.0.1 --port 8000 & sleep 3 && streamlit run frontend/app.py --server.port 7860 --server.address 0.0.0.0"
