import os
import numpy as np
from flask_cors import CORS
from collections import defaultdict
from flask import Flask, jsonify, request, render_template, send_from_directory
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.exceptions import NotFittedError
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import Normalizer
from sklearn.metrics import silhouette_score
from elasticsearch import Elasticsearch
# from search.app import search
# import logging
import elasticsearch
import json

app = Flask(__name__)
CORS(app)

# 初始化Elasticsearch连接
es = Elasticsearch(
    hosts=["http://localhost:9200"],
    request_timeout=30,
    max_retries=3,
    retry_on_timeout=True
)

class DocumentStore:
    def __init__(self):
        self.documents = []
        self.vectorizer = TfidfVectorizer(tokenizer=lambda x: x.split(), lowercase=False)
        self.tfidf_matrix = None
        self._is_fitted = False
        self.cluster_cache = {}  # 缓存不同参数的聚类结果

    def load_documents(self, files):
        """预加载所有文档并计算TF-IDF矩阵"""
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
        """获取两个文档的相似度"""
        if not self._is_fitted:
            raise NotFittedError("Vectorizer not fitted yet")

        if idx1 < 0 or idx2 < 0 or idx1 >= len(self.documents) or idx2 >= len(self.documents):
            raise ValueError("Invalid document index")

        vec1 = self.tfidf_matrix[idx1]
        vec2 = self.tfidf_matrix[idx2]
        return cosine_similarity(vec1, vec2)[0][0]

    def cluster_documents(self, n_clusters=20):
        """执行文档聚类并缓存结果"""
        try:
            if n_clusters <= 0:
                raise ValueError("聚类数量必须大于0")

            cache_key = f"kmeans_{n_clusters}"
            if cache_key in self.cluster_cache:
                return self.cluster_cache[cache_key]

            if not self._is_fitted or self.tfidf_matrix is None:
                raise NotFittedError("请先成功加载文档数据")

            # 增加数据校验
            if self.tfidf_matrix.shape[0] < n_clusters:
                raise ValueError(f"文档数量({self.tfidf_matrix.shape[0]})不能小于聚类数({n_clusters})")

            # 增加进度日志
            print(f"[Clustering] 开始处理 {self.tfidf_matrix.shape[0]} 个文档，聚类数={n_clusters}")

            # 数据归一化处理
            normalizer = Normalizer(norm='l2')
            normalized_vectors = normalizer.fit_transform(self.tfidf_matrix)

            # 使用MiniBatchKMeans提高大数据集处理效率
            kmeans = MiniBatchKMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=5,
                batch_size=1000,
                max_iter=100
            )
            
            cluster_labels = kmeans.fit_predict(normalized_vectors)
            
            # 计算每个文档到所属簇中心的距离
            distances = kmeans.transform(normalized_vectors)
            
            # 组织聚类结果
            clusters = defaultdict(list)
            for idx, (label, distance) in enumerate(zip(cluster_labels, distances)):
                clusters[int(label)].append({
                    "doc_idx": idx,
                    "distance": distance[label]
                })
            
            # 对每个簇按距离排序并保留前5个
            processed_clusters = {}
            for label, docs in clusters.items():
                sorted_docs = sorted(docs, key=lambda x: x["distance"])[:5]
                processed_clusters[label] = {
                    "size": len(docs),
                    "representatives": [d["doc_idx"] for d in sorted_docs]
                }
            
            # 按簇大小排序
            sorted_clusters = sorted(
                processed_clusters.items(),
                key=lambda x: -x[1]["size"]
            )
            
            # 缓存结果
            self.cluster_cache[cache_key] = {
                "clusters": sorted_clusters,
                "model": kmeans
            }
            
            return self.cluster_cache[cache_key]
            
        except Exception as e:
            print(f"[Clustering Error] 聚类失败: {str(e)}")
            raise

# 初始化文档存储
doc_store = DocumentStore()

def initialize_data():
    """服务启动时预加载数据"""
    files = get_files()
    doc_store.load_documents(files)
    print(f"成功加载 {len(files)} 个文档")


@app.route('/api/duplicates', methods=['GET'])
def find_duplicates():
    """查找所有可能的重复文档对"""
    threshold = request.args.get('threshold', default=0.8, type=float)
    results = []

    # 矩阵全量计算
    cosine_matrix = cosine_similarity(doc_store.tfidf_matrix)
    n = cosine_matrix.shape[0]

    # 找出所有相似度超过阈值的组合
    for i in range(n):
        for j in range(i + 1, n):
            if cosine_matrix[i][j] >= threshold:
                results.append({
                    'doc1': doc_store.documents[i]['name'],
                    'doc2': doc_store.documents[j]['name'],
                    'similarity': float(cosine_matrix[i][j]),
                    'lang': doc_store.documents[i]['lang']
                })

    return jsonify(sorted(results, key=lambda x: -x['similarity']))


@app.route('/api/similar/<int:doc_index>', methods=['GET'])
def find_similar_documents(doc_index):
    """查找与指定文档相似的其他文档"""
    threshold = request.args.get('threshold', default=0.6, type=float)
    top_n = request.args.get('top', default=5, type=int)

    try:
        similarities = cosine_similarity(doc_store.tfidf_matrix[doc_index], doc_store.tfidf_matrix)
    except IndexError:
        return jsonify({'error': 'Invalid document index'}), 400

    # 获取相似度结果并排序
    sim_scores = list(enumerate(similarities[0]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # 过滤结果
    results = []
    for idx, score in sim_scores:
        if idx == doc_index:  # 跳过自身
            continue
        if score < threshold:
            break
        results.append({
            'document': doc_store.documents[idx]['name'],
            'similarity': float(score),
            'lang': doc_store.documents[idx]['lang']
        })
        if len(results) >= top_n:
            break

    return jsonify(results)

def get_files():
    """获取所有预处理文件信息"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../crawler'))
    files = []

    for lang in ['zh', 'en']:
        lang_dir = os.path.join(base_dir, lang)
        if not os.path.exists(lang_dir):
            continue

        # 遍历每个语言下的网站目录
        for website in os.listdir(lang_dir):
            website_path = os.path.join(lang_dir, website)
            if not os.path.isdir(website_path):
                continue

            # 构建processed和original路径
            processed_dir = os.path.join(website_path, 'downloads', 'processed')
            original_dir = os.path.join(website_path, 'downloads', 'original')
            if not os.path.isdir(processed_dir):
                continue


            # 收集处理后的文件
            for filename in os.listdir(processed_dir):
                if (filename.endswith('_e.txt') and lang == 'en') or (filename.endswith('_c.txt') and lang == 'zh'):
                    processed_path = os.path.join(processed_dir, filename)
                    original_filename = filename[:-6] + '_org.txt'
                    original_path = os.path.join(original_dir, original_filename)

                    if os.path.isfile(original_path):
                        files.append({
                            'name': original_filename,  # 关键修改：使用原始文件名
                            'lang': lang,
                            'processed_path': processed_path,
                            'original_path': original_path
                        })
    return files

@app.route('/')
def index():
    """渲染前端页面"""
    return render_template('index.html')


@app.route('/api/files', methods=['GET'])
def api_files():
    """获取文件列表接口"""
    files = get_files()

    return jsonify([{
        'name': f['name'],
        'lang': f['lang'],
        'processed_path': f['processed_path'],
        'original_path': f['original_path']
    } for f in files])


@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    """计算相似度接口"""
    data = request.get_json()
    file1 = data['file1']
    file2 = data['file2']

    # 校验语言一致性
    if file1['lang'] != file2['lang']:
        return jsonify({'error': '不同语言文档不可比较'}), 400

    try:
        # 读取预处理内容
        with open(file1['processed_path'], 'r', encoding='utf-8') as f:
            doc1 = f.read().strip()
        with open(file2['processed_path'], 'r', encoding='utf-8') as f:
            doc2 = f.read().strip()

        # 计算TF-IDF向量
        vectorizer = TfidfVectorizer(tokenizer=lambda x: x.split(), lowercase=False)
        tfidf = vectorizer.fit_transform([doc1, doc2])
        similarity = cosine_similarity(tfidf[0], tfidf[1])[0][0]
        distance = 1 - similarity

        # 读取原始内容
        with open(file1['original_path'], 'r', encoding='utf-8') as f:
            content1 = f.read()
        with open(file2['original_path'], 'r', encoding='utf-8') as f:
            content2 = f.read()

        return jsonify({
            'similarity': similarity,
            'distance': distance,
            'content1': content1,
            'content2': content2
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_silhouette_score(X, model):
    """计算轮廓系数"""
    try:
        return silhouette_score(X, model.labels_, metric='cosine')
    except:
        return -1  # 当只有一个簇时返回-1

@app.route('/api/cluster', methods=['GET'])
def handle_clustering():
    try:
        n_clusters_list = list(map(int, request.args.get('n_clusters', '20').split(',')))
        lang_filter = request.args.get('lang', None)
        
        results = {}
        for n_clusters in n_clusters_list:
            if n_clusters <= 0:
                continue
                
            try:
                cluster_result = doc_store.cluster_documents(n_clusters)
                
                # 重构过滤逻辑
                doc_indices = [
                    idx for idx, doc in enumerate(doc_store.documents)
                    if lang_filter in [None, doc['lang']]
                ]
                
                if not doc_indices:
                    continue

                # 修正聚类结果处理
                clusters = []
                for cluster_id, cluster_info in cluster_result["clusters"]:  # 移除[:3]限制
                    cluster_docs = [
                        idx for idx in cluster_info["representatives"]
                        if idx in doc_indices
                    ][:5]  # 安全截断
                    
                    clusters.append({
                        "id": cluster_id,
                        "size": cluster_info["size"],
                        "representatives": [{
                            "name": doc_store.documents[idx]["name"],
                            "lang": doc_store.documents[idx]["lang"],
                        } for idx in cluster_docs]
                    })
                
                results[str(n_clusters)] = {
                    "top_clusters": sorted(clusters, key=lambda x: -x["size"]),
                    "silhouette": calculate_silhouette_score(doc_store.tfidf_matrix, cluster_result["model"])
                }

            except Exception as e:
                print(f"处理聚类数 {n_clusters} 时出错: {str(e)}")
                continue
        
        if not results:
            return jsonify({"error": "没有成功完成任何聚类"}), 400
            
        return jsonify(results)
    
    except Exception as e:
        return jsonify({"error": f"聚类失败: {str(e)}"}), 500

# @app.route('/search')
# def search_page():
#     """搜索功能前端页面"""
#     return send_from_directory('static', 'search.html')

@app.route('/api/search', methods=['GET'])
def handle_search():
    """执行搜索功能"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    search_body = {
        "query": {
            "match": {
                "processed_content": {
                    "query": query,
                }
            }
        },
        "_source": ["url", "language", "timestamp"],
        "size": 100
    }

    try:
        response = es.search(index="search_craft", body=search_body)
        results = []
        for hit in response["hits"]["hits"]:
            source = hit.get("_source", {})
            results.append({
                "url": source.get("url", "未知URL"),
                "language": str(source.get("language", "unknown")).lower(),
                "timestamp": source.get("timestamp")
            })

        return jsonify({
            "total": response["hits"]["total"]["value"],
            "results": results
        })

    except elasticsearch.NotFoundError:
        return jsonify({"error": "索引不存在"}), 404
    except Exception as e:
        app.logger.error(f"ES查询失败: {str(e)}", exc_info=True)
        return jsonify({"error": "搜索服务暂时不可用"}), 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify(error=str(e)), 404

@app.after_request
def normalize_json_fields(response):
    """统一JSON字段名为小写"""
    if response.is_json:
        data = response.get_json()
        def normalize_keys(obj):
            if isinstance(obj, dict):
                return {k.lower(): normalize_keys(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [normalize_keys(item) for item in obj]
            return obj
        response.data = json.dumps(normalize_keys(data))
    return response

if __name__ == '__main__':
    initialize_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
