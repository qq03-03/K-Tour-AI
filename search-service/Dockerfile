FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

# Pre-download CLIP model weights into the image's HF cache at build time,
# before HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE are set below. The runtime
# loads this model eagerly at startup (lifespan warmup) with offline mode
# on, so the weights must already be present in the image filesystem.
RUN python -c "from transformers import CLIPModel, CLIPProcessor; CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

COPY src ./src
COPY app ./app
COPY data ./data

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# BLAS backends (OpenMP/MKL) read these at process start, before
# torch.set_num_threads() runs -- set them too so CPU thread count stays
# capped from the very first inference call, not just after ClipRuntime
# has constructed once. See src/clip_backend.py's ClipRuntime.__init__.
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

EXPOSE 8000

# Railway (and most PaaS platforms) inject the bind port via $PORT at
# container runtime; exec-form CMD does not expand shell variables, so
# use sh -c with a local-dev fallback of 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
