import json
import elasticsearch
from elasticsearch import Elasticsearch
from document_store import DocumentStore
from flask import jsonify, request, render_template, current_app
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from utils import get_files, calculate_silhouette_score

def init_routes(app):
    @app.before_request
    def initialize_data():
        if not hasattr(current_app, '_initialized'):
            files = get_files()
            current_app.document_store.load_documents(files)
            print(f"成功加载 {len(files)} 个文档")
            current_app._initialized = True

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/duplicates', methods=['GET'])
    def find_duplicates():
        threshold = request.args.get('threshold', default=0.8, type=float)
        results = []
        
        cosine_matrix = cosine_similarity(current_app.document_store.tfidf_matrix)
        n = cosine_matrix.shape[0]

        for i in range(n):
            for j in range(i + 1, n):
                if cosine_matrix[i][j] >= threshold:
                    results.append({
                        'doc1': current_app.document_store.documents[i]['name'],
                        'doc2': current_app.document_store.documents[j]['name'],
                        'similarity': float(cosine_matrix[i][j]),
                        'lang': current_app.document_store.documents[i]['lang']
                    })

        return jsonify(sorted(results, key=lambda x: -x['similarity']))

    # 其他路由保持类似结构，通过current_app访问资源
    # ...


    
    @app.route('/api/similar/<int:doc_index>', methods=['GET'])
    def find_similar_documents(doc_index):
        """查找与指定文档相似的其他文档"""
        threshold = request.args.get('threshold', default=0.6, type=float)
        top_n = request.args.get('top', default=5, type=int)

        try:
            similarities = cosine_similarity(DocumentStore.tfidf_matrix[doc_index], DocumentStore.tfidf_matrix)
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
                'document': DocumentStore.documents[idx]['name'],
                'similarity': float(score),
                'lang': DocumentStore.documents[idx]['lang']
            })
            if len(results) >= top_n:
                break

        return jsonify(results)
    
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
                    cluster_result = DocumentStore.cluster_documents(n_clusters)
                    
                    # 重构过滤逻辑
                    doc_indices = [
                        idx for idx, doc in enumerate(DocumentStore.documents)
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
                                "name": DocumentStore.documents[idx]["name"],
                                "lang": DocumentStore.documents[idx]["lang"],
                            } for idx in cluster_docs]
                        })
                    
                    results[str(n_clusters)] = {
                        "top_clusters": sorted(clusters, key=lambda x: -x["size"]),
                        "silhouette": calculate_silhouette_score(DocumentStore.tfidf_matrix, cluster_result["model"])
                    }

                except Exception as e:
                    print(f"处理聚类数 {n_clusters} 时出错: {str(e)}")
                    continue
            
            if not results:
                return jsonify({"error": "没有成功完成任何聚类"}), 400
                
            return jsonify(results)
        
        except Exception as e:
            return jsonify({"error": f"聚类失败: {str(e)}"}), 500


    
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
            # 初始化Elasticsearch连接
            es = Elasticsearch(
                hosts=["http://localhost:9200"],
                request_timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
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



    @app.after_request
    def normalize_json_fields(response):
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
