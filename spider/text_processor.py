import re
import nltk
import requests
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize


class TextProcessor:
    def __init__(self, language):
        self.language = language
        self.stemmer = PorterStemmer()
        self._check_nltk_resources()
        self.stopwords = self._load_stopwords()
        self.es_endpoint = "http://localhost:9200"

    def _check_nltk_resources(self):
        resources = [
            ('tokenizers/punkt', 'punkt'),
            ('tokenizers/punkt_tab', 'punkt_tab'),
            ('corpora/stopwords', 'stopwords')
        ]

        for path, name in resources:
            try:
                nltk.data.find(path)
            except LookupError:
                nltk.download(name, quiet=True)

    def _load_stopwords(self):
        try:
            with open('stopwords.txt', 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f)
        except FileNotFoundError:
            return set(stopwords.words(self.language))

    def process_text(self, raw_text):
        if self.language == 'cn':
            return self._process_chinese_text(raw_text)
        else:
            return self._process_english_text(raw_text)

    # 中文文本处理流水线
    def _process_chinese_text(self, raw_text):

        try:
            # 通过ES的_analyze接口进行分词和停用词处理
            response = requests.post(
                f"{self.es_endpoint}/_analyze",
                json={
                    "analyzer": "ik_max_word",  # 使用IK分词器
                    "text": raw_text
                },
                timeout=5,
                headers={'Connection': 'close'},  # 明确关闭连接
                verify=False  # 如果是本地测试可跳过证书验证
            )

            if response.status_code == 200:
                # 提取分词结果并过滤
                tokens = [token['token'] for token in response.json()['tokens']]
                filtered = [
                    word for word in tokens
                    if word.strip() and
                       word not in self.stopwords and
                       re.match(r'[\u4e00-\u9fa5]', word)
                ]
                return ' '.join(self.deduplicate(filtered))
            else:
                print(f"ES分词失败：{response.text}")
                return ""

        except Exception as e:
            print(f"ES连接异常：{str(e)}")
            # 降级方案：使用简易分词
            return ' '.join(re.findall(r'[\u4e00-\u9fa5]+', raw_text))


    # 英文文本处理流水线
    def _process_english_text(self, raw_text):

        # 预处理特殊格式
        text = raw_text.lower()
        text = re.sub(r'\b(https?://|www\.)\S+\b', ' ', text)  # 移除URL
        text = re.sub(r'@\w+', ' ', text)  # 移除@提及
        text = re.sub(r'#\w+', ' ', text)  # 移除标签

        # 处理技术术语粘连（驼峰命名转换）
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # CamelCase -> Camel Case
        text = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', text)  # 数字字母分离
        text = re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', text)

        # 保留必要标点（如连字符、撇号）
        text = re.sub(r"[^a-zA-Z0-9'\-\.]", ' ', text)  # 保留基本字符

        # 增强分词处理
        try:
            # 使用改进的分词策略
            tokens = word_tokenize(text, language='english')
        except:
            # 备用分词方案
            tokens = re.findall(r"[\w'-]+|[.!?]", text)

        # 智能停用词过滤（保留否定形式）
        filtered = [
            word for word in tokens
            if word.lower() not in self.stopwords
               and len(word) > 1
               and not word.isdigit()
        ]

        # 词干提取优化（保留常见名词）
        common_nouns = {'data', 'analysis', 'system'}  # 自定义保留词表
        stemmed = []
        for word in filtered:
            if word in common_nouns:
                stemmed.append(word)
            else:
                stemmed.append(self.stemmer.stem(word))

        # 后处理修正
        stemmed = self.deduplicate(stemmed)
        processed = ' '.join(stemmed)
        processed = re.sub(r"\s+['-]\s+", '', processed)  # 修复分离的撇号
        processed = re.sub(r'\b(\w+)\s+-\s+(\w+)\b', r'\1-\2', processed)  # 恢复连字符单词

        return processed

    def deduplicate(self,content):
        return list(set(content))
