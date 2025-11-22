import os
import subprocess

def get_tracked_files():
    try:
        # Get list of tracked files
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, encoding='utf-8')
        return result.stdout.splitlines()
    except Exception as e:
        print(f"Error getting tracked files: {e}")
        return []

def get_file_sizes(files):
    file_sizes = []
    for file_path in files:
        if os.path.isfile(file_path):
            try:
                size = os.path.getsize(file_path)
                file_sizes.append((size, file_path))
            except OSError:
                pass # File might have been deleted or not accessible
    return file_sizes

if __name__ == "__main__":
    tracked_files = get_tracked_files()
    all_files = get_file_sizes(tracked_files)
    all_files.sort(key=lambda x: x[0], reverse=True)
    
    print(f"Found {len(all_files)} tracked files.")
    print("Top 50 largest tracked files:")
    for size, path in all_files[:50]:
        print(f"{size / (1024*1024):.2f} MB - {path}")