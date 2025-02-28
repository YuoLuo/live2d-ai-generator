#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
参数生成模块 - 为Live2D模型生成动画参数
"""

import os
import logging
import json
import math
import random
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import shutil

logger = logging.getLogger("live2d_generator.parameters_gen")

class ParametersGenerator:
    """参数生成器类，负责为Live2D模型生成动画参数"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化参数生成器
        
        Args:
            config: 配置字典，包含参数生成的相关设置
        """
        self.config = config
        self.parameters_config = config['parameters']
        self.output_dir = os.path.join(config['export']['output_dir'], 'model')
        self.temp_dir = config['misc']['temp_dir']
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # 默认参数模板路径
        self.templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        Path(self.templates_dir).mkdir(parents=True, exist_ok=True)
    
    def generate(self, project_path: str) -> bool:
        """生成参数
        
        Args:
            project_path: Cubism项目路径
            
        Returns:
            是否成功生成
        """
        logger.info(f"为项目{project_path}生成参数")
        
        try:
            # 如果project_path是目录，查找.cmo3文件
            if os.path.isdir(project_path):
                cmo3_files = list(Path(project_path).glob("*.cmo3"))
                if cmo3_files:
                    model_path = str(cmo3_files[0])
                    logger.info(f"找到模型文件: {model_path}")
                else:
                    logger.error(f"在目录{project_path}中未找到.cmo3文件")
                    return False
            else:
                model_path = project_path
            
            # 生成各种参数
            
            # 1. 生成眨眼参数
            self._generate_eye_blink_params(model_path)
            
            # 2. 生成嘴部参数
            self._generate_mouth_params(model_path)
            
            # 3. 生成头部旋转参数
            self._generate_head_rotation_params(model_path)
            
            # 4. 生成身体参数
            self._generate_body_params(model_path)
            
            # 5. 生成物理参数
            self._generate_physics_params(model_path)
            
            # 6. 生成组合参数
            self._generate_combined_params(model_path)
            
            logger.info("参数生成完成")
            return True
            
        except Exception as e:
            logger.error(f"生成参数时出错: {str(e)}")
            return False
    
    def _generate_eye_blink_params(self, model_path: str) -> None:
        """生成眨眼参数
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成眨眼参数...")
        
        # 眨眼参数配置
        eye_config = self.parameters_config['eye']
        blink_speed = eye_config['blink_speed']
        random_blink = eye_config['random_blink']
        
        # 生成眨眼序列
        """
        典型的眨眼序列如下:
        1. 眼睛完全打开 (值为1.0)
        2. 快速闭合 (值从1.0降至0.0)
        3. 短暂保持闭合状态
        4. 快速打开 (值从0.0升至1.0)
        
        这里我们生成一个简单的眨眼模式
        """
        
        # 创建眨眼模式
        eye_open_curve = self._create_eye_blink_curve(blink_speed, random_blink)
        
        # 将生成的参数保存到文件中
        # 这里仅记录生成的眨眼曲线信息
        logger.info(f"已生成眨眼曲线，共{len(eye_open_curve)}个关键帧")
    
    def _create_eye_blink_curve(self, speed: float, random_blink: bool) -> List[Dict[str, float]]:
        """创建眨眼曲线
        
        Args:
            speed: 眨眼速度
            random_blink: 是否随机眨眼
            
        Returns:
            眨眼曲线关键帧列表
        """
        # 关键帧列表
        keyframes = []
        
        # 眨眼持续时间 (秒)
        blink_duration = 0.3 / speed
        
        # 眨眼间隔时间 (秒)
        if random_blink:
            interval = random.uniform(2.0, 6.0)
        else:
            interval = 4.0
        
        # 总时长 (秒)
        total_time = 10.0
        
        current_time = 0.0
        while current_time < total_time:
            # 添加眼睛打开状态
            keyframes.append({"time": current_time, "value": 1.0})
            
            # 眼睛开始闭合
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.9})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.7})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.5})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.2})
            
            # 眼睛完全闭合
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.0})
            
            # 保持闭合状态
            current_time += 0.06
            keyframes.append({"time": current_time, "value": 0.0})
            
            # 眼睛开始打开
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.2})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.5})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.7})
            
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 0.9})
            
            # 眼睛完全打开
            current_time += 0.02
            keyframes.append({"time": current_time, "value": 1.0})
            
            # 等待下一次眨眼
            if random_blink:
                wait_time = random.uniform(interval * 0.7, interval * 1.3)
            else:
                wait_time = interval
                
            current_time += wait_time
        
        return keyframes
    
    def _generate_mouth_params(self, model_path: str) -> None:
        """生成嘴部参数
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成嘴部参数...")
        
        # 嘴部参数配置
        mouth_config = self.parameters_config['mouth']
        
        # 这里可以实现嘴部动作参数的生成
        # 例如说话模式、情绪表达等
        
        # 生成口型同步数据（如果启用）
        if mouth_config['auto_lip_sync']:
            # 创建一些示例口型数据
            lip_sync_data = self._create_sample_lip_sync()
            logger.info(f"已生成口型同步数据，共{len(lip_sync_data)}个关键帧")
        
        # 添加不同表情的嘴型
        expressions = mouth_config['preset_expressions']
        for expression in expressions:
            logger.info(f"创建{expression}表情的嘴型参数")
    
    def _create_sample_lip_sync(self) -> List[Dict[str, float]]:
        """创建示例口型同步数据
        
        Returns:
            口型同步关键帧列表
        """
        # 关键帧列表
        keyframes = []
        
        # 示例口型同步，模拟一段简单的说话
        # 设置总时长和说话节奏
        total_time = 5.0  # 5秒的示例
        syllable_count = 10  # 大约10个音节
        
        for i in range(syllable_count):
            # 每个音节开始时间
            start_time = i * (total_time / syllable_count)
            
            # 嘴巴开始张开
            keyframes.append({"time": start_time, "value": 0.0})
            
            # 嘴巴达到最大张开度
            max_open = random.uniform(0.3, 0.7)  # 随机张开度
            keyframes.append({"time": start_time + 0.1, "value": max_open})
            
            # 嘴巴开始闭合
            keyframes.append({"time": start_time + 0.2, "value": 0.2})
            
            # 嘴巴完全闭合
            keyframes.append({"time": start_time + 0.3, "value": 0.0})
        
        return keyframes
    
    def _generate_head_rotation_params(self, model_path: str) -> None:
        """生成头部旋转参数
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成头部旋转参数...")
        
        # 头部参数配置
        head_config = self.parameters_config['head']
        
        # 获取旋转范围
        x_range = head_config['rotation_range_x']
        y_range = head_config['rotation_range_y']
        z_range = head_config['rotation_range_z']
        
        # 生成自然的头部运动曲线
        # 这里使用正弦波模拟自然摇头动作
        
        # X轴旋转 (上下点头)
        x_curve = self._create_head_rotation_curve('x', x_range)
        
        # Y轴旋转 (左右摇头)
        y_curve = self._create_head_rotation_curve('y', y_range)
        
        # Z轴旋转 (头部倾斜)
        z_curve = self._create_head_rotation_curve('z', z_range)
        
        logger.info("已生成头部旋转参数")
    
    def _create_head_rotation_curve(self, axis: str, range_values: List[float]) -> List[Dict[str, float]]:
        """创建头部旋转曲线
        
        Args:
            axis: 旋转轴 ('x', 'y', 'z')
            range_values: 旋转范围 [min, max]
            
        Returns:
            旋转曲线关键帧列表
        """
        # 关键帧列表
        keyframes = []
        
        # 设置曲线参数
        total_time = 10.0  # 10秒循环
        
        if axis == 'x':
            # X轴使用较快的频率
            frequency = 0.2  # Hz
            phase = 0.0
        elif axis == 'y':
            # Y轴使用较慢的频率
            frequency = 0.15  # Hz
            phase = 1.57  # 与X轴相位差90度
        else:  # z
            # Z轴使用最慢的频率
            frequency = 0.1  # Hz
            phase = 3.14  # 与X轴相位差180度
        
        # 计算中值和振幅
        min_val, max_val = range_values
        mid_val = (min_val + max_val) / 2
        amplitude = (max_val - min_val) / 2
        
        # 生成关键帧
        step = 0.1  # 每0.1秒一个关键帧
        for t in range(int(total_time / step) + 1):
            time_point = t * step
            # 使用正弦函数生成自然的摇摆曲线
            value = mid_val + amplitude * math.sin(2 * math.pi * frequency * time_point + phase)
            keyframes.append({"time": time_point, "value": value})
        
        return keyframes
    
    def _generate_body_params(self, model_path: str) -> None:
        """生成身体参数
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成身体参数...")
        
        # 身体参数配置
        body_config = self.parameters_config['body']
        
        # 生成呼吸动作
        if body_config['breathing_enabled']:
            breathing_depth = body_config['breathing_depth']
            breathing_speed = body_config['breathing_speed']
            
            # 创建呼吸曲线
            breathing_curve = self._create_breathing_curve(breathing_depth, breathing_speed)
            logger.info(f"已生成呼吸曲线，共{len(breathing_curve)}个关键帧")
    
    def _create_breathing_curve(self, depth: float, speed: float) -> List[Dict[str, float]]:
        """创建呼吸曲线
        
        Args:
            depth: 呼吸深度
            speed: 呼吸速度
            
        Returns:
            呼吸曲线关键帧列表
        """
        # 关键帧列表
        keyframes = []
        
        # 设置曲线参数
        total_time = 10.0  # 10秒循环
        frequency = 0.25 * speed  # 基础频率 * 速度系数
        
        # 生成正弦曲线
        step = 0.1  # 每0.1秒一个关键帧
        for t in range(int(total_time / step) + 1):
            time_point = t * step
            # 呼吸曲线：基础值 + 深度 * sin曲线
            # 使用0.5作为基础值，使得呼吸在0到1之间
            value = 0.5 + depth * 0.5 * math.sin(2 * math.pi * frequency * time_point)
            keyframes.append({"time": time_point, "value": value})
        
        return keyframes
    
    def _generate_physics_params(self, model_path: str) -> None:
        """生成物理参数
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成物理参数...")
        
        # 物理参数配置
        physics_config = self.parameters_config['physics']
        
        # 设置头发刚度和阻尼
        hair_stiffness = physics_config['hair_stiffness']
        hair_damping = physics_config['hair_damping']
        
        # 设置衣服刚度和阻尼
        cloth_stiffness = physics_config['cloth_stiffness']
        cloth_damping = physics_config['cloth_damping']
        
        # 物理参数通常直接保存到模型中，而不是作为动画曲线
        # 在这里我们记录物理参数配置
        logger.info(f"物理参数配置: 头发刚度={hair_stiffness}, 头发阻尼={hair_damping}, "
                   f"衣服刚度={cloth_stiffness}, 衣服阻尼={cloth_damping}")
    
    def _generate_combined_params(self, model_path: str) -> None:
        """生成组合参数，如整体的表情和动作
        
        Args:
            model_path: 模型文件路径
        """
        logger.info("生成组合参数...")
        
        # 这里可以创建一些组合参数
        # 例如同时控制多个参数的表情组合
        
        # 生成示例表情组合
        expressions = self.parameters_config['mouth']['preset_expressions']
        for expression in expressions:
            logger.info(f"创建{expression}组合表情参数")
    
    def cleanup(self) -> None:
        """清理资源"""
        # 清理临时文件等
        logger.info("清理参数生成资源") 