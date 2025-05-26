# 🚀 Whisper Large V3 Cloud Deployment Guide

This guide shows you how to deploy the Whisper Large V3 model to the cloud so you don't have to run it locally on your laptop.

## 🎯 **Option 1: Hugging Face Inference Endpoints (Recommended)**

**Cost: $0.50-$1.00/hour** | **Setup Time: 5 minutes** | **Best Performance**

### Step 1: Create Hugging Face Account
1. Go to [huggingface.co](https://huggingface.co) and sign up
2. Add a payment method in [billing settings](https://huggingface.co/settings/billing)

### Step 2: Get API Token
1. Go to [Settings > Access Tokens](https://huggingface.co/settings/tokens)
2. Click "New token" → Name it "Whisper-Bot" → Select "Write" permissions
3. Copy the token (starts with `hf_...`)

### Step 3: Deploy Whisper Large V3
1. Go to [Inference Endpoints](https://ui.endpoints.huggingface.co/)
2. Click "Create new endpoint"
3. **Configuration:**
   - **Model Repository:** `openai/whisper-large-v3`
   - **Task:** `Automatic Speech Recognition`
   - **Cloud Provider:** `AWS` (recommended)
   - **Region:** `us-east-1` (fastest)
   - **Instance Type:** Choose based on your needs:
     - **NVIDIA T4 (1 GPU)**: $0.50/hour - Good for moderate usage
     - **NVIDIA L4 (1 GPU)**: $0.80/hour - Better performance
     - **NVIDIA A10G (1 GPU)**: $1.00/hour - Best performance
   - **Min Replicas:** `1`
   - **Max Replicas:** `1` (or higher for scaling)

4. Click "Create Endpoint"
5. Wait 2-3 minutes for deployment
6. Copy the endpoint URL (looks like: `https://xyz123.us-east-1.aws.endpoints.huggingface.cloud`)

### Step 4: Update Your Bot Configuration
1. Open your `.env` file
2. Add these lines:
```bash
# Hugging Face Configuration
HF_API_TOKEN=hf_your_token_here
HF_ENDPOINT_URL=https://your-endpoint-url.endpoints.huggingface.cloud
```

### Step 5: Update Your Code
The bot is already configured to use Hugging Face! Just run:
```bash
python main.py
```

**Monthly Cost Estimate:**
- Light usage (2 hours/day): ~$30/month
- Moderate usage (6 hours/day): ~$90/month  
- Heavy usage (12 hours/day): ~$180/month

---

## 🎯 **Option 2: Hugging Face Spaces (Budget Option)**

**Cost: $0.40-$0.60/hour** | **Setup Time: 10 minutes** | **Good Performance**

### Step 1: Create a Space
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. **Configuration:**
   - **Space name:** `whisper-api`
   - **License:** `MIT`
   - **Space SDK:** `Gradio`
   - **Hardware:** `T4 small` ($0.40/hour)

### Step 2: Create the Space Code
Create `app.py` in your Space:

```python
import gradio as gr
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import numpy as np

# Load Whisper Large V3
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3"
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device,
)

def transcribe_audio(audio_file):
    """Transcribe audio file"""
    if audio_file is None:
        return "No audio provided"
    
    # Process audio
    result = pipe(audio_file)
    return result["text"]

# Create Gradio interface
iface = gr.Interface(
    fn=transcribe_audio,
    inputs=gr.Audio(type="filepath"),
    outputs="text",
    title="Whisper Large V3 API",
    description="Upload audio to transcribe with Whisper Large V3"
)

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0", server_port=7860)
```

### Step 3: Create requirements.txt
```
torch
transformers
accelerate
gradio
```

### Step 4: Deploy and Get URL
1. Push your code to the Space
2. Wait for deployment (5-10 minutes)
3. Your API will be available at: `https://your-username-whisper-api.hf.space`

### Step 5: Update Your Bot
Modify `voice_recognition_hf.py` to use your Space URL:
```python
# Replace the endpoint URL
self.hf_endpoint_url = "https://your-username-whisper-api.hf.space/api/predict"
```

---

## 🎯 **Option 3: RunPod (GPU Cloud)**

**Cost: $0.34-$0.89/hour** | **Setup Time: 15 minutes** | **Most Flexible**

### Step 1: Create RunPod Account
1. Go to [runpod.io](https://runpod.io) and sign up
2. Add credits to your account ($10 minimum)

### Step 2: Deploy a Pod
1. Go to "Pods" → "Deploy"
2. **Template:** `RunPod PyTorch`
3. **GPU:** Choose based on budget:
   - **RTX 4090**: $0.34/hour
   - **RTX A6000**: $0.79/hour  
   - **A100 40GB**: $0.89/hour
4. **Container Disk:** 50GB
5. **Volume:** 20GB (optional)

### Step 3: Setup Whisper Large V3 API
SSH into your pod and run:

```bash
# Install dependencies
pip install torch transformers accelerate flask

# Create API server
cat > whisper_api.py << 'EOF'
from flask import Flask, request, jsonify
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import io
import soundfile as sf

app = Flask(__name__)

# Load model
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3"
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)
pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device,
)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    
    # Read audio
    audio_data, sample_rate = sf.read(io.BytesIO(audio_file.read()))
    
    # Transcribe
    result = pipe({"array": audio_data, "sampling_rate": sample_rate})
    
    return jsonify({'text': result['text']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF

# Start the API
python whisper_api.py
```

### Step 4: Update Your Bot
Get your pod's public IP and update `voice_recognition_hf.py`:
```python
self.hf_endpoint_url = "http://YOUR_POD_IP:8000/transcribe"
```

---

## 🎯 **Option 4: Google Colab Pro (Development)**

**Cost: $10/month** | **Setup Time: 5 minutes** | **Good for Testing**

### Step 1: Get Colab Pro
1. Go to [colab.research.google.com](https://colab.research.google.com)
2. Subscribe to Colab Pro ($10/month)

### Step 2: Create Whisper Notebook
```python
# Install dependencies
!pip install transformers accelerate flask-ngrok

# Setup Whisper
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from flask import Flask, request, jsonify
from pyngrok import ngrok
import threading

# Load model
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model_id = "openai/whisper-large-v3"
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id, torch_dtype=torch.float16)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)
pipe = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor, torch_dtype=torch.float16, device=device)

# Create API
app = Flask(__name__)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    audio_file = request.files['audio']
    result = pipe(audio_file)
    return jsonify({'text': result['text']})

# Start ngrok tunnel
public_url = ngrok.connect(5000)
print(f"API available at: {public_url}")

# Start Flask app
app.run(port=5000)
```

---

## 📊 **Cost Comparison**

| Option | Setup Time | Cost/Hour | Monthly (6h/day) | Best For |
|--------|------------|-----------|------------------|----------|
| **HF Inference Endpoints** | 5 min | $0.50-$1.00 | $90-$180 | Production use |
| **HF Spaces** | 10 min | $0.40-$0.60 | $72-$108 | Moderate use |
| **RunPod** | 15 min | $0.34-$0.89 | $61-$160 | Custom setups |
| **Colab Pro** | 5 min | $10/month | $10 | Development |

## 🚀 **Quick Start (Recommended)**

For the fastest setup, use **Hugging Face Inference Endpoints**:

1. **Deploy in 2 minutes:**
   ```bash
   # 1. Go to https://ui.endpoints.huggingface.co/
   # 2. Create endpoint with openai/whisper-large-v3
   # 3. Copy the endpoint URL
   ```

2. **Update your .env:**
   ```bash
   HF_API_TOKEN=hf_your_token_here
   HF_ENDPOINT_URL=https://your-endpoint.endpoints.huggingface.cloud
   ```

3. **Run your bot:**
   ```bash
   python main.py
   ```

**Done!** Your bot now uses cloud-hosted Whisper Large V3 instead of running locally. 🎉

## 🔧 **Troubleshooting**

### Common Issues:

1. **"Endpoint not found"**
   - Check your endpoint URL is correct
   - Ensure endpoint is in "Running" state

2. **"Authentication failed"**
   - Verify your HF_API_TOKEN is correct
   - Check token has "Write" permissions

3. **"Slow transcription"**
   - Upgrade to faster GPU (L4 or A10G)
   - Check your internet connection

4. **"High costs"**
   - Use auto-scaling (min replicas = 0)
   - Pause endpoint when not in use
   - Consider HF Spaces for lower usage

### Cost Optimization:

1. **Auto-scaling:** Set min replicas to 0, max to 1
2. **Pause when idle:** Manually pause endpoints
3. **Use smaller models:** Try `whisper-large-v3-turbo` (faster, cheaper)
4. **Batch processing:** Process multiple audio files together

---

**Need help?** Open an issue on GitHub or check the [Hugging Face documentation](https://huggingface.co/docs/inference-endpoints/). 