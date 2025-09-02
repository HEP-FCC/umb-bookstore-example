-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- for fuzzy string matching (trigram similarity)

-- Helper functions
-- This function concatenates all values of a JSONB object into a single string,
-- which can then be indexed for full-text search.
CREATE OR REPLACE FUNCTION jsonb_values_to_text(jsonb_in JSONB)
RETURNS TEXT LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    RETURN (SELECT string_agg(value, ' ') FROM jsonb_each_text(jsonb_in));
END;
$$;

-- Navigation tables (lookup tables for categorical data)
CREATE TABLE IF NOT EXISTS publishers (
    publisher_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS genres (
    genre_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS languages (
    language_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS formats (
    format_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Main books table
CREATE TABLE IF NOT EXISTS books (
    entity_id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),

    -- Core book fields
    name TEXT NOT NULL, -- Maps to title for search compatibility
    title TEXT NOT NULL,
    authors TEXT[] NOT NULL,
    isbn TEXT UNIQUE,
    publication_date DATE,
    pages INTEGER,
    price DECIMAL(10,2),
    description TEXT,
    cover_image_url TEXT,
    purchase_url TEXT,

    -- Foreign key relationships for navigation
    publisher_id INTEGER REFERENCES publishers(publisher_id) ON DELETE SET NULL,
    genre_id INTEGER REFERENCES genres(genre_id) ON DELETE SET NULL,
    language_id INTEGER REFERENCES languages(language_id) ON DELETE SET NULL,
    format_id INTEGER REFERENCES formats(format_id) ON DELETE SET NULL,

    -- Required fields for template framework
    metadata JSONB, -- Store additional flexible data

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_edited_at TIMESTAMPTZ DEFAULT NULL,
    edited_by_name TEXT DEFAULT NULL,

    -- Constraints
    CONSTRAINT chk_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_title_not_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT chk_updated_at_after_created CHECK (updated_at >= created_at),
    CONSTRAINT chk_edited_at_after_created CHECK (last_edited_at IS NULL OR last_edited_at >= created_at),
    CONSTRAINT chk_metadata_valid CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object'),
    CONSTRAINT chk_price_positive CHECK (price IS NULL OR price >= 0),
    CONSTRAINT chk_pages_positive CHECK (pages IS NULL OR pages > 0)
);

-- Search indexes for performance
CREATE INDEX IF NOT EXISTS idx_books_title_gin ON books USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_books_description_gin ON books USING GIN (description gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_books_authors_gin ON books USING GIN (authors);
CREATE INDEX IF NOT EXISTS idx_books_name_gin ON books USING GIN (name gin_trgm_ops);

-- Foreign key indexes
CREATE INDEX IF NOT EXISTS idx_books_publisher_id ON books(publisher_id);
CREATE INDEX IF NOT EXISTS idx_books_genre_id ON books(genre_id);
CREATE INDEX IF NOT EXISTS idx_books_language_id ON books(language_id);
CREATE INDEX IF NOT EXISTS idx_books_format_id ON books(format_id);

-- Other useful indexes
CREATE INDEX IF NOT EXISTS idx_books_uuid ON books(uuid);
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS idx_books_publication_date ON books(publication_date);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at DESC);

-- Navigation table search indexes
CREATE INDEX IF NOT EXISTS idx_publishers_name_gin ON publishers USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_genres_name_gin ON genres USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_languages_name_gin ON languages USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_formats_name_gin ON formats USING GIN (name gin_trgm_ops);

-- Temporal indexes
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
CREATE INDEX IF NOT EXISTS idx_books_updated_at ON books(updated_at);
CREATE INDEX IF NOT EXISTS idx_books_publication_date ON books(publication_date);
CREATE INDEX IF NOT EXISTS idx_books_created_at_desc ON books(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_books_updated_at_desc ON books(updated_at DESC);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_books_edited_id_composite ON books(last_edited_at DESC, entity_id);
CREATE INDEX IF NOT EXISTS idx_books_title_lower ON books(LOWER(title));

-- GIN index on an expression to enable fast fuzzy search on JSONB values
CREATE INDEX IF NOT EXISTS idx_books_metadata_search_gin ON books USING GIN (jsonb_values_to_text(metadata) gin_trgm_ops);

-- Additional JSONB indexes for metadata search optimization
CREATE INDEX IF NOT EXISTS idx_books_metadata_gin ON books USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_books_metadata_path_gin ON books USING GIN (metadata jsonb_path_ops);

-- Performance optimization: Set statistics targets
ALTER TABLE books ALTER COLUMN name SET STATISTICS 1000;
ALTER TABLE books ALTER COLUMN title SET STATISTICS 1000;
ALTER TABLE books ALTER COLUMN authors SET STATISTICS 1000;
ALTER TABLE books ALTER COLUMN metadata SET STATISTICS 1000;
ALTER TABLE books ALTER COLUMN updated_at SET STATISTICS 500;

-- Set statistics for lookup tables
ALTER TABLE publishers ALTER COLUMN name SET STATISTICS 100;
ALTER TABLE genres ALTER COLUMN name SET STATISTICS 100;
ALTER TABLE languages ALTER COLUMN name SET STATISTICS 100;
ALTER TABLE formats ALTER COLUMN name SET STATISTICS 100;
