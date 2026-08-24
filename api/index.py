import os
import json
import random
import re
import time
from collections import defaultdict
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException, Path, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(
    title="Free 5,000+ Music & Songs API",
    description="High-performance, ultra-fast free REST API with 5,700+ cached songs ready for direct audio/video streaming with built-in DDoS & Rate Limiting Protection.",
    version="1.3.0",
    docs_url="/swagger",
    redoc_url="/redoc"
)

# CORS & GZip Compression
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Available Endpoints Directory ──────────────────────────────────────────
AVAILABLE_ENDPOINTS = {
    "search": {
        "method": "GET",
        "path": "/api/search?q={query}&limit=10",
        "description": "Smart multi-keyword token matching with relevance ranking"
    },
    "song_by_id": {
        "method": "GET",
        "path": "/api/song/{video_id}",
        "description": "Direct YouTube 11-char Video ID lookup"
    },
    "random": {
        "method": "GET",
        "path": "/api/random?limit=10",
        "description": "Get random playlist for shuffle and discovery"
    },
    "songs_catalog": {
        "method": "GET",
        "path": "/api/songs?page=1&limit=50",
        "description": "Paginated catalog of all 5,778+ indexed tracks"
    },
    "stats": {
        "method": "GET",
        "path": "/api/stats",
        "description": "API health check and catalog statistics"
    },
    "docs": {
        "method": "GET",
        "path": "/docs",
        "description": "Custom interactive API documentation & code playground"
    },
    "swagger": {
        "method": "GET",
        "path": "/swagger",
        "description": "Raw OpenAPI Swagger specification UI"
    }
}

# ── DDoS & Sliding Window Rate Limiter ─────────────────────────────────────
DEFAULT_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.window = 60  # seconds
        self.hits = defaultdict(list)

    def get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        return request.client.host if request.client else "127.0.0.1"

    def get_remaining(self, request: Request, custom_limit: Optional[int] = None) -> int:
        limit = custom_limit or self.rpm
        ip = self.get_client_ip(request)
        now = time.time()
        self.hits[ip] = [ts for ts in self.hits[ip] if now - ts < self.window]
        return max(0, limit - len(self.hits[ip]))

    def check(self, request: Request, custom_limit: Optional[int] = None):
        limit = custom_limit or self.rpm
        ip = self.get_client_ip(request)
        now = time.time()
        
        # Clean timestamps older than 60 seconds
        self.hits[ip] = [ts for ts in self.hits[ip] if now - ts < self.window]
        
        if len(self.hits[ip]) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded (Max {limit} requests/min). Please slow down to prevent abuse.",
                headers={"Retry-After": "60"}
            )
        self.hits[ip].append(now)

rate_limiter = SlidingWindowRateLimiter(DEFAULT_RATE_LIMIT)

# ── Custom Headers & Rate Limit Middleware ─────────────────────────────────
@app.middleware("http")
async def custom_headers_and_rate_limit_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Apply rate limiting to /api/* endpoints
    if request.url.path.startswith("/api/"):
        try:
            rate_limiter.check(request)
        except HTTPException as exc:
            process_time = (time.time() - start_time) * 1000
            headers = getattr(exc, "headers", {}) or {}
            headers.update({
                "X-Powered-By": "Yuki-Music-Engine",
                "X-API-Version": "1.3.0",
                "X-Total-Songs": str(len(SONGS_DATA)),
                "X-RateLimit-Limit": str(DEFAULT_RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-Response-Time-MS": f"{process_time:.2f}ms",
                "X-Documentation": f"{str(request.base_url).rstrip('/')}/docs"
            })
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Too Many Requests",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "status_code": 429,
                    "message": exc.detail,
                    "retry_after_seconds": 60,
                    "hint": "You exceeded the 60 req/min rate limit. Please wait 60 seconds before making new requests."
                },
                headers=headers
            )

    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    # Inject Custom Headers on every response
    response.headers["X-Powered-By"] = "Yuki-Music-Engine"
    response.headers["X-API-Version"] = "1.3.0"
    response.headers["X-Total-Songs"] = str(len(SONGS_DATA))
    response.headers["X-RateLimit-Limit"] = str(DEFAULT_RATE_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining(request))
    response.headers["X-Response-Time-MS"] = f"{process_time:.2f}ms"
    response.headers["X-Documentation"] = f"{str(request.base_url).rstrip('/')}/docs"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

# ── Custom Bad Route & HTTP Exception Handlers with Hints ───────────────────
@app.exception_handler(StarletteHTTPException)
async def custom_starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    headers = getattr(exc, "headers", None)
    
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Route Not Found",
                "code": "NOT_FOUND",
                "status_code": 404,
                "message": f"Endpoint '{request.url.path}' does not exist on this server.",
                "hint": "Check the available_endpoints directory below or visit the interactive documentation at /docs",
                "available_endpoints": AVAILABLE_ENDPOINTS
            },
            headers=headers
        )
    elif exc.status_code == 405:
        return JSONResponse(
            status_code=405,
            content={
                "success": False,
                "error": "Method Not Allowed",
                "code": "METHOD_NOT_ALLOWED",
                "status_code": 405,
                "message": f"HTTP Method '{request.method}' is not supported for '{request.url.path}'.",
                "hint": "Use HTTP GET method for all API endpoints. See /docs for details."
            },
            headers=headers
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP Error",
            "code": "HTTP_ERROR",
            "status_code": exc.status_code,
            "message": str(exc.detail),
            "hint": "Refer to /docs or check your request parameters."
        },
        headers=headers
    )

@app.exception_handler(Exception)
async def general_500_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "code": "INTERNAL_SERVER_ERROR",
            "status_code": 500,
            "message": "An unexpected error occurred on the server.",
            "hint": "Please report bugs or try again in a few moments.",
            "detail": str(exc)
        }
    )

# ── In-Memory Cache & Search Engine ─────────────────────────────────────────
SONGS_DATA: List[dict] = []
SONGS_BY_ID: dict = {}

def load_songs():
    global SONGS_DATA, SONGS_BY_ID
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "songs.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "songs.json"),
        "api/songs.json",
        "data/songs.json",
        "songs.json"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    SONGS_DATA = json.load(f)
                    SONGS_BY_ID = {s["video_id"]: s for s in SONGS_DATA if "video_id" in s}
                    print(f"Loaded {len(SONGS_DATA)} songs into in-memory index from {path}")
                    return
            except Exception as e:
                print(f"Failed to load songs from {path}: {e}")

load_songs()

# Optional MongoDB Client for Live Sync
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGO_DB_URI")
mongo_col = None

if MONGO_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        mongo_col = mongo_client["MusicAPI_DB"]["songs_cache"]
        print("Connected to MongoDB for live fallback search!")
    except Exception as e:
        print(f"MongoDB connection skipped: {e}")

# Models
class SongItem(BaseModel):
    video_id: str
    title: str
    stream_url: str
    source: Optional[str] = "cloud"
    thumbnail: Optional[str] = None

class SearchResponse(BaseModel):
    success: bool
    total_results: int
    query: str
    hint: Optional[str] = None
    results: List[SongItem]

class StatsResponse(BaseModel):
    success: bool
    total_songs: int
    yukiapi_cloud_songs: int
    catbox_songs: int
    rate_limit_per_minute: int
    status: str
    version: str
    hint: Optional[str] = None

def rank_search(query: str, limit: int = 10) -> List[dict]:
    clean_q = query.strip().lower()
    if not clean_q:
        return []

    tokens = [t for t in re.split(r"\s+", clean_q) if t]
    exact_matches = []
    prefix_matches = []
    token_matches = []

    for song in SONGS_DATA:
        title_lower = song.get("title", "").lower()
        vid = song.get("video_id", "").lower()

        if clean_q == vid:
            return [song]

        if clean_q in title_lower:
            if title_lower.startswith(clean_q):
                exact_matches.append((0, song))
            else:
                exact_matches.append((1, song))
            continue

        if all(token in title_lower for token in tokens):
            token_matches.append((2, song))
            continue

        match_count = sum(1 for token in tokens if token in title_lower)
        if match_count > 0:
            prefix_matches.append((10 - match_count, song))

    combined = sorted(exact_matches + token_matches + prefix_matches, key=lambda x: x[0])
    results = [item[1] for item in combined[:limit]]
    return results

# ── Home Page ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    """Serves the interactive Web Search & Stream Playground with Endpoints Showcase"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Free 5,000+ Music API | High Speed REST API</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: #0b0f19; color: #f3f4f6; }
        .glass { background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .glow { box-shadow: 0 0 50px -10px rgba(59, 130, 246, 0.3); }
        .song-card:hover { transform: translateY(-3px); border-color: rgba(59, 130, 246, 0.5); }
        .endpoint-card:hover { border-color: rgba(99, 102, 241, 0.6); }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <!-- Header -->
    <header class="border-b border-gray-800/80 sticky top-0 z-50 glass">
        <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
                    <i class="fa-solid fa-music text-white text-lg"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg leading-tight bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">Free Songs API</h1>
                    <p class="text-xs text-gray-400">5,778+ Cloud Cached Songs · Anti-DDoS Protected</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <a href="/docs" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 transition">
                    <i class="fa-solid fa-book-bookmark mr-1.5 text-indigo-400"></i> API Docs
                </a>
                <a href="/swagger" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 transition">
                    <i class="fa-solid fa-code mr-1.5 text-blue-400"></i> Swagger
                </a>
                <a href="https://github.com" target="_blank" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/30 transition">
                    <i class="fa-brands fa-github mr-1.5"></i> GitHub
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
        <!-- Hero Section -->
        <div class="text-center mb-8">
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium mb-4">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> 5,778+ Songs Ready · 2ms Response Latency
            </div>
            <h2 class="text-3xl md:text-5xl font-extrabold tracking-tight mb-4">
                Lightning Fast <span class="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">Music API</span> for Apps & Bots
            </h2>
            <p class="text-gray-400 text-sm md:text-base max-w-2xl mx-auto">
                Search songs by keywords or YouTube Video ID, get instant high-speed direct audio/video streaming URLs with zero buffering.
            </p>
        </div>

        <!-- Search Box -->
        <div class="max-w-2xl mx-auto mb-10">
            <div class="glass rounded-2xl p-2 flex items-center gap-2 glow">
                <i class="fa-solid fa-magnifying-glass text-gray-400 ml-3 text-lg"></i>
                <input id="searchInput" type="text" placeholder="Search by song name, artist, or YouTube ID (e.g. Kesariya, Arijit)..." 
                    class="w-full bg-transparent border-none outline-none text-sm text-gray-100 placeholder-gray-500 px-2 py-2">
                <button onclick="performSearch()" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-semibold text-xs text-white transition flex items-center gap-2 shadow-lg shadow-blue-600/30">
                    <span>Search</span>
                    <i class="fa-solid fa-arrow-right text-xs"></i>
                </button>
            </div>
            <!-- Quick Suggestions -->
            <div class="flex flex-wrap items-center justify-center gap-2 mt-3 text-xs text-gray-400">
                <span>Try searching:</span>
                <button onclick="quickSearch('Arijit Singh')" class="hover:text-blue-400 bg-gray-800/50 px-2.5 py-0.5 rounded-md border border-gray-700">Arijit Singh</button>
                <button onclick="quickSearch('Sun Saathiya')" class="hover:text-blue-400 bg-gray-800/50 px-2.5 py-0.5 rounded-md border border-gray-700">Sun Saathiya</button>
                <button onclick="quickSearch('Sidhu Moosewala')" class="hover:text-blue-400 bg-gray-800/50 px-2.5 py-0.5 rounded-md border border-gray-700">Sidhu Moosewala</button>
                <button onclick="getRandomSongs()" class="hover:text-purple-400 bg-purple-900/20 text-purple-300 px-2.5 py-0.5 rounded-md border border-purple-800/40"><i class="fa-solid fa-shuffle mr-1"></i> Random 10</button>
            </div>
        </div>

        <!-- Audio Player Bar -->
        <div id="playerContainer" class="hidden mb-8 glass rounded-2xl p-4 border border-blue-500/30 glow">
            <div class="flex flex-col md:flex-row items-center justify-between gap-4">
                <div class="flex items-center gap-3 w-full md:w-auto">
                    <img id="playerThumb" src="" class="w-12 h-12 rounded-lg object-cover border border-gray-700">
                    <div class="overflow-hidden">
                        <h4 id="playerTitle" class="font-semibold text-sm truncate max-w-xs md:max-w-md">Playing song...</h4>
                        <p id="playerVid" class="text-xs text-gray-400">ID: </p>
                    </div>
                </div>
                <audio id="audioElement" controls class="w-full md:w-1/2 h-10 outline-none"></audio>
            </div>
        </div>

        <!-- Results Grid -->
        <div id="resultsGrid" class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-16"></div>
        <div id="loading" class="hidden text-center py-10">
            <i class="fa-solid fa-circle-notch fa-spin text-blue-500 text-3xl"></i>
            <p class="text-xs text-gray-400 mt-2">Searching 5,778+ tracks...</p>
        </div>
        <div id="noResults" class="hidden text-center py-12 glass rounded-2xl mb-16">
            <i class="fa-regular fa-face-frown text-gray-500 text-4xl mb-2"></i>
            <p class="text-sm font-semibold text-gray-300">No matching songs found</p>
            <p class="text-xs text-gray-500 mt-1">Try another keyword or search by YouTube Video ID</p>
        </div>

        <!-- API Endpoints Directory Section -->
        <section id="endpoints" class="pt-6 border-t border-gray-800">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h3 class="text-xl font-bold text-gray-100 flex items-center gap-2">
                        <i class="fa-solid fa-network-wired text-indigo-400"></i> API Endpoints Reference
                    </h3>
                    <p class="text-xs text-gray-400 mt-1">All available REST API routes ready for integration with music bots and applications.</p>
                </div>
                <a href="/docs" class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold">
                    Full Documentation & Examples <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                </a>
            </div>

            <div class="space-y-3">
                <div class="glass rounded-xl p-4 border border-gray-800/90 endpoint-card transition">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                            <code class="text-sm font-mono text-gray-200">/api/search?q={query}&limit={10}</code>
                        </div>
                        <a href="/api/search?q=Sun%20Saathiya&limit=2" target="_blank" class="px-3 py-1 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 transition font-medium self-start sm:self-auto">Try it <i class="fa-solid fa-arrow-right text-[10px] ml-1"></i></a>
                    </div>
                    <p class="text-xs text-gray-400 mt-2">Search songs by keyword, title, or artist with token relevance ranking.</p>
                </div>

                <div class="glass rounded-xl p-4 border border-gray-800/90 endpoint-card transition">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                            <code class="text-sm font-mono text-gray-200">/api/song/{video_id}</code>
                        </div>
                        <a href="/api/song/UNs50T6EYwE" target="_blank" class="px-3 py-1 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 transition font-medium self-start sm:self-auto">Try it <i class="fa-solid fa-arrow-right text-[10px] ml-1"></i></a>
                    </div>
                    <p class="text-xs text-gray-400 mt-2">Get direct stream link and metadata for a specific YouTube 11-char Video ID.</p>
                </div>

                <div class="glass rounded-xl p-4 border border-gray-800/90 endpoint-card transition">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                            <code class="text-sm font-mono text-gray-200">/api/random?limit={10}</code>
                        </div>
                        <a href="/api/random?limit=5" target="_blank" class="px-3 py-1 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 transition font-medium self-start sm:self-auto">Try it <i class="fa-solid fa-arrow-right text-[10px] ml-1"></i></a>
                    </div>
                    <p class="text-xs text-gray-400 mt-2">Get a random playlist of songs (ideal for Music Bot shuffle & autoplay).</p>
                </div>

                <div class="glass rounded-xl p-4 border border-gray-800/90 endpoint-card transition">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                            <code class="text-sm font-mono text-gray-200">/api/songs?page={1}&limit={50}</code>
                        </div>
                        <a href="/api/songs?page=1&limit=10" target="_blank" class="px-3 py-1 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 transition font-medium self-start sm:self-auto">Try it <i class="fa-solid fa-arrow-right text-[10px] ml-1"></i></a>
                    </div>
                    <p class="text-xs text-gray-400 mt-2">Browse the complete 5,778+ songs database page-by-page.</p>
                </div>

                <div class="glass rounded-xl p-4 border border-gray-800/90 endpoint-card transition">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex items-center gap-3">
                            <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                            <code class="text-sm font-mono text-gray-200">/api/stats</code>
                        </div>
                        <a href="/api/stats" target="_blank" class="px-3 py-1 rounded-lg text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 transition font-medium self-start sm:self-auto">Try it <i class="fa-solid fa-arrow-right text-[10px] ml-1"></i></a>
                    </div>
                    <p class="text-xs text-gray-400 mt-2">Returns server health status, song counts, and active rate limit settings.</p>
                </div>
            </div>
        </section>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-800/80 py-6 text-center text-xs text-gray-500">
        <div class="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-2">
            <p>© 2026 Free Songs API · Open Source Serverless Music Index</p>
            <div class="flex items-center gap-4">
                <a href="/api/stats" class="hover:text-gray-300">API Stats</a>
                <a href="/docs" class="hover:text-gray-300">Docs</a>
                <a href="/swagger" class="hover:text-gray-300">Swagger</a>
                <a href="/api/random" class="hover:text-gray-300">Random</a>
            </div>
        </div>
    </footer>

    <script>
        const input = document.getElementById('searchInput');
        input.addEventListener('keypress', (e) => { if (e.key === 'Enter') performSearch(); });

        function quickSearch(q) {
            input.value = q;
            performSearch();
        }

        async function performSearch() {
            const query = input.value.trim();
            if (!query) return;

            const grid = document.getElementById('resultsGrid');
            const loading = document.getElementById('loading');
            const noResults = document.getElementById('noResults');

            grid.innerHTML = '';
            noResults.classList.add('hidden');
            loading.classList.remove('hidden');

            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=20`);
                if (res.status === 429) {
                    loading.classList.add('hidden');
                    alert('⚠️ Rate limit exceeded! Please wait a few seconds before searching again.');
                    return;
                }
                const data = await res.json();
                loading.classList.add('hidden');

                if (!data.results || data.results.length === 0) {
                    noResults.classList.remove('hidden');
                    return;
                }

                renderSongs(data.results);
            } catch (e) {
                loading.classList.add('hidden');
                alert('Search failed: ' + e);
            }
        }

        async function getRandomSongs() {
            const grid = document.getElementById('resultsGrid');
            const loading = document.getElementById('loading');
            const noResults = document.getElementById('noResults');

            grid.innerHTML = '';
            noResults.classList.add('hidden');
            loading.classList.remove('hidden');

            try {
                const res = await fetch('/api/random?limit=8');
                const data = await res.json();
                loading.classList.add('hidden');
                renderSongs(data.results);
            } catch (e) {
                loading.classList.add('hidden');
            }
        }

        function renderSongs(songs) {
            const grid = document.getElementById('resultsGrid');
            grid.innerHTML = '';

            songs.forEach(song => {
                const card = document.createElement('div');
                card.className = 'glass rounded-xl p-4 flex items-center justify-between gap-4 transition song-card border border-gray-800';
                card.innerHTML = `
                    <div class="flex items-center gap-3 overflow-hidden">
                        <img src="${song.thumbnail}" alt="Thumbnail" class="w-14 h-14 rounded-lg object-cover bg-gray-800 border border-gray-700 flex-shrink-0" onerror="this.src='https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100&q=80'">
                        <div class="overflow-hidden">
                            <h3 class="font-semibold text-sm text-gray-100 truncate" title="${song.title}">${song.title}</h3>
                            <div class="flex items-center gap-2 mt-1">
                                <span class="text-[10px] font-mono bg-gray-800 px-1.5 py-0.5 rounded text-gray-400">${song.video_id}</span>
                                <span class="text-[10px] px-1.5 py-0.5 rounded ${song.source === 'yukiapi_cloud' ? 'bg-indigo-900/40 text-indigo-300 border border-indigo-700/40' : 'bg-emerald-900/40 text-emerald-300 border border-emerald-700/40'}">${song.source}</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <button onclick="playSong('${song.stream_url.replace(/'/g, "\\'")}', '${song.title.replace(/'/g, "\\'")}', '${song.video_id}', '${song.thumbnail}')" 
                            class="w-9 h-9 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-md shadow-blue-600/30 transition">
                            <i class="fa-solid fa-play text-xs ml-0.5"></i>
                        </button>
                        <button onclick="copyUrl('${song.stream_url}')" title="Copy Stream URL"
                            class="w-9 h-9 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-300 flex items-center justify-center transition">
                            <i class="fa-regular fa-copy text-xs"></i>
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        function playSong(url, title, vid, thumb) {
            const container = document.getElementById('playerContainer');
            const audio = document.getElementById('audioElement');
            const titleEl = document.getElementById('playerTitle');
            const vidEl = document.getElementById('playerVid');
            const thumbEl = document.getElementById('playerThumb');

            container.classList.remove('hidden');
            titleEl.textContent = title;
            vidEl.textContent = 'YouTube ID: ' + vid;
            thumbEl.src = thumb;

            audio.src = url;
            audio.play();
        }

        function copyUrl(url) {
            navigator.clipboard.writeText(url);
            alert('Copied stream URL to clipboard:\n' + url);
        }

        window.addEventListener('DOMContentLoaded', getRandomSongs);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

# ── Custom /docs Interactive Documentation Page ──────────────────────────────
@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def custom_docs_page(request: Request):
    """Serves the Custom Interactive API Documentation Page with Code Snippets & Live Tester"""
    base = str(request.base_url).rstrip('/')
    docs_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Free Songs API Documentation | Developer Guide</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #0b0f19; color: #f3f4f6; }}
        code, pre {{ font-family: 'Fira Code', monospace; }}
        .glass {{ background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <!-- Header -->
    <header class="border-b border-gray-800/80 sticky top-0 z-50 glass">
        <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <a href="/" class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
                    <i class="fa-solid fa-music text-white text-lg"></i>
                </a>
                <div>
                    <h1 class="font-bold text-lg leading-tight bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">Developer Documentation</h1>
                    <p class="text-xs text-gray-400">Free 5,000+ Music API Reference v1.3.0</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <a href="/" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 transition">
                    <i class="fa-solid fa-house mr-1.5 text-blue-400"></i> Web Player
                </a>
                <a href="/swagger" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 transition">
                    <i class="fa-solid fa-code mr-1.5"></i> Swagger UI
                </a>
            </div>
        </div>
    </header>

    <!-- Docs Main Body -->
    <div class="max-w-6xl mx-auto px-4 py-10 grid grid-cols-1 lg:grid-cols-4 gap-8 flex-1 w-full">
        <!-- Sidebar Navigation -->
        <aside class="lg:col-span-1 space-y-2 sticky top-20 h-fit">
            <div class="glass rounded-xl p-4 border border-gray-800 space-y-1 text-xs">
                <p class="font-bold text-gray-400 uppercase tracking-wider text-[10px] mb-2">Getting Started</p>
                <a href="#overview" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">Overview</a>
                <a href="#headers" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">Response Headers</a>
                <a href="#ratelimits" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">Rate Limits & Hints</a>
                
                <p class="font-bold text-gray-400 uppercase tracking-wider text-[10px] pt-4 mb-2">Endpoints</p>
                <a href="#search" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">1. Keyword Search</a>
                <a href="#song" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">2. Video ID Lookup</a>
                <a href="#random" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">3. Random Playlist</a>
                <a href="#catalog" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">4. Songs Catalog</a>
                <a href="#stats" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">5. API Stats</a>
                
                <p class="font-bold text-gray-400 uppercase tracking-wider text-[10px] pt-4 mb-2">Code Examples</p>
                <a href="#code-python" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">Python (Music Bot)</a>
                <a href="#code-js" class="block py-1.5 px-3 rounded-lg text-gray-300 hover:bg-gray-800 hover:text-white transition">JavaScript (Node.js)</a>
            </div>
        </aside>

        <!-- Main Content -->
        <div class="lg:col-span-3 space-y-12">
            <!-- Section 1: Overview -->
            <section id="overview" class="glass rounded-2xl p-6 border border-gray-800">
                <h2 class="text-2xl font-bold text-gray-100 mb-2">API Overview</h2>
                <p class="text-sm text-gray-400 leading-relaxed">
                    The <strong>Free Songs API</strong> is a high-speed, serverless music indexing service providing direct, high-quality audio & video streaming links for over <strong>5,778 songs</strong>.
                </p>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                    <div class="bg-gray-900/60 p-3 rounded-xl border border-gray-800 text-center">
                        <p class="text-xs text-gray-400">Total Songs</p>
                        <p class="text-lg font-bold text-emerald-400">5,778+</p>
                    </div>
                    <div class="bg-gray-900/60 p-3 rounded-xl border border-gray-800 text-center">
                        <p class="text-xs text-gray-400">Latency</p>
                        <p class="text-lg font-bold text-blue-400">&lt; 2ms</p>
                    </div>
                    <div class="bg-gray-900/60 p-3 rounded-xl border border-gray-800 text-center">
                        <p class="text-xs text-gray-400">Rate Limit</p>
                        <p class="text-lg font-bold text-purple-400">60 req/min</p>
                    </div>
                    <div class="bg-gray-900/60 p-3 rounded-xl border border-gray-800 text-center">
                        <p class="text-xs text-gray-400">Base URL</p>
                        <p class="text-xs font-mono font-bold text-gray-200 mt-1 truncate">{base}</p>
                    </div>
                </div>
            </section>

            <!-- Section 2: Custom Response Headers -->
            <section id="headers" class="glass rounded-2xl p-6 border border-gray-800">
                <h2 class="text-xl font-bold text-gray-100 mb-2 flex items-center gap-2">
                    <i class="fa-solid fa-heading text-indigo-400"></i> Custom Response Headers
                </h2>
                <p class="text-xs text-gray-400 mb-4">Every API response includes useful debug and telemetry headers:</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs border border-gray-800 rounded-lg overflow-hidden">
                        <thead class="bg-gray-900 text-gray-400">
                            <tr>
                                <th class="p-2.5">Header Name</th>
                                <th class="p-2.5">Example Value</th>
                                <th class="p-2.5">Description</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800 text-gray-300">
                            <tr><td class="p-2.5 font-mono text-blue-400">X-Powered-By</td><td class="p-2.5 font-mono">Yuki-Music-Engine</td><td class="p-2.5">API Engine identifier</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-API-Version</td><td class="p-2.5 font-mono">1.3.0</td><td class="p-2.5">Current API schema version</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-Total-Songs</td><td class="p-2.5 font-mono">5778</td><td class="p-2.5">Total tracks in database</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-RateLimit-Limit</td><td class="p-2.5 font-mono">60</td><td class="p-2.5">Max requests allowed per minute per IP</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-RateLimit-Remaining</td><td class="p-2.5 font-mono">59</td><td class="p-2.5">Remaining request quota for current window</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-Response-Time-MS</td><td class="p-2.5 font-mono">1.25ms</td><td class="p-2.5">Total server-side processing duration</td></tr>
                            <tr><td class="p-2.5 font-mono text-blue-400">X-Documentation</td><td class="p-2.5 font-mono">{base}/docs</td><td class="p-2.5">Link to this documentation</td></tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Section 3: Rate Limiting & Hints -->
            <section id="ratelimits" class="glass rounded-2xl p-6 border border-gray-800">
                <h2 class="text-xl font-bold text-gray-100 mb-2 flex items-center gap-2">
                    <i class="fa-solid fa-shield-halved text-emerald-400"></i> Rate Limits & Smart Hints
                </h2>
                <p class="text-xs text-gray-400 leading-relaxed mb-3">
                    All requests include a helpful <code class="text-indigo-300 font-mono">hint</code> field in the response JSON to guide developers on parameters, best practices, and next steps.
                </p>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <pre><code class="language-json">{{
  "success": false,
  "error": "Route Not Found",
  "code": "NOT_FOUND",
  "status_code": 404,
  "message": "Endpoint '/api/invalid' does not exist.",
  "hint": "Check the available_endpoints directory below or visit /docs"
}}</code></pre>
                </div>
            </section>

            <!-- Section 4: Endpoints Reference -->
            <!-- Search -->
            <section id="search" class="glass rounded-2xl p-6 border border-gray-800 space-y-3">
                <div class="flex items-center gap-3">
                    <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                    <h3 class="text-lg font-bold font-mono text-gray-100">/api/search</h3>
                </div>
                <p class="text-xs text-gray-400">Searches songs by keywords, song title, or artist with token relevance ranking.</p>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <p class="text-xs text-gray-400 mb-1 font-semibold">Example Request:</p>
                    <pre><code class="language-bash">curl -X GET "{base}/api/search?q=Sun%20Saathiya&limit=1"</code></pre>
                    <p class="text-xs text-gray-400 mt-3 mb-1 font-semibold">Example Response:</p>
                    <pre><code class="language-json">{{
  "success": true,
  "total_results": 1,
  "query": "Sun Saathiya",
  "hint": "Use /api/song/{{video_id}} for direct lookups or stream directly via 'stream_url'",
  "results": [
    {{
      "video_id": "UNs50T6EYwE",
      "title": "Sun Saathiya - Full Video | Disney'S Abcd 2 | Varun Dhawan, Shraddha Kapoor",
      "stream_url": "https://yukiapi.site/file/UNs50T6EYwE",
      "source": "yukiapi_cloud",
      "thumbnail": "https://img.youtube.com/vi/UNs50T6EYwE/hqdefault.jpg"
    }}
  ]
}}</code></pre>
                </div>
            </section>

            <!-- Song by ID -->
            <section id="song" class="glass rounded-2xl p-6 border border-gray-800 space-y-3">
                <div class="flex items-center gap-3">
                    <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                    <h3 class="text-lg font-bold font-mono text-gray-100">/api/song/{{video_id}}</h3>
                </div>
                <p class="text-xs text-gray-400">Lookup single track metadata and streaming URL by YouTube 11-char Video ID.</p>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <pre><code class="language-bash">curl -X GET "{base}/api/song/UNs50T6EYwE"</code></pre>
                </div>
            </section>

            <!-- Random -->
            <section id="random" class="glass rounded-2xl p-6 border border-gray-800 space-y-3">
                <div class="flex items-center gap-3">
                    <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                    <h3 class="text-lg font-bold font-mono text-gray-100">/api/random?limit=10</h3>
                </div>
                <p class="text-xs text-gray-400">Returns a random playlist of songs (ideal for Music Bot shuffle/autoplay).</p>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <pre><code class="language-bash">curl -X GET "{base}/api/random?limit=5"</code></pre>
                </div>
            </section>

            <!-- Stats -->
            <section id="stats" class="glass rounded-2xl p-6 border border-gray-800 space-y-3">
                <div class="flex items-center gap-3">
                    <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">GET</span>
                    <h3 class="text-lg font-bold font-mono text-gray-100">/api/stats</h3>
                </div>
                <p class="text-xs text-gray-400">Health check, song counts, and active rate limit settings.</p>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <pre><code class="language-bash">curl -X GET "{base}/api/stats"</code></pre>
                </div>
            </section>

            <!-- Code Examples -->
            <section id="code-python" class="glass rounded-2xl p-6 border border-gray-800 space-y-3">
                <h2 class="text-lg font-bold text-gray-100 flex items-center gap-2">
                    <i class="fa-brands fa-python text-yellow-400"></i> Python Music Bot Integration (PyTgCalls / Discord)
                </h2>
                <div class="bg-gray-950 p-4 rounded-xl border border-gray-800">
                    <pre><code class="language-python">import aiohttp
import asyncio

async def search_and_play(query: str):
    api_url = f"{base}/api/search?q={{query}}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()
            if data.get("success") and data.get("results"):
                song = data["results"][0]
                print(f"🎵 Title: {{song['title']}}")
                print(f"🔗 Stream URL: {{song['stream_url']}}")
                return song["stream_url"]
            print("Song not found in cache")

# Run search
asyncio.run(search_and_play("Kesariya"))</code></pre>
                </div>
            </section>
        </div>
    </div>

    <!-- Footer -->
    <footer class="border-t border-gray-800/80 py-6 text-center text-xs text-gray-500">
        <p>© 2026 Free Songs API · Open Source Serverless Music Index</p>
    </footer>
</body>
</html>
"""
    return HTMLResponse(content=docs_html)

# ── API Endpoints ────────────────────────────────────────────────────────────
@app.get("/api/search", response_model=SearchResponse, summary="Search songs by keyword or title")
async def api_search(
    q: str = Query(..., description="Song name, artist keyword, or YouTube Video ID"),
    limit: int = Query(10, ge=1, le=50, description="Max number of results to return")
):
    """Search songs with smart multi-token relevance ranking"""
    results = rank_search(q, limit=limit)
    
    # Fallback to MongoDB if in-memory returned empty and mongo is configured
    if not results and mongo_col is not None:
        try:
            db_matches = list(mongo_col.find(
                {"$or": [
                    {"video_id": q},
                    {"title": {"$regex": re.escape(q), "$options": "i"}}
                ]}
            ).limit(limit))
            
            for doc in db_matches:
                vid = doc.get("video_id")
                url = doc.get("yukiapi_url") or doc.get("catbox_link")
                if vid and url:
                    results.append({
                        "video_id": vid,
                        "title": doc.get("title") or f"Song {vid}",
                        "stream_url": url,
                        "source": doc.get("source", "cloud"),
                        "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                    })
        except Exception as e:
            print(f"Mongo fallback error: {e}")

    hint = "Use /api/song/{video_id} for direct lookups or stream directly via 'stream_url'" if results else "No matches found. Try searching by YouTube Video ID or broader keywords."
    return {
        "success": True,
        "total_results": len(results),
        "query": q,
        "hint": hint,
        "results": results
    }

@app.get("/api/song/{video_id}", summary="Lookup a song by YouTube Video ID")
async def api_get_song(video_id: str = Path(..., description="YouTube 11-char Video ID")):
    """Get single song metadata and direct stream URL by Video ID"""
    if video_id in SONGS_BY_ID:
        return {
            "success": True,
            "hint": "Stream audio/video directly using the 'stream_url' link.",
            "song": SONGS_BY_ID[video_id]
        }

    if mongo_col is not None:
        try:
            doc = mongo_col.find_one({"video_id": video_id})
            if doc:
                url = doc.get("yukiapi_url") or doc.get("catbox_link")
                return {
                    "success": True,
                    "hint": "Stream audio/video directly using the 'stream_url' link.",
                    "song": {
                        "video_id": video_id,
                        "title": doc.get("title") or f"Song {video_id}",
                        "stream_url": url,
                        "source": doc.get("source", "cloud"),
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    }
                }
        except Exception as e:
            print(f"Mongo lookup error: {e}")

    raise HTTPException(
        status_code=404,
        detail=f"Song with Video ID '{video_id}' not found in database"
    )

@app.get("/api/random", response_model=SearchResponse, summary="Get random songs (discovery / shuffle)")
async def api_random(limit: int = Query(10, ge=1, le=50, description="Number of random songs")):
    """Get a random playlist of songs"""
    count = min(limit, len(SONGS_DATA))
    sampled = random.sample(SONGS_DATA, count) if SONGS_DATA else []
    return {
        "success": True,
        "total_results": len(sampled),
        "query": "random",
        "hint": "Call /api/random again to get a fresh shuffle playlist.",
        "results": sampled
    }

@app.get("/api/songs", summary="Get paginated list of all songs")
async def api_list_songs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page")
):
    """Browse the complete 5,778+ songs catalog with pagination"""
    start = (page - 1) * limit
    end = start + limit
    items = SONGS_DATA[start:end]
    total_pages = (len(SONGS_DATA) + limit - 1) // limit
    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total_songs": len(SONGS_DATA),
        "total_pages": total_pages,
        "hint": f"Next page is /api/songs?page={page+1}&limit={limit}" if page < total_pages else "Reached last page of catalog.",
        "results": items
    }

@app.get("/api/stats", response_model=StatsResponse, summary="Get API health & catalog statistics")
async def api_stats():
    """Returns total song count, cloud sources, and rate limit settings"""
    yuki_count = sum(1 for s in SONGS_DATA if "yukiapi" in s.get("stream_url", ""))
    catbox_count = len(SONGS_DATA) - yuki_count
    return {
        "success": True,
        "total_songs": len(SONGS_DATA),
        "yukiapi_cloud_songs": yuki_count,
        "catbox_songs": catbox_count,
        "rate_limit_per_minute": DEFAULT_RATE_LIMIT,
        "status": "healthy",
        "version": "1.3.0",
        "hint": "Visit /docs for interactive developer guide and code samples."
    }

