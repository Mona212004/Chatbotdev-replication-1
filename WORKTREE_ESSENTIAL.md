# Essential Worktree - Core Project Files Only

This document maps the essential files and structure needed to rebuild and rerun the chatbot project. Excluded: test files, logs, cache, temporary files, and unneeded archives.

## Root Level
```
chatbotdev/
├── .env.example              # Environment configuration template
├── .gitignore                # Git ignore rules
└── requirements.txt          # Root dependencies (if applicable)
```

---

## 1. MAIN PROJECT: movieRec (Movie Recommendation Chatbot)

### Core Application
```
movieRec/
├── config.py                 # Main configuration
├── connect.py                # Database connection setup
├── db_params.ini             # Database parameters
├── Dockerfile                # Container image
├── docker-compose.yml        # Multi-container orchestration
├── .env.example              # Environment template
│
├── init/
│   └── 01-schema.sql         # Database schema initialization
│
└── movieRecommendation/      # Main application package
    ├── __init__.py
    ├── agent.py              # Main chatbot agent
    ├── prompt.py             # Agent prompts
    ├── requirements.txt       # Project dependencies
    ├── evalset1.evalset.json  # Evaluation dataset
    │
    ├── entities/
    │   ├── __init__.py
    │   └── user.py            # User entity model
    │
    ├── sharedLibraries/       # Shared utilities
    │   ├── __init__.py
    │   ├── check_device.py     # GPU/CPU device checking
    │   ├── device.py           # Device utilities
    │   ├── config_embed_model.py  # Embedding model config
    │   ├── load_reranker.py    # Reranker loading
    │   └── user_query_to_vector.py  # Query vectorization
    │
    └── sub_agents/            # Specialized agents
        ├── __init__.py
        │
        ├── greetingAgent/
        │   ├── __init__.py
        │   ├── agent.py
        │   ├── prompt.py
        │   ├── checkIfUserExist.py
        │   └── sayHello.py
        │
        ├── find_movie_title_agent/
        │   ├── __init__.py
        │   ├── agent.py
        │   ├── prompt.py
        │   └── get_movie_title.py
        │
        ├── recAgent/           # Main recommendation agent
        │   ├── __init__.py
        │   ├── agent.py
        │   ├── prompt.py
        │   ├── check_preferences.py
        │   ├── add_preferences.py
        │   ├── delete_preferences.py
        │   ├── ask_for_approval.py
        │   ├── content_based_filtering.py
        │   └── recommend_similar_movies_by_plot.py
        │
        ├── retrieve_from_db_agent/
        │   ├── __init__.py
        │   ├── agent.py
        │   ├── prompt.py
        │   ├── movieIsExist.py
        │   ├── get_movie_title.py
        │   ├── get_movie_rating.py
        │   ├── get_movie_genres.py
        │   ├── get_movie_duration.py
        │   ├── get_movie_plot_summary.py
        │   └── get_movie_plot_synopsis.py
        │
        └── farewellAgent/
            ├── __init__.py
            ├── agent.py
            ├── prompt.py
            └── sayByeBye.py
```

---

## 2. EMBEDDINGS & RERANKER: Emb_Rerank

### Vector Database Creation & Query Processing
```
Emb_Rerank/
├── __init__.py
│
├── Embeddings/               # Vector embedding creation
│   ├── __init__.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── createVectorDB/       # Scripts to build vector database
│   │   └── [main scripts here]
│   │
│   └── UserQuery/            # Query embedding service
│       └── [query processing scripts]
│
└── Pretrained_reranker/      # Reranking models
    ├── __init__.py
    ├── load_reranker.py      # Load pretrained reranker
    ├── reranker_ex.py        # Reranker examples/utilities
    └── requirements.txt
```

---

## 3. DATABASE UTILITIES: PostgreSQL

### Helper Functions & Connection Management
```
PostgreSQL/
├── config.py                 # Configuration loader
├── connect.py                # Database connection
├── database.ini              # Database parameters
├── createTable.py            # Table creation utilities
├── call_stored_procedure.py  # Stored procedure execution
├── callfunction.py           # Function calling utilities
├── insertData.py             # Single insert operations
├── insertMultipleData.py     # Batch insert operations
├── fetchone_func.py          # Single row retrieval
├── fetchall_func.py          # All rows retrieval
├── fetchmany.py              # Limited row retrieval
├── updateOneCol.py           # Column update utilities
├── deleting_data.py          # Data deletion utilities
└── transaction.py            # Transaction management
```

---

## 4. DATA & CONFIGURATION: ProcessedData

### Processed Datasets
```
ProcessedData/
└── cleaned_imdb_*.csv        # Cleaned IMDB movie dataset
```

---

## 5. WEB SCRAPING (Optional - Separate Project): site_scrapper_camtech-master

### Content Scraping & Processing
```
site_scrapper_camtech-master/
├── requirements.txt
├── fetch.py                  # Main fetching script
├── chain_fetcher.py          # Chained fetching logic
├── combine_markdown.py       # Markdown combining utility
├── format_whitespace.py      # Whitespace formatter
├── strip_links_keep_firstline.py  # Link stripping utility
├── generate_code_base.sh     # Shell script for codebase generation
│
├── inputsite.txt             # Input URLs
├── urls_to_fetch.txt         # URLs to fetch
├── exclude_patterns.conf     # Exclusion patterns
│
└── processed_content/        # Output processed markdown files
    └── [*.md files]
```

---

## SETUP & EXECUTION FLOW

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # On Windows

# Install core dependencies
pip install -r movieRec/movieRecommendation/requirements.txt
pip install -r Emb_Rerank/Embeddings/requirements.txt
pip install -r Emb_Rerank/Pretrained_reranker/requirements.txt
```

### 2. Database Setup
```bash
# Update db_params.ini with your PostgreSQL credentials
# Run schema initialization
psql -U postgres < movieRec/init/01-schema.sql
```

### 3. Environment Configuration
```bash
# Copy and configure
cp movieRec/.env.example movieRec/.env
# Edit .env with actual credentials and API keys
```

### 4. Data Preparation
```bash
# Ensure processed data is in place
# ProcessedData/cleaned_imdb_*.csv should exist
```

### 5. Run Application
```bash
# From movieRec directory
python -m movieRecommendation.agent
```

---

## FILES TO EXCLUDE FROM BACKUP

**Safely Ignored (Large/Regenerable):**
- `__pycache__/` directories
- `.git/` directory (use git clone instead)
- `venv/` or `env/` directories
- `.adk/` directories (Azure tools)
- `ProcessedData/` (regenerable from source data)

**Safely Ignored (Testing/Logging):**
- `archive/` directory (old code)
- `test_logs/` directory
- `*_test.py`, `test_*.py` files
- `*.log` files

**Safely Ignored (Environment):**
- `.env` files (keep `.env.example`)
- `.DS_Store` (macOS)
- `__pycache__/` and `.pyc` files

---

## QUICK REFERENCE: Commands to Reproduce Project

```bash
# Clone and setup
git clone <repo>
cd chatbotdev
python -m venv venv
source venv/Scripts/activate

# Install dependencies
pip install -r movieRec/movieRecommendation/requirements.txt
pip install -r Emb_Rerank/Embeddings/requirements.txt
pip install -r Emb_Rerank/Pretrained_reranker/requirements.txt

# Configure database
psql -U postgres < movieRec/init/01-schema.sql
cp movieRec/.env.example movieRec/.env
# Edit .env with credentials

# Prepare data
# Ensure ProcessedData/cleaned_imdb_*.csv exists

# Run
python -m movieRecommendation.agent
```

---

**Last Updated:** 2026-04-25
**Project Type:** Movie Recommendation Chatbot with Vector Search & Reranking
