#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
下载模型脚本 - 下载项目所需的预训练模型
"""

import os
import sys
import argparse
import logging
import yaml
import requests
import zipfile
import tarfile
import hashlib
import tqdm
from pathlib import Path

# 添加项目根目录到Python路径
root_dir = str(Path(__file__).parent.parent.absolute())
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("download_models")

# 预训练模型信息
MODELS = {
    "segment_anything": {
        "name": "Segment Anything Model (SAM)",
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
        "dest_dir": "models/segment_anything",
        "md5": "4b8939a88964f0f4ff5e00a996aeebb0",
        "size_mb": 2560,
        "extract": False,
        "description": "图像分割模型，用于分离角色的各个部位"
    },
    "u2net": {
        "name": "U^2-Net",
        "url": "https://github.com/xuebinqin/U-2-Net/releases/download/NeurIPS2020/u2net.pth",
        "dest_dir": "models/u2net",
        "md5": "e5e98cef7dfac15d75eb7abc3c8c6c55",
        "size_mb": 176,
        "extract": False,
        "description": "物体分割模型，用于图像分割和背景移除"
    },
    "sd_xl_base": {
        "name": "Stable Diffusion XL Base 1.0",
        "url": None,  # 需要通过huggingface下载
        "huggingface_repo": "stabilityai/stable-diffusion-xl-base-1.0",
        "dest_dir": "models/stable_diffusion",
        "size_mb": 6800,
        "extract": False,
        "download_method": "huggingface",
        "description": "Stable Diffusion XL基础模型，用于生成角色图像"
    }
}

def check_exists(filepath, md5=None):
    """检查文件是否存在并验证MD5（如果提供）
    
    Args:
        filepath: 文件路径
        md5: 可选的MD5哈希值
        
    Returns:
        文件是否存在且MD5匹配（如果提供）
    """
    if not os.path.exists(filepath):
        return False
    
    if md5:
        logger.info(f"验证文件 {filepath} 的MD5...")
        file_md5 = hashlib.md5(open(filepath, "rb").read()).hexdigest()
        if file_md5 != md5:
            logger.warning(f"MD5不匹配: {filepath}")
            logger.warning(f"预期: {md5}")
            logger.warning(f"实际: {file_md5}")
            return False
    
    return True

def download_file(url, dest_path, expected_md5=None):
    """下载文件并显示进度条
    
    Args:
        url: 下载URL
        dest_path: 目标文件路径
        expected_md5: 预期的MD5哈希值
        
    Returns:
        下载是否成功
    """
    logger.info(f"下载文件: {url}")
    
    # 创建目标目录
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # 设置临时文件路径
    temp_path = f"{dest_path}.download"
    
    try:
        # 发出HEAD请求以获取文件大小
        response = requests.head(url, allow_redirects=True)
        file_size = int(response.headers.get('content-length', 0))
        
        # 开始下载
        response = requests.get(url, stream=True, allow_redirects=True)
        response.raise_for_status()  # 如果请求不成功则抛出异常
        
        # 创建进度条
        progress_bar = tqdm.tqdm(
            total=file_size, unit='B', unit_scale=True, 
            desc=f"下载 {os.path.basename(dest_path)}"
        )
        
        # 写入文件
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    progress_bar.update(len(chunk))
        
        progress_bar.close()
        
        # 如果提供了MD5，验证下载的文件
        if expected_md5:
            file_md5 = hashlib.md5(open(temp_path, "rb").read()).hexdigest()
            if file_md5 != expected_md5:
                logger.error(f"下载的文件MD5不匹配: {temp_path}")
                logger.error(f"预期: {expected_md5}")
                logger.error(f"实际: {file_md5}")
                return False
        
        # 重命名临时文件为最终文件
        os.rename(temp_path, dest_path)
        logger.info(f"下载完成: {dest_path}")
        return True
        
    except Exception as e:
        logger.error(f"下载失败: {e}")
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def extract_archive(archive_path, dest_dir):
    """解压缩归档文件
    
    Args:
        archive_path: 归档文件路径
        dest_dir: 目标目录
        
    Returns:
        解压缩是否成功
    """
    logger.info(f"解压缩 {archive_path} 到 {dest_dir}...")
    
    try:
        # 确保目标目录存在
        os.makedirs(dest_dir, exist_ok=True)
        
        # 根据文件扩展名选择解压缩方法
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
        elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(dest_dir)
        elif archive_path.endswith('.tar'):
            with tarfile.open(archive_path, 'r') as tar_ref:
                tar_ref.extractall(dest_dir)
        else:
            logger.error(f"不支持的归档格式: {archive_path}")
            return False
        
        logger.info(f"解压缩完成: {dest_dir}")
        return True
        
    except Exception as e:
        logger.error(f"解压缩失败: {e}")
        return False

def download_from_huggingface(repo_id, dest_dir):
    """从HuggingFace下载模型
    
    Args:
        repo_id: HuggingFace仓库ID
        dest_dir: 目标目录
        
    Returns:
        下载是否成功
    """
    logger.info(f"从HuggingFace下载模型: {repo_id}")
    
    try:
        # 确保目标目录存在
        os.makedirs(dest_dir, exist_ok=True)
        
        # 尝试使用transformers库下载模型
        from transformers import AutoModel
        
        logger.info(f"正在下载模型 {repo_id}...")
        # 使用from_pretrained下载模型，并保存到指定目录
        model = AutoModel.from_pretrained(repo_id)
        model.save_pretrained(dest_dir)
        
        logger.info(f"模型下载完成: {dest_dir}")
        return True
        
    except ImportError:
        logger.error("未安装transformers库，无法从HuggingFace下载模型")
        logger.error("请安装transformers: pip install transformers")
        return False
    except Exception as e:
        logger.error(f"从HuggingFace下载模型失败: {e}")
        return False

def download_model(model_id, model_info, force=False):
    """下载指定的模型
    
    Args:
        model_id: 模型ID
        model_info: 模型信息字典
        force: 是否强制重新下载
        
    Returns:
        下载是否成功
    """
    logger.info(f"准备下载模型: {model_info['name']}")
    logger.info(f"描述: {model_info.get('description', '无描述')}")
    
    # 确定目标路径
    dest_dir = os.path.join(root_dir, model_info['dest_dir'])
    os.makedirs(dest_dir, exist_ok=True)
    
    # 检查是否已经存在
    if model_info.get('download_method') == 'huggingface':
        # HuggingFace模型的检测方式不同
        config_file = os.path.join(dest_dir, 'config.json')
        if os.path.exists(config_file) and not force:
            logger.info(f"模型已存在: {dest_dir}")
            return True
        
        # 从HuggingFace下载
        return download_from_huggingface(model_info['huggingface_repo'], dest_dir)
    else:
        # 常规下载方式
        # 确定文件名和路径
        filename = os.path.basename(model_info['url'])
        dest_path = os.path.join(dest_dir, filename)
        
        # 检查文件是否已存在
        if check_exists(dest_path, model_info.get('md5')) and not force:
            logger.info(f"文件已存在且MD5匹配: {dest_path}")
            return True
        
        # 下载文件
        success = download_file(model_info['url'], dest_path, model_info.get('md5'))
        if not success:
            return False
        
        # 如果需要解压缩
        if model_info.get('extract', False):
            return extract_archive(dest_path, dest_dir)
        
        return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="下载项目所需的预训练模型")
    parser.add_argument('--models', nargs='+', choices=list(MODELS.keys()) + ['all'],
                        default=['all'], help="要下载的模型ID，使用'all'下载所有模型")
    parser.add_argument('--force', action='store_true', help="强制重新下载已存在的模型")
    parser.add_argument('--config', type=str, default='config.yml', help="配置文件路径")
    args = parser.parse_args()
    
    # 读取项目配置
    try:
        config_path = os.path.join(root_dir, args.config)
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"已加载配置文件: {config_path}")
                
                # 检查配置中的模型设置，更新模型信息
                if 'character' in config and 'model' in config['character']:
                    model_id = config['character']['model']
                    logger.info(f"配置中指定的字符生成模型: {model_id}")
                
                if 'layer_separation' in config and 'model' in config['layer_separation']:
                    model_id = config['layer_separation']['model']
                    logger.info(f"配置中指定的图层分割模型: {model_id}")
    except Exception as e:
        logger.warning(f"读取配置文件失败: {e}")
        logger.warning("将使用默认模型设置")
    
    # 确定要下载的模型
    models_to_download = []
    if 'all' in args.models:
        models_to_download = list(MODELS.keys())
    else:
        models_to_download = args.models
    
    # 下载模型
    success_count = 0
    for model_id in models_to_download:
        if model_id not in MODELS:
            logger.warning(f"未知的模型ID: {model_id}")
            continue
        
        logger.info(f"=== 处理模型: {model_id} ===")
        if download_model(model_id, MODELS[model_id], args.force):
            success_count += 1
        else:
            logger.error(f"下载模型失败: {model_id}")
    
    # 显示结果
    if success_count == len(models_to_download):
        logger.info(f"所有模型下载成功! ({success_count}/{len(models_to_download)})")
    else:
        logger.warning(f"部分模型下载失败. 成功: {success_count}/{len(models_to_download)}")

if __name__ == "__main__":
    main() 