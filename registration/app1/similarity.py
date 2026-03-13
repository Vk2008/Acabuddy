from .models import Question
from pgvector.django import CosineDistance

SIMILARITY_THRESHOLD = 0.65


def find_similar_questions(text, limit=5):

    from registration.embeddings import embed   # lazy import

    query_embedding = embed(text)

    results = (
        Question.objects
        .exclude(embedding__isnull=True)
        .annotate(similarity=1 - CosineDistance("embedding", query_embedding))
        .filter(similarity__gte=SIMILARITY_THRESHOLD)
        .order_by("-similarity")[:limit]
    )

    return results