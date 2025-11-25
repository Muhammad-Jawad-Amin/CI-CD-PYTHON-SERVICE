from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean


class Author(Base):
    """
    Author model representing book authors.

    Relationships:
    - One author can have many books (one-to-many)

    The relationship() function creates a bidirectional link:
    - Author.books: List of Book objects for this author
    - back_populates connects to Book.author
    """

    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    bio = Column(String, nullable=True)

    books = relationship(
        "Book",
        back_populates="author",
        cascade="all, delete-orphan",
    )


class Book(Base):
    """
    Book model representing library books.

    Relationships:
    - Many books belong to one author (many-to-one)
    - One book can have many loan records (one-to-many)

    Internal Working:
    - ForeignKey creates a database constraint ensuring author_id references authors.id
    - relationship() creates Python object references without additional queries
    - back_populates ensures bidirectional navigation (book.author and author.books)
    """

    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    genre = Column(String, nullable=False, index=True)
    isbn = Column(String, unique=True, nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)

    author = relationship("Author", back_populates="books")

    loan_records = relationship(
        "LoanRecord",
        back_populates="book",
        cascade="all, delete-orphan",
    )


class LoanRecord(Base):
    """
    LoanRecord model representing book loans.

    Relationships:
    - Many loan records belong to one book (many-to-one)

    Business Logic:
    - is_returned tracks whether the book has been returned
    - loaned_at records when the book was borrowed
    - returned_at records when the book was returned (nullable)

    Internal Working:
    - DateTime columns store timezone-aware timestamps
    - Boolean default=False ensures new loans are marked as not returned
    - The combination of book_id and is_returned can determine book availability
    """

    __tablename__ = "loan_records"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    borrower_name = Column(String, nullable=False)
    loaned_at = Column(DateTime, default=datetime.now, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    is_returned = Column(Boolean, default=False, nullable=False)

    book = relationship("Book", back_populates="loan_records")
