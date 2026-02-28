# RAG System with AWS Deployment

A production-ready Retrieval-Augmented Generation (RAG) system deployed on AWS infrastructure.

## Architecture

This system uses:
- **AWS S3**: Document storage
- **AWS SQS**: Message queue for document processing
- **AWS OpenSearch**: Vector database for document embeddings
- **AWS Bedrock**: LLM and embedding models
- **EC2**: Hosting Flask API and background worker

## Project Structure

```
RAG_with_AWS_deployment/
├── src/              # Main application code
├── config/           # Configuration modules
├── scripts/          # Utility scripts
├── deployment/       # Deployment configurations
├── tests/            # Test files
└── docs/             # Documentation
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/davidmovsisian/RAG_with_AWS_deployment.git
cd RAG_with_AWS_deployment
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your AWS credentials and configuration
```

5. Run tests:
```bash
pytest
```

## Development Stages

- ✅ Stage 1: AWS Infrastructure Setup
- ✅ Stage 2: Project Repository Structure & Dependencies
- ⏳ Stage 3: Utility Modules Development
- ⏳ Stage 4: Worker Development
- ⏳ Stage 5: Flask API Development
- ⏳ Stage 6: Scripts & Testing
- ⏳ Stage 7: Deployment & Systemd Configuration
- ⏳ Stage 8: UI/UX Layer (Optional)
- ⏳ Stage 9: Optional AI Services Integration
- ⏳ Stage 10: Stretch Goals & Optimization

## License

MIT