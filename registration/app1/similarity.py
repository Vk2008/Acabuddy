from .models import Question
from registration.embeddings import embed
from pgvector.django import CosineDistance
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
SIMILARITY_THRESHOLD = 0.5

def find_similar_questions(text, limit=5):

    query_embedding = embed(text)

    results = (
        Question.objects
        .exclude(embedding=None)
        .annotate(similarity=1 - CosineDistance("embedding", query_embedding))
        .filter(similarity__gte=SIMILARITY_THRESHOLD)
        .order_by("-similarity")[:limit]
    )

    return results