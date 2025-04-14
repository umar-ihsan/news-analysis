import spacy
from typing import List, Dict, Any
import numpy as np
from ..models.schemas import ClusterAnalysisResponse, PossibilityItem
from ..utils.db import Database
from datetime import datetime
import logging
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FutureAnalysisService:
    def __init__(self):
        logger.info("Initializing FutureAnalysisService")
        # Load the smaller English language model for better performance
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Successfully loaded spaCy model")
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {str(e)}")
            raise
            
        # Keywords that indicate future predictions
        self.future_indicators = [
            "will", "could", "might", "may", "expect", "predict",
            "forecast", "projected", "potential", "likely", "possible",
            "anticipated", "planned", "scheduled", "upcoming"
        ]
        
        # Batch processing settings
        self.batch_size = 5  # Process 5 articles at a time
        logger.info("FutureAnalysisService initialized successfully")

    async def analyze_cluster(self, cluster_id: str) -> ClusterAnalysisResponse:
        logger.info(f"Starting analysis for cluster: {cluster_id}")
        # Get articles from database
        articles = await Database.get_cluster_articles(cluster_id)
        if not articles:
            logger.error(f"No articles found for cluster {cluster_id}")
            raise ValueError(f"No articles found for cluster {cluster_id}")
        
        logger.info(f"Retrieved {len(articles)} articles for analysis")
        
        # Process articles in batches
        all_possibilities = []
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i:i + self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1} with {len(batch)} articles")
            batch_possibilities = await self._process_article_batch(batch)
            all_possibilities.extend(batch_possibilities)
        
        logger.info(f"Found {len(all_possibilities)} initial possibilities")
        
        # Merge and score possibilities
        merged_possibilities = self._merge_similar_possibilities(all_possibilities)
        logger.info(f"Merged into {len(merged_possibilities)} unique possibilities")
        
        scored_possibilities = self._calculate_likelihood_scores(merged_possibilities)
        logger.info(f"Calculated scores for all possibilities")
        
        # Create response
        response = ClusterAnalysisResponse(
            clusterId=cluster_id,
            clusterTopic=articles[0].get("title", "Unknown Topic"),
            possibilities=scored_possibilities
        )
        
        # Save analysis to database
        logger.info("Saving analysis results to database")
        await Database.save_analysis(response.dict())
        logger.info("Analysis completed and saved successfully")
        
        return response

    async def _process_article_batch(self, articles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        possibilities = []
        
        for idx, article in enumerate(articles):
            logger.debug(f"Processing article {idx+1}/{len(articles)}")
            
            # Skip articles with no content
            if not article.get("content"):
                logger.warning(f"Skipping article {idx+1} - no content found")
                continue
                
            # Process each article
            try:
                doc = self.nlp(article["content"])
                
                # Process each sentence
                sentence_count = 0
                future_sentence_count = 0
                for sent in doc.sents:
                    sentence_count += 1
                    # Check if sentence contains future indicators
                    if any(indicator in sent.text.lower() for indicator in self.future_indicators):
                        future_sentence_count += 1
                        # Extract the main prediction
                        prediction = self._extract_prediction(sent)
                        if prediction:
                            possibilities.append({
                                "text": str(sent),
                                "prediction": prediction,
                                "source": article.get("publication", "Unknown Source"),
                                "date": article.get("date", "Unknown Date"),
                                "url": article.get("url", "#")
                            })
                
                logger.debug(f"Found {future_sentence_count} future-related sentences out of {sentence_count} total sentences")
            except Exception as e:
                logger.error(f"Error processing article {idx+1}: {str(e)}")
                continue
        
        logger.info(f"Batch processing complete. Found {len(possibilities)} possibilities in this batch")
        return possibilities

    def _calculate_likelihood_scores(self, possibilities: List[Dict[str, Any]]) -> List[PossibilityItem]:
        scored_items = []
        
        for idx, possibility in enumerate(possibilities):
            # Calculate likelihood score based on various factors
            base_score = 50  # Start with a neutral score
            
            # 1. Number of sources (30% weight)
            source_count = len(set(p["source"] for p in possibility["similar_mentions"]))
            source_score = min(source_count * 10, 30)
            
            # 2. Confidence markers in text (20% weight)
            confidence_score = self._analyze_confidence_markers(possibility["text"])
            
            # 3. Source reliability (using biasness as a factor) (20% weight)
            source_reliability = self._calculate_source_reliability(possibility)
            
            # 4. Recency of predictions (30% weight)
            recency_score = self._calculate_recency_score(possibility)
            
            # Combine scores with weights
            final_score = (
                source_score +
                min(confidence_score, 20) +
                source_reliability +
                recency_score
            )
            
            # Normalize to 0-100
            final_score = min(max(final_score, 0), 100)
            
            scored_items.append(PossibilityItem(
                id=str(idx + 1),
                title=possibility["prediction"][:100],  # Limit title length
                likelihoodScore=final_score,
                summary=possibility["text"][:200],
                reasoning=self._generate_reasoning(possibility, source_count)
            ))
        
        return sorted(scored_items, key=lambda x: x.likelihoodScore, reverse=True)

    def _calculate_source_reliability(self, possibility: Dict[str, Any]) -> float:
        # Simple source reliability score based on number of reliable sources
        reliable_sources = 0
        total_sources = len(possibility["similar_mentions"]) + 1
        
        for mention in possibility["similar_mentions"] + [possibility]:
            # Consider source more reliable if it's not marked as highly biased
            if mention.get("biasness", "Unclassified") not in ["LABEL_2", "Unclassified"]:
                reliable_sources += 1
        
        return (reliable_sources / total_sources) * 20  # Max 20 points

    def _calculate_recency_score(self, possibility: Dict[str, Any]) -> float:
        try:
            # Convert date strings to datetime objects
            dates = []
            for mention in possibility["similar_mentions"] + [possibility]:
                try:
                    date = datetime.strptime(mention["date"], "%Y-%m-%d")
                    dates.append(date)
                except:
                    continue
            
            if not dates:
                return 15  # Default score if no valid dates
            
            # Calculate days from most recent mention
            most_recent = max(dates)
            days_ago = (datetime.now() - most_recent).days
            
            # Score based on recency (max 30 points)
            if days_ago <= 1:
                return 30
            elif days_ago <= 3:
                return 25
            elif days_ago <= 7:
                return 20
            elif days_ago <= 14:
                return 15
            else:
                return 10
                
        except Exception:
            return 15  # Default score if there's any error

    def _analyze_confidence_markers(self, text: str) -> float:
        confidence_markers = {
            "definitely": 15,
            "certainly": 12,
            "likely": 10,
            "probably": 8,
            "possibly": 5,
            "maybe": 3,
            "uncertain": -5,
            "unlikely": -10
        }
        
        score = 0
        doc = self.nlp(text.lower())
        for word in doc:
            if word.text in confidence_markers:
                score += confidence_markers[word.text]
        
        return score

    def _generate_reasoning(self, possibility: Dict[str, Any], source_count: int) -> str:
        reasoning = []
        
        # Add source count information
        reasoning.append(f"This prediction appears in {source_count} different sources.")
        
        # Add key evidence
        reasoning.append(f"Key evidence: {possibility['text']}")
        
        # Add source information
        sources = [possibility["source"]] + [m["source"] for m in possibility["similar_mentions"]]
        reasoning.append(f"Sources reporting this: {', '.join(set(sources))}")
        
        # Add recency information
        try:
            dates = [datetime.strptime(possibility["date"], "%Y-%m-%d")]
            dates.extend([datetime.strptime(m["date"], "%Y-%m-%d") for m in possibility["similar_mentions"]])
            most_recent = max(dates).strftime("%Y-%m-%d")
            reasoning.append(f"Most recent mention: {most_recent}")
        except:
            pass
        
        return " ".join(reasoning)

    def _merge_similar_possibilities(self, possibilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged = []
        for possibility in possibilities:
            # Find similar existing predictions
            similar_found = False
            for existing in merged:
                if self._are_predictions_similar(possibility["prediction"], existing["prediction"]):
                    existing["similar_mentions"].append(possibility)
                    similar_found = True
                    break
            
            if not similar_found:
                possibility["similar_mentions"] = []
                merged.append(possibility)
        
        return merged

    def _are_predictions_similar(self, pred1: str, pred2: str) -> bool:
        # Using simpler similarity check with smaller model
        doc1 = self.nlp(pred1)
        doc2 = self.nlp(pred2)
        
        # Calculate word overlap
        words1 = set(token.text.lower() for token in doc1 if not token.is_stop and not token.is_punct)
        words2 = set(token.text.lower() for token in doc2 if not token.is_stop and not token.is_punct)
        
        if not words1 or not words2:
            return False
            
        overlap = len(words1.intersection(words2)) / min(len(words1), len(words2))
        return overlap > 0.6  # 60% word overlap threshold

    def _extract_prediction(self, sent) -> str:
        # Simple extraction - just return the sentence text
        # This could be enhanced with more sophisticated NLP techniques if needed
        return sent.text 

    @classmethod
    async def get_cluster_articles(cls, cluster_id: str) -> List[Dict[str, Any]]:
        try:
            logger.info(f"Fetching cluster with ID: {cluster_id}")
            
            # Convert string to ObjectId
            object_id = ObjectId(cluster_id)
            
            # Get cluster first
            cluster = await cls.clusters_collection.find_one({"_id": object_id})
            if not cluster:
                logger.warning(f"No cluster found with ID: {cluster_id}")
                return []
            
            logger.info(f"Cluster found. Fetching articles for cluster ID: {cluster_id}")
            
            # Get all articles in the cluster
            articles = []
            for article_id in cluster["articles"]:
                article = await cls.articles_collection.find_one({"_id": article_id})
                if article:
                    # Convert content array to single string for processing
                    article["content"] = " ".join(article["content"])
                    articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles for cluster ID: {cluster_id}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching articles for cluster ID: {cluster_id}: {str(e)}")
            return [] 