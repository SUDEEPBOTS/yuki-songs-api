# 🎵 Free 5,000+ Music & Songs REST API

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/yuki-songs-api)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Songs](https://img.shields.io/badge/Indexed_Songs-5%2C778+-brightgreen.svg)](#)

A high-performance, open-source serverless REST API that indexes **5,778+ high-quality songs** with direct, instant high-speed audio/video streaming URLs. Built with **FastAPI** for sub-millisecond response latency, ready for instant **1-Click deployment on Vercel**.

---

## ✨ Features

- ⚡ **Sub-2ms Latency:** In-memory indexed token search engine for lightning fast lookups.
- 🔍 **Smart Multi-Keyword Search:** Search songs by title, artist, or keywords with relevance scoring.
- 🆔 **YouTube Video ID Lookup:** Direct `O(1)` constant-time lookup by YouTube Video ID.
- 🎲 **Random Song / Shuffle Endpoint:** Perfect for Telegram / Discord music bot radio and autoplay features.
- 📱 **Interactive Web Search Playground:** Built-in modern glassmorphism web UI with real-time audio playback.
- 🚀 **1-Click Vercel Deployment:** Zero database setup required to get started!
- 🗄️ **Optional MongoDB Sync:** Plug in `MONGO_URI` in `.env` for real-time dynamic sync.

---

## 🚀 Quick Deploy to Vercel

Click the button below to deploy your own instance of this API on Vercel for free:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/yuki-songs-api)

---

## 📡 API Endpoints

### 1. Keyword Search (Multiple Results)
Search across 5,778+ songs with keyword relevance scoring.

```http
GET /api/search?q={query}&limit={limit}
```

**Parameters:**
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | **Required** | Song name, artist keyword, or Video ID |
| `limit` | `int` | `10` | Max results to return (1 - 50) |

**Example Request:**
```bash
curl -X GET "https://your-api.vercel.app/api/search?q=Sun%20Saathiya&limit=2"
```

**Example Response:**
```json
{
  "success": true,
  "total_results": 1,
  "query": "Sun Saathiya",
  "results": [
    {
      "video_id": "UNs50T6EYwE",
      "title": "Sun Saathiya - Full Video | Disney'S Abcd 2 | Varun Dhawan, Shraddha Kapoor | Sachin Jigar | Priya S",
      "stream_url": "https://yukiapi.site/file/UNs50T6EYwE",
      "source": "yukiapi_cloud",
      "thumbnail": "https://img.youtube.com/vi/UNs50T6EYwE/hqdefault.jpg"
    }
  ]
}
```

---

### 2. Video ID Direct Lookup
Lookup single song metadata and direct stream link by YouTube Video ID.

```http
GET /api/song/{video_id}
```

**Example Request:**
```bash
curl -X GET "https://your-api.vercel.app/api/song/UNs50T6EYwE"
```

**Example Response:**
```json
{
  "success": true,
  "song": {
    "video_id": "UNs50T6EYwE",
    "title": "Sun Saathiya - Full Video | Disney'S Abcd 2",
    "stream_url": "https://yukiapi.site/file/UNs50T6EYwE",
    "source": "yukiapi_cloud",
    "thumbnail": "https://img.youtube.com/vi/UNs50T6EYwE/hqdefault.jpg"
  }
}
```

---

### 3. Random Songs (Discovery / Radio)
Fetch a random playlist of songs.

```http
GET /api/random?limit=10
```

---

### 4. Catalog Pagination
Browse the complete catalog page by page.

```http
GET /api/songs?page=1&limit=50
```

---

### 5. API Stats & Health Check
```http
GET /api/stats
```

---

## 💻 Code Examples for Music Bots

### Python (aiohttp / requests)
```python
import aiohttp
import asyncio

async def play_song(query: str):
    url = f"https://your-api.vercel.app/api/search?q={query}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if data["success"] and data["results"]:
                song = data["results"][0]
                print(f"Playing: {song['title']}")
                print(f"Stream URL: {song['stream_url']}")
                return song["stream_url"]
            print("Song not found")

asyncio.run(play_song("Arijit Singh"))
```

### JavaScript / Node.js (Axios)
```javascript
const axios = require('axios');

async function searchSongs(query) {
    const res = await axios.get(`https://your-api.vercel.app/api/search`, {
        params: { q: query, limit: 5 }
    });
    console.log(res.data.results);
}

searchSongs("Sidhu Moosewala");
```

---

## 🛠️ Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/yuki-songs-api.git
   cd yuki-songs-api
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run local development server:**
   ```bash
   uvicorn api.index:app --reload --port 8000
   ```

4. Open `http://localhost:8000` in your browser to view the interactive Web UI and test queries!

---

## 📄 License
This project is open-source and licensed under the [MIT License](LICENSE).
