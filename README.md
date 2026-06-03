# FreshCart AI Search Demo

> **Welcome!** This guide walks you through a hands-on exploration of the **FreshCart Multi-Modal Search** application. Follow the steps below to get the system running, then experiment with its three search engines to see how natural-language queries are transformed into structured filters and vector-based results.

---

## 🎯 Goal
Demonstrate an end‑to‑end AI‑augmented product search that combines:
- **Traditional SQL** filtering (price, rating, category, description wildcards)
- **Semantic vector search** using `pgvector`
- **Hybrid search** (SQL + vector) with **Redis** caching

---

## 📋 Prerequisites
| Item | Version / Requirement | How to install |
|------|----------------------|----------------|
| **Docker Desktop** | >= 4.0 | <https://www.docker.com/products/docker-desktop/> |
| **Python** | 3.9+ (recommended 3.11) via **Miniconda** | <https://docs.conda.io/en/latest/miniconda.html> |
| **Git** (optional) | any recent version | `brew install git` |
| **Internet** (first run) | to download the SentenceTransformer model | – |

> **Tip:** After installing Miniconda, create an isolated environment:
> ```bash
> conda create -n freshcart_ai python=3.11
> conda activate freshcart_ai
> ```

---

## 📁 Navigate to Project Directory
```bash
cd freshcart-ai-search
```

## 🛠️ Install Python Dependencies
```bash
pip install \
    streamlit \
    fastapi uvicorn \
    psycopg2-binary redis \
    sentence-transformers pgvector \
    python-dotenv
```

## 🔑 Set Up Environment Variables
The app reads credentials from a `.env` file. This file is git-ignored and **never pushed to GitHub**.
```bash
cp .env.example .env
```
The default values work out of the box for local development — no changes needed unless you customise your Docker setup.

---

## 🐳 Spin Up Docker Services
The project ships a `docker‑compose.yml` that defines PostgreSQL 15 with the `pgvector` extension and a Redis 7 cache.
```bash
# From the project root
docker compose up -d   # starts both containers in detached mode
```
Verify they are running:
```bash
docker ps   # should list "ai_search_db" and "ai_search_cache"
```

---

## 📥 Seed the Database (one‑time only)
`generate_dataset.py` creates 100 realistic product rows **and** computes their 384‑dim embeddings.
```bash
python generate_dataset.py
```
You should see a short log confirming insertion of 100 rows.

---

## 🚀 Launch the Application
1. **Backend (FastAPI)**
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   *The API will be reachable at `http://127.0.0.1:8000`.*
2. **Frontend (Streamlit)** – in a **new terminal**
   ```bash
   streamlit run frontend.py
   ```
   *Visit `http://localhost:8501` in any modern browser.*

---

## 🖥️ UI Overview
The Streamlit UI consists of four tabs:
- **🔍 Search** – explore the three engines side‑by‑side.
- **📦 Cache Viewer** – see Redis entries and TTL.
- **➕ Add Product** – insert new items and instantly generate embeddings.
- **🏗️ Architecture** – visual diagram of the whole stack.

![Architecture diagram](architecture_diagram.png)

---

## 🔎 Exploring the Search Tab
1. **Set sidebar filters** (price slider, rating slider, description keyword, category dropdown).
2. **Enter a free-text query** in the main search bar, e.g.:
   ```text
   organic snacks under $5 rated above 4 in Breakfast
   ```
3. Click **"🔍 Search Now"**.
4. Compare the three result columns side-by-side:
   - **Traditional SQL** — returns products that match only the sidebar filter criteria.
   - **Vector Search Only** — parses your natural-language query, auto-detects constraints (price, rating, category), and returns the top 3 semantically similar products.
   - **SQL + Vector (Hybrid)** — applies sidebar filters first, then re-ranks the narrowed set by vector similarity; results are cached in Redis for 5 minutes.
5. Hover over each result card to read the full product description.
6. Switch to the **Cache Viewer** tab — you will see a fresh cache entry for the hybrid query with a live TTL countdown.

> **Things to try:**
> - Run the same hybrid query **twice** — the second run shows a **Cache Hit** badge and near-zero latency.
> - Search for a concept that shares no keywords with any product name (e.g. "morning energy food") and observe how the vector engine still finds relevant results.
> - Apply a tight price filter via the sidebar, then run a hybrid search — notice how the candidate set shrinks before vector re-ranking kicks in.

---

## ➕ Adding a New Product
1. Switch to the **Add Product** tab.
2. Fill out the form (name, category, price, stock, rating, description).
3. Click **"🧠 Generate Embedding & Save to PostgreSQL"**.
4. A success toast appears, showing:
   - Assigned product ID
   - Embedding dimensionality (384)
   - A preview of the first eight vector values
5. The cache is automatically flushed, ensuring the new product is searchable immediately.

---

## 🧹 Clean-up
When you are done:
```bash
# Stop containers
docker compose down
# (Optional) Remove the database volume to start completely fresh
docker volume prune   # ⚠️ This deletes all persisted data!
```

---

## 💡 Things to Explore
- After running a vector-only search, look at the **constraint badges** displayed in the results (e.g. `price ≤ $4 | rating ≥ 4.5 | category = Snacks`). These show what the regex parser extracted from your query.
- Run the same hybrid search query **twice** and compare the latency — the second run is served from Redis cache and is dramatically faster.
- Adjust the sidebar filters to create a very narrow candidate pool, then run a hybrid search and observe how vector ranking picks the best match within that smaller set.
- Open `http://127.0.0.1:8000/docs` to explore the raw FastAPI endpoints with the built-in Swagger UI.

## 📚 Further Exploration
- Swap the SentenceTransformer model for a larger one (e.g. `all-mpnet-base-v2`) to see the impact on semantic quality.
- Increase the dataset size in `generate_dataset.py` and observe latency changes.
- Extend the NLP parser (`extract_query_constraints`) to support additional operators (e.g., `between $5 and $10`).

---

## ❓ Frequently Asked Questions (FAQ)

### 🔧 Setup & Environment

**Q: Do I need a GPU to run this demo?**  
No. The `all-MiniLM-L6-v2` model is small (~80 MB) and runs entirely on your CPU. It may take a few seconds to encode queries, but it works fine without a GPU.

**Q: Why does the first launch take so long?**  
On the very first run, `SentenceTransformer('all-MiniLM-L6-v2')` downloads the model weights (~80 MB) from Hugging Face. After that it is cached locally and loads instantly. An internet connection is required only for this first download.

**Q: I see a "HuggingFace Hub unauthenticated request" warning — is that a problem?**  
No. It is just a warning, not an error. The model downloads and runs fine without an API token. You can safely ignore it.

**Q: Do I need to run `python generate_dataset.py` every time I demo?**  
No — only once. The data and vectors are stored inside the PostgreSQL Docker volume. As long as you don't run `docker compose down -v` or `docker volume prune`, the data persists across sessions. Simply `docker compose up -d` the next time and you are ready.

**Q: The server says "404 Not Found" when I open `http://127.0.0.1:8000` in the browser — is something broken?**  
No. The FastAPI backend has no route at `/`. The root URL is intentionally empty. Either open `http://127.0.0.1:8000/docs` for the interactive Swagger API explorer, or open `http://localhost:8501` for the Streamlit UI (which is the proper demo interface).

**Q: Can I run this on Windows?**  
Yes, with minor changes. Use `docker compose up -d` in PowerShell or WSL. All Python commands are the same. If you encounter line-ending issues with the CSV, make sure your editor uses LF line endings.

---

### 🧠 Concepts & AI

**Q: What is a vector / embedding?**  
An embedding is a list of numbers (e.g. 384 decimal values) that represents the *meaning* of a piece of text. Words or sentences with similar meaning produce vectors that are close together in space. This is how the vector search finds "whole grain breakfast cereal" even when you search for "morning porridge".

**Q: What does `all-MiniLM-L6-v2` mean?**  
It is the name of the pre-trained model used to generate embeddings:
- **all** — trained on a large, general-purpose dataset.
- **MiniLM** — a compressed (mini) language model that runs fast on CPU.
- **L6** — has 6 transformer layers (instead of the full 12 in BERT).
- **v2** — second improved version.

It outputs 384-dimensional vectors and is a popular choice for demos because it is fast, small, and free.

**Q: Is this system using ChatGPT / an LLM?**  
No. There are no large language models (LLMs) involved. The system uses:
1. A **sentence embedding model** (`all-MiniLM-L6-v2`) to convert text into vectors.
2. A **regex-based NLP parser** (`extract_query_constraints`) to pull out structured filters (price, rating, category) from natural language. This parser uses pattern matching — not AI reasoning.

**Q: Why do we need embeddings if there is already an NLP parser?**  
The NLP parser only extracts *structured constraints* (e.g., `price ≤ $5`, `category = Snacks`). It cannot understand *semantic intent* — e.g., the difference between "morning energy food" and "high-protein gym snack". The embedding model captures this meaning and finds products that are conceptually similar to the query, even if they share no keywords.

**Q: Which columns are turned into vectors?**  
Only the `description` column. The product name, category, price, and rating are stored as regular SQL columns and searched with standard filters.

**Q: Why is the vector 384 numbers long specifically?**  
That is the output dimension chosen when `all-MiniLM-L6-v2` was trained. Different models produce different sizes (e.g. `all-mpnet-base-v2` produces 768). A larger dimension can capture more nuance but is slower and uses more storage.

**Q: What does "cosine distance" / `<=>` mean in the SQL query?**  
`<=>` is the pgvector operator for **cosine distance** — it measures the angle between two vectors. A distance of 0 means identical meaning; 2 means opposite. The query orders results by `distance ASC` so the most semantically similar products appear first.

---

### 🔍 Search Engines

**Q: What is the difference between the three search engines?**

| Engine | Uses sidebar filters? | Uses text query? | Caching? |
|--------|-----------------------|-----------------|---------|
| Traditional SQL | ✅ Yes | ❌ No | ❌ No |
| Vector Search Only | ❌ No (parses query itself) | ✅ Yes (semantic) | ❌ No |
| SQL + Vector (Hybrid) | ✅ Yes | ✅ Yes (semantic) | ✅ Yes (Redis, 5 min) |

**Q: Why does the vector search sometimes return products outside my price range?**  
The vector search extracts price/rating/category constraints from the *text query* using the regex parser. If your query does not mention a price (e.g. you typed "organic cereal"), no price filter is applied and all prices may appear. The Traditional SQL and Hybrid engines use the sidebar sliders for price filtering.

**Q: Why does the rating filter not work in vector search when I type "rating of 4.7"?**  
The regex parser recognises patterns like "rated above 4.7" or "rating above 4.7" but not "rating of 4.7". Use the phrasing "rated above X" or "at least X stars" to trigger the filter correctly.

**Q: What does the "Cache Hit" badge mean?**  
When you run a hybrid search, the result is stored in Redis for 5 minutes using the query + filter values as the cache key. If you run the *exact same* query again within 5 minutes, the result is served directly from Redis (no database hit), which is why the latency drops near to zero.

**Q: Why does the cache clear when I add a new product?**  
When a new product is added, any previously cached search results could be stale (the new product might be relevant to past queries). The backend calls `cache.flushdb()` after every insert to guarantee freshness.

---

### 🐳 Infrastructure

**Q: What is Docker doing here?**  
Docker runs two background services:
- **PostgreSQL 15** with the `pgvector` extension — stores products and their 384-dim embedding vectors.
- **Redis 7** — acts as an in-memory cache for hybrid search results.

The Python backend (FastAPI) and the UI (Streamlit) run directly on your machine, not inside Docker.

**Q: What is `pgvector`? Is it a built-in feature of PostgreSQL?**  
No — `pgvector` is a **third-party open-source extension**, not a built-in feature of PostgreSQL. You have to install it separately. It adds three things on top of standard PostgreSQL:
1. A new `vector` column type to store floating-point arrays (e.g. 384 numbers per row).
2. Similarity operators: `<=>` (cosine distance), `<->` (Euclidean distance), `<#>` (inner product).
3. Vector indexes (IVFFlat and HNSW) for fast approximate nearest-neighbour search at scale.

In this project, the Docker image `pgvector/pgvector:pg15` is used instead of plain `postgres:15` — that automatically bundles the extension. Once the container is running, it is enabled per-database with:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Q: Do all databases support vector search?**  
No — far from it. Support varies widely:

| Database | Vector Search | Notes |
|---|---|---|
| **PostgreSQL + pgvector** | ✅ Yes (extension) | Free, open source. Used in this project. |
| **MySQL / MariaDB** | ⚠️ Limited | MySQL 9.0 added a basic vector type, but immature. |
| **SQLite** | ⚠️ Extension only | `sqlite-vec` plugin exists but very niche. |
| **MongoDB Atlas** | ✅ Yes | Atlas Vector Search — cloud only. |
| **Elasticsearch / OpenSearch** | ✅ Yes | Mature k-NN vector search, widely used in production. |
| **Pinecone** | ✅ Yes (purpose-built) | Stores *only* vectors — dedicated vector database. |
| **Weaviate** | ✅ Yes (purpose-built) | Dedicated vector DB with GraphQL API. |
| **Chroma** | ✅ Yes (purpose-built) | Popular for LLM/RAG applications. |
| **Qdrant** | ✅ Yes (purpose-built) | Rust-based, very high performance. |
| **Standard SQL Server / Oracle** | ❌ No native support | No built-in vector type or operators. |

**Q: Why use `pgvector` instead of a dedicated vector database like Pinecone or Weaviate?**  

| Factor | pgvector | Dedicated vector DB |
|---|---|---|
| **Setup complexity** | Low — runs inside existing PostgreSQL | High — separate service and API keys |
| **Cost** | Free and open source | Often paid (especially cloud-hosted) |
| **SQL joins** | ✅ Yes — join vectors with other columns natively | ❌ No — separate from relational data |
| **Scale** | Good for millions of rows | Better for billions of rows |
| **Best for** | Teaching, prototypes, small-to-medium apps | Large-scale production AI search |

For this demo, `pgvector` is the ideal choice — one fewer service to manage, everything lives in one database, and it is completely free.

**Q: What is Redis used for and why not just use PostgreSQL for caching?**  
Redis is an in-memory key-value store that returns data in microseconds. PostgreSQL is disk-based and involves query parsing, planning, and I/O even for simple lookups. Redis is the industry standard for application-level caching because of its speed and built-in TTL (time-to-live) support.

**Q: Is the data lost when I stop the Docker containers?**  
Not by default. Docker creates a named volume for PostgreSQL data. `docker compose down` stops the containers but keeps the volume. Only `docker compose down -v` or `docker volume prune` deletes the data.

---

### 📂 Code Structure

**Q: Where does the NLP parsing happen?**  
In `app.py`, inside the function `extract_query_constraints()` (lines 22–99). It uses Python's built-in `re` (regular expressions) module — there is no AI model involved in this step.

**Q: Where are the vectors generated?**  
In two places:
1. `generate_dataset.py` — generates vectors for the initial 100 products in bulk and inserts them into PostgreSQL.
2. `app.py` (`add_product` endpoint) — generates a vector for each newly added product in real time.

**Q: What is `products_precalculated.csv` for?**  
It is a by-product of `generate_dataset.py`. The file contains the 100 products with their pre-computed vector columns saved as JSON strings. It is **not used by the app** — it exists purely for student inspection (e.g. opening in Excel or Pandas to see what a raw embedding looks like).

---

*Happy searching!* 🎉
