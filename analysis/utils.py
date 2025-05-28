import os
from sklearn.metrics import silhouette_score

def get_files():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../crawler'))
    files = []

    for lang in ['zh', 'en']:
        lang_dir = os.path.join(base_dir, lang)
        if not os.path.exists(lang_dir):
            continue

        for website in os.listdir(lang_dir):
            website_path = os.path.join(lang_dir, website)
            processed_dir = os.path.join(website_path, 'downloads', 'processed')
            original_dir = os.path.join(website_path, 'downloads', 'original')

            for filename in os.listdir(processed_dir):
                if (filename.endswith('_e.txt') and lang == 'en') or (filename.endswith('_c.txt') and lang == 'zh'):
                    processed_path = os.path.join(processed_dir, filename)
                    original_filename = filename[:-6] + '_org.txt'
                    original_path = os.path.join(original_dir, original_filename)

                    if os.path.isfile(original_path):
                        files.append({
                            'name': original_filename,
                            'lang': lang,
                            'processed_path': processed_path,
                            'original_path': original_path
                        })
    return files

def calculate_silhouette_score(X, model):
    try:
        return silhouette_score(X, model.labels_, metric='cosine')
    except:
        return -1
