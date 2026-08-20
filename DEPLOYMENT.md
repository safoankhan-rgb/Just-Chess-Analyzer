# Deployment Guide for Chess Analyzer

## Docker-Based Deployment (Recommended)

This project now includes Docker support for easy deployment with Stockfish binary included.

### Local Docker Testing

#### Using Docker Compose (Recommended)
```bash
docker-compose up --build
```
Access at http://localhost:8501

#### Using Docker Directly
```bash
docker build -t chess-analyzer .
docker run -p 8501:8501 chess-analyzer
```

### Option 1: Hugging Face Spaces (Free - Recommended)

#### Prerequisites
- GitHub account with your code pushed
- Stockfish binary included in repository

#### Steps
1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Create new Space
3. Select "Docker" as the Space type
4. Connect your GitHub repository
5. The Dockerfile will automatically build with Stockfish included
6. Deploy

#### Why Hugging Face Spaces?
- Free hosting for ML/chess projects
- Full Docker support with custom binaries
- Simple Git-based deployment
- Good for public projects

### Option 2: Railway (Supports Docker)

#### Steps
1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Connect GitHub repository
4. Railway will detect Docker setup
5. Deploy automatically

#### Configuration
Railway automatically handles the Docker build process. Stockfish binary is included in the container.

### Option 3: Render (Supports Docker)

#### Steps
1. Go to [render.com](https://render.com)
2. Click "New +"
3. Select "Web Service"
4. Connect GitHub repository
5. Configure:
   - Runtime: Docker
   - Render will use your Dockerfile
6. Deploy

### Option 4: Streamlit Cloud (Limited Support)

**Note**: Streamlit Cloud has limited support for custom binaries. Docker-based deployment is recommended instead.

If you still want to use Streamlit Cloud, you would need to:
1. Use a cloud chess API instead of local Stockfish
2. Or use a platform that supports Docker containers

## Important Notes

### Stockfish Binary
The Dockerfile automatically includes the Stockfish binary in the container, so no manual setup is needed for Docker deployments.

### Environment Variables
The Docker container sets these automatically:
- `STREAMLIT_SERVER_PORT=8501`
- `STREAMLIT_SERVER_ADDRESS=0.0.0.0`
- `PYTHONUNBUFFERED=1`

### Custom Domain
Once deployed, you can add a custom domain through your platform's settings.

## Monitoring
- Hugging Face Spaces: Basic metrics and logs
- Railway: Built-in logs and metrics
- Render: Built-in monitoring
- Docker: Use `docker logs` for local monitoring

## Scaling
- Free tiers have resource limits
- Upgrade to paid plans for:
  - More CPU/RAM for faster analysis
  - Better performance with deep analysis
  - Custom domains
  - Priority support

## Troubleshooting

### Docker Build Issues
- Ensure Docker is running: `docker ps`
- Check available disk space
- Try `docker system prune` to clean up

### Stockfish Not Found in Container
- Verify the binary was copied correctly in Dockerfile
- Check file permissions: `RUN chmod +x stockfish/stockfish`
- Test locally first with `docker run`

### Port Already in Use
- Change port mapping: `docker run -p 8502:8501 chess-analyzer`
- Or stop conflicting services

### Memory Issues
- Deep analysis (depth 30+) requires more RAM
- Consider reducing depth for free tier deployments
- Upgrade to paid tier for better performance
