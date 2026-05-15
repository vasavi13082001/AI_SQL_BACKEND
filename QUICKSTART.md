# Quick Start Guide

Get your AI SQL Backend running in 5 minutes!

## 1️⃣ Install Dependencies

### Windows
```bash
setup.bat
```

### macOS/Linux
```bash
bash setup.sh
```

### Manual Setup
```bash
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 2️⃣ Configure Database

```bash
cp .env.example .env
```

Edit `.env` and update:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_sql_db
```

## 3️⃣ Create Database

```bash
# Option 1: Using Python
python -c "from app.database import init_db; init_db()"

# Option 2: Using Alembic
alembic upgrade head
```

## 4️⃣ Start Application

```bash
python main.py
```

Or with uvicorn:
```bash
uvicorn main:app --reload
```

## 5️⃣ Access API

- **API**: http://localhost:8000
- **Docs (Swagger)**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

## 📝 Test the API

### Create a User
```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "password": "securepass123"
  }'
```

### List Users
```bash
curl http://localhost:8000/api/v1/users/
```

### Create a Product
```bash
curl -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Widget",
    "description": "A useful widget",
    "price": 29.99,
    "stock": 100,
    "sku": "WIDGET-001"
  }'
```

### List Products
```bash
curl http://localhost:8000/api/v1/products/
```

## 🐳 Using Docker

### Run with Docker Compose
```bash
docker-compose up -d
```

### Access Services
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- User: user
- Password: password

### Stop Services
```bash
docker-compose down
```

## 🧪 Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_users.py

# Specific test
pytest tests/test_users.py::test_create_user -v
```

## 📚 Documentation

- **API Documentation**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Full README**: [README.md](README.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

## 🔑 Key Features

✅ FastAPI - Modern async web framework
✅ PostgreSQL - Robust database
✅ SQLAlchemy - Powerful ORM
✅ Alembic - Database migrations
✅ Pydantic - Data validation
✅ Structured Logging - JSON & text formats
✅ Modular Routing - Clean API organization
✅ Docker Support - Easy containerization
✅ Testing - Pytest with examples
✅ Production Ready - Security, monitoring, deployment guides

## 🏗️ Project Structure

```
app/
├── main.py              # FastAPI app factory
├── config.py            # Configuration management
├── database.py          # Database setup
├── logging_config.py    # Logging configuration
├── models/              # Database models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
└── api/v1/              # API routes

migrations/              # Database migrations (Alembic)
tests/                   # Test suite
```

## 🚀 Next Steps

1. **Explore the API** using Swagger at `/docs`
2. **Read the documentation** in README.md
3. **Add more models** by creating new files in `app/models/`
4. **Add more routes** in `app/api/v1/`
5. **Implement authentication** for production use
6. **Deploy** using Docker or traditional server

## ❓ Common Commands

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Create new database migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Downgrade migrations
alembic downgrade -1

# Run tests
pytest

# Format code
black app/
isort app/

# Type checking
mypy app/
```

## 🐛 Troubleshooting

### Database Connection Error
- Check DATABASE_URL in .env
- Ensure PostgreSQL is running
- Verify credentials

### Import Error
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

### Port Already in Use
- Change port: `uvicorn main:app --port 8001`
- Or kill process using port 8000

## 📞 Need Help?

- Check documentation files
- Review example tests in `tests/`
- Check FastAPI docs: https://fastapi.tiangolo.com
- Review SQLAlchemy docs: https://www.sqlalchemy.org

## 🎯 Success Checklist

- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] .env file configured with database URL
- [ ] Database tables created
- [ ] Application starts without errors
- [ ] Can access /docs endpoint
- [ ] Can create/list users and products
- [ ] Tests pass

**You're ready to build! 🚀**
