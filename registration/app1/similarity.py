from sentence_transformers import SentenceTransformer, util
from .models import Question

model = SentenceTransformer("all-MiniLM-L6-v2")
SIMILARITY_THRESHOLD = 0.5

def find_similar_questions(text):
    existing = Question.objects.all()

    if not existing.exists():
        return []

    corpus = [q.title + " " + q.body for q in existing]
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)

    new_embedding = model.encode(text, convert_to_tensor=True)
    scores = util.cos_sim(new_embedding, corpus_embeddings)[0]

    similar = []

    for idx, score in enumerate(scores):
        if score.item() >= SIMILARITY_THRESHOLD:
            similar.append({
                "question": existing[idx],
                "score": round(score.item(), 2)
            })

    return sorted(similar, key=lambda x: x["score"], reverse=True)
