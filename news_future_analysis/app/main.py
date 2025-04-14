from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from .services.future_analysis import FutureAnalysisService
from .models.schemas import ClusterAnalysisResponse, PossibilityItem
from .utils.db import Database
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="News Future Analysis API",
    description="API for analyzing future possibilities from news article clusters",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the application...")
    try:
        # Async connection
        await Database.connect()
        logger.info("Successfully connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

@app.get("/")
async def root():
    return {"message": "News Future Analysis API is running"}

@app.post("/analyze/cluster/{cluster_id}", response_model=ClusterAnalysisResponse)
async def analyze_cluster(cluster_id: str):
    logger.info(f"Received analysis request for cluster: {cluster_id}")
    try:
        analysis_service = FutureAnalysisService()
        logger.info("Created FutureAnalysisService instance")
        
        result = await analysis_service.analyze_cluster(cluster_id)
        logger.info(f"Successfully analyzed cluster {cluster_id}")
        return result
    except ValueError as e:
        logger.error(f"Cluster not found error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing cluster {cluster_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 