from app import models
from app import schemas
from app.auth import verify_api_key
from app.database import engine, get_db

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, HTTPException, status, Query


models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Book Library Management API",
    description="A comprehensive library management system with authors, books, and loan tracking",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        Simple status message indicating the service is running
    """
    return {"status": "healthy", "service": "library-api"}


@app.post(
    "/authors",
    response_model=schemas.Author,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_author(author: schemas.AuthorCreate, db: Session = Depends(get_db)):
    """
    Create a new author (requires API key).

    Internal Working:
    1. FastAPI validates request body against AuthorCreate schema
    2. verify_api_key dependency checks authentication
    3. get_db dependency provides database session
    4. We create a new Author ORM instance
    5. SQLAlchemy tracks this as a pending change
    6. db.commit() executes INSERT SQL and commits transaction
    7. db.refresh() fetches the new record (with auto-generated id)
    8. FastAPI serializes the result using Author schema

    Args:
        author: Validated author data from request body
        db: Database session (injected)

    Returns:
        The created author with generated id
    """
    db_author = models.Author(**author.model_dump())
    db.add(db_author)
    db.commit()
    db.refresh(db_author)
    return db_author


@app.get("/authors", response_model=List[schemas.Author])
async def list_authors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List all authors with pagination.

    Internal Working:
    1. Query() validates query parameters (skip >= 0, 1 <= limit <= 1000)
    2. db.query() creates a SELECT statement
    3. offset() and limit() add pagination to SQL
    4. all() executes the query and returns a list
    5. FastAPI serializes each Author object using the schema

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session (injected)

    Returns:
        List of authors
    """
    authors = db.query(models.Author).offset(skip).limit(limit).all()
    return authors


@app.get("/authors/{author_id}", response_model=schemas.AuthorWithBooks)
async def get_author(author_id: int, db: Session = Depends(get_db)):
    """
    Get a specific author by ID with their books.

    Internal Working:
    1. Path parameter {author_id} is extracted and validated as int
    2. first() returns the first matching record or None
    3. If None, we raise HTTPException (FastAPI returns 404 response)
    4. SQLAlchemy's relationship() lazy-loads books when accessed
    5. AuthorWithBooks schema includes nested books list

    Args:
        author_id: The author's database ID
        db: Database session (injected)

    Returns:
        Author with all their books

    Raises:
        HTTPException: 404 if author not found
    """
    author = db.query(models.Author).filter(models.Author.id == author_id).first()
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author with id {author_id} not found",
        )
    return author


@app.post(
    "/books",
    response_model=schemas.Book,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    """
    Create a new book (requires API key).

    Internal Working:
    1. Validates that the author exists before creating book
    2. Checks ISBN uniqueness (database constraint would also catch this)
    3. Creates Book ORM instance linked to the author
    4. Commits to database and returns with author data

    Business Logic:
    - Books must have a valid author_id
    - ISBN must be unique across all books

    Args:
        book: Validated book data from request body
        db: Database session (injected)

    Returns:
        The created book with author information

    Raises:
        HTTPException: 404 if author not found, 400 if ISBN exists
    """
    author = db.query(models.Author).filter(models.Author.id == book.author_id).first()
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author with id {book.author_id} not found",
        )

    existing_book = db.query(models.Book).filter(models.Book.isbn == book.isbn).first()
    if existing_book:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Book with ISBN {book.isbn} already exists",
        )

    db_book = models.Book(**book.model_dump())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


@app.get("/books", response_model=List[schemas.Book])
async def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    genre: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List all books with optional genre filtering and pagination.

    Internal Working:
    1. Builds base query for all books
    2. If genre provided, adds WHERE clause to filter
    3. Applies pagination with offset and limit
    4. Eager loads author data to avoid N+1 query problem

    The N+1 Problem:
    - Without eager loading: 1 query for books + N queries for each book's author
    - With joinedload: 1 query with JOIN to fetch everything at once

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        genre: Optional genre filter
        db: Database session (injected)

    Returns:
        List of books matching the criteria
    """
    query = db.query(models.Book)

    if genre:
        query = query.filter(models.Book.genre.ilike(f"%{genre}%"))

    books = query.offset(skip).limit(limit).all()
    return books


@app.get("/books/{book_id}", response_model=schemas.BookWithLoans)
async def get_book(book_id: int, db: Session = Depends(get_db)):
    """
    Get a specific book by ID with loan history.

    Args:
        book_id: The book's database ID
        db: Database session (injected)

    Returns:
        Book with author and loan records

    Raises:
        HTTPException: 404 if book not found
    """
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found",
        )
    return book


@app.put(
    "/books/{book_id}",
    response_model=schemas.Book,
    dependencies=[Depends(verify_api_key)],
)
async def update_book(
    book_id: int, book_update: schemas.BookUpdate, db: Session = Depends(get_db)
):
    """
    Update a book's information (requires API key).

    Internal Working:
    1. Fetches the existing book from database
    2. Iterates through provided fields (excluding None values)
    3. Updates only the fields that were provided
    4. Validates ISBN uniqueness if ISBN is being changed
    5. Commits changes to database

    This implements partial updates (PATCH-like behavior with PUT).

    Args:
        book_id: The book's database ID
        book_update: Fields to update (all optional)
        db: Database session (injected)

    Returns:
        The updated book

    Raises:
        HTTPException: 404 if book not found, 400 if ISBN conflict
    """
    db_book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not db_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found",
        )

    update_data = book_update.model_dump(exclude_unset=True)

    if "isbn" in update_data and update_data["isbn"] != db_book.isbn:
        existing_book = (
            db.query(models.Book)
            .filter(models.Book.isbn == update_data["isbn"])
            .first()
        )
        if existing_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Book with ISBN {update_data['isbn']} already exists",
            )

    for key, value in update_data.items():
        setattr(db_book, key, value)

    db.commit()
    db.refresh(db_book)
    return db_book


@app.post(
    "/books/{book_id}/loan",
    response_model=schemas.LoanRecord,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def loan_book(
    book_id: int, loan_data: schemas.LoanRecordCreate, db: Session = Depends(get_db)
):
    """
    Loan a book to a borrower (requires API key).

    Business Logic:
    1. Verify the book exists
    2. Check if the book is already loaned out (not returned)
    3. Create a new loan record

    Internal Working:
    - Query filters for unreturned loans (is_returned=False)
    - If any exist, the book is currently loaned out
    - Otherwise, create a new LoanRecord with current timestamp

    Args:
        book_id: The book's database ID
        loan_data: Borrower information
        db: Database session (injected)

    Returns:
        The created loan record

    Raises:
        HTTPException: 404 if book not found, 400 if already loaned
    """
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {book_id} not found",
        )

    active_loan = (
        db.query(models.LoanRecord)
        .filter(
            models.LoanRecord.book_id == book_id, models.LoanRecord.is_returned == False
        )
        .first()
    )

    if active_loan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Book is already loaned out to {active_loan.borrower_name}",
        )

    db_loan = models.LoanRecord(
        book_id=book_id,
        borrower_name=loan_data.borrower_name,
        loaned_at=datetime.now(),
        is_returned=False,
    )
    db.add(db_loan)
    db.commit()
    db.refresh(db_loan)
    return db_loan


@app.post(
    "/loans/{loan_id}/return",
    response_model=schemas.LoanRecord,
    dependencies=[Depends(verify_api_key)],
)
async def return_book(loan_id: int, db: Session = Depends(get_db)):
    """
    Mark a book as returned (requires API key).

    Business Logic:
    1. Verify the loan record exists
    2. Check if the book was already returned
    3. Update the loan record with return timestamp

    Internal Working:
    - Sets is_returned to True
    - Records returned_at timestamp
    - Commits the update to database

    Args:
        loan_id: The loan record's database ID
        db: Database session (injected)

    Returns:
        The updated loan record

    Raises:
        HTTPException: 404 if loan not found, 400 if already returned
    """
    loan = db.query(models.LoanRecord).filter(models.LoanRecord.id == loan_id).first()
    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loan record with id {loan_id} not found",
        )

    if loan.is_returned is True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This book has already been returned",
        )

    loan.is_returned = True
    loan.returned_at = datetime.now()
    db.commit()
    db.refresh(loan)
    return loan


@app.get("/loans", response_model=List[schemas.LoanRecordWithBook])
async def list_loans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    List all loan records with optional filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        active_only: If True, only return unreturned loans
        db: Database session (injected)

    Returns:
        List of loan records with book and author information
    """
    query = db.query(models.LoanRecord)

    if active_only:
        query = query.filter(models.LoanRecord.is_returned == False)

    loans = query.offset(skip).limit(limit).all()
    return loans
