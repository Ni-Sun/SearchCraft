import os
import numpy as np
from flask_cors import CORS
from collections import defaultdict
from flask import Flask, jsonify, request, render_template
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.exceptions import NotFittedError

app = Flask(__name__)
CORS(app)

class DocumentStore:
    def __init__(self):
        self.documents = []
        self.vectorizer = TfidfVectorizer(tokenizer=lambda x: x.split(), lowercase=False)
        self.tfidf_matrix = None
        self._is_fitted = False

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
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../spider/crawler'))
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
                    original_path = os.path.join(original_dir, filename[:-6]+'_org.txt')    # 将 _e/_c 转为 _org

                    if os.path.isfile(original_path):
                        files.append({
                            'name': filename,
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


if __name__ == '__main__':
    initialize_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
