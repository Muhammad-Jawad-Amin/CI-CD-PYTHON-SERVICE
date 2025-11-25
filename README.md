# Book Library Management API

A comprehensive, production-ready library management system built with FastAPI, SQLAlchemy, and PostgreSQL. This service provides complete CRUD operations for managing authors, books, and loan records with API key authentication.

## Features

- **Authors Management**: Create and retrieve author information
- **Books Management**: Full CRUD operations with genre filtering
- **Loan Tracking**: Loan and return books with validation to prevent double-loaning
- **API Key Authentication**: Secure write operations with API key verification
- **Database**: SQLAlchemy ORM with PostgreSQL (production) and SQLite (development)
- **Comprehensive Testing**: Full test suite with pytest
- **Docker Support**: Complete containerization with Docker Compose
- **CI/CD Pipeline**: Automated testing, building, and deployment with GitHub Actions

## Architecture Overview

### Database Schema

```
Authors (1) ----< (N) Books (1) ----< (N) Loan Records
```

**Internal Working of Relationships:**
- One-to-Many: An author can have multiple books, implemented using `author_id` foreign key in Books table
- One-to-Many: A book can have multiple loan records (history), implemented using `book_id` foreign key in Loan Records
- SQLAlchemy's `relationship()` creates Python-level bidirectional navigation without additional queries
- Cascade deletes ensure referential integrity (deleting an author deletes their books)

### API Endpoints

#### Authors
- `POST /authors` - Create author (requires API key)
- `GET /authors` - List all authors with pagination
- `GET /authors/{id}` - Get author details with books

#### Books
- `POST /books` - Create book (requires API key)
- `GET /books` - List books with optional genre filtering
- `GET /books/{id}` - Get book details with loan history
- `PUT /books/{id}` - Update book information (requires API key)

#### Loans
- `POST /books/{id}/loan` - Loan a book (requires API key)
- `POST /loans/{id}/return` - Return a book (requires API key)
- `GET /loans` - List all loans with optional active-only filtering

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- PostgreSQL (for production) or SQLite (for development)

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd library-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**
   ```bash
   uvicorn main:app --reload
   ```

6. **Access the API**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

### Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_main.py -v
```

## Docker Deployment

### Using Docker Compose

**Internal Working of Docker Compose:**
1. `db` service starts PostgreSQL with health checks
2. `app` service waits for `db` health check to pass (via `depends_on` with condition)
3. Docker's internal DNS resolves service names (app can reach db via hostname `db`)
4. Named volumes persist PostgreSQL data across container restarts

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Run tests in container
docker-compose --profile test up tests

# Stop services
docker-compose down

# Stop and remove volumes (delete database)
docker-compose down -v
```

### Services

- **db**: PostgreSQL database on port 5432
- **app**: FastAPI application on port 8000
- **tests**: Test runner (runs once and exits)

## API Authentication

All write operations (POST, PUT) require an API key in the `X-API-Key` header.

**Internal Working:**
1. FastAPI's `Security()` dependency extracts the header value
2. `verify_api_key()` function compares it against `AUTH_KEY` environment variable
3. If invalid, raises `HTTPException` (stops request processing)
4. If valid, proceeds to endpoint handler

```bash
# Example with curl
curl -X POST http://localhost:8000/authors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"name": "J.K. Rowling", "bio": "British author"}'
```

## API Usage Examples

### Create an Author
```bash
curl -X POST http://localhost:8000/authors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-12345" \
  -d '{
    "name": "George Orwell",
    "bio": "English novelist and essayist"
  }'
```

### Create a Book
```bash
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-12345" \
  -d '{
    "title": "1984",
    "genre": "Dystopian Fiction",
    "isbn": "9780451524935",
    "author_id": 1
  }'
```

### List Books by Genre
```bash
curl http://localhost:8000/books?genre=Fiction&limit=10
```

### Loan a Book
```bash
curl -X POST http://localhost:8000/books/1/loan \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-12345" \
  -d '{
    "borrower_name": "John Doe"
  }'
```

### Return a Book
```bash
curl -X POST http://localhost:8000/loans/1/return \
  -H "X-API-Key: dev-secret-key-12345"
```

## CI/CD Pipeline

The GitHub Actions workflow automatically:

1. **CI (Continuous Integration)**
   - Runs full test suite on every push/PR
   - Validates code quality and functionality
   - Caches dependencies for faster builds

2. **Build**
   - Builds Docker image with multi-stage optimization
   - Pushes to Docker Hub with appropriate tags
   - Uses layer caching for efficiency

3. **CD (Continuous Deployment)**
   - Deploys to EC2 instance on main branch pushes
   - Pulls latest image and restarts services
   - Verifies deployment health

**Internal Working of Deployment:**
1. GitHub Actions connects to EC2 via SSH
2. Executes remote commands to pull new image
3. Runs `docker-compose down` to stop old containers
4. Runs `docker-compose up -d` to start with new image
5. Verifies health endpoint returns success

### Required GitHub Secrets

Configure these in your GitHub repository settings:

- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password/token
- `EC2_HOST`: EC2 instance public IP or hostname
- `EC2_USER`: SSH user (typically `ec2-user` or `ubuntu`)
- `EC2_SSH_KEY`: Private SSH key for EC2 access
- `AUTH_KEY`: API key for production environment

## Project Structure

```
library-api/
├── main.py                 # FastAPI application and endpoints
├── models.py              # SQLAlchemy ORM models
├── schemas.py             # Pydantic schemas for validation
├── database.py            # Database configuration
├── auth.py                # API key authentication
├── test_main.py           # Comprehensive test suite
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Service orchestration
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore rules
├── .github/
│   └── workflows/
│       └── ci-cd.yml    # GitHub Actions pipeline
└── README.md            # This file
```

## Database Internals

### SQLAlchemy Session Management

**How Sessions Work:**
1. `SessionLocal()` creates a new database session (transaction)
2. Session tracks all changes to objects (inserts, updates, deletes)
3. `commit()` flushes changes to database and commits transaction
4. `refresh()` reloads object from database to get auto-generated values
5. `close()` releases connection back to pool

### Connection Pooling

SQLAlchemy maintains a connection pool to reuse database connections:
- Reduces overhead of creating new connections
- Limits maximum concurrent connections
- Automatically handles connection lifecycle

### Query Optimization

The API uses several optimization techniques:
- **Eager Loading**: `joinedload()` prevents N+1 query problem
- **Indexing**: Key columns (id, isbn, name) have database indexes
- **Pagination**: `offset()` and `limit()` prevent loading entire tables

## Security Considerations

1. **API Key Storage**: Store AUTH_KEY in environment variables, never in code
2. **Database Credentials**: Use strong passwords and limit network access
3. **SQL Injection**: SQLAlchemy ORM parameterizes queries automatically
4. **Input Validation**: Pydantic validates all input data before processing
5. **HTTPS**: Use HTTPS in production (configure at reverse proxy level)

## Production Deployment Checklist

- [ ] Change `AUTH_KEY` to strong, random value
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set up database backups
- [ ] Configure HTTPS with SSL certificates
- [ ] Set up monitoring and logging
- [ ] Configure firewall rules
- [ ] Use Docker secrets for sensitive data
- [ ] Set up database connection pooling limits
- [ ] Configure Uvicorn workers for concurrency
- [ ] Set up health checks and alerts

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps

# View database logs
docker-compose logs db

# Test database connection
docker-compose exec db psql -U libraryuser -d librarydb
```

### Application Errors

```bash
# View application logs
docker-compose logs app

# Restart application
docker-compose restart app

# Access container shell
docker-compose exec app /bin/bash
```

### Test Failures

```bash
# Run tests with verbose output
pytest -vv

# Run specific test
pytest test_main.py::test_create_author_success -v

# Run with debugging
pytest --pdb
```

## Performance Considerations

### Database Optimization
- Indexes on frequently queried columns (id, isbn, genre)
- Foreign key constraints for referential integrity
- Connection pooling to reuse database connections

### API Performance
- Pagination prevents loading entire tables
- Eager loading prevents N+1 query problems
- Response models limit serialized data

### Scaling
- Horizontal scaling: Multiple app containers behind load balancer
- Vertical scaling: Increase container resources
- Database replication: Read replicas for query distribution

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the API documentation at `/docs`