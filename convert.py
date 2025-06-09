import os
import re
import datetime
from pathlib import Path


def parse_frontmatter(content):
    """解析 YAML Front Matter"""
    metadata = {}
    if not content.startswith('---'):
        return metadata, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return metadata, content

    yaml_lines = parts[1].strip().split('\n')
    for line in yaml_lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if value:  # 忽略空值
                metadata[key] = value

    return metadata, parts[2]


def convert_hexo_to_hugo(input_file, output_dir):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, body = parse_frontmatter(content)

        # 1. 处理日期
        if 'date' in metadata:
            try:
                dt = datetime.datetime.strptime(metadata['date'], "%Y-%m-%d %H:%M:%S")
                metadata['date'] = dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            except ValueError:
                pass

        # 2. 处理 tags（确保非空）
        if 'tags' in metadata:
            tags = [t.strip() for t in metadata['tags'].split(',') if t.strip()]
            metadata['tags'] = tags if tags else None

        # 3. 处理 categories（确保非空）
        if 'categories' in metadata:
            categories = [c.strip() for c in metadata['categories'].split(',') if c.strip()]
            metadata['categories'] = categories if categories else None

        # 4. 清理空字段
        for field in ['tags', 'categories']:
            if field in metadata and not metadata[field]:
                del metadata[field]

        # 5. 生成新内容
        new_yaml = "---\n"
        for key, value in metadata.items():
            if isinstance(value, list):
                new_yaml += f"{key}: {value}\n"
            else:
                new_yaml += f"{key}: {value}\n"
        new_yaml += "---\n"

        # 写入文件
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, os.path.basename(input_file))
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_yaml + body)

        print(f"转换成功: {input_file} -> {output_file}")

    except Exception as e:
        print(f"转换失败 {input_file}: {str(e)}")


if __name__ == "__main__":
    input_dir = "."  # Hexo 文章目录
    output_dir = "content/posts"  # Hugo 文章目录

    for filename in Path(input_dir).glob("*.md"):
        convert_hexo_to_hugo(str(filename), output_dir)

    print("所有文件转换完成！")