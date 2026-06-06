CREATE TABLE IF NOT EXISTS personality_traits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_slug VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(100),
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    tags TEXT[] DEFAULT '{}',
    weight FLOAT DEFAULT 1.0,
    stable BOOLEAN DEFAULT FALSE,
    source VARCHAR(255) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(profile_slug, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_traits_profile_cat ON personality_traits(profile_slug, category);
CREATE INDEX IF NOT EXISTS idx_traits_profile_weight ON personality_traits(profile_slug, weight DESC);
CREATE INDEX IF NOT EXISTS idx_traits_tags ON personality_traits USING GIN(tags);
