#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图层分割模块 - 将角色图像分解为Live2D所需的各个图层
"""

import os
import logging
import numpy as np
import cv2
import torch
from PIL import Image
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from tqdm import tqdm
import time
from datetime import datetime

# 导入分割模型
from segment_anything import SamPredictor, sam_model_registry
import rembg

logger = logging.getLogger("live2d_generator.layer_separator")

class LayerSeparator:
    """图层分割器类，负责将角色图像分解为Live2D所需的各个图层"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化图层分割器
        
        Args:
            config: 配置字典，包含图层分割的相关设置
        """
        self.config = config
        self.layers_config = config['layers']
        self.output_dir = os.path.join(config['export']['output_dir'], 'layers')
        self.temp_dir = config['misc']['temp_dir']
        self.device = "cuda" if torch.cuda.is_available() and config['misc']['use_gpu'] else "cpu"
        self.segmentation_model = None
        self.sam_predictor = None
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # 定义部位图层顺序和关系
        self.part_hierarchy = {
            "background": 0,
            "hair_back": 1,
            "body": 2,
            "arm_left": 3,
            "arm_right": 3,
            "leg_left": 3,
            "leg_right": 3,
            "face": 4,
            "eye_white_left": 5,
            "eye_white_right": 5,
            "iris_left": 6,
            "iris_right": 6,
            "highlight_left": 7,
            "highlight_right": 7,
            "eyebrows_left": 8,
            "eyebrows_right": 8,
            "nose": 9,
            "mouth": 10,
            "upper_lip": 11,
            "lower_lip": 11,
            "hair_side": 12,
            "hair_front": 13,
            "accessories": 14
        }
        
        # 部位的颜色提示（用于SAM模型）
        self.part_colors = {
            "hair_front": [(200, 150, 100), (240, 180, 120)],   # 金色/棕色
            "hair_side": [(200, 150, 100), (240, 180, 120)],    # 金色/棕色
            "hair_back": [(200, 150, 100), (240, 180, 120)],    # 金色/棕色
            "face": [(255, 200, 200), (255, 220, 220)],         # 肤色
            "eyebrows": [(100, 80, 80), (80, 60, 60)],          # 深棕色
            "eye_white": [(250, 250, 250), (240, 240, 240)],    # 白色
            "iris": [(100, 150, 200), (50, 200, 50)],           # 蓝色/绿色
            "highlight": [(255, 255, 255)],                     # 白色高光
            "nose": [(255, 200, 200), (255, 180, 180)],         # 肤色
            "mouth": [(240, 120, 120), (250, 150, 150)],        # 红色
            "upper_lip": [(240, 120, 120), (250, 150, 150)],    # 红色
            "lower_lip": [(240, 120, 120), (250, 150, 150)],    # 红色
            "body": [(180, 180, 220), (220, 220, 250)],         # 浅蓝色/灰色
            "arm": [(255, 200, 200), (255, 220, 220)],          # 肤色
            "leg": [(255, 200, 200), (255, 220, 220)],          # 肤色
            "accessories": [(220, 220, 100), (250, 250, 150)]   # 金色
        }
    
    def _load_model(self) -> None:
        """加载分割模型"""
        model_type = self.layers_config['segmentation_model']
        
        if model_type == "segment_anything":
            logger.info("加载Segment Anything模型...")
            
            # 检查模型文件是否存在，不存在则下载
            model_dir = os.path.join(self.temp_dir, "sam_models")
            Path(model_dir).mkdir(parents=True, exist_ok=True)
            
            model_path = os.path.join(model_dir, "sam_vit_h_4b8939.pth")
            if not os.path.exists(model_path):
                logger.info("下载SAM模型...")
                import urllib.request
                urllib.request.urlretrieve(
                    "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
                    model_path
                )
            
            # 加载SAM模型
            sam = sam_model_registry["vit_h"](checkpoint=model_path)
            sam.to(device=self.device)
            self.sam_predictor = SamPredictor(sam)
            
        elif model_type == "u2net":
            # U2Net已经集成在rembg中，不需要显式加载
            logger.info("使用U2Net模型（通过rembg库）")
            pass
            
        else:
            logger.warning(f"未知的分割模型类型: {model_type}，使用回退方法")
            # 使用rembg作为回退
            pass
    
    def _remove_background(self, image_path: str) -> Image.Image:
        """移除图像背景
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            去除背景后的图像
        """
        logger.info("移除图像背景...")
        
        # 使用rembg库移除背景
        with open(image_path, 'rb') as f:
            input_data = f.read()
        
        output_data = rembg.remove(input_data)
        
        # 保存中间文件用于调试
        no_bg_path = os.path.join(self.temp_dir, "no_background.png")
        with open(no_bg_path, 'wb') as f:
            f.write(output_data)
        
        # 转换为PIL图像
        img = Image.open(no_bg_path).convert("RGBA")
        return img
    
    def _segment_with_sam(self, image: np.ndarray, part_name: str) -> List[np.ndarray]:
        """使用Segment Anything Model进行分割
        
        Args:
            image: 输入图像数组
            part_name: 部位名称
            
        Returns:
            分割掩码列表
        """
        if self.sam_predictor is None:
            logger.warning("SAM预测器未加载，无法执行分割")
            return []
        
        # 设置输入图像
        self.sam_predictor.set_image(image)
        
        # 根据部位名称获取颜色提示
        base_part = part_name.split('_')[0] if '_' in part_name else part_name
        colors = self.part_colors.get(base_part, None)
        if not colors:
            colors = self.part_colors.get(part_name, None)
        
        if not colors:
            logger.warning(f"没有为部位{part_name}找到颜色提示")
            return []
        
        # 寻找与颜色匹配的区域作为提示点
        masks = []
        for color in colors:
            points = []
            labels = []
            
            # 颜色匹配的阈值
            threshold = 30
            
            # 将RGB颜色转换为HSV以便更好地匹配
            color_hsv = cv2.cvtColor(np.uint8([[color]]), cv2.COLOR_RGB2HSV)[0][0]
            
            # 将图像转换为HSV
            image_hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            
            # 创建颜色掩码
            lower_bound = np.array([max(0, color_hsv[0] - threshold), 50, 50])
            upper_bound = np.array([min(179, color_hsv[0] + threshold), 255, 255])
            color_mask = cv2.inRange(image_hsv, lower_bound, upper_bound)
            
            # 找到颜色匹配区域的坐标
            coords = np.column_stack(np.where(color_mask > 0))
            
            if len(coords) > 0:
                # 采样一些点作为提示
                sample_size = min(10, len(coords))
                sampled_indices = np.random.choice(len(coords), sample_size, replace=False)
                sampled_coords = coords[sampled_indices]
                
                for coord in sampled_coords:
                    points.append([coord[1], coord[0]])  # 注意xy坐标转换
                    labels.append(1)  # 前景点
            
            if points:
                # 使用SAM模型进行分割
                points_array = np.array(points)
                labels_array = np.array(labels)
                masks_output, _, _ = self.sam_predictor.predict(
                    point_coords=points_array,
                    point_labels=labels_array,
                    multimask_output=True
                )
                
                # 添加到结果列表
                for mask in masks_output:
                    masks.append(mask)
        
        return masks
    
    def _segment_part(self, image: Image.Image, part_name: str) -> Optional[Image.Image]:
        """分割特定部位
        
        Args:
            image: 输入图像
            part_name: 部位名称
            
        Returns:
            分割后的部位图像，如果分割失败则返回None
        """
        logger.info(f"分割部位: {part_name}")
        
        # 转换为NumPy数组以便处理
        np_image = np.array(image)
        
        # 根据不同部位使用不同的分割策略
        masks = []
        
        # 使用SAM模型分割
        if self.layers_config['segmentation_model'] == "segment_anything":
            masks = self._segment_with_sam(np_image, part_name)
        
        # 如果没有找到掩码，使用回退方法
        if not masks:
            logger.warning(f"未能使用主要模型分割{part_name}，尝试回退方法")
            
            # 针对特定部位的回退分割逻辑
            if "eye" in part_name:
                # 眼睛区域可能在脸部上半部分
                height, width = np_image.shape[:2]
                face_top = height // 4
                face_bottom = height // 2
                face_left = width // 4
                face_right = 3 * width // 4
                
                # 创建一个简单的掩码
                mask = np.zeros((height, width), dtype=np.bool_)
                mask[face_top:face_bottom, face_left:face_right] = True
                masks = [mask]
                
            elif "mouth" in part_name:
                # 嘴巴区域可能在脸部下半部分
                height, width = np_image.shape[:2]
                face_top = height // 2
                face_bottom = 3 * height // 4
                face_left = width // 3
                face_right = 2 * width // 3
                
                # 创建一个简单的掩码
                mask = np.zeros((height, width), dtype=np.bool_)
                mask[face_top:face_bottom, face_left:face_right] = True
                masks = [mask]
                
            elif "hair" in part_name:
                # 头发区域可能在图像上部
                height, width = np_image.shape[:2]
                hair_bottom = height // 2
                
                # 创建一个简单的掩码
                mask = np.zeros((height, width), dtype=np.bool_)
                mask[:hair_bottom, :] = True
                masks = [mask]
        
        # 如果有多个掩码，选择最大的一个
        if masks:
            # 按面积排序
            sorted_masks = sorted(masks, key=lambda m: m.sum(), reverse=True)
            selected_mask = sorted_masks[0]
            
            # 应用掩码
            result = np.zeros((np_image.shape[0], np_image.shape[1], 4), dtype=np.uint8)
            result[selected_mask, :3] = np_image[selected_mask, :3]
            result[selected_mask, 3] = 255  # 设置alpha通道
            
            # 转换回PIL图像
            segmented_image = Image.fromarray(result)
            
            # 如果需要细化边缘
            if self.layers_config['refine_edges']:
                # 简单的边缘细化：使用高斯模糊处理alpha通道
                alpha = np.array(segmented_image.split()[3])
                alpha_blurred = cv2.GaussianBlur(alpha, (5, 5), 0)
                segmented_image.putalpha(Image.fromarray(alpha_blurred))
            
            return segmented_image
        
        logger.warning(f"未能分割部位: {part_name}")
        return None
    
    def _create_psd(self, layers: Dict[str, Image.Image], output_path: str) -> None:
        """创建PSD文件
        
        Args:
            layers: 图层字典，键为部位名称，值为图像
            output_path: 输出文件路径
        """
        try:
            from psd_tools import PSDImage
            from psd_tools.constants import ColorMode
            
            # 获取图像尺寸
            width, height = next(iter(layers.values())).size
            
            # 创建PSD文件
            psd = PSDImage.new(width=width, height=height, color_mode=ColorMode.RGB)
            
            # 按层级添加图层
            ordered_parts = sorted(layers.keys(), key=lambda p: self.part_hierarchy.get(p, 999))
            
            for part_name in ordered_parts:
                layer_img = layers[part_name]
                psd.create_layer(name=part_name, image=layer_img)
            
            # 保存PSD文件
            psd.save(output_path)
            logger.info(f"已创建PSD文件: {output_path}")
            
        except ImportError:
            logger.error("无法创建PSD文件：缺少psd_tools库")
            logger.info("请安装psd_tools: pip install psd-tools")
    
    def separate(self, image_path: str) -> str:
        """将角色图像分割为多个图层
        
        Args:
            image_path: 角色图像路径
            
        Returns:
            图层目录路径
        """
        # 加载模型
        if self.segmentation_model is None and self.sam_predictor is None:
            self._load_model()
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_subdir = os.path.join(self.output_dir, f"layers_{timestamp}")
        Path(output_subdir).mkdir(parents=True, exist_ok=True)
        
        # 移除背景
        no_bg_image = self._remove_background(image_path)
        no_bg_path = os.path.join(output_subdir, "character_no_bg.png")
        no_bg_image.save(no_bg_path)
        
        # 获取需要分割的部位列表
        parts = self.layers_config['parts']
        
        # 分割每个部位
        layers = {}
        for part_name in tqdm(parts, desc="分割图层"):
            segmented_part = self._segment_part(no_bg_image, part_name)
            if segmented_part:
                # 保存部位图像
                part_path = os.path.join(output_subdir, f"{part_name}.png")
                segmented_part.save(part_path)
                layers[part_name] = segmented_part
        
        # 添加背景图层（如果需要）
        if self.layers_config['fill_background']:
            bg_color = tuple(self.layers_config['background_color'])
            bg_image = Image.new("RGBA", no_bg_image.size, bg_color)
            bg_path = os.path.join(output_subdir, "background.png")
            bg_image.save(bg_path)
            layers["background"] = bg_image
        
        # 创建PSD文件（如果需要）
        if self.layers_config['export_psd']:
            psd_path = os.path.join(output_subdir, "character_layers.psd")
            self._create_psd(layers, psd_path)
        
        return output_subdir
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.sam_predictor is not None:
            del self.sam_predictor
        if self.segmentation_model is not None:
            del self.segmentation_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("已清理分割模型资源") 