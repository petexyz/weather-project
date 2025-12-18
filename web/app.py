#!/usr/bin/env python3
"""
Weather Dashboard API - Refactored
Clean architecture with proper separation of concerns
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import signal
import sys

from config import Config
from database import DatabaseManager

# Initialize
config = Config()
db = DatabaseManager(config.database)
app = FastAPI(title="Lowell Weather Dashboard", version="2.0")


# Graceful shutdown
def shutdown_handler(signum, frame):
    """Handle shutdown gracefully"""
    print("Shutting down...")
    db.close()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


@app.get("/api/latest")
def api_latest():
    """Get most recent weather reading"""
    data = db.get_latest_reading()
    if not data:
        raise HTTPException(status_code=404, detail="No data available")
    return data


@app.get("/api/history/24h")
def api_24h_history():
    """Get last 24 hours of data"""
    data = db.get_24h_history()
    return {"data": data}


@app.get("/api/history/7d")
def api_7d_summary():
    """Get 7-day hourly averages"""
    data = db.get_7d_summary()
    return {"data": data}


@app.get("/api/stats")
def api_stats():
    """Get database and system statistics"""
    stats = db.get_statistics()
    if not stats:
        raise HTTPException(status_code=500, detail="Could not fetch statistics")
    
    # Add collection count from file
    try:
        count_file = config.count_file
        if count_file.exists():
            stats['collection_count'] = int(count_file.read_text().strip())
        else:
            stats['collection_count'] = None
    except Exception:
        stats['collection_count'] = None
    
    return stats


@app.get("/api/health")
def api_health():
    """Health check endpoint"""
    try:
        # Test database connection
        stats = db.get_statistics()
        if stats:
            return {"status": "healthy", "database": "connected"}
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "database": "error"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the dashboard HTML"""
    try:
        html_path = Path("/app/static/index.html")
        return html_path.read_text()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load page: {e}")


# Serve static files
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.web.host,
        port=config.web.port,
        log_level="info"
    )