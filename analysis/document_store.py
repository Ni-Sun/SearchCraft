import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import Normalizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.exceptions import NotFittedError
from collections import defaultdict

class DocumentStore:
    def __init__(self):
        self.documents = []
        self.vectorizer = TfidfVectorizer(tokenizer=lambda x: x.split(), lowercase=False)
        self.tfidf_matrix = None
        self._is_fitted = False
        self.cluster_cache = {}

    def load_documents(self, files):
        processed_docs = []
        self.documents = []

        for file in files:
            try:
                with open(file['processed_path'], 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    processed_docs.append(content)
                    self.documents.append(file)
            except Exception as e:
                print(f"Error loading {file['processed_path']}: {str(e)}")

        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(processed_docs)
            self._is_fitted = True
        except ValueError:
            self.tfidf_matrix = None
            self._is_fitted = False

    def get_similarity(self, idx1, idx2):
        if not self._is_fitted:
            raise NotFittedError("Vectorizer not fitted yet")

        vec1 = self.tfidf_matrix[idx1]
        vec2 = self.tfidf_matrix[idx2]
        return cosine_similarity(vec1, vec2)[0][0]

    def cluster_documents(self, n_clusters=20):
        try:
            if n_clusters <= 0:
                raise ValueError("聚类数量必须大于0")

            cache_key = f"kmeans_{n_clusters}"
            if cache_key in self.cluster_cache:
                return self.cluster_cache[cache_key]

            normalizer = Normalizer(norm='l2')
            normalized_vectors = normalizer.fit_transform(self.tfidf_matrix)

            kmeans = MiniBatchKMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=5,
                batch_size=1000,
                max_iter=100
            )
            
            cluster_labels = kmeans.fit_predict(normalized_vectors)
            distances = kmeans.transform(normalized_vectors)
            
            clusters = defaultdict(list)
            for idx, (label, distance) in enumerate(zip(cluster_labels, distances)):
                clusters[int(label)].append({
                    "doc_idx": idx,
                    "distance": distance[label]
                })
            
            processed_clusters = {}
            for label, docs in clusters.items():
                sorted_docs = sorted(docs, key=lambda x: x["distance"])[:5]
                processed_clusters[label] = {
                    "size": len(docs),
                    "representatives": [d["doc_idx"] for d in sorted_docs]
                }
            
            sorted_clusters = sorted(
                processed_clusters.items(),
                key=lambda x: -x[1]["size"]
            )
            
            self.cluster_cache[cache_key] = {
                "clusters": sorted_clusters,
                "model": kmeans
            }
            
            return self.cluster_cache[cache_key]
            
        except Exception as e:
            print(f"[Clustering Error] 聚类失败: {str(e)}")
            raise
