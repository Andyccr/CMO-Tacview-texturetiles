import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import concurrent.futures
import time

def download_file(url, save_path):
    """下载单个文件"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True, save_path
    except Exception as e:
        return False, f"{url} 下载失败: {e}"

def download_webp_files(url, output_folder, max_workers=5):
    """使用多线程下载所有WebP文件"""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"无法获取网页内容: {e}")
        return
    
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    webp_links = [link['href'] for link in links if link['href'].lower().endswith('.webp')]
    
    if not webp_links:
        print("未找到WebP文件链接")
        return
    
    print(f"找到 {len(webp_links)} 个WebP文件，开始多线程下载...")
    
    # 准备下载任务
    download_tasks = []
    for webp_link in webp_links:
        file_url = urljoin(url, webp_link)
        filename = os.path.basename(file_url)
        filepath = os.path.join(output_folder, filename)
        download_tasks.append((file_url, filepath))
    
    # 使用线程池下载
    start_time = time.time()
    success_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_file, task[0], task[1]) for task in download_tasks]
        
        for future in concurrent.futures.as_completed(futures):
            success, message = future.result()
            if success:
                success_count += 1
                print(f"✓ 已下载: {message}")
            else:
                print(f"✗ {message}")
    
    total_time = time.time() - start_time
    print(f"\n下载完成! 成功: {success_count}/{len(webp_links)}")
    print(f"总耗时: {total_time:.2f}秒")

if __name__ == "__main__":
    target_url = "https://warfaresims.slitherine.com/Tacview_Textures/"
    save_directory = "downloaded_webp_files"
    download_webp_files(target_url, save_directory, max_workers=10)  # 可以调整线程数