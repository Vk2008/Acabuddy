from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-MiniLM-L3-v2")

def embed(text: str):
    return model.encode(text).tolist()