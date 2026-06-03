# app.py
from fastapi import FastAPI, Query
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
import psycopg2, redis, json, time, re, os
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables

app = FastAPI()
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
        port=int(os.getenv("POSTGRES_PORT", 5432))
    )

# All categories known to the system — used for category detection
KNOWN_CATEGORIES = [
    "Bakery", "Beverages", "Breakfast", "Condiments", "Dairy",
    "Grains", "Produce", "Proteins", "Snacks", "Supplements"
]

CACHE_TTL_SECONDS = 300   # 5 minutes

def extract_query_constraints(query: str) -> dict:
    """
    Generic NLP constraint parser.
    Extracts structured filter criteria from a free-text query, covering:
      • max_price        e.g. "less than $4", "under $10", "$5 or less"
      • min_price        e.g. "more than $2", "over $6", "at least $3"
      • min_rating       e.g. "rated above 4.5", "at least 4 stars"
      • max_rating       e.g. "rating below 3", "under 2 stars"
      • category         e.g. "in Dairy", "Snacks products", "from Beverages"
      • description_kw   e.g. "description contains protein", "with omega in description"
    Returns a dict with only the keys that were detected.
    """
    c = {}

    # ── Price: upper bound ─────────────────────────────────────────────────────
    m = re.search(
        r'(?:less than|under|below|cheaper than|no more than|at most|within'
        r'|max(?:imum)?(?:\s+price)?(?:\s+of)?)\s*\$?\s*(\d+(?:\.\d+)?)',
        query, re.IGNORECASE)
    m2 = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:or less|or under|or below)', query, re.IGNORECASE)
    if m:  c["max_price"] = float(m.group(1))
    elif m2: c["max_price"] = float(m2.group(1))

    # ── Price: lower bound ─────────────────────────────────────────────────────
    m = re.search(
        r'(?:more than|over|above|at least|greater than|pricier than'
        r'|min(?:imum)?(?:\s+price)?(?:\s+of)?)\s*\$?\s*(\d+(?:\.\d+)?)',
        query, re.IGNORECASE)
    m2 = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:or more|or above|or over)', query, re.IGNORECASE)
    if m:  c["min_price"] = float(m.group(1))
    elif m2: c["min_price"] = float(m2.group(1))

    # ── Rating: minimum ────────────────────────────────────────────────────────
    m = re.search(
        r'(?:rat(?:ed?|ing)|stars?)\s*(?:above|over|at least|higher than|>=|=>|minimum|min\.?)\s*(\d+(?:\.\d+)?)',
        query, re.IGNORECASE)
    m2 = re.search(
        r'(?:at least|minimum|min\.?)\s*(\d+(?:\.\d+)?)\s*(?:stars?|rating)',
        query, re.IGNORECASE)
    m3 = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:stars?|rating)\s*(?:or\s+(?:above|more|higher|over))',
        query, re.IGNORECASE)
    if m:  c["min_rating"] = float(m.group(1))
    elif m2: c["min_rating"] = float(m2.group(1))
    elif m3: c["min_rating"] = float(m3.group(1))

    # ── Rating: maximum ────────────────────────────────────────────────────────
    m = re.search(
        r'(?:rat(?:ed?|ing)|stars?)\s*(?:below|under|less than|at most|lower than|<=|=<|maximum|max\.?)\s*(\d+(?:\.\d+)?)',
        query, re.IGNORECASE)
    if m: c["max_rating"] = float(m.group(1))

    # ── Category ───────────────────────────────────────────────────────────────
    for cat in KNOWN_CATEGORIES:
        negated = re.search(
            r'(?:non-|free|without|no\s+|not\s+)' + re.escape(cat),
            query, re.IGNORECASE)
        if negated:
            continue
        if re.search(
            r'(?:in|from|under|category[:\s]+)\s*' + re.escape(cat) + r'\b'
            r'|\b' + re.escape(cat) + r'\s+(?:products?|items?|food|section|category)',
            query, re.IGNORECASE):
            c["category"] = cat
            break

    # ── Description keyword (explicit description mentions only) ───────────────
    m = re.search(
        r'description\s+(?:has|contains?|includes?|mentions?)\s+["\']?(\w+)["\']?'
        r'|(?:containing|mentioning)\s+["\']?(\w+)["\']?\s+in\s+(?:the\s+)?description'
        r'|with\s+["\']?(\w+)["\']?\s+in\s+(?:the\s+)?description',
        query, re.IGNORECASE)
    if m:
        kw = next((g for g in m.groups() if g), None)
        if kw:
            c["description_kw"] = kw

    return c

# ─────────────────────────────────────────────────────────────────────────────
# CACHE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/setup")
def setup():
    cache.flushdb()
    return {"message": "Cache cleared successfully."}

@app.get("/cache/contents")
def cache_contents():
    """Return all Redis cache entries with their parameters, TTL, and cached products."""
    keys = sorted(cache.keys("combined:*"))
    entries = []
    for key in keys:
        ttl = cache.ttl(key)
        raw = cache.get(key)
        try:
            results = json.loads(raw)
            result_count = len(results)
            products = [{"name": r[1], "price": r[3], "rating": r[6]} for r in results]
        except Exception:
            result_count = 0
            products = []

        # Parse key back to readable params: combined:term:max_price:min_rating:desc:category
        parts = key.split(":", 5)
        params = {}
        if len(parts) == 6:
            params = {
                "query":       parts[1] if parts[1] else "(empty)",
                "max_price":   f"${parts[2]}",
                "min_rating":  f"⭐ {parts[3]}",
                "description": parts[4] if parts[4] else "(none)",
                "category":    parts[5] if parts[5] else "All",
            }

        entries.append({
            "key":          key,
            "params":       params,
            "ttl_seconds":  ttl,
            "result_count": result_count,
            "products":     products,
        })

    return {"entries": entries, "total": len(entries)}

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 1: Traditional SQL
#   • Uses ONLY sidebar criteria (price, rating, description wildcard, category)
#   • The text query from the right panel is NOT used here
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/search/traditional")
def traditional_search(
    max_price: float = 50.0,
    min_rating: float = 0.0,
    description: str = "",
    category: str = "All"
):
    conn = get_db_connection(); cur = conn.cursor()
    query_str = ("SELECT product_id, name, category, price, stock_quantity, description, rating "
                 "FROM products WHERE price <= %s AND rating >= %s")
    query_args = [max_price, min_rating]

    if description.strip():
        desc_pattern = description.replace("*", "%")
        query_str += " AND description ILIKE %s"
        query_args.append(f"%{desc_pattern}%")
    if category != "All":
        query_str += " AND category = %s"
        query_args.append(category)

    cur.execute(query_str, tuple(query_args))
    results = cur.fetchall(); cur.close(); conn.close()
    return {"results": results}

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 2: Vector Search Only
#   • Uses ONLY the text query for semantic/vector similarity (pgvector)
#   • No sidebar SQL criteria — but the generic NLP parser extracts any
#     structured constraints mentioned in the query and applies them as SQL
#     e.g. "organic products under $5 rated above 4 in Breakfast"
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/search/vector")
def vector_search(
    q: str = Query(None)
):
    if not q or not q.strip():
        return {"engine": "DB", "latency_ms": 0, "results": [], "extracted": {}}

    start_time = time.time()
    conn = get_db_connection(); cur = conn.cursor()

    # Generic NLP parse: extract all constraint types from natural language
    cx = extract_query_constraints(q)

    query_vector = embedding_model.encode(q).tolist()
    query_str = ("SELECT product_id, name, category, price, stock_quantity, description, rating, "
                 "(description_vector <=> %s::vector) AS distance "
                 "FROM products WHERE 1=1")
    query_args = [query_vector]

    if "max_price"      in cx: query_str += " AND price <= %s";            query_args.append(cx["max_price"])
    if "min_price"      in cx: query_str += " AND price >= %s";            query_args.append(cx["min_price"])
    if "min_rating"     in cx: query_str += " AND rating >= %s";           query_args.append(cx["min_rating"])
    if "max_rating"     in cx: query_str += " AND rating <= %s";           query_args.append(cx["max_rating"])
    if "category"       in cx: query_str += " AND category = %s";          query_args.append(cx["category"])
    if "description_kw" in cx: query_str += " AND description ILIKE %s";  query_args.append(f"%{cx['description_kw']}%")

    query_str += " ORDER BY distance ASC LIMIT 3;"
    cur.execute(query_str, tuple(query_args))

    results = cur.fetchall(); cur.close(); conn.close()
    return {"engine": "DB", "latency_ms": round((time.time() - start_time) * 1000, 2),
            "results": results, "extracted": cx}

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 3: SQL + Vector Search  (Redis cached)
#   • Sidebar criteria narrow the candidate pool first (same SQL as Engine 1)
#   • Text query then re-ranks those candidates by vector similarity
#   • Result = semantically best matches WITHIN the SQL-filtered set
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/search/combined")
def combined_search(
    q: str = Query(None),
    max_price: float = 50.0,
    min_rating: float = 0.0,
    description: str = "",
    category: str = "All"
):
    if not q or not q.strip():
        return {"engine": "DB", "latency_ms": 0, "results": []}

    start_time = time.time()
    conn = get_db_connection(); cur = conn.cursor()

    search_term = q.strip().lower()
    cache_key = f"combined:{search_term}:{max_price}:{min_rating}:{description.lower()}:{category.lower()}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"engine": "Redis", "latency_ms": 0.5, "results": json.loads(cached_data)}

    # Step 1: Apply sidebar SQL criteria as the WHERE filter
    query_vector = embedding_model.encode(q).tolist()
    query_str = ("SELECT product_id, name, category, price, stock_quantity, description, rating, "
                 "(description_vector <=> %s::vector) AS distance "
                 "FROM products WHERE price <= %s AND rating >= %s")
    query_args = [query_vector, max_price, min_rating]

    if description.strip():
        desc_pattern = description.replace("*", "%")
        query_str += " AND description ILIKE %s"
        query_args.append(f"%{desc_pattern}%")
    if category != "All":
        query_str += " AND category = %s"
        query_args.append(category)

    # Step 2: Vector similarity ranks the SQL-filtered candidates
    query_str += " ORDER BY distance ASC LIMIT 3;"
    cur.execute(query_str, tuple(query_args))

    results = cur.fetchall(); cur.close(); conn.close()
    cache.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(results, default=str))
    return {"engine": "DB", "latency_ms": round((time.time() - start_time) * 1000, 2), "results": results}

# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT MANAGEMENT
#   • POST /products/add — generate embedding from description, insert to PG
# ─────────────────────────────────────────────────────────────────────────────
class ProductIn(BaseModel):
    name:           str
    category:       str
    price:          float
    stock_quantity: int
    rating:         float
    description:    str

@app.post("/products/add")
def add_product(product: ProductIn):
    # 1. Generate 384-dim sentence embedding from the description
    embedding = embedding_model.encode(product.description).tolist()

    conn = get_db_connection(); cur = conn.cursor()

    # 2. Get the next available product_id
    cur.execute("SELECT COALESCE(MAX(product_id), 0) + 1 FROM products")
    new_id = cur.fetchone()[0]

    # 3. Insert into Postgres with the pgvector column
    cur.execute(
        "INSERT INTO products "
        "(product_id, name, category, price, stock_quantity, rating, description, description_vector) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)",
        (new_id, product.name, product.category, product.price,
         product.stock_quantity, product.rating, product.description, embedding)
    )
    conn.commit(); cur.close(); conn.close()

    # 4. Flush cache — catalog has changed, stale results must be evicted
    cache.flushdb()

    return {
        "message":          f"Product '{product.name}' added successfully.",
        "product_id":       new_id,
        "embedding_dims":   len(embedding),
        "embedding_preview": [round(v, 6) for v in embedding[:8]],
    }
