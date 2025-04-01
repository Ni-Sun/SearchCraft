import os


# Each website is a separate project (folder)
def create_project_dir(directory):
    if not os.path.exists(directory):
        print('Creating directory ' + directory)
        os.makedirs(directory)


# Create queue and crawled files (if not created)
def create_data_files(project_name, base_url):
    queue = os.path.join(project_name , 'queue.txt')
    crawled = os.path.join(project_name,"crawled.txt")
    if not os.path.isfile(queue):
        write_file(queue, base_url)
    if not os.path.isfile(crawled):
        write_file(crawled, '')


# Create a new file
def write_file(path, data):
    with open(path, 'w') as f:
        f.write(data)


# Add data onto an existing file
def append_to_file(path, data):
    with open(path, 'a') as file:
        file.write(data + '\n')


# Delete the contents of a file
def delete_file_contents(path):
    open(path, 'w').close()


# 清理小文件
def clean_small_files(project_name, min_size_kb=1):
    """
    清理指定项目downloads目录中的小文件
    :param project_name: 项目名称
    :param min_size_kb: 最小文件大小（KB）
    """
    download_dir = os.path.join(project_name, 'downloads')
    if not os.path.exists(download_dir):
        return

    min_size = min_size_kb * 1024  # 转换为字节
    removed_count = 0

    for filename in os.listdir(download_dir):
        file_path = os.path.join(download_dir, filename)
        try:
            # 跳过目录和非txt文件
            if os.path.isdir(file_path) or not filename.endswith('.txt'):
                continue

            # 检查文件大小
            if os.path.getsize(file_path) < min_size:
                os.remove(file_path)
                removed_count += 1
                print(f'Removed small file: {filename} ({os.path.getsize(file_path)} bytes)')
        except Exception as e:
            print(f'Failed to remove {filename}: {str(e)}')

    print(f'Cleanup completed. Removed {removed_count} files smaller than {min_size_kb}KB.')


# Read a file and convert each line to set items
def file_to_set(file_name):
    results = set()
    with open(file_name, 'rt') as f:
        for line in f:
            results.add(line.replace('\n', ''))
    return results


# 将网页内容写入文件
def set_to_file(links, file_name):
    with open(file_name,"w") as f:
        for l in sorted(links):
            f.write(l+"\n")
