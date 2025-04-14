from pydantic import BaseModel, Field
from typing import List

class PossibilityItem(BaseModel):
    id: str
    title: str
    likelihoodScore: float = Field(ge=0, le=100)  # Score between 0 and 100
    summary: str
    reasoning: str

class ClusterAnalysisResponse(BaseModel):
    clusterId: str
    clusterTopic: str
    possibilities: List[PossibilityItem] 