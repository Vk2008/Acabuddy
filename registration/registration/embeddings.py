import cohere
import os

co = cohere.Client(os.getenv("COHERE_API_KEY"))

def embed(text):

    response = co.embed(
        texts=[text],
        model="embed-english-light-v3.0"
    )

    return response.embeddings[0]