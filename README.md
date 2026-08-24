<div align="center">

<!-- Animated Header Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=1,11,20&height=220&section=header&text=🎵%20Free%20Songs%20API&fontSize=48&fontColor=ffffff&animation=twinkling&fontAlignY=38&desc=High-Performance%20Serverless%20Music%20Search%20%26%20Stream%20Engine&descAlignY=58&descSize=18&descAlign=50" width="100%"/>

<!-- Badges Row 1: Frameworks & Deploy -->
<p align="center">
  <a href="https://vercel.com/new/clone?repository-url=https://github.com/SUDEEPBOTS/yuki-songs-api">
    <img src="https://vercel.com/button" alt="Deploy with Vercel" height="28">
  </a>
</p>

<!-- Badges Row 2: Stats & Tech -->
<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python_3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+"/>
  <img src="https://img.shields.io/badge/Vercel_Serverless-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Vercel"/>
  <img src="https://img.shields.io/badge/Indexed_Songs-5%2C778+-7928CA?style=for-the-badge&logo=music&logoColor=white" alt="Indexed Tracks"/>
  <img src="https://img.shields.io/badge/Latency-%3C_2ms-0070F3?style=for-the-badge&logo=speedtest&logoColor=white" alt="Latency"/>
  <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="MIT License"/>
</p>

<p align="center">
  <b>⚡ Sub-2ms Latency</b> · <b>🔍 Smart Multi-Keyword Matching</b> · <b>🛡️ Anti-DDoS Sliding Window</b> · <b>📱 Built-in Web Player & Scratchpad</b>
</p>

---

</div>

## 🌟 Highlights & Features

<table>
  <tr>
    <td width="50%">
      <h3 align="left">⚡ Lightning Fast Serverless Engine</h3>
      <p>Pre-bundled in-memory token trie search index answering queries in <b>&lt; 2 milliseconds</b> with zero database overhead.</p>
    </td>
    <td width="50%">
      <h3 align="left">🔍 Smart Multi-Token Search</h3>
      <p>Matches artist names, song titles, and multi-word keywords in any order with automatic relevance scoring.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3 align="left">🛡️ Sliding-Window Anti-DDoS</h3>
      <p>Automatic per-IP rate limiting (60 req/min) preventing scraper abuse, bot flooding, and DDoS vectors.</p>
    </td>
    <td width="50%">
      <h3 align="left">📱 Interactive Console & Scratchpad</h3>
      <p>Modern glassmorphism Web Player at <code>/</code> and live interactive developer scratchpad console at <code>/docs</code>.</p>
    </td>
  </tr>
</table>

---

## 🚀 1-Click Free Deployment

Deploy your own standalone music search API to Vercel in seconds:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/SUDEEPBOTS/yuki-songs-api)

1. Click the **Deploy with Vercel** button above.
2. Connect your GitHub account and create the repository.
3. *(Optional)* Add `MONGO_URI` in Vercel Environment Variables if you want real-time dynamic sync with an external database.
4. Your API is live instantly on `https://your-project.vercel.app`! 🎉

---

## 📡 REST API Reference

### 1. 🔍 Keyword Search
Search across 5,778+ songs with multi-word relevance scoring.

```http
GET /api/search?q={query}&limit={limit}
```

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `q` | `string` | **Required** | Song name, artist keyword, or YouTube Video ID |
| `limit` | `integer` | `10` | Number of results to return (1 - 50) |

<details>
<summary><b>📋 View Example JSON Response (Click to expand)</b></summary>

```json
{
  "success": true,
  "total_results": 1,
  "query": "Sun Saathiya",
  "hint": "Use /api/song/{video_id} for direct lookups or stream directly via 'stream_url'",
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
</details>

---

### 2. 🆔 YouTube Video ID Lookup
Instant $O(1)$ constant-time lookup by YouTube 11-char Video ID.

```http
GET /api/song/{video_id}
```

<details>
<summary><b>📋 View Example JSON Response (Click to expand)</b></summary>

```json
{
  "success": true,
  "hint": "Stream audio/video directly using the 'stream_url' link.",
  "song": {
    "video_id": "UNs50T6EYwE",
    "title": "Sun Saathiya - Full Video | Disney'S Abcd 2",
    "stream_url": "https://yukiapi.site/file/UNs50T6EYwE",
    "source": "yukiapi_cloud",
    "thumbnail": "https://img.youtube.com/vi/UNs50T6EYwE/hqdefault.jpg"
  }
}
```
</details>

---

### 3. 🎲 Random Songs (Discovery & Autoplay)
Returns a randomized playlist of tracks (ideal for Telegram/Discord music bot autoplay & radio).

```http
GET /api/random?limit=10
```

---

### 4. 📊 Catalog Statistics & Health Check
```http
GET /api/stats
```

---

## 🏷️ Custom Telemetry Headers

Every HTTP response includes detailed diagnostics and telemetry headers:

```http
X-Powered-By: Yuki-Music-Engine
X-API-Version: 1.4.0
X-Total-Songs: 5778
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-Response-Time-MS: 1.25ms
X-Documentation: https://your-api.vercel.app/docs
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
```

---

## 🤖 Music Bot Integration Code Snippets

### 🐍 Python (Telegram Bot / PyTgCalls / Pyrogram)
```python
import aiohttp
import asyncio

async def play_music(query: str):
    api_url = f"https://your-api.vercel.app/api/search?q={query}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()
            if data.get("success") and data.get("results"):
                track = data["results"][0]
                print(f"🎶 Title: {track['title']}")
                print(f"🔗 Direct Stream: {track['stream_url']}")
                return track["stream_url"]
            print("Track not found in index.")

asyncio.run(play_music("Kesariya"))
```

### 🟨 JavaScript / Node.js (Discord.js)
```javascript
const axios = require('axios');

async function searchTrack(query) {
    const res = await axios.get(`https://your-api.vercel.app/api/search`, {
        params: { q: query, limit: 3 }
    });
    console.log(res.data.results);
}

searchTrack("Sidhu Moosewala");
```

---

## 🛠️ Local Development

```bash
# 1. Clone the repository
git clone https://github.com/SUDEEPBOTS/yuki-songs-api.git
cd yuki-songs-api

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start local development server
uvicorn api.index:app --reload --port 8000
```
Open `http://localhost:8000` in your browser to view the interactive Web UI and test queries!

---

<div align="center">

## ⚖️ Legal Disclaimer & Copyright Notice

</div>

> [!IMPORTANT]
> **NO COPYRIGHT INFRINGEMENT INTENDED · ZERO MEDIA HOSTING ON GITHUB**
>
> 1. **No Media Files Stored on this Repository:** This repository and GitHub do **NOT** host, store, upload, transmit, or distribute any copyrighted MP3, MP4, video, or audio media files. This repository consists **exclusively of open-source software code, search algorithms, and public metadata references**.
>
> 2. **Information Location / Search Indexing Tool:** This API operates strictly as a **metadata search engine and hyperlinking directory** (similar to Google Search or DuckDuckGo). All multimedia URLs indexed by this tool are hosted and stored on independent, publicly accessible third-party cloud networks over which the maintainers of this repository exercise no operational control.
>
> 3. **Non-Commercial & Educational Fair Use:** This project is created for **educational, non-profit, architectural research, and open-source demonstration purposes only** under Section 107 of the Copyright Act of 1976 (*Fair Use*).
>
> 4. **DMCA Takedown & Copyright Delisting Procedure:** We strongly respect the intellectual property rights of creators. If you are a copyright owner or authorized representative and wish to request the removal or delisting of any metadata entry or search index reference:
>    - Please open a **[DMCA Delisting Request](https://github.com/SUDEEPBOTS/yuki-songs-api/issues/new?template=dmca_takedown.md)** using our formal template.
>    - Verified requests will result in the **immediate, permanent delisting** of the referenced metadata from the index within 24 hours.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=1,11,20&height=100&section=footer" width="100%"/>

<p align="center">
  Released under the <a href="LICENSE">MIT License</a> · Built with ❤️ for Developers & Creators
</p>

</div>
