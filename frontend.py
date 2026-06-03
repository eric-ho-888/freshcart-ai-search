import streamlit as st
import requests
import urllib.parse
import os

st.set_page_config(layout="wide")
st.title("🛒 FreshCart Multi-Modal Search")

CATEGORIES = [
    "Bakery", "Beverages", "Breakfast", "Condiments", "Dairy",
    "Grains", "Produce", "Proteins", "Snacks", "Supplements"
]

# ─────────────────────────────────────────────────────────────────────────────
# Read persistent state from URL query params
#   ?tab=search|cache|add   — active tab
#   ?q=organic+products     — search query (survives tab navigation)
# ─────────────────────────────────────────────────────────────────────────────
active_tab = st.query_params.get("tab", "search")
if active_tab not in ("search", "cache", "add", "arch"):
    active_tab = "search"

# On a fresh page load (tab click = new session), restore query from URL.
# On a Streamlit rerun (slider moved etc.), session_state already has the value.
if "search_q" not in st.session_state:
    st.session_state.search_q = st.query_params.get("q", "")

# ─────────────────────────────────────────────────────────────────────────────
# Tab bar — pure HTML links so font size is fully under our control.
# Each link carries BOTH the target tab AND the current query so neither
# is lost during browser navigation.
# ─────────────────────────────────────────────────────────────────────────────
_q_enc = urllib.parse.quote_plus(st.session_state.search_q)
_q_part = f"&q={_q_enc}" if st.session_state.search_q else ""

def _tab_link(label: str, tab_id: str) -> str:
    active   = active_tab == tab_id
    color    = "#ff4b4b" if active else "#555"
    weight   = "700"     if active else "600"
    underline = "3px solid #ff4b4b" if active else "3px solid transparent"
    href = f"?tab={tab_id}{_q_part}"
    return (
        f'<a href="{href}" style="'
        f'  font-size:1.45rem; font-weight:{weight}; color:{color};'
        f'  text-decoration:none; border-bottom:{underline};'
        f'  padding:10px 28px 12px; margin-right:2px; display:inline-block;'
        f'  transition:color .2s, border-color .2s;">'
        f'{label}</a>'
    )

st.markdown(
    '<div style="border-bottom:2px solid #e0e0e0; margin-bottom:6px;">'
    + _tab_link("🔍  Search",       "search")
    + _tab_link("📦  Cache Viewer", "cache")
    + _tab_link("➕  Add Product",  "add")
    + _tab_link("🏗️  Architecture", "arch")
    + "</div>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# SQL Preview builder
# ─────────────────────────────────────────────────────────────────────────────
def build_sql_preview(max_price, min_rating, description, category):
    conditions = [f"price <= {max_price:.2f}"]
    if min_rating > 0:
        conditions.append(f"rating >= {min_rating:.1f}")
    if description.strip():
        desc_pattern = description.replace("*", "%")
        conditions.append(f"description ILIKE '%{desc_pattern}%'")
    if category != "All":
        conditions.append(f"category = '{category}'")
    where_clause = "\n  AND ".join(conditions)
    return (
        "SELECT product_id, name, category,\n"
        "       price, stock_quantity,\n"
        "       description, rating\n"
        "FROM products\n"
        f"WHERE {where_clause};"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    if st.button("🔄 Reset Cache"):
        requests.post("http://127.0.0.1:8000/setup")
        st.success("Cache cleared!")

    st.caption("🔍 Search Filters")
    max_price    = st.slider("Max Price ($)", 1.0, 50.0, 50.0, step=0.5)
    min_rating   = st.slider("Min Rating ⭐", 0.0, 5.0, 0.0, step=0.1)
    description  = st.text_input(
        "Description (supports * wildcard)",
        placeholder="e.g. organic* or *protein*"
    )
    selected_cat = st.selectbox("Category", ["All"] + CATEGORIES)

    st.divider()
    st.caption("📋 SQL Preview — Traditional SQL (sidebar criteria only)")
    st.code(build_sql_preview(max_price, min_rating, description, selected_cat), language="sql")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — SEARCH
# ═════════════════════════════════════════════════════════════════════════════
if active_tab == "search":
    st.subheader("🔍 Search Products In Catalog")

    # ── Search input + ✕ clear button on the same row ─────────────────────────
    input_col, clear_col = st.columns([22, 1])
    with input_col:
        # key="search_q" binds to st.session_state.search_q automatically.
        # Value is already pre-loaded from URL params above.
        query = st.text_input(
            "In addition to the criteria selected on the sidebar, what are you looking for today?",
            key="search_q",
        )
    with clear_col:
        # Small vertical spacer to align the button with the input field
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if st.button("✕", help="Clear search query", key="clear_q_btn"):
            st.session_state.search_q = ""
            # Remove q from URL and stay on search tab
            st.query_params["tab"] = "search"
            if "q" in st.query_params:
                del st.query_params["q"]
            st.rerun()

    search_clicked = st.button("🔍 Search Now", key="search_btn")

    if search_clicked:
        # Persist the query in the URL so tab navigation won't lose it
        st.query_params["tab"] = "search"
        st.query_params["q"]   = query

    col1, col2, col3 = st.columns(3)

    params_sql      = {"max_price": max_price, "min_rating": min_rating,
                       "description": description, "category": selected_cat}
    params_combined = {**params_sql, "q": query}
    params_vector   = {"q": query}

    if search_clicked:

        with col1:
            st.subheader("🕵️‍♂️ 1. Traditional SQL")
            st.caption("Sidebar criteria only — no text query.")
            res = requests.get("http://127.0.0.1:8000/search/traditional", params=params_sql).json()
            if res["results"]:
                for item in res["results"]:
                    st.markdown(f"**{item[1]}** | ${float(item[3]):.2f} | Stock: {item[4]} | ⭐ {item[6]}")
                    st.caption(f"📄 {item[5]}")
            else:
                st.info("No results found.")

        if query.strip():

            with col2:
                st.subheader("🧠 2. Vector Search Only")
                st.caption("Text query → pgvector semantic search — no sidebar SQL criteria")
                res2 = requests.get("http://127.0.0.1:8000/search/vector", params=params_vector).json()

                extracted = res2.get("extracted", {})
                if extracted:
                    label_map = {
                        "max_price":      lambda v: f"price ≤ ${v:.2f}",
                        "min_price":      lambda v: f"price ≥ ${v:.2f}",
                        "min_rating":     lambda v: f"rating ≥ {v}",
                        "max_rating":     lambda v: f"rating ≤ {v}",
                        "category":       lambda v: f"category = {v}",
                        "description_kw": lambda v: f"description has '{v}'",
                    }
                    badges = [label_map[k](v) for k, v in extracted.items() if k in label_map]
                    st.info(f"🤖 AI auto-detected: **{' | '.join(badges)}**")

                if res2["results"]:
                    sorted2 = sorted(res2["results"], key=lambda x: float(x[7]))
                    for item in sorted2:
                        similarity = round(1 - float(item[7]), 3)
                        st.markdown(
                            f"**{item[1]}** | ${float(item[3]):.2f} | "
                            f"Stock: {item[4]} | ⭐ {item[6]} | Similarity: {similarity}"
                        )
                        st.caption(f"📄 {item[5]}")
                else:
                    st.info("No results found.")

            with col3:
                st.subheader("⚡ 3. SQL + Vector Search")
                st.caption("Sidebar SQL filters first → vector re-ranks survivors, cached in Redis")
                res3 = requests.get("http://127.0.0.1:8000/search/combined", params=params_combined).json()
                is_cache_hit = res3.get("engine") == "Redis"

                lat_col, status_col = st.columns(2)
                with lat_col:
                    st.markdown(f"### ⏱ {res3['latency_ms']} ms")
                with status_col:
                    st.markdown("### 🔥 Cache Hit" if is_cache_hit else "### ❄️ Cache Miss")

                if res3["results"]:
                    sorted3 = sorted(res3["results"], key=lambda x: float(x[7]))
                    for item in sorted3:
                        similarity = round(1 - float(item[7]), 3)
                        st.markdown(
                            f"**{item[1]}** | ${float(item[3]):.2f} | "
                            f"Stock: {item[4]} | ⭐ {item[6]} | Similarity: {similarity}"
                        )
                        st.caption(f"📄 {item[5]}")
                else:
                    st.info("No results within your sidebar criteria match the query semantically.")
        else:
            with col2:
                st.subheader("🧠 2. Vector Search Only")
                st.info("Enter a search query above to activate vector search.")
            with col3:
                st.subheader("⚡ 3. SQL + Vector Search")
                st.info("Enter a search query above to activate SQL + vector search.")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CACHE VIEWER
# ═════════════════════════════════════════════════════════════════════════════
elif active_tab == "cache":
    st.subheader("📦 Redis Cache Viewer")
    st.caption("Shows all active entries in the Redis cache for the SQL + Vector Search engine.")

    btn_col1, btn_col2, _ = st.columns([1, 1, 5])
    with btn_col1:
        st.button("🔄 Refresh", key="refresh_cache")
    with btn_col2:
        if st.button("🗑️ Clear All", key="clear_cache"):
            requests.post("http://127.0.0.1:8000/setup")
            st.success("Cache cleared!")

    cache_data = requests.get("http://127.0.0.1:8000/cache/contents").json()

    if cache_data["total"] == 0:
        st.info("🗄️ Cache is currently empty — run some searches on the Search tab first!")
    else:
        st.success(f"**{cache_data['total']} entr{'y' if cache_data['total'] == 1 else 'ies'}** currently in Redis cache")

        for entry in cache_data["entries"]:
            params  = entry.get("params", {})
            ttl     = entry["ttl_seconds"]
            count   = entry["result_count"]
            ttl_bar = "🟩" * min(ttl // 10, 6) + "⬜" * (6 - min(ttl // 10, 6))

            header = (
                f"🔑 Query: **{params.get('query', '?')}** | "
                f"Max: {params.get('max_price','?')} | "
                f"Rating: {params.get('min_rating','?')} | "
                f"Desc: {params.get('description','?')} | "
                f"Cat: {params.get('category','?')} | "
                f"📦 {count} results | ⏳ TTL: {ttl}s {ttl_bar}"
            )

            with st.expander(header):
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Query",      params.get("query", "—"))
                c2.metric("Max Price",  params.get("max_price", "—"))
                c3.metric("Min Rating", params.get("min_rating", "—"))
                c4.metric("Category",   params.get("category", "—"))
                c5.metric("TTL (s)",    ttl)

                if entry["products"]:
                    st.write("**Cached Products:**")
                    for p in entry["products"]:
                        st.markdown(f"- **{p['name']}** | ${float(p['price']):.2f} | ⭐ {p['rating']}")
                else:
                    st.caption("No products in this cache entry.")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — ARCHITECTURE DIAGRAM
# ═════════════════════════════════════════════════════════════════════════════
elif active_tab == "arch":
    st.subheader("🏗️ Application Architecture")
    st.caption(
        "End-to-end overview of all processes, services, and data flows "
        "that power the FreshCart Multi-Modal Search application."
    )

    _img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture_diagram.png")
    _l, _mid, _r = st.columns([1, 5, 1])
    with _mid:
        st.image(
            _img_path,
            use_column_width=True,
            caption="FreshCart Multi-Modal Search — Application Architecture",
        )

    st.divider()

    # ── Layer-by-layer legend ─────────────────────────────────────────────────────
    st.markdown("### 📖 Layer-by-Layer Breakdown")

    leg1, leg2 = st.columns(2)

    with leg1:
        st.markdown("""
**💻 Frontend — Streamlit** `localhost:8501`
- Interactive UI built with Python + Streamlit
- Sidebar: SQL filter controls (price, rating, description, category)
- 3 search result columns + Cache Viewer + Add Product tabs
- Run: `streamlit run frontend.py`

---

**⚙️ Backend API — FastAPI + Uvicorn** `localhost:8000`
- REST API layer between Streamlit and the databases
- Hosts all 3 search engines as separate endpoints
- Loads `SentenceTransformer` (`all-MiniLM-L6-v2`) at startup
  to generate **384-dimensional** word embeddings
- Run: `uvicorn app:app --reload`

---

**🧠 NLP Constraint Extractor** *(inside FastAPI)*
- Parses free-text queries for structured filters:
  `price < $4`, `rating above 4.5`, `in Dairy`, etc.
- Applied only in **Vector Search Only** (Engine 2)
""")

    with leg2:
        st.markdown("""
**🔍 Engine ① — Traditional SQL**
- Uses only **sidebar criteria** as SQL `WHERE` conditions
- `ILIKE` pattern matching on description (wildcard supported)
- No embeddings, no ML, no caching
- Endpoint: `GET /search/traditional`

---

**🧠 Engine ② — Vector Search Only**
- Encodes the **text query** into a 384-dim vector
- Finds semantically similar products using **pgvector cosine distance**
- No sidebar SQL filters applied
- NLP extractor parses any constraints mentioned in the query text
- Endpoint: `GET /search/vector`

---

**⚡ Engine ③ — SQL + Vector Search (Hybrid)**
- **Step 1:** Sidebar SQL filters narrow the candidate pool
- **Step 2:** pgvector ranks survivors by semantic similarity
- **Step 3:** Result cached in **Redis** for 5 minutes (`SETEX 300`)
- Cache key: `combined:<query>:<price>:<rating>:<desc>:<category>`
- Endpoint: `GET /search/combined`
""")

    st.divider()
    st.markdown("### 🐳 Docker Infrastructure")
    d1, d2 = st.columns(2)
    with d1:
        st.info("""
**PostgreSQL 15 + pgvector extension**
- Port: `5432`
- Database: `postgres` / User: `postgres`
- Table: `products` (100 rows + embeddings)
- Column: `description_vector vector(384)`
- Start: `docker compose up -d postgres`
""")
    with d2:
        st.info("""
**Redis 7**
- Port: `6379`
- Stores JSON-serialised search results
- Key pattern: `combined:*`
- TTL: **300 seconds (5 minutes)**
- Start: `docker compose up -d redis`
""")

    st.divider()
    st.markdown("### ✅ Pre-requisites")
    st.caption("Everything you need installed and running before starting the application.")

    pre1, pre2 = st.columns(2)
    with pre1:
        st.markdown("""
**🐳 Docker Desktop**
- Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- Required to run **PostgreSQL 15** and **Redis 7** as containers
- Ensure Docker engine is running before launching the app
- Verify: `docker --version` and `docker compose version`

---

**🐍 Python 3.9+ (via Miniconda or Anaconda)**
- Download Miniconda: [docs.conda.io](https://docs.conda.io/en/latest/miniconda.html)
- Create a dedicated environment:
  ```bash
  conda create -n freshcart_ai python=3.11
  conda activate freshcart_ai
  ```

---

**📦 Required Python Packages**
```bash
pip install streamlit fastapi uvicorn \\
    psycopg2-binary redis \\
    sentence-transformers pgvector
```
""")

    with pre2:
        st.markdown("""
**💾 Hardware Requirements**
- **RAM:** ≥ 4 GB recommended
  - SentenceTransformer model: ~90 MB
  - PostgreSQL container: ~200 MB
  - Redis container: ~30 MB
- **Disk:** ≥ 2 GB free space
- **CPU:** Any modern multi-core processor

---

**🌐 Internet Access (first run only)**
- The `all-MiniLM-L6-v2` model (~90 MB) is downloaded
  automatically from HuggingFace on first startup
- Subsequent runs use the locally cached model

---

**🖥️ Web Browser**
- Any modern browser: Chrome, Firefox, Edge, Safari
- Used to access the Streamlit UI at `localhost:8501`

---

**📁 Project Files**
- `app.py` — FastAPI backend
- `frontend.py` — Streamlit UI
- `docker-compose.yml` — PostgreSQL + Redis services
- `generate_dataset.py` — seed 100 products with embeddings
""")

    st.divider()
    st.markdown("### ▶️ How to Start All Services")
    st.code("""
# 1. Start Docker containers (Postgres + Redis)
docker compose up -d

# 2. (First time only) Seed the database with 100 products + embeddings
python generate_dataset.py

# 3. Start FastAPI backend (Uvicorn with hot-reload)
uvicorn app:app --reload --port 8000

# 4. Start Streamlit frontend
streamlit run frontend.py
""", language="bash")
# ═════════════════════════════════════════════════════════════════════════════
elif active_tab == "add":
    st.subheader("➕ Add New Product to Catalog")
    st.caption(
        "Fill in the product details below. The app will automatically run the description "
        "through **all-MiniLM-L6-v2** to generate a **384-dimensional word embedding** "
        "before saving the product to PostgreSQL — making it instantly searchable by vector similarity."
    )

    with st.form("add_product_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)

        with col_a:
            p_name     = st.text_input("Product Name *", placeholder="e.g. Organic Chia Protein Bars")
            p_category = st.selectbox("Category *", CATEGORIES)
            p_price    = st.number_input("Price ($) *", min_value=0.01, max_value=999.99,
                                          value=9.99, step=0.01, format="%.2f")
        with col_b:
            p_stock  = st.number_input("Stock Quantity *", min_value=0, max_value=10000, value=50)
            p_rating = st.slider("Initial Rating ⭐", 0.0, 5.0, 4.0, step=0.1)
            st.write("")

        p_desc = st.text_area(
            "Description * — this text becomes the vector embedding",
            height=130,
            placeholder=(
                "Describe the product in rich detail.\n"
                "The more descriptive, the better the semantic search results.\n"
                "e.g. 'High-protein organic chia seed bars made with dark chocolate and almonds, "
                "perfect for post-workout recovery and rich in omega-3 fatty acids.'"
            )
        )

        submitted = st.form_submit_button("🧠 Generate Embedding & Save to PostgreSQL")

    if submitted:
        if not p_name.strip():
            st.error("⚠️ Product name is required.")
        elif not p_desc.strip():
            st.error("⚠️ Description is required — it is used to generate the vector embedding.")
        else:
            with st.spinner("⚙️ Generating 384-dim embedding and saving to PostgreSQL..."):
                res = requests.post(
                    "http://127.0.0.1:8000/products/add",
                    json={
                        "name":           p_name.strip(),
                        "category":       p_category,
                        "price":          p_price,
                        "stock_quantity": p_stock,
                        "rating":         p_rating,
                        "description":    p_desc.strip(),
                    }
                )

            if res.status_code == 200:
                data = res.json()
                st.success(f"✅ **{p_name}** saved to PostgreSQL with Product ID **#{data['product_id']}**!")

                st.divider()
                info_col, embed_col = st.columns([1, 2])
                with info_col:
                    st.metric("Product ID",     f"#{data['product_id']}")
                    st.metric("Embedding Dims", data["embedding_dims"])
                    st.metric("Cache Flushed",  "✅ Yes")
                with embed_col:
                    st.write("**Embedding Preview** *(first 8 of 384 dimensions)*")
                    st.code(str(data["embedding_preview"]), language="python")
                    st.caption(
                        "This 384-float vector captures the semantic meaning of the description "
                        "and is stored in the `description_vector` column in Postgres. "
                        "Vector search will now consider this product instantly."
                    )
            else:
                st.error(f"❌ Failed to save: {res.text}")
