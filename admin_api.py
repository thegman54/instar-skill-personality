"""
Personality skill — admin API routes for traits CRUD and YAML import.

Handler signature: async handler(pool, body=None, **regex_groups)
Returns: dict (JSON response). Use __status key for non-200 status codes.
"""

import hashlib

import structlog
import yaml

log = structlog.get_logger()

VALID_CATEGORIES = {'identity', 'tone', 'stance', 'boundary', 'phrase', 'situational'}


async def list_traits(pool, body=None, slug=None, **kw):
    """List all personality traits for a profile."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, category, subcategory, content, tags, weight, stable, source,
                      created_at, updated_at
               FROM personality_traits
               WHERE profile_slug = $1
               ORDER BY stable DESC, category, weight DESC""",
            slug,
        )
    traits = [
        {
            "id": str(row['id']),
            "category": row['category'],
            "subcategory": row['subcategory'],
            "content": row['content'],
            "tags": row['tags'] or [],
            "weight": row['weight'],
            "stable": row['stable'],
            "source": row['source'],
            "created_at": row['created_at'].isoformat(),
            "updated_at": row['updated_at'].isoformat(),
        }
        for row in rows
    ]
    return {"profile_slug": slug, "count": len(traits), "traits": traits}


async def create_trait(pool, body=None, slug=None, **kw):
    """Create a new personality trait."""
    if not body:
        return {"__status": 400, "detail": "Request body required"}

    content = (body.get('content') or '').strip()
    if not content:
        return {"__status": 400, "detail": "content is required"}

    category = body.get('category', 'tone')
    if category not in VALID_CATEGORIES:
        return {"__status": 400, "detail": f"category must be one of: {VALID_CATEGORIES}"}

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    tags = body.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]

    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO personality_traits
                    (profile_slug, category, subcategory, content, content_hash, tags, weight, stable, source)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING id""",
                slug,
                category,
                body.get('subcategory'),
                content,
                content_hash,
                tags,
                float(body.get('weight', 1.0)),
                bool(body.get('stable', False)),
                body.get('source', 'manual'),
            )
            return {"id": str(row['id']), "status": "created"}
        except Exception as e:
            if "unique" in str(e).lower():
                return {"__status": 409, "detail": "Duplicate trait content for this profile"}
            raise


async def update_trait(pool, body=None, slug=None, trait_id=None, **kw):
    """Update an existing personality trait."""
    if not body:
        return {"__status": 400, "detail": "Request body required"}

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM personality_traits WHERE id = $1::uuid AND profile_slug = $2",
            trait_id, slug,
        )
        if not existing:
            return {"__status": 404, "detail": "Trait not found"}

        updates = []
        params = [trait_id, slug]
        idx = 3

        if 'content' in body:
            content = body['content'].strip()
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            updates.append(f"content = ${idx}")
            params.append(content)
            idx += 1
            updates.append(f"content_hash = ${idx}")
            params.append(content_hash)
            idx += 1

        if 'category' in body:
            updates.append(f"category = ${idx}")
            params.append(body['category'])
            idx += 1

        if 'tags' in body:
            tags = body['tags']
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            updates.append(f"tags = ${idx}")
            params.append(tags)
            idx += 1

        if 'weight' in body:
            updates.append(f"weight = ${idx}")
            params.append(float(body['weight']))
            idx += 1

        if 'stable' in body:
            updates.append(f"stable = ${idx}")
            params.append(bool(body['stable']))
            idx += 1

        if not updates:
            return {"status": "no changes"}

        updates.append("updated_at = NOW()")
        sql = f"UPDATE personality_traits SET {', '.join(updates)} WHERE id = $1::uuid AND profile_slug = $2"
        await conn.execute(sql, *params)

    return {"status": "updated"}


async def delete_trait(pool, body=None, slug=None, trait_id=None, **kw):
    """Delete a personality trait."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM personality_traits WHERE id = $1::uuid AND profile_slug = $2",
            trait_id, slug,
        )
    if result == "DELETE 0":
        return {"__status": 404, "detail": "Trait not found"}
    return {"status": "deleted"}


async def import_traits(pool, body=None, slug=None, **kw):
    """Import traits from YAML data."""
    if not body:
        return {"__status": 400, "detail": "Request body required"}

    yaml_content = body.get('yaml', '')
    if not yaml_content:
        return {"__status": 400, "detail": "yaml field is required"}

    try:
        parsed = yaml.safe_load(yaml_content)
    except Exception as e:
        return {"__status": 400, "detail": f"Invalid YAML: {e}"}

    traits_data = parsed.get('traits', [])
    if not traits_data:
        return {"__status": 400, "detail": "No traits found in YAML"}

    created = 0
    skipped = 0
    async with pool.acquire() as conn:
        for t in traits_data:
            content = (t.get('content') or '').strip()
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            tags = t.get('tags', [])
            try:
                await conn.execute(
                    """INSERT INTO personality_traits
                        (profile_slug, category, subcategory, content, content_hash, tags, weight, stable, source)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'import')
                       ON CONFLICT (profile_slug, content_hash) DO NOTHING""",
                    slug,
                    t.get('category', 'tone'),
                    t.get('subcategory'),
                    content,
                    content_hash,
                    tags,
                    float(t.get('weight', 1.0)),
                    bool(t.get('stable', False)),
                )
                created += 1
            except Exception:
                skipped += 1

    return {"created": created, "skipped": skipped}


# =============================================================================
# ROUTE TABLE
# =============================================================================

routes = [
    ("GET",    r"/(?P<slug>[\w-]+)/traits$",                        list_traits),
    ("POST",   r"/(?P<slug>[\w-]+)/traits$",                        create_trait),
    ("POST",   r"/(?P<slug>[\w-]+)/traits/(?P<trait_id>[\w-]+)$",   update_trait),
    ("DELETE", r"/(?P<slug>[\w-]+)/traits/(?P<trait_id>[\w-]+)$",   delete_trait),
    ("POST",   r"/(?P<slug>[\w-]+)/import$",                        import_traits),
]
