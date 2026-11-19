from functools import lru_cache

@lru_cache(maxsize=1)
def model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',device='cpu')

def embed(text):
    return model().encode(text,normalize_embeddings=True).tolist()
