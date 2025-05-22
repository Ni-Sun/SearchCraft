import os
import re
from pathlib import Path


class FileManager:
    def __init__(self, project_name):
        self.project_name = project_name
        self.download_dir = os.path.join(project_name, 'downloads')
        self._ensure_directory()

    def _ensure_directory(self):
        """确保下载目录和子目录结构存在"""
        directories = [
            self.download_dir,
            os.path.join(self.download_dir, 'processed'),
            os.path.join(self.download_dir, 'original')
        ]
        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)

    def save_content(self, url, content, suffix):
        """保存内容到指定目录"""
        # 参数校验
        if suffix not in ('e', 'c', 'org'):
            raise ValueError(f"Invalid suffix: {suffix}. Must be 'e', 'c' or 'org'.")

        # 确定存储子目录
        subdir = 'processed' if suffix in ('e', 'c') else 'original'
        filename = self._generate_filename(url, suffix)
        filepath = os.path.join(self.download_dir, subdir, filename)

        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f'Save failed: {filename} - {str(e)}')
            return False

    def _generate_filename(self, url, suffix):
        """生成标准化文件名"""
        # 移除协议头并清理非法字符
        clean_url = re.sub(r'^https?://', '', url)
        clean_url = re.sub(r'[\\/*?:"<>|&\u200b]', '_', clean_url)

        # 长度限制和冗余下划线处理
        clean_url = clean_url[:150].rstrip('_')
        clean_url = re.sub(r'_+', '_', clean_url)

        return f"{clean_url}_{suffix}.txt"

    def get_valid_file_count(self):
        """统计所有子目录中的有效文件数量"""
        count = 0
        try:
            for root, dirs, files in os.walk(self.download_dir):
                count += sum(1 for f in files if f.endswith('.txt'))
        except Exception as e:
            print(f'Error counting files: {str(e)}')
            return 0
        return count
    

    # 清理小文件
    def clean_small_files(self, min_size_kb=1):
        """
        清理指定项目downloads目录中original和processed子文件夹的小文件
        :param min_size_kb: 最小文件大小（KB）
        """
        base_dir = Path(self.project_name).resolve()  # 自动解析为绝对路径
        download_dir = base_dir / 'downloads'
        
        # 遍历时使用pathlib处理路径
        for subdir in ['original', 'processed']:
            subdir_path = download_dir / subdir
            if not subdir_path.exists():
                print(f'Subdirectory not found: {subdir_path}')
                continue
                
            for file_path in subdir_path.glob('*.txt'):  # 直接匹配txt文件
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    if file_size < min_size_kb * 1024:
                        try:
                            file_path.unlink()
                            print(f'Removed: {file_path.relative_to(base_dir)}')
                        except Exception as e:
                            print(f'Failed to remove {file_path}: {e}')


