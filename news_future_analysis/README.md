# News Future Analysis Service

This service analyzes news article clusters to predict and score possible future outcomes. It uses NLP techniques to extract future-oriented statements and calculate likelihood scores for different possibilities.

## Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Download the spaCy model:
```bash
python -m spacy download en_core_web_lg
```

## Running the Service

Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

The service will be available at `http://localhost:8000`

## API Endpoints

### Analyze Cluster
- **URL**: `/analyze/cluster/{cluster_id}`
- **Method**: POST
- **Response**: JSON object containing:
  - clusterId: String
  - clusterTopic: String
  - possibilities: Array of possibility items, each containing:
    - id: String
    - title: String
    - likelihoodScore: Number (0-100)
    - summary: String
    - reasoning: String

## Integration

To integrate with your existing news app:
1. Make sure your news app can provide article clusters with the required format
2. Call the analyze endpoint with your cluster ID
3. Use the returned JSON to display the possibilities in your frontend

## Example Response

```json
{
  "clusterId": "cluster-123",
  "clusterTopic": "US-China Trade Negotiations",
  "possibilities": [
    {
      "id": "1",
      "title": "Trade Agreement Reached",
      "likelihoodScore": 75,
      "summary": "Both countries reach a compromise agreement within weeks",
      "reasoning": "Multiple sources cite progress in negotiations, with officials from both sides expressing optimism."
    }
  ]
}
``` 