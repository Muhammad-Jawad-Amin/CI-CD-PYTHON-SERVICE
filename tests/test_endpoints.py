from app.endpoints import app
from app.auth import AUTH_KEY
from app.database import Base, get_db

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """
    Override function for the database dependency.

    This replaces the normal get_db() with one that uses the test database.
    FastAPI's dependency injection will call this instead during tests.
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """
    Fixture to set up and tear down the database for each test.

    Internal Working:
    1. autouse=True: This fixture runs automatically before each test
    2. Before yield: Create all tables in the test database
    3. yield: Control passes to the test function
    4. After yield: Drop all tables to ensure clean slate for next test

    This ensures complete test isolation - each test starts with a fresh database.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers():
    """
    Fixture providing authentication headers.

    Returns:
        Dictionary with X-API-Key header for authenticated requests
    """
    return {"X-API-Key": AUTH_KEY}


def test_health_check():
    """
    Test the health check endpoint.

    Verifies:
    - Endpoint returns 200 OK
    - Response contains expected status message
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "library-api"}


def test_create_author_success(auth_headers):
    """
    Test successful author creation.

    Internal Working:
    1. Sends POST request with valid data and auth header
    2. Database creates new author record with auto-generated ID
    3. Response includes the created author with ID

    Verifies:
    - 201 Created status
    - Response contains all submitted data plus generated ID
    """
    author_data = {
        "name": "J.K. Rowling",
        "bio": "British author, best known for Harry Potter series",
    }
    response = client.post("/authors", json=author_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == author_data["name"]
    assert data["bio"] == author_data["bio"]
    assert "id" in data


def test_create_author_without_auth():
    """
    Test author creation fails without authentication.

    Verifies:
    - 401 Unauthorized when API key is missing
    - Appropriate error message
    """
    author_data = {"name": "Test Author", "bio": "Test bio"}
    response = client.post("/authors", json=author_data)
    assert response.status_code == 401
    assert "API Key is missing" in response.json()["detail"]


def test_create_author_invalid_auth():
    """
    Test author creation fails with invalid API key.

    Verifies:
    - 403 Forbidden when API key is wrong
    """
    author_data = {"name": "Test Author", "bio": "Test bio"}
    headers = {"X-API-Key": "wrong-key"}
    response = client.post("/authors", json=author_data, headers=headers)
    assert response.status_code == 403


def test_list_authors(auth_headers):
    """
    Test listing authors.

    Internal Working:
    1. Creates two authors
    2. Lists all authors
    3. Verifies both are returned

    Tests pagination works correctly (default skip=0, limit=100)
    """
    author1 = {"name": "Author One", "bio": "First author"}
    author2 = {"name": "Author Two", "bio": "Second author"}
    client.post("/authors", json=author1, headers=auth_headers)
    client.post("/authors", json=author2, headers=auth_headers)

    response = client.get("/authors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Author One"
    assert data[1]["name"] == "Author Two"


def test_get_author_by_id(auth_headers):
    """
    Test retrieving a specific author by ID.

    Verifies:
    - Can retrieve author by ID
    - Response includes author data and books list (initially empty)
    """

    author_data = {"name": "Test Author", "bio": "Test bio"}
    create_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = create_response.json()["id"]

    response = client.get(f"/authors/{author_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == author_id
    assert data["name"] == author_data["name"]
    assert "books" in data
    assert isinstance(data["books"], list)


def test_get_author_not_found():
    """
    Test retrieving non-existent author returns 404.
    """
    response = client.get("/authors/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_create_book_success(auth_headers):
    """
    Test successful book creation.

    Internal Working:
    1. Creates an author first (books require author_id)
    2. Creates a book linked to that author
    3. Verifies book includes author information in response

    Tests the relationship between books and authors works correctly.
    """
    author_data = {"name": "George Orwell", "bio": "English novelist"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "1984",
        "genre": "Dystopian Fiction",
        "isbn": "9780451524935",
        "author_id": author_id,
    }
    response = client.post("/books", json=book_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == book_data["title"]
    assert data["genre"] == book_data["genre"]
    assert data["isbn"] == book_data["isbn"]
    assert data["author_id"] == author_id
    assert data["author"]["name"] == "George Orwell"


def test_create_book_author_not_found(auth_headers):
    """
    Test book creation fails with non-existent author.

    Verifies:
    - 404 when trying to create book with invalid author_id
    - Maintains referential integrity
    """
    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": 99999,
    }
    response = client.post("/books", json=book_data, headers=auth_headers)
    assert response.status_code == 404
    assert "Author" in response.json()["detail"]


def test_create_book_duplicate_isbn(auth_headers):
    """
    Test book creation fails with duplicate ISBN.

    Business Logic:
    - ISBNs must be unique across all books
    - Database constraint prevents duplicates
    - API checks and returns appropriate error

    Verifies:
    - First book creation succeeds
    - Second book with same ISBN fails with 400
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "First Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    response1 = client.post("/books", json=book_data, headers=auth_headers)
    assert response1.status_code == 201

    book_data2 = {
        "title": "Second Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    response2 = client.post("/books", json=book_data2, headers=auth_headers)
    assert response2.status_code == 400
    assert "ISBN" in response2.json()["detail"]


def test_list_books(auth_headers):
    """
    Test listing books with their authors.

    Verifies:
    - Can list all books
    - Each book includes nested author information
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book1 = {
        "title": "Book One",
        "genre": "Fiction",
        "isbn": "1111111111111",
        "author_id": author_id,
    }
    book2 = {
        "title": "Book Two",
        "genre": "Non-Fiction",
        "isbn": "2222222222222",
        "author_id": author_id,
    }
    client.post("/books", json=book1, headers=auth_headers)
    client.post("/books", json=book2, headers=auth_headers)

    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_books_filter_by_genre(auth_headers):
    """
    Test filtering books by genre.

    Internal Working:
    - Creates books with different genres
    - Queries with genre filter
    - Verifies only matching books are returned

    Tests the SQL WHERE clause filtering works correctly.
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book1 = {
        "title": "Fiction Book",
        "genre": "Fiction",
        "isbn": "1111111111111",
        "author_id": author_id,
    }
    book2 = {
        "title": "Science Book",
        "genre": "Science",
        "isbn": "2222222222222",
        "author_id": author_id,
    }
    client.post("/books", json=book1, headers=auth_headers)
    client.post("/books", json=book2, headers=auth_headers)

    response = client.get("/books?genre=Fiction")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["genre"] == "Fiction"


def test_get_book_by_id(auth_headers):
    """
    Test retrieving a specific book by ID.

    Verifies:
    - Can retrieve book with all details
    - Response includes author and loan_records (initially empty)
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == book_id
    assert data["title"] == book_data["title"]
    assert "loan_records" in data


def test_update_book(auth_headers):
    """
    Test updating a book's information.

    Internal Working:
    1. Creates a book
    2. Updates specific fields (title and genre)
    3. Verifies only updated fields changed
    4. Tests partial update functionality

    This tests the PUT endpoint's partial update behavior.
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Original Title",
        "genre": "Original Genre",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    update_data = {"title": "Updated Title", "genre": "Updated Genre"}
    response = client.put(f"/books/{book_id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["genre"] == "Updated Genre"
    assert data["isbn"] == book_data["isbn"]


def test_loan_book_success(auth_headers):
    """
    Test successfully loaning a book.

    Business Logic:
    - Creates a loan record
    - Marks book as loaned out
    - Records borrower and timestamp

    Verifies:
    - 201 Created status
    - Loan record contains correct data
    - is_returned is False for new loans
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data = {"borrower_name": "John Doe"}
    response = client.post(
        f"/books/{book_id}/loan", json=loan_data, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["book_id"] == book_id
    assert data["borrower_name"] == "John Doe"
    assert data["is_returned"] == False
    assert "loaned_at" in data


def test_loan_book_already_loaned(auth_headers):
    """
    Test preventing double-loaning of a book.

    Business Logic Critical:
    - A book can only be loaned to one person at a time
    - Attempting to loan an already-loaned book must fail
    - This prevents conflicts and maintains data integrity

    Verifies:
    - First loan succeeds
    - Second loan attempt fails with 400
    - Error message indicates book is already loaned
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data1 = {"borrower_name": "John Doe"}
    response1 = client.post(
        f"/books/{book_id}/loan", json=loan_data1, headers=auth_headers
    )
    assert response1.status_code == 201

    loan_data2 = {"borrower_name": "Jane Smith"}
    response2 = client.post(
        f"/books/{book_id}/loan", json=loan_data2, headers=auth_headers
    )
    assert response2.status_code == 400
    assert "already loaned" in response2.json()["detail"]


def test_return_book_success(auth_headers):
    """
    Test successfully returning a book.

    Business Logic:
    1. Loan a book
    2. Return it
    3. Verify loan record is updated correctly

    Verifies:
    - is_returned changes to True
    - returned_at timestamp is set
    - Book becomes available for future loans
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data = {"borrower_name": "John Doe"}
    loan_response = client.post(
        f"/books/{book_id}/loan", json=loan_data, headers=auth_headers
    )
    loan_id = loan_response.json()["id"]

    response = client.post(f"/loans/{loan_id}/return", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["is_returned"] == True
    assert data["returned_at"] is not None


def test_return_book_already_returned(auth_headers):
    """
    Test preventing double-return of a book.

    Business Logic:
    - A book can only be returned once
    - Attempting to return an already-returned book should fail

    Verifies:
    - First return succeeds
    - Second return attempt fails with 400
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data = {"borrower_name": "John Doe"}
    loan_response = client.post(
        f"/books/{book_id}/loan", json=loan_data, headers=auth_headers
    )
    loan_id = loan_response.json()["id"]

    response1 = client.post(f"/loans/{loan_id}/return", headers=auth_headers)
    assert response1.status_code == 200

    response2 = client.post(f"/loans/{loan_id}/return", headers=auth_headers)
    assert response2.status_code == 400
    assert "already been returned" in response2.json()["detail"]


def test_loan_and_return_workflow(auth_headers):
    """
    Test complete loan and return workflow.

    Integration Test:
    1. Create author and book
    2. Loan book (should succeed)
    3. Try to loan again (should fail)
    4. Return book (should succeed)
    5. Loan book again (should succeed now)

    This tests the complete business logic flow and ensures
    the book becomes available after return.
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data1 = {"borrower_name": "John Doe"}
    loan_response1 = client.post(
        f"/books/{book_id}/loan", json=loan_data1, headers=auth_headers
    )
    assert loan_response1.status_code == 201
    loan_id = loan_response1.json()["id"]

    loan_data2 = {"borrower_name": "Jane Smith"}
    loan_response2 = client.post(
        f"/books/{book_id}/loan", json=loan_data2, headers=auth_headers
    )
    assert loan_response2.status_code == 400

    return_response = client.post(f"/loans/{loan_id}/return", headers=auth_headers)
    assert return_response.status_code == 200

    loan_response3 = client.post(
        f"/books/{book_id}/loan", json=loan_data2, headers=auth_headers
    )
    assert loan_response3.status_code == 201
    assert loan_response3.json()["borrower_name"] == "Jane Smith"


def test_list_loans(auth_headers):
    """
    Test listing all loan records.

    Verifies:
    - Can list all loans
    - Each loan includes nested book and author information
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book_data = {
        "title": "Test Book",
        "genre": "Fiction",
        "isbn": "1234567890123",
        "author_id": author_id,
    }
    book_response = client.post("/books", json=book_data, headers=auth_headers)
    book_id = book_response.json()["id"]

    loan_data = {"borrower_name": "John Doe"}
    client.post(f"/books/{book_id}/loan", json=loan_data, headers=auth_headers)

    response = client.get("/loans")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "book" in data[0]


def test_list_active_loans_only(auth_headers):
    """
    Test filtering for active (unreturned) loans only.

    Internal Working:
    1. Creates multiple loans
    2. Returns some of them
    3. Queries with active_only=true
    4. Verifies only unreturned loans are included

    Tests the SQL WHERE clause filtering on is_returned column.
    """
    author_data = {"name": "Test Author", "bio": "Test"}
    author_response = client.post("/authors", json=author_data, headers=auth_headers)
    author_id = author_response.json()["id"]

    book1_data = {
        "title": "Book 1",
        "genre": "Fiction",
        "isbn": "1111111111111",
        "author_id": author_id,
    }
    book1_response = client.post("/books", json=book1_data, headers=auth_headers)
    book1_id = book1_response.json()["id"]

    book2_data = {
        "title": "Book 2",
        "genre": "Fiction",
        "isbn": "2222222222222",
        "author_id": author_id,
    }
    book2_response = client.post("/books", json=book2_data, headers=auth_headers)
    book2_id = book2_response.json()["id"]

    loan1_response = client.post(
        f"/books/{book1_id}/loan",
        json={"borrower_name": "Person 1"},
        headers=auth_headers,
    )
    loan1_id = loan1_response.json()["id"]
    client.post(
        f"/books/{book2_id}/loan",
        json={"borrower_name": "Person 2"},
        headers=auth_headers,
    )

    client.post(f"/loans/{loan1_id}/return", headers=auth_headers)

    response = client.get("/loans?active_only=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["borrower_name"] == "Person 2"
    assert data[0]["is_returned"] == False
