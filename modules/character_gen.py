#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
角色生成模块 - 使用AI模型生成虚拟角色立绘
"""

import os
import logging
import random
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

import torch
from PIL import Image
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
from diffusers.utils import make_image_grid
import numpy as np
from tqdm import tqdm

logger = logging.getLogger("live2d_generator.character_gen")

# 预定义的可用模型列表
AVAILABLE_MODELS = {
    "stable-diffusion-v1-5": {
        "name": "Stable Diffusion v1.5",
        "provider": "runwayml",
        "size": "4GB",
        "description": "通用模型，体积较小",
        "id": "runwayml/stable-diffusion-v1-5"
    },
    "stable-diffusion-xl-base-1.0": {
        "name": "Stable Diffusion XL",
        "provider": "stability-ai",
        "size": "10GB",
        "description": "高质量模型，体积较大",
        "id": "stabilityai/stable-diffusion-xl-base-1.0"
    },
    "anything-v3.0": {
        "name": "Anything v3.0",
        "provider": "Linaqruf",
        "size": "4GB",
        "description": "动漫风格专用模型",
        "id": "Linaqruf/anything-v3.0"
    },
    "dreamlike-anime-1.0": {
        "name": "Dreamlike Anime",
        "provider": "dreamlike-art",
        "size": "4GB",
        "description": "高质量动漫风格模型",
        "id": "dreamlike-art/dreamlike-anime-1.0"
    },
    "dreamshaper-8": {
        "name": "DreamShaper v8",
        "provider": "Lykon",
        "size": "4GB",
        "description": "综合性能优秀的模型",
        "id": "Lykon/dreamshaper-8"
    },
}

class CharacterGenerator:
    """角色生成器类，负责使用AI模型生成虚拟角色立绘"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化角色生成器
        
        Args:
            config: 配置字典，包含角色生成的相关设置
        """
        self.config = config
        self.character_config = config['character']
        self.output_dir = os.path.join(config['export']['output_dir'], 'character')
        self.temp_dir = config['misc']['temp_dir']
        self.device = "cuda" if torch.cuda.is_available() and config['misc']['gpu']['enabled'] else "cpu"
        self.model = None
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_available_models() -> Dict[str, Dict[str, str]]:
        """获取可用模型列表
        
        Returns:
            可用模型字典，键为模型ID，值为模型详情
        """
        return AVAILABLE_MODELS
    
    @staticmethod
    def download_model(model_id: str, download_dir: Optional[str] = None) -> bool:
        """下载指定的模型
        
        Args:
            model_id: 模型ID或模型完整路径
            download_dir: 下载目录，默认使用huggingface缓存目录
            
        Returns:
            下载是否成功
        """
        try:
            # 检查模型是否在预定义列表中
            if model_id in AVAILABLE_MODELS:
                model_path = AVAILABLE_MODELS[model_id]['id']
            else:
                model_path = model_id
                
            logger.info(f"开始下载模型: {model_path}")
            
            # 使用diffusers下载模型（但不加载到内存，仅预下载）
            StableDiffusionPipeline.from_pretrained(
                model_path,
                torch_dtype=torch.float32,  # 使用float32仅用于下载
                safety_checker=None,
                cache_dir=download_dir
            )
            
            logger.info(f"模型 {model_path} 下载完成")
            return True
            
        except Exception as e:
            logger.error(f"下载模型时出错: {str(e)}")
            return False
    
    def _load_model(self) -> None:
        """加载AI模型"""
        model_id = self.character_config['model']
        provider = self.character_config['provider']
        
        logger.info(f"加载{model_id}模型...")
        
        # 如果指定了提供商和模型ID
        if provider and model_id:
            full_model_path = f"{provider}/{model_id}"
        else:
            # 检查是否使用预定义模型
            if model_id in AVAILABLE_MODELS:
                full_model_path = AVAILABLE_MODELS[model_id]['id']
            else:
                # 尝试直接使用模型ID
                full_model_path = model_id
        
        try:
            # 尝试加载模型
            self.model = StableDiffusionPipeline.from_pretrained(
                full_model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None  # 禁用安全检查器以提高速度
            )
            
            # 使用DPM-Solver++调度器以提高性能
            self.model.scheduler = DPMSolverMultistepScheduler.from_config(
                self.model.scheduler.config,
                algorithm_type="dpmsolver++",
                solver_order=2
            )
            
            # 移至设备
            self.model = self.model.to(self.device)
            
            # 启用模型加速
            if self.device == "cuda":
                self.model.enable_attention_slicing()
                
        except Exception as e:
            logger.error(f"加载模型失败: {str(e)}")
            self._load_model_fallback()
            
    def _load_model_fallback(self) -> None:
        """模型加载失败时的回退方案"""
        logger.info("使用默认Stable Diffusion模型作为回退")
        try:
            self.model = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None
            ).to(self.device)
        except Exception as e:
            logger.error(f"加载回退模型也失败了: {str(e)}")
            raise RuntimeError("无法加载任何模型，请检查网络连接或手动下载模型")
    
    def _enhance_prompt(self, prompt: str) -> str:
        """增强提示词以获得更好的生成效果
        
        Args:
            prompt: 原始提示词
        
        Returns:
            增强后的提示词
        """
        style = self.character_config['style']
        
        # 根据风格增强提示词
        style_keywords = {
            "anime": "high quality, detailed anime character, best quality, vtuber model reference sheet",
            "realistic": "high quality, detailed, realistic, photorealistic, 8k, best quality",
            "cartoon": "high quality, cartoon character, vibrant colors, clean lines, best quality"
        }
        
        # 确保提示词包含必要的要素
        essentials = "front facing, full face visible, white background, character reference, symmetrical"
        
        # 组合提示词
        enhanced = f"{prompt}, {style_keywords.get(style, '')}, {essentials}"
        
        return enhanced
    
    def generate(self) -> str:
        """生成角色立绘
        
        Returns:
            生成的角色图像文件路径
        """
        # 加载模型
        if self.model is None:
            self._load_model()
        
        # 准备生成参数
        prompt = self._enhance_prompt(self.character_config['prompt'])
        negative_prompt = self.character_config['negative_prompt']
        num_samples = self.character_config['num_samples']
        width = self.character_config['width']
        height = self.character_config['height']
        
        # 设置随机种子
        seed = self.character_config['seed']
        if seed < 0:
            seed = random.randint(0, 2147483647)
        generator = torch.Generator(device=self.device).manual_seed(seed)
        
        logger.info(f"使用种子: {seed}")
        logger.info(f"生成{num_samples}个样本...")
        
        # 生成图像
        with torch.autocast(self.device):
            images = self.model(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_images_per_prompt=num_samples,
                generator=generator,
                guidance_scale=7.5,  # 提示词引导强度
                num_inference_steps=30  # 推理步数
            ).images
        
        # 创建网格图以便比较
        grid_image = make_image_grid(images, rows=1, cols=len(images))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        grid_path = os.path.join(self.output_dir, f"character_samples_{timestamp}.png")
        grid_image.save(grid_path)
        
        logger.info(f"样本网格图已保存到: {grid_path}")
        
        # 保存每个样本
        sample_paths = []
        for i, image in enumerate(images):
            sample_path = os.path.join(self.output_dir, f"character_sample_{timestamp}_{i}.png")
            image.save(sample_path)
            sample_paths.append(sample_path)
            
        # 如果只有一个样本，直接返回路径
        if len(sample_paths) == 1:
            return sample_paths[0]
            
        # 如果有多个样本，需要选择最佳的一个
        # 这里可以实现一个自动评估逻辑，或者等待用户选择
        # 目前简单返回第一个样本
        logger.info("已生成多个样本，选择第一个作为最终结果")
        return sample_paths[0]
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.model is not None:
            del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        logger.info("已清理模型资源") 