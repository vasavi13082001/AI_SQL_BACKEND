# API Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
Currently, the API doesn't require authentication. In production, implement JWT or OAuth2.

## Response Format
All responses are in JSON format with consistent structure.

### Success Response
```json
{
  "id": 1,
  "name": "value",
  "created_at": "2024-05-15T10:30:00",
  "updated_at": "2024-05-15T10:30:00"
}
```

### Error Response
```json
{
  "detail": "Error message describing the issue"
}
```

## Pagination
Endpoints supporting lists use `skip` and `limit` query parameters.

```bash
GET /api/v1/users/?skip=0&limit=10
```

- `skip` (default: 0): Number of items to skip
- `limit` (default: 100, max: 1000): Number of items to return

## User Endpoints

### List Users
```bash
GET /users/
```

Query Parameters:
- `skip`: integer (default: 0)
- `limit`: integer (default: 100, max: 1000)

Response:
```json
[
  {
    "id": 1,
    "email": "user@example.com",
    "username": "username",
    "full_name": "Full Name",
    "is_active": true
  }
]
```

### Create User
```bash
POST /users/
```

Request Body:
```json
{
  "email": "user@example.com",
  "username": "username",
  "full_name": "Full Name",
  "password": "securepassword"
}
```

Response (201 Created):
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "username",
  "full_name": "Full Name",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2024-05-15T10:30:00",
  "updated_at": "2024-05-15T10:30:00"
}
```

### Get User
```bash
GET /users/{id}
```

Path Parameters:
- `id`: integer (User ID)

Response:
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "username",
  "full_name": "Full Name",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2024-05-15T10:30:00",
  "updated_at": "2024-05-15T10:30:00"
}
```

### Update User
```bash
PUT /users/{id}
```

Path Parameters:
- `id`: integer (User ID)

Request Body (all fields optional):
```json
{
  "email": "newemail@example.com",
  "full_name": "New Name",
  "is_active": true
}
```

Response:
```json
{
  "id": 1,
  "email": "newemail@example.com",
  "username": "username",
  "full_name": "New Name",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2024-05-15T10:30:00",
  "updated_at": "2024-05-15T10:30:01"
}
```

### Delete User
```bash
DELETE /users/{id}
```

Path Parameters:
- `id`: integer (User ID)

Response: 204 No Content

## Product Endpoints

### List Products
```bash
GET /products/
```

Query Parameters:
- `skip`: integer (default: 0)
- `limit`: integer (default: 100, max: 1000)
- `is_active`: boolean (default: true)

Response:
```json
[
  {
    "id": 1,
    "name": "Product Name",
    "price": 99.99,
    "stock": 10,
    "is_active": true
  }
]
```

### Create Product
```bash
POST /products/
```

Request Body:
```json
{
  "name": "Product Name",
  "description": "Product description",
  "price": 99.99,
  "stock": 10,
  "sku": "PROD-001"
}
```

Response (201 Created):
```json
{
  "id": 1,
  "name": "Product Name",
  "description": "Product description",
  "price": 99.99,
  "stock": 10,
  "sku": "PROD-001",
  "is_active": true,
  "created_at": "2024-05-15T10:30:00",
  "updated_at": "2024-05-15T10:30:00"
}
```

### Get Product
```bash
GET /products/{id}
```

Path Parameters:
- `id`: integer (Product ID)

### Search Products
```bash
GET /products/search/?q=search_term
```

Query Parameters:
- `q`: string (search term, required, min_length: 1)

Response:
```json
[
  {
    "id": 1,
    "name": "Product Name",
    "price": 99.99,
    "stock": 10,
    "is_active": true
  }
]
```

### Update Product
```bash
PUT /products/{id}
```

Request Body (all fields optional):
```json
{
  "name": "Updated Name",
  "price": 199.99,
  "stock": 5,
  "is_active": true
}
```

### Delete Product
```bash
DELETE /products/{id}
```

Response: 204 No Content

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "invalid email format",
      "type": "value_error.email"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

## Rate Limiting
Not currently implemented. Configure in production using middleware.

## API Versioning
Current version: v1

Future versions will be available at:
```
/api/v2/...
/api/v3/...
```

## Testing API with cURL

### List users
```bash
curl http://localhost:8000/api/v1/users/
```

### Create user
```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "password": "testpass123"
  }'
```

### Get user
```bash
curl http://localhost:8000/api/v1/users/1
```

### Update user
```bash
curl -X PUT http://localhost:8000/api/v1/users/1 \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Updated Name"
  }'
```

### Delete user
```bash
curl -X DELETE http://localhost:8000/api/v1/users/1
```
