# AI SQL Backend

Production-ready FastAPI backend with PostgreSQL, SQLAlchemy ORM, Alembic migrations, and modular routing.

## Features

- **FastAPI**: Modern async web framework for building APIs
- **PostgreSQL**: Robust relational database
- **SQLAlchemy**: Powerful ORM for database operations
- **Alembic**: Database migration tool
- **Pydantic**: Data validation and serialization
- **Structured Logging**: JSON and text format logging
- **Environment Configuration**: .env support with pydantic-settings
- **Modular Routing**: API organized by version and resource
- **CORS Support**: Cross-origin resource sharing configured
- **Testing**: Pytest setup with example tests

## Project Structure

```
AI_SQL_BACKEND/
├── app/                          # Main application
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory
│   ├── config.py                 # Configuration management
│   ├── database.py               # Database setup
│   ├── logging_config.py         # Logging configuration
│   ├── models/                   # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   └── product.py
│   ├── schemas/                  # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── product.py
│   ├── services/                 # Business logic
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── product_service.py
│   └── api/                      # API routes
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── users.py
│           └── products.py
├── migrations/                   # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   ├── alembic.ini
│   └── README
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_users.py
│   └── test_products.py
├── logs/                         # Application logs (auto-created)
├── main.py                       # Application entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
└── README.md                     # This file
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- pip or poetry

### 1. Clone Repository

```bash
git clone <repository-url>
cd AI_SQL_BACKEND
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_sql_db
APP_NAME=AI SQL Backend
DEBUG=False
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 5. Initialize Database

```bash
# Create database tables
python -c "from app.database import init_db; init_db()"
```

Or using Alembic:

```bash
alembic upgrade head
```

### 6. Run Application

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Application will be available at: http://localhost:8000

## API Endpoints

### Health Check

```bash
GET /health
```

### Users

```bash
GET    /api/v1/users/              # List users
POST   /api/v1/users/              # Create user
GET    /api/v1/users/{id}          # Get user
PUT    /api/v1/users/{id}          # Update user
DELETE /api/v1/users/{id}          # Delete user
```

### Products

```bash
GET    /api/v1/products/           # List products
POST   /api/v1/products/           # Create product
GET    /api/v1/products/{id}       # Get product
GET    /api/v1/products/search/?q= # Search products
PUT    /api/v1/products/{id}       # Update product
DELETE /api/v1/products/{id}       # Delete product
```

## Documentation

### Swagger UI (OpenAPI)
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

## Database Migrations

### Create Migration

```bash
alembic revision --autogenerate -m "Add user table"
```

### Apply Migration

```bash
alembic upgrade head
```

### Downgrade

```bash
alembic downgrade -1
```

### View Migration History

```bash
alembic current
alembic history
```

## Testing

### Run Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test

```bash
pytest tests/test_users.py::test_create_user
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `DATABASE_ECHO`: Log SQL queries (True/False)
- `APP_NAME`: Application name
- `APP_VERSION`: Application version
- `DEBUG`: Debug mode (True/False)
- `ENVIRONMENT`: development/staging/production
- `LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR/CRITICAL
- `LOG_FORMAT`: json/text
- `SECRET_KEY`: JWT secret key
- `ALGORITHM`: JWT algorithm
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time

## Logging

Logs are stored in `logs/app.log` with rotation (10MB max file size, 5 backup files).

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for suspicious events
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical messages for severe failures

### Log Format

Supports both JSON and text formats configured in `.env`:

```env
LOG_FORMAT=json  # or "text"
```

## Docker Deployment

### Build Image

```bash
docker build -t ai-sql-backend:latest .
```

### Run Container

```bash
docker run -d \
  --name ai-sql-backend \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:password@host:5432/db \
  ai-sql-backend:latest
```

## Development

### Code Style

Run linting:

```bash
flake8 app/
black app/
isort app/
```

### Type Checking

```bash
mypy app/
```

## Production Considerations

1. **Security**
   - Change `SECRET_KEY` in production
   - Set `DEBUG=False`
   - Use HTTPS
   - Implement proper authentication (JWT, OAuth2)
   - Validate all inputs

2. **Database**
   - Use connection pooling
   - Set up backups
   - Monitor performance
   - Use indexes for frequently queried columns

3. **Logging**
   - Centralize logs (ELK, Splunk, etc.)
   - Set appropriate log levels
   - Monitor error rates

4. **Performance**
   - Use caching (Redis)
   - Implement pagination
   - Add API rate limiting
   - Use async operations

5. **Monitoring**
   - Set up APM (Application Performance Monitoring)
   - Monitor database performance
   - Track API response times

## Contributing

1. Create feature branch: `git checkout -b feature/feature-name`
2. Commit changes: `git commit -am 'Add feature'`
3. Push to branch: `git push origin feature/feature-name`
4. Submit pull request

## License

MIT License

## Support

For issues or questions, please create an issue in the repository.
