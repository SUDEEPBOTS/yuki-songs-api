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
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(
    title="Free 5,000+ Music & Songs API",
    description="High-performance, ultra-fast free REST API with 5,700+ cached songs ready for direct audio/video streaming with built-in DDoS & Rate Limiting Protection.",
    version="1.1.0",
    docs_url="/docs",
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

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Apply rate limiting to all /api/* routes
    if request.url.path.startswith("/api/"):
        try:
            rate_limiter.check(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": "Too Many Requests",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": exc.detail,
                    "retry_after_seconds": 60
                },
                headers=exc.headers
            )
    return await call_next(request)

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
    results: List[SongItem]

class StatsResponse(BaseModel):
    success: bool
    total_songs: int
    yukiapi_cloud_songs: int
    catbox_songs: int
    rate_limit_per_minute: int
    status: str
    version: str

def rank_search(query: str, limit: int = 10) -> List[dict]:
    """Smart multi-keyword token matching and ranking algorithm"""
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

        # Exact Video ID
        if clean_q == vid:
            return [song]

        # Exact Title Substring
        if clean_q in title_lower:
            if title_lower.startswith(clean_q):
                exact_matches.append((0, song))
            else:
                exact_matches.append((1, song))
            continue

        # All tokens match
        if all(token in title_lower for token in tokens):
            token_matches.append((2, song))
            continue

        # Any token matches
        match_count = sum(1 for token in tokens if token in title_lower)
        if match_count > 0:
            prefix_matches.append((10 - match_count, song))

    # Combine & Sort
    combined = sorted(exact_matches + token_matches + prefix_matches, key=lambda x: x[0])
    results = [item[1] for item in combined[:limit]]
    return results

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    """Serves the interactive Web Search & Stream Playground"""
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
                    <p class="text-xs text-gray-400">5,778+ Cloud Cached Songs · DDoS Protected</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <a href="/docs" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 transition">
                    <i class="fa-solid fa-book-open mr-1.5 text-blue-400"></i> API Docs
                </a>
                <a href="https://github.com" target="_blank" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/30 transition">
                    <i class="fa-brands fa-github mr-1.5"></i> GitHub
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
        <!-- Hero Section -->
        <div class="text-center mb-10">
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium mb-4">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> 5,778+ Songs Available · Protected & Rate-Limited
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
        <div id="resultsGrid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
        <div id="loading" class="hidden text-center py-10">
            <i class="fa-solid fa-circle-notch fa-spin text-blue-500 text-3xl"></i>
            <p class="text-xs text-gray-400 mt-2">Searching 5,778+ tracks...</p>
        </div>
        <div id="noResults" class="hidden text-center py-12 glass rounded-2xl">
            <i class="fa-regular fa-face-frown text-gray-500 text-4xl mb-2"></i>
            <p class="text-sm font-semibold text-gray-300">No matching songs found</p>
            <p class="text-xs text-gray-500 mt-1">Try another keyword or search by YouTube Video ID</p>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-800/80 py-6 text-center text-xs text-gray-500">
        <div class="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-2">
            <p>© 2026 Free Songs API · Open Source Serverless Music Index</p>
            <div class="flex items-center gap-4">
                <a href="/api/stats" class="hover:text-gray-300">API Stats</a>
                <a href="/docs" class="hover:text-gray-300">Swagger Docs</a>
                <a href="/api/random" class="hover:text-gray-300">Random Endpoint</a>
            </div>
        </div>
    </footer>

    <!-- Script -->
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
                const res = await fetch('/api/random?limit=12');
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

# API Endpoints
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

    return {
        "success": True,
        "total_results": len(results),
        "query": q,
        "results": results
    }

@app.get("/api/song/{video_id}", summary="Lookup a song by YouTube Video ID")
async def api_get_song(video_id: str = Path(..., description="YouTube 11-char Video ID")):
    """Get single song metadata and direct stream URL by Video ID"""
    if video_id in SONGS_BY_ID:
        return {"success": True, "song": SONGS_BY_ID[video_id]}

    if mongo_col is not None:
        try:
            doc = mongo_col.find_one({"video_id": video_id})
            if doc:
                url = doc.get("yukiapi_url") or doc.get("catbox_link")
                return {
                    "success": True,
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

    raise HTTPException(status_code=404, detail="Song not found in database")

@app.get("/api/random", response_model=SearchResponse, summary="Get random songs (discovery / shuffle)")
async def api_random(limit: int = Query(10, ge=1, le=50, description="Number of random songs")):
    """Get a random playlist of songs"""
    count = min(limit, len(SONGS_DATA))
    sampled = random.sample(SONGS_DATA, count) if SONGS_DATA else []
    return {
        "success": True,
        "total_results": len(sampled),
        "query": "random",
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
    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total_songs": len(SONGS_DATA),
        "total_pages": (len(SONGS_DATA) + limit - 1) // limit,
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
        "version": "1.1.0"
    }

