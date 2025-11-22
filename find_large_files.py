import os

def get_file_sizes(directory):
    file_sizes = []
    for dirpath, _, filenames in os.walk(directory):
        if '.git' in dirpath:
            continue
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not os.path.islink(file_path):
                file_sizes.append((os.path.getsize(file_path), file_path))
    return file_sizes

if __name__ == "__main__":
    all_files = get_file_sizes('.')
    all_files.sort(key=lambda x: x[0], reverse=True)
    for size, path in all_files[:50]:
        print(f"{size / (1024*1024):.2f} MB - {path}")