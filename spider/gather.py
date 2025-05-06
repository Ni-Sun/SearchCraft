import os
import shutil
from pathlib import Path

# 把处理后的文件复制到../processed/zh 和../processed/en 目录下
def organize_translations():
    # 定义基础路径
    base_dir = Path("crawler")
    processed_dir = Path("../processed")

    # 遍历所有crawler的子目录
    for crawler_subdir in base_dir.iterdir():
        if not crawler_subdir.is_dir():
            continue

        downloads_path = crawler_subdir / "downloads"
        if not downloads_path.exists():
            continue

        # 遍历downloads目录中的所有文件
        for file_path in downloads_path.glob("*.txt"):
            if file_path.suffix != ".txt":
                continue

            # 判断文件类型
            filename = file_path.stem  # 获取不带后缀的文件名
            if filename.endswith("_c"):
                lang_dir = processed_dir / "zh"
            elif filename.endswith("_e"):
                lang_dir = processed_dir / "en"
            else:
                continue  # 跳过不符合命名规则的文件

            # 创建目标目录（如果不存在）
            lang_dir.mkdir(parents=True, exist_ok=True)

            # 构建目标路径并复制文件
            target_path = lang_dir / file_path.name
            shutil.copy2(str(file_path), str(target_path))
            # print(f"Copied: {file_path} -> {target_path}")


if __name__ == "__main__":
    organize_translations()
