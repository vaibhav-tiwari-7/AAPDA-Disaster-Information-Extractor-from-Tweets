# Use a full Python image so scientific libraries build and run reliably
FROM python:3.11

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Install Python dependencies
# (root requirements.txt already includes everything needed:
#  streamlit, pandas, scikit-learn, numpy, altair, google-cloud-*)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Default Streamlit port
EXPOSE 8501

# Run the local dashboard by default
CMD ["streamlit", "run", "local_dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]