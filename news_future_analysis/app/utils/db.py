from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any
import logging
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    client = None
    db = None
    clusters_collection = None
    articles_collection = None
    analysis_collection = None

    @classmethod
    async def connect(cls):
        try:
            # Using motor for async MongoDB operations
            logger.info("Attempting to connect to MongoDB...")
            cls.client = AsyncIOMotorClient("mongodb+srv://jamshidjunaid763:JUNAID12345@insightwirecluster.qz5cz.mongodb.net/?retryWrites=true&w=majority&appName=InsightWireCluster")
            cls.db = cls.client["Scraped-Articles-10"]
            cls.clusters_collection = cls.db["categorizedarticles"]  # Collection containing clusters
            cls.articles_collection = cls.db["Articles2"]  # Collection containing actual articles
            cls.analysis_collection = cls.db["future_analysis"]
            logger.info("Successfully connected to MongoDB and initialized collections")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    @classmethod
    async def get_cluster_articles(cls, cluster_id: str) -> List[Dict[str, Any]]:
        try:
            # Convert string to ObjectId if it's not already
            if not isinstance(cluster_id, ObjectId):
                logger.info(f"Converting cluster_id string {cluster_id} to ObjectId")
                try:
                    cluster_id = ObjectId(cluster_id)
                except Exception as e:
                    logger.error(f"Failed to convert cluster_id to ObjectId: {str(e)}")
                    return []

            # First, get the cluster document from categorizedarticles collection
            logger.info(f"Fetching cluster with ObjectId: {cluster_id}")
            cluster = await cls.clusters_collection.find_one({"_id": cluster_id})
            
            if not cluster:
                logger.warning(f"No cluster found with ID: {cluster_id}")
                return []
            
            # Log the cluster structure
            logger.info(f"Found cluster. Available fields: {cluster.keys()}")
            
            # Get the article IDs from the cluster
            article_ids = cluster.get("articles", [])
            if not article_ids:
                logger.warning("Cluster has no articles field or it's empty")
                return []
                
            logger.info(f"Cluster contains {len(article_ids)} article references")
            
            # Fetch all referenced articles from Articles2 collection
            articles = []
            for article_id in article_ids:
                try:
                    # Convert article_id to ObjectId if needed
                    if not isinstance(article_id, ObjectId):
                        article_id = ObjectId(article_id)
                        
                    # Look for the article in Articles2 collection
                    article = await cls.articles_collection.find_one({"_id": article_id})
                    if article:
                        # Log article structure for debugging
                        logger.debug(f"Found article {article_id}. Fields: {article.keys()}")
                        
                        # Process article content if it exists
                        if "content" in article:
                            if isinstance(article["content"], list):
                                article["content"] = " ".join(article["content"])
                            articles.append(article)
                            logger.debug(f"Successfully processed article {article_id}")
                        else:
                            logger.warning(f"Article {article_id} has no content field")
                    else:
                        logger.warning(f"Article not found in Articles2 collection: {article_id}")
                except Exception as e:
                    logger.error(f"Error processing article {article_id}: {str(e)}")
                    continue
            
            logger.info(f"Successfully fetched {len(articles)} articles out of {len(article_ids)} referenced")
            return articles
            
        except Exception as e:
            logger.error(f"Error in get_cluster_articles: {str(e)}")
            logger.exception("Full traceback:")
            return []

    @classmethod
    async def save_analysis(cls, analysis_result: Dict[str, Any]):
        try:
            logger.info(f"Saving analysis for cluster: {analysis_result.get('clusterId')}")
            # Store the analysis result
            await cls.analysis_collection.update_one(
                {"clusterId": analysis_result["clusterId"]},
                {"$set": analysis_result},
                upsert=True
            )
            logger.info("Analysis saved successfully")
        except Exception as e:
            logger.error(f"Failed to save analysis: {str(e)}")
            raise 