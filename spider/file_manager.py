import os
import re

class FileManager:
    def __init__(self, project_name):
        self.project_name = project_name
        self.download_dir = os.path.join(project_name, 'downloads')
        self._ensure_directory()

    def _ensure_directory(self):
        os.makedirs(self.download_dir, exist_ok=True)

    def save_content(self, url, content, suffix):
        filename = self._generate_filename(url, suffix)
        filepath = os.path.join(self.download_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f'Save failed: {filename} - {str(e)}')
            return False

    def _generate_filename(self, url, suffix):
        filename = url.replace('https://', '').replace('http://', '')
        filename = re.sub(r'[\\/*?:"<>|&\u200b]', '_', filename)[:150]
        filename = re.sub(r'__+', '_', filename)
        return f"{filename}_{suffix}.txt"

    def get_valid_file_count(self):
        """获取有效文件数量"""
        try:
            files = os.listdir(self.download_dir)
            return len([f for f in files if f.endswith('.txt')])
        except Exception as e:
            print(f'Error counting files: {str(e)}')
            return 0
