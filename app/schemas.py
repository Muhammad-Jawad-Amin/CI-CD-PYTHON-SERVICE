from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AuthorBase(BaseModel):
    """
    Base schema with common author fields.

    This is the parent class to avoid field duplication.
    """

    name: str = Field(..., min_length=1, max_length=200)
    bio: Optional[str] = Field(None, max_length=2000)


class AuthorCreate(AuthorBase):
    """
    Schema for creating a new author.

    Used for POST requests. Inherits all fields from AuthorBase.
    The ... in Field(...) means the field is required.
    """

    pass


class Author(AuthorBase):
    """
    Schema for author responses.

    Includes database-generated fields like id.

    Internal Working:
    - from_attributes=True: Allows Pydantic to read data from ORM objects
    - SQLAlchemy objects have attributes like obj.id, obj.name
    - Pydantic extracts these attributes and validates them against the schema
    """

    id: int

    class ConfigDict:
        from_attributes = True


class AuthorWithBooks(Author):
    """
    Extended author schema including related books.

    Used when we want to return an author with their books list.
    Forward reference "Book" is used because Book schema is defined later.
    """

    books: List["Book"] = []

    class ConfigDict:
        from_attributes = True


class BookBase(BaseModel):
    """Base schema with common book fields."""

    title: str = Field(..., min_length=1, max_length=500)
    genre: str = Field(..., min_length=1, max_length=100)
    isbn: str = Field(..., min_length=10, max_length=13)


class BookCreate(BookBase):
    """
    Schema for creating a new book.

    Includes author_id to link the book to an author.
    """

    author_id: int = Field(..., gt=0)


class BookUpdate(BaseModel):
    """
    Schema for updating a book.

    All fields are optional to support partial updates.
    Only provided fields will be updated.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    genre: Optional[str] = Field(None, min_length=1, max_length=100)
    isbn: Optional[str] = Field(None, min_length=10, max_length=13)


class Book(BookBase):
    """
    Schema for book responses.

    Includes related author data using nested schema.
    """

    id: int
    author_id: int
    author: Author

    class ConfigDict:
        from_attributes = True


class BookWithLoans(Book):
    """
    Extended book schema including loan history.

    Used when we want to return a book with its loan records.
    """

    loan_records: List["LoanRecord"] = []

    class ConfigDict:
        from_attributes = True


class LoanRecordBase(BaseModel):
    """Base schema with common loan record fields."""

    borrower_name: str = Field(..., min_length=1, max_length=200)


class LoanRecordCreate(LoanRecordBase):
    """
    Schema for creating a loan record (borrowing a book).

    Only requires borrower name; book_id comes from URL path.
    """

    pass


class LoanRecord(LoanRecordBase):
    """
    Schema for loan record responses.

    Internal Working:
    - datetime objects are automatically serialized to ISO format strings
    - Optional[datetime] means returned_at can be null (for unreturned books)
    """

    id: int
    book_id: int
    loaned_at: datetime
    returned_at: Optional[datetime] = None
    is_returned: bool

    class ConfigDict:
        from_attributes = True


class LoanRecordWithBook(LoanRecord):
    """
    Extended loan record schema including book details.
    """

    book: Book

    class ConfigDict:
        from_attributes = True


AuthorWithBooks.model_rebuild()
BookWithLoans.model_rebuild()
