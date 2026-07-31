# Deployment Guide for Chess Analyzer

## Option 1: Streamlit Cloud (Easiest - Free Tier)

### Prerequisites
- GitHub account with your code pushed
- Stockfish binary issue needs resolution (see below)

### Steps
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "New app"
3. Connect your GitHub repository
4. Select `main.py` as main file
5. Click "Deploy"

### Stockfish Binary Issue
Streamlit Cloud doesn't support custom binaries well. You have two options:

#### Option A: Use Chess API (Recommended)
Replace local Stockfish with a cloud API. This is the most reliable solution.

#### Option B: Use Railway/Render (Supports Binaries)
These platforms support custom binaries and can run Stockfish.

## Option 2: Railway (Supports Stockfish Binary)

### Steps
1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Connect GitHub repository
4. Railway will detect it's a Python project
5. Add environment variable for Stockfish path if needed
6. Deploy

### Configuration
Railway automatically handles the build process. Make sure your `requirements.txt` is complete.

## Option 3: Render (Supports Stockfish Binary)

### Steps
1. Go to [render.com](https://render.com)
2. Click "New +"
3. Select "Web Service"
4. Connect GitHub repository
5. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run main.py --server.port=$PORT --server.address=0.0.0.0`
6. Deploy

## Option 4: Hugging Face Spaces (Free)

### Steps
1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Create new Space
3. Select "Streamlit" SDK
4. Upload your files or connect GitHub
5. Deploy

### Note
Hugging Face Spaces may have limitations with Stockfish binary.

## Important Notes

### Stockfish Binary Path
The app expects Stockfish at specific paths. For cloud deployment, you may need to:
1. Upload the Stockfish binary to your repository
2. Update the path in the code or settings
3. Or use a chess API instead

### Environment Variables
Consider adding environment variables for:
- Stockfish path
- API keys (if using chess API)
- Other configuration

### Custom Domain
Once deployed, you can add a custom domain through your platform's settings.

## Monitoring
- Streamlit Cloud: Built-in metrics
- Railway: Built-in logs and metrics
- Render: Built-in monitoring
- Hugging Face: Basic metrics

## Scaling
- Free tiers have resource limits
- Upgrade to paid plans for:
  - More CPU/RAM
  - Better performance
  - Custom domains
  - Priority support
