#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
导出模块 - 将Live2D模型导出为可用的格式
"""

import os
import logging
import json
import shutil
import zipfile
import time
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from PIL import Image
import pyautogui

logger = logging.getLogger("live2d_generator.exporter")

class ModelExporter:
    """模型导出器类，负责将模型导出为可用的格式"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化模型导出器
        
        Args:
            config: 配置字典，包含导出的相关设置
        """
        self.config = config
        self.export_config = config['export']
        self.output_dir = os.path.join(config['export']['output_dir'], 'model')
        self.temp_dir = config['misc']['temp_dir']
        
        # Cubism可执行文件路径
        if 'cubism' in config:
            self.cubism_path = config['cubism']['executable_path']
        else:
            self.cubism_path = None
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def export(self, project_path: str) -> str:
        """导出模型
        
        Args:
            project_path: Cubism项目路径
            
        Returns:
            导出文件路径
        """
        logger.info(f"导出项目: {project_path}")
        
        try:
            # 创建导出目录
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_dir = os.path.join(self.output_dir, f"export_{timestamp}")
            Path(export_dir).mkdir(parents=True, exist_ok=True)
            
            # 如果project_path是目录，查找.cmo3文件
            if os.path.isdir(project_path):
                cmo3_files = list(Path(project_path).glob("*.cmo3"))
                if cmo3_files:
                    model_path = str(cmo3_files[0])
                    logger.info(f"找到模型文件: {model_path}")
                else:
                    logger.error(f"在目录{project_path}中未找到.cmo3文件")
                    return ""
            else:
                model_path = project_path
            
            # 根据导出格式选择导出方法
            export_format = self.export_config['format']
            
            if export_format == "moc3":
                # 导出为moc3格式
                output_path = self._export_moc3(model_path, export_dir)
            else:  # model3.json
                # 导出为model3.json格式
                output_path = self._export_model3_json(model_path, export_dir)
            
            # 复制必要的资源
            self._copy_resources(project_path, export_dir)
            
            # 生成附加文件
            self._generate_additional_files(export_dir, model_path)
            
            # 压缩导出文件（如果需要）
            if self.export_config['compression']['enabled']:
                zip_path = self._compress_export(export_dir)
                logger.info(f"已压缩导出文件: {zip_path}")
                return zip_path
            
            return export_dir
            
        except Exception as e:
            logger.error(f"导出模型时出错: {str(e)}")
            return ""
    
    def _export_moc3(self, model_path: str, export_dir: str) -> str:
        """导出为moc3格式
        
        Args:
            model_path: 模型文件路径
            export_dir: 导出目录
            
        Returns:
            导出文件路径
        """
        logger.info(f"导出为moc3格式: {model_path}")
        
        # 检查是否需要通过Cubism软件导出
        if self.cubism_path and os.path.exists(self.cubism_path):
            # 通过Cubism软件导出
            return self._export_via_cubism(model_path, export_dir, "moc3")
        else:
            # 直接复制模型文件
            target_path = os.path.join(export_dir, "model.moc3")
            try:
                # 复制模型文件到导出目录
                shutil.copy2(model_path, target_path)
                logger.info(f"已复制模型文件: {target_path}")
                return target_path
            except Exception as e:
                logger.error(f"复制模型文件失败: {str(e)}")
                return ""
    
    def _export_model3_json(self, model_path: str, export_dir: str) -> str:
        """导出为model3.json格式
        
        Args:
            model_path: 模型文件路径
            export_dir: 导出目录
            
        Returns:
            导出文件路径
        """
        logger.info(f"导出为model3.json格式: {model_path}")
        
        # 检查是否需要通过Cubism软件导出
        if self.cubism_path and os.path.exists(self.cubism_path):
            # 通过Cubism软件导出
            return self._export_via_cubism(model_path, export_dir, "model3.json")
        else:
            # 无法导出model3.json，生成一个示例文件
            target_path = os.path.join(export_dir, "model.model3.json")
            
            # 创建一个基本的model3.json文件
            model_data = {
                "Version": 3,
                "FileReferences": {
                    "Moc": "model.moc3",
                    "Textures": [
                        "textures/texture_00.png"
                    ],
                    "Physics": "physics.json",
                    "Motions": {
                        "Idle": [
                            {"File": "motions/idle.motion3.json"}
                        ],
                        "TapBody": [
                            {"File": "motions/tap_body.motion3.json"}
                        ]
                    }
                },
                "Groups": [
                    {
                        "Target": "Parameter",
                        "Name": "LipSync",
                        "Ids": ["ParamMouthOpen"]
                    },
                    {
                        "Target": "Parameter",
                        "Name": "EyeBlink",
                        "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]
                    }
                ]
            }
            
            # 写入JSON文件
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, indent=2)
            
            logger.info(f"已创建model3.json文件: {target_path}")
            return target_path
    
    def _export_via_cubism(self, model_path: str, export_dir: str, format_type: str) -> str:
        """通过Cubism软件导出模型
        
        Args:
            model_path: 模型文件路径
            export_dir: 导出目录
            format_type: 导出格式类型
            
        Returns:
            导出文件路径
        """
        logger.info(f"通过Cubism软件导出模型: {model_path}")
        
        # 这里需要实现通过控制Cubism软件UI来导出模型的逻辑
        # 由于UI自动化比较复杂，这里提供一个简化的实现
        
        # 检查操作系统
        if platform.system() == "Windows":
            # Windows实现
            # 启动Cubism并打开模型文件
            subprocess.run([self.cubism_path, model_path], check=False)
            
        elif platform.system() == "Darwin":  # macOS
            # macOS实现
            subprocess.run(["open", "-a", self.cubism_path, model_path], check=False)
            
        else:
            logger.error(f"不支持的操作系统: {platform.system()}")
            return ""
        
        # 等待Cubism启动
        time.sleep(5)
        
        # 执行导出操作
        try:
            # 按下Alt键显示菜单
            pyautogui.hotkey('alt')
            time.sleep(0.5)
            
            # 点击File菜单
            pyautogui.press('f')
            time.sleep(0.5)
            
            # 点击Export子菜单
            pyautogui.press('e')
            time.sleep(0.5)
            
            # 根据导出格式选择相应选项
            if format_type == "moc3":
                pyautogui.press('m')  # 假设'm'对应moc3选项
            else:  # model3.json
                pyautogui.press('j')  # 假设'j'对应model3.json选项
                
            time.sleep(1)
            
            # 在文件选择对话框中输入保存路径
            export_path = os.path.join(export_dir, f"model.{format_type}")
            pyautogui.write(export_path)
            time.sleep(0.5)
            pyautogui.press('enter')
            
            # 等待导出完成
            time.sleep(3)
            
            # 关闭Cubism
            pyautogui.hotkey('alt', 'f4')
            
            # 检查导出文件是否存在
            if os.path.exists(export_path):
                logger.info(f"导出成功: {export_path}")
                return export_path
            else:
                logger.warning(f"找不到导出文件: {export_path}")
                return ""
                
        except Exception as e:
            logger.error(f"通过Cubism导出时出错: {str(e)}")
            return ""
    
    def _copy_resources(self, project_path: str, export_dir: str) -> None:
        """复制必要的资源文件
        
        Args:
            project_path: 项目路径
            export_dir: 导出目录
        """
        logger.info(f"复制资源文件: {project_path} -> {export_dir}")
        
        # 创建资源目录
        textures_dir = os.path.join(export_dir, "textures")
        motions_dir = os.path.join(export_dir, "motions")
        
        Path(textures_dir).mkdir(parents=True, exist_ok=True)
        Path(motions_dir).mkdir(parents=True, exist_ok=True)
        
        # 如果project_path是目录，复制其中的纹理文件
        if os.path.isdir(project_path):
            # 复制纹理文件
            for ext in ['.png', '.jpg', '.jpeg']:
                for texture_file in Path(project_path).glob(f"*{ext}"):
                    target_path = os.path.join(textures_dir, texture_file.name)
                    shutil.copy2(texture_file, target_path)
                    logger.info(f"已复制纹理文件: {target_path}")
            
            # 复制动作文件
            for motion_file in Path(project_path).glob("*.motion3.json"):
                target_path = os.path.join(motions_dir, motion_file.name)
                shutil.copy2(motion_file, target_path)
                logger.info(f"已复制动作文件: {target_path}")
                
            # 复制物理文件
            for physics_file in Path(project_path).glob("physics*.json"):
                target_path = os.path.join(export_dir, physics_file.name)
                shutil.copy2(physics_file, target_path)
                logger.info(f"已复制物理文件: {target_path}")
        
        # 如果没有找到纹理文件，创建示例纹理
        if not list(Path(textures_dir).glob("*.png")):
            self._create_sample_texture(textures_dir)
        
        # 如果没有找到动作文件且需要包含演示动作，创建示例动作
        if not list(Path(motions_dir).glob("*.motion3.json")) and self.export_config['include_demo_motion']:
            self._create_sample_motion(motions_dir)
    
    def _create_sample_texture(self, textures_dir: str) -> None:
        """创建示例纹理
        
        Args:
            textures_dir: 纹理目录
        """
        logger.info("创建示例纹理")
        
        # 创建一个简单的示例纹理
        texture_path = os.path.join(textures_dir, "texture_00.png")
        
        # 创建一个1024x1024的透明图像
        img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        
        # 保存图像
        img.save(texture_path, "PNG")
        
        logger.info(f"已创建示例纹理: {texture_path}")
    
    def _create_sample_motion(self, motions_dir: str) -> None:
        """创建示例动作
        
        Args:
            motions_dir: 动作目录
        """
        logger.info("创建示例动作")
        
        # 创建一个简单的示例动作
        idle_path = os.path.join(motions_dir, "idle.motion3.json")
        
        # 创建一个基本的idle动作
        idle_motion = {
            "Version": 3,
            "Meta": {
                "Duration": 3.0,
                "Fps": 30.0,
                "Loop": True,
                "AreBeziersRestricted": True,
                "CurveCount": 2,
                "TotalSegmentCount": 7,
                "TotalPointCount": 20,
                "UserDataCount": 0,
                "TotalUserDataSize": 0
            },
            "Curves": [
                {
                    "Target": "Parameter",
                    "Id": "ParamBreath",
                    "Segments": [
                        0, 0, 0, 0,
                        0, 0, 0, 0.5, 0, 1.5, 1.0, 0,
                        1.5, 0, 0, 3.0, 0, 0, 0
                    ]
                },
                {
                    "Target": "Parameter",
                    "Id": "ParamEyeBlink",
                    "Segments": [
                        0, 1, 0, 0,
                        0, 0, 0, 0.2, 0, 0.3, 0, 0,
                        0.3, 0, 0, 0.5, 1, 0, 0,
                        2.0, 1, 0, 0,
                        2.0, 0, 0, 2.2, 0, 2.3, 0, 0,
                        2.3, 0, 0, 2.5, 1, 0, 0,
                        3.0, 1, 0, 0
                    ]
                }
            ]
        }
        
        # 写入JSON文件
        with open(idle_path, 'w', encoding='utf-8') as f:
            json.dump(idle_motion, f, indent=2)
        
        # 创建点击身体动作
        tap_path = os.path.join(motions_dir, "tap_body.motion3.json")
        
        # 创建一个基本的tap动作
        tap_motion = {
            "Version": 3,
            "Meta": {
                "Duration": 2.0,
                "Fps": 30.0,
                "Loop": False,
                "AreBeziersRestricted": True,
                "CurveCount": 2,
                "TotalSegmentCount": 6,
                "TotalPointCount": 16,
                "UserDataCount": 0,
                "TotalUserDataSize": 0
            },
            "Curves": [
                {
                    "Target": "Parameter",
                    "Id": "ParamBodyAngleX",
                    "Segments": [
                        0, 0, 0, 0,
                        0, 0, 0, 0.5, 10, 1.0, 0, 0,
                        1.0, 0, 0, 1.5, -8, 2.0, 0, 0
                    ]
                },
                {
                    "Target": "Parameter",
                    "Id": "ParamMouthForm",
                    "Segments": [
                        0, 0, 0, 0,
                        0, 0, 0, 0.3, 1, 1.0, 0, 0,
                        1.0, 0, 0, 2.0, 0, 0, 0
                    ]
                }
            ]
        }
        
        # 写入JSON文件
        with open(tap_path, 'w', encoding='utf-8') as f:
            json.dump(tap_motion, f, indent=2)
        
        logger.info(f"已创建示例动作: {idle_path}, {tap_path}")
    
    def _generate_additional_files(self, export_dir: str, model_path: str) -> None:
        """生成附加文件
        
        Args:
            export_dir: 导出目录
            model_path: 模型文件路径
        """
        logger.info("生成附加文件")
        
        additional_files = self.export_config['additional_files']
        
        # 生成README文件
        if "readme" in additional_files:
            readme_path = os.path.join(export_dir, "README.txt")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write("Live2D AI Generator 生成的模型\n")
                f.write("===========================\n\n")
                f.write("此模型由Live2D AI Generator自动生成。\n\n")
                f.write("使用方法：\n")
                f.write("1. 在支持Live2D的应用程序中导入model3.json文件\n")
                f.write("2. 如果您使用的是Web应用，请按照Web应用的文档设置\n\n")
                f.write("文件说明：\n")
                f.write("- model.moc3: 模型文件\n")
                f.write("- model.model3.json: 模型配置文件\n")
                f.write("- textures/: 纹理文件目录\n")
                f.write("- motions/: 动作文件目录\n")
                f.write("- physics.json: 物理效果配置文件（如果有）\n\n")
                f.write("注意事项：\n")
                f.write("- 此模型仅供学习和研究目的使用\n")
                f.write("- 请遵守Live2D的使用条款\n")
            
            logger.info(f"已创建README文件: {readme_path}")
        
        # 生成缩略图
        if "thumbnail" in additional_files:
            thumbnail_path = os.path.join(export_dir, "thumbnail.png")
            
            # 如果可以找到模型的纹理，使用第一个纹理作为基础创建缩略图
            texture_files = list(Path(os.path.join(export_dir, "textures")).glob("*.png"))
            if texture_files:
                try:
                    # 打开第一个纹理文件
                    texture = Image.open(texture_files[0])
                    
                    # 调整大小为缩略图
                    thumbnail = texture.resize((512, 512), Image.LANCZOS)
                    
                    # 保存缩略图
                    thumbnail.save(thumbnail_path, "PNG")
                    
                    logger.info(f"已创建缩略图: {thumbnail_path}")
                except Exception as e:
                    logger.error(f"创建缩略图失败: {str(e)}")
            else:
                # 如果没有纹理，创建一个简单的缩略图
                img = Image.new("RGB", (512, 512), (200, 200, 200))
                img.save(thumbnail_path, "PNG")
                logger.info(f"已创建默认缩略图: {thumbnail_path}")
    
    def _compress_export(self, export_dir: str) -> str:
        """压缩导出文件
        
        Args:
            export_dir: 导出目录
            
        Returns:
            压缩文件路径
        """
        logger.info(f"压缩导出文件: {export_dir}")
        
        # 创建ZIP文件路径
        zip_path = f"{export_dir}.zip"
        
        # 设置压缩级别
        compression_level = self.export_config['compression']['level']
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
            # 遍历导出目录中的所有文件
            for root, _, files in os.walk(export_dir):
                for file in files:
                    # 获取文件的完整路径
                    file_path = os.path.join(root, file)
                    # 获取相对路径
                    rel_path = os.path.relpath(file_path, export_dir)
                    # 添加到ZIP文件
                    zipf.write(file_path, rel_path)
        
        return zip_path
    
    def cleanup(self) -> None:
        """清理资源"""
        # 清理临时文件等
        logger.info("清理导出资源") 