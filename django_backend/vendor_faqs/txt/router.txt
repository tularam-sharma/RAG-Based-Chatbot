from sentence_transformers import SentenceTransformer
import numpy as np

class SimpleRouter:
    def __init__(self, threshold: float = 0.5):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.threshold = threshold

        self.faq_utterances = [
            "What is the return policy of the products?",
            "Do I get discount with the HDFC credit card?",
            "How can I track my order?",
            "What payment methods are accepted?",
            "How long does it take to process a refund?",
        ]

        # Encode and normalize all utterances once
        embeddings = self.model.encode(self.faq_utterances, convert_to_numpy=True)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.faq_embeddings = embeddings / (norms + 1e-10)

    def __call__(self, query: str):
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)

        # Cosine similarities
        faq_similarities = np.dot(self.faq_embeddings, query_embedding)
        faq_score = float(np.max(faq_similarities))

        class RouteResult:
            def __init__(self, name):
                self.name = name

        if faq_score > self.threshold:
            return RouteResult('faq')
        else:
            return RouteResult('llm_response')

router = SimpleRouter()

if __name__ == "__main__":
    print(router("What is your policy on defective product?").name)
    print(router("Pink Puma shoes in price range 5000 to 1000").name)