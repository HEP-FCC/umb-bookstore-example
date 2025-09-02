"""
Bookstore-specific data models for the Universal Metadata Browser.

This file defines the Pydantic models used to parse and validate
book data from JSON files.
"""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.logging_utils import get_logger

logger = get_logger()


class BaseEntityData(BaseModel, ABC):
    """
    Abstract base class for entity data that provides a common interface
    for all entity types that can be processed by the data import system.
    """

    @abstractmethod
    def get_all_metadata(self) -> dict[str, Any]:
        """
        Abstract method that must be implemented by all entity data classes.
        Should return all metadata for the entity as a dictionary.

        Returns:
            Dictionary containing all metadata fields for the entity
        """
        pass


class Book(BaseEntityData):
    """
    Pydantic model for a single book from the JSON dictionary.

    Handles all book-specific fields and validation logic.
    """

    # Required name field for template compatibility
    name: str = Field(default="Untitled Book")

    # Core book fields
    title: str | None = Field(default=None)
    authors: list[str] = Field(default_factory=list)
    isbn: str | None = Field(default=None)
    publication_date: date | str | None = Field(default=None)
    pages: int | None = Field(default=None)
    price: float | None = Field(default=None)
    description: str | None = Field(default=None)
    cover_image_url: str | None = Field(default=None)
    purchase_url: str | None = Field(default=None)

    # Navigation entity fields (will become foreign keys)
    publisher: str | None = Field(default=None)
    genre: str | None = Field(default=None)
    language: str | None = Field(default=None)
    format: str | None = Field(default=None)

    # Store all other fields as metadata
    raw_metadata: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator(
        "name",
        "title",
        "description",
        "isbn",
        "cover_image_url",
        "purchase_url",
        "publisher",
        "genre",
        "language",
        "format",
        mode="before",
    )
    @classmethod
    def handle_string_fields(cls, v: Any) -> str | None:
        """
        Handles string fields that might be missing, null, or need whitespace normalization.
        Returns None for null/empty values to avoid storing meaningless data.
        """
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        if isinstance(v, str):
            normalized = re.sub(r"\s+", " ", v.strip())
            return normalized if normalized else None
        return str(v) if v is not None else None

    @field_validator("authors", mode="before")
    @classmethod
    def handle_authors_field(cls, v: Any) -> list[str]:
        """
        Handles authors field which can be a string or list of strings.
        """
        if v is None:
            return []
        if isinstance(v, str):
            # Split on common separators and clean up
            authors = [
                author.strip() for author in re.split(r"[,;]", v) if author.strip()
            ]
            return authors
        if isinstance(v, list):
            return [str(author).strip() for author in v if str(author).strip()]
        return [str(v).strip()] if str(v).strip() else []

    @field_validator("pages", mode="before")
    @classmethod
    def handle_pages_field(cls, v: Any) -> int | None:
        """
        Handles pages field that might be missing or null.
        """
        if v is None or v == "":
            return None
        try:
            pages = int(v)
            return pages if pages > 0 else None
        except (ValueError, TypeError):
            logger.warning(f"Cannot parse pages value: {v}. Setting to None.")
            return None

    @field_validator("price", mode="before")
    @classmethod
    def handle_price_field(cls, v: Any) -> float | None:
        """
        Handles price field that might be missing or null.
        """
        if v is None or v == "":
            return None
        try:
            price = float(v)
            return price if price >= 0 else None
        except (ValueError, TypeError):
            logger.warning(f"Cannot parse price value: {v}. Setting to None.")
            return None

    @field_validator("publication_date", mode="before")
    @classmethod
    def handle_publication_date_field(cls, v: Any) -> date | str | None:
        """
        Handles publication_date field that can be a date string in various formats.
        """
        if v is None or v == "":
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            # Try to parse common date formats
            v = v.strip()
            try:
                # Try ISO format first (YYYY-MM-DD)
                from datetime import datetime

                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                try:
                    # Try alternative formats
                    return datetime.strptime(v, "%Y/%m/%d").date()
                except ValueError:
                    try:
                        return datetime.strptime(v, "%m/%d/%Y").date()
                    except ValueError:
                        # If parsing fails, store as string for manual review
                        logger.warning(
                            f"Cannot parse date format: {v}. Storing as string."
                        )
                        return v
        return str(v)

    @model_validator(mode="before")
    @classmethod
    def extract_metadata(cls, data: Any) -> Any:
        """
        Extract all fields not explicitly defined in the model into raw_metadata.
        """
        if not isinstance(data, dict):
            return data

        # Fields that are explicitly handled by the model
        core_fields = {
            "name",
            "title",
            "authors",
            "isbn",
            "publication_date",
            "pages",
            "price",
            "description",
            "cover_image_url",
            "purchase_url",
            "publisher",
            "genre",
            "language",
            "format",
        }

        # Create a copy of the data for manipulation
        processed_data = data.copy()
        raw_metadata = {}

        # Extract all non-core fields into raw_metadata
        for key, value in data.items():
            if key not in core_fields:
                raw_metadata[key] = value

        # Add raw_metadata to the processed data
        processed_data["raw_metadata"] = raw_metadata

        # Ensure title is set as name for compatibility
        if "title" in processed_data and processed_data["title"]:
            processed_data["name"] = processed_data["title"]
        elif "name" not in processed_data or not processed_data["name"]:
            processed_data["name"] = "Untitled Book"

        return processed_data

    def get_all_metadata(self) -> dict[str, Any]:
        """
        Returns all metadata including both core fields and raw_metadata.
        Excludes None values and navigation entity fields.
        """
        metadata: dict[str, Any] = {}

        # Add core fields that have values (excluding navigation fields)
        if self.title is not None:
            metadata["title"] = self.title
        if self.authors:
            metadata["authors"] = self.authors
        if self.isbn is not None:
            metadata["isbn"] = self.isbn
        if self.publication_date is not None:
            metadata["publication_date"] = str(self.publication_date)
        if self.pages is not None:
            metadata["pages"] = self.pages
        if self.price is not None:
            metadata["price"] = self.price
        if self.description is not None:
            metadata["description"] = self.description
        if self.cover_image_url is not None:
            metadata["cover_image_url"] = self.cover_image_url
        if self.purchase_url is not None:
            metadata["purchase_url"] = self.purchase_url

        # Add all raw metadata
        metadata.update(self.raw_metadata)

        return metadata


class BaseEntityCollection(BaseModel, ABC):
    """
    Abstract base class for entity collections that provides a common interface
    for all collection types that can be processed by the data import system.
    """

    @abstractmethod
    def get_entities(self) -> list[BaseEntityData]:
        """
        Abstract method that must be implemented by all entity collection classes.
        Should return a list of entities contained in the collection.

        Returns:
            List of BaseEntityData instances
        """
        pass


class BookCollection(BaseEntityCollection):
    """
    Pydantic model for the root of the book JSON dictionary.
    """

    books: list[Book]

    def get_entities(self) -> list[BaseEntityData]:
        """
        Return the list of books in this collection.

        Returns:
            List of Book instances
        """
        return self.books  # type: ignore[return-value]


class EntityTypeRegistry:
    """
    Registry for user-defined entity and collection classes.
    """

    _entity_classes: dict[str, type[BaseEntityData]] = {}
    _collection_classes: dict[str, type[BaseEntityCollection]] = {}
    _detection_rules: list[
        tuple[Callable[[dict[str, Any]], bool], type[BaseEntityCollection]]
    ] = []

    @classmethod
    def register_entity_class(
        cls, name: str, entity_class: type[BaseEntityData]
    ) -> None:
        """Register a custom entity class."""
        cls._entity_classes[name] = entity_class

    @classmethod
    def register_collection_class(
        cls, name: str, collection_class: type[BaseEntityCollection]
    ) -> None:
        """Register a custom collection class."""
        cls._collection_classes[name] = collection_class

    @classmethod
    def register_detection_rule(
        cls,
        detection_func: Callable[[dict[str, Any]], bool],
        collection_class: type[BaseEntityCollection],
    ) -> None:
        """
        Register a detection rule that determines which collection class to use.
        """
        cls._detection_rules.append((detection_func, collection_class))

    @classmethod
    def detect_collection_class(
        cls, raw_data: dict[str, Any]
    ) -> type[BaseEntityCollection] | None:
        """
        Auto-detect the data format and return the appropriate collection class.
        """
        for detection_func, collection_class in cls._detection_rules:
            try:
                if detection_func(raw_data):
                    logger.debug(f"Detected format for {collection_class.__name__}")
                    return collection_class
            except Exception as e:
                logger.warning(f"Detection failed for {collection_class.__name__}: {e}")
                continue

        logger.warning("No suitable data format detected")
        return None

    @classmethod
    def get_entity_class(cls, name: str) -> type[BaseEntityData] | None:
        """Get a registered entity class by name."""
        return cls._entity_classes.get(name)

    @classmethod
    def get_collection_class(cls, name: str) -> type[BaseEntityCollection] | None:
        """Get a registered collection class by name."""
        return cls._collection_classes.get(name)

    @classmethod
    def get_default_collection_class(cls) -> type[BaseEntityCollection] | None:
        """Get the first registered collection class as default."""
        if cls._collection_classes:
            return next(iter(cls._collection_classes.values()))
        return None

    @classmethod
    def list_registered_classes(cls) -> dict[str, Any]:
        """List all registered classes for debugging."""
        return {
            "entities": cls._entity_classes.copy(),
            "collections": cls._collection_classes.copy(),
            "detection_rules": [
                (str(func), cls_type) for func, cls_type in cls._detection_rules
            ],
        }


def _detect_book_format(raw_data: dict[str, Any]) -> bool:
    """
    Detect if raw_data matches the book collection format.
    """
    return "books" in raw_data and isinstance(raw_data["books"], list)


# Register the book classes
EntityTypeRegistry.register_entity_class("Book", Book)
EntityTypeRegistry.register_collection_class("BookCollection", BookCollection)
EntityTypeRegistry.register_detection_rule(_detect_book_format, BookCollection)
