#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI模块 - 为Live2D AI Generator提供图形用户界面
"""

import os
import sys
import gradio as gr
import logging
import yaml
import time
import threading
import webbrowser
import numpy as np
from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Union, Tuple

# 添加项目根目录到Python路径
root_dir = str(Path(__file__).parent.parent.absolute())
if root_dir not in sys.path:
    sys.path.append(root_dir)

from main import main as run_main, load_config, setup_logging
from modules.character_gen import CharacterGenerator, AVAILABLE_MODELS
from modules.layer_separator import LayerSeparator
from modules.cubism_automation import CubismAutomation
from modules.parameters_gen import ParametersGenerator
from modules.exporter import ModelExporter

logger = logging.getLogger("live2d_generator.gui")

# 定义一些常量和主题设置
PRIMARY_COLOR = "#4F46E5"  # 靛蓝色，现代感
SECONDARY_COLOR = "#10B981"  # 绿松石色
BG_COLOR = "#F9FAFB"  # 浅灰色背景
TEXT_COLOR = "#111827"  # 深灰近黑色文字
FONT = "Arial"

# 自定义主题
CUSTOM_THEME = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#EBEDFF", 
        c100="#D8DDFF", 
        c200="#B0BAFE", 
        c300="#8897FC", 
        c400="#6677FA", 
        c500=PRIMARY_COLOR, 
        c600="#3F39C7", 
        c700="#3530A8", 
        c800="#292687", 
        c900="#22216B",
        c950="#171650",
    ),
    secondary_hue=gr.themes.Color(
        c50="#ECFDF5",
        c100="#D1FAE5",
        c200="#A7F3D0",
        c300="#6EE7B7",
        c400="#34D399",
        c500=SECONDARY_COLOR,
        c600="#059669",
        c700="#047857",
        c800="#065F46",
        c900="#064E3B",
        c950="#022C22",
    ),
    neutral_hue=gr.themes.Color(
        c50=BG_COLOR,
        c100="#F3F4F6",
        c200="#E5E7EB",
        c300="#D1D5DB",
        c400="#9CA3AF",
        c500="#6B7280",
        c600="#4B5563",
        c700="#374151",
        c800="#1F2937",
        c900=TEXT_COLOR,
        c950="#030712",
    ),
    radius_size=gr.themes.Size(
        xxs="1px", xs="2px", sm="4px", md="6px", lg="12px", xl="16px", xxl="20px"
    ),
    font=[FONT, "ui-sans-serif", "system-ui", "sans-serif"],
)

class Live2DGUI:
    """Live2D模型生成器的图形用户界面"""
    
    def __init__(self, config_path: str = 'config.yml'):
        """初始化GUI
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = load_config(config_path)
        setup_logging(self.config)
        
        # 确保输出和临时目录存在
        self._ensure_directories()
        
        # 状态追踪
        self.processing = False
        self.current_task = ""
        self.progress = 0
        self.messages = []
        
        # 加载配置参数
        self._load_config_params()
    
    def _ensure_directories(self):
        """确保所有必要的目录存在"""
        # 输出目录
        self.output_dir = self.config['io']['output_dir']
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 临时目录
        self.temp_dir = self.config['io']['temp_dir']
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 日志目录
        log_dir = os.path.dirname(self.config['logging']['file'])
        os.makedirs(log_dir, exist_ok=True)
    
    def _load_config_params(self):
        """从配置文件加载参数"""
        char_config = self.config['character']
        self.char_styles = ["anime", "realistic", "cartoon", "sketch"]
        self.poses = ["front_facing", "3/4_view", "profile"]
        self.resolutions = ["512x512", "768x768", "1024x1024", "1536x1536"]
        
        # 图层分割参数
        layer_config = self.config['layer_separation']
        self.segmentation_models = ["segment_anything", "u2net"]
        self.segmentation_qualities = ["low", "medium", "high"]
        
        # 参数生成参数
        params_config = self.config['parameters']
        self.physics_qualities = ["low", "medium", "high"]
        self.deformer_complexities = ["low", "medium", "high"]
        
        # 导出参数
        export_config = self.config['export']
        self.export_formats = ["moc3", "model3.json"]
    
    def _update_status(self, message: str, progress: float = None):
        """更新状态消息
        
        Args:
            message: 状态消息
            progress: 进度值（0-100）
        """
        timestamp = time.strftime("%H:%M:%S")
        self.messages.append(f"[{timestamp}] {message}")
        if progress is not None:
            self.progress = progress
        self.current_task = message
        logger.info(message)
        
        # 只保留最新的100条消息
        if len(self.messages) > 100:
            self.messages = self.messages[-100:]
        
        return "\n".join(self.messages[-10:]), self.progress
    
    def _process_task(self, task_fn, *args, **kwargs):
        """处理长时间运行的任务
        
        Args:
            task_fn: 任务函数
            args: 传递给任务函数的位置参数
            kwargs: 传递给任务函数的关键字参数
            
        Returns:
            任务结果
        """
        self.processing = True
        result = None
        try:
            result = task_fn(*args, **kwargs)
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            logger.error(error_msg)
            self._update_status(error_msg)
        finally:
            self.processing = False
        return result
    
    def generate_character(self, prompt: str, negative_prompt: str, style: str, pose: str, 
                          resolution: str, samples: int, seed: int) -> List[np.ndarray]:
        """生成角色图像
        
        Args:
            prompt: 提示词
            negative_prompt: 负面提示词
            style: 风格
            pose: 姿势
            resolution: 分辨率
            samples: 样本数量
            seed: 随机种子
            
        Returns:
            生成的图像列表
        """
        self._update_status(f"开始生成角色图像，风格: {style}，姿势: {pose}", 0)
        
        # 解析分辨率
        width, height = map(int, resolution.split('x'))
        
        # 准备配置
        char_config = self.config['character'].copy()
        char_config['prompt'] = prompt
        char_config['negative_prompt'] = negative_prompt
        char_config['style'] = style
        char_config['pose'] = pose
        char_config['width'] = width
        char_config['height'] = height
        char_config['num_samples'] = samples
        char_config['seed'] = seed
        
        # 更新配置
        self.config['character'] = char_config
        
        # 创建生成器
        generator = CharacterGenerator(self.config)
        
        # 生成图像
        self._update_status("正在生成角色图像...", 20)
        
        try:
            character_path = generator.generate()
            
            if character_path and os.path.exists(character_path):
                self._update_status(f"成功生成角色图像: {character_path}", 40)
                # 加载生成的图像
                output_image = Image.open(character_path)
                return [np.array(output_image)]
            else:
                self._update_status("生成角色图像失败", 0)
                return []
        except Exception as e:
            self._update_status(f"生成角色时出错: {str(e)}", 0)
            return []
    
    def separate_layers(self, image, model: str, quality: str, parts: List[str]) -> np.ndarray:
        """分割图层
        
        Args:
            image: 输入图像
            model: 分割模型
            quality: 分割质量
            parts: 要分割的部位
            
        Returns:
            分层预览图像
        """
        self._update_status(f"开始分离图层，使用模型: {model}，质量: {quality}", 40)
        
        # 如果输入是numpy数组，转换为PIL图像
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image.astype('uint8'))
        
        # 保存选择的图像
        character_path = os.path.join(self.temp_dir, "selected_character.png")
        image.save(character_path)
        
        # 准备配置
        layer_config = self.config['layer_separation'].copy()
        layer_config['model'] = model
        layer_config['quality'] = quality
        
        # 更新要分割的部位
        for part in layer_config['parts']:
            layer_config['parts'][part] = part in parts
        
        # 创建分割器
        separator = LayerSeparator(self.config)
        
        # 分割图层
        self._update_status("正在分离图层...", 50)
        layers_dir = self._process_task(separator.separate, character_path)
        
        if layers_dir:
            self._update_status(f"成功分离图层，保存到: {layers_dir}", 60)
            
            # 创建图层预览
            layers_preview = self._create_layers_preview(layers_dir)
            return layers_preview
        else:
            self._update_status("分离图层失败", 40)
            return None
    
    def _create_layers_preview(self, layers_dir: str) -> np.ndarray:
        """创建图层预览图像
        
        Args:
            layers_dir: 图层目录
            
        Returns:
            预览图像
        """
        # 查找所有PNG文件
        png_files = list(Path(layers_dir).glob("*.png"))
        
        if not png_files:
            return np.zeros((400, 600, 3), dtype=np.uint8)
        
        # 限制最多显示16个图层
        png_files = png_files[:16]
        
        # 确定网格大小
        grid_size = int(np.ceil(np.sqrt(len(png_files))))
        
        # 创建一个matplotlib图形
        fig, axes = plt.subplots(grid_size, grid_size, figsize=(10, 10))
        fig.subplots_adjust(hspace=0.3, wspace=0.3)
        
        # 如果只有一个元素，确保axes是一个数组
        if grid_size == 1:
            axes = np.array([[axes]])
        
        for i, file_path in enumerate(png_files):
            row = i // grid_size
            col = i % grid_size
            
            # 加载图像
            img = Image.open(file_path)
            
            # 显示图像
            axes[row, col].imshow(img)
            axes[row, col].axis('off')
            axes[row, col].set_title(file_path.stem, fontsize=8)
        
        # 隐藏未使用的子图
        for i in range(len(png_files), grid_size * grid_size):
            row = i // grid_size
            col = i % grid_size
            axes[row, col].axis('off')
        
        # 将图形转换为numpy数组
        fig.canvas.draw()
        preview_img = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        preview_img = preview_img.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        
        plt.close(fig)
        
        return preview_img
    
    def automate_cubism(self, layers_dir: str) -> str:
        """自动化Cubism操作
        
        Args:
            layers_dir: 图层目录
            
        Returns:
            项目路径
        """
        self._update_status("开始自动化Cubism操作", 60)
        
        # 检查Cubism路径
        cubism_path = self.config['cubism']['executable_path']
        if not cubism_path or not os.path.exists(cubism_path):
            self._update_status("Cubism可执行文件路径未设置或不存在，请先设置路径", 60)
            return None
        
        # 创建自动化器
        automation = CubismAutomation(self.config)
        
        # 执行自动化
        self._update_status("正在与Cubism交互...", 70)
        project_path = self._process_task(automation.automate, layers_dir)
        
        if project_path:
            self._update_status(f"Cubism自动化完成，项目保存到: {project_path}", 80)
            return project_path
        else:
            self._update_status("Cubism自动化失败", 60)
            return None
    
    def generate_parameters(self, project_path: str) -> bool:
        """生成参数
        
        Args:
            project_path: 项目路径
            
        Returns:
            是否成功
        """
        self._update_status("开始生成模型参数", 80)
        
        # 创建参数生成器
        params_generator = ParametersGenerator(self.config)
        
        # 生成参数
        self._update_status("正在生成动画参数...", 85)
        success = self._process_task(params_generator.generate, project_path)
        
        if success:
            self._update_status("参数生成完成", 90)
            return True
        else:
            self._update_status("参数生成失败", 80)
            return False
    
    def export_model(self, project_path: str, format: str) -> str:
        """导出模型
        
        Args:
            project_path: 项目路径
            format: 导出格式
            
        Returns:
            导出文件路径
        """
        self._update_status(f"开始导出模型，格式: {format}", 90)
        
        # 准备配置
        export_config = self.config['export'].copy()
        export_config['format'] = format
        
        # 创建导出器
        exporter = ModelExporter(self.config)
        
        # 导出模型
        self._update_status("正在导出模型...", 95)
        export_path = self._process_task(exporter.export, project_path)
        
        if export_path:
            self._update_status(f"模型导出完成，保存到: {export_path}", 100)
            return export_path
        else:
            self._update_status("模型导出失败", 90)
            return None
    
    def run_full_process(self, character_image, prompt, negative_prompt, model_selection, style, pose, resolution,
                        samples, seed, segm_model, segm_quality, parts, include_physics,
                        export_format) -> Tuple[str, np.ndarray]:
        """运行完整的处理流程
        
        Args:
            character_image: 角色图像（如果已有）
            prompt: 提示词
            negative_prompt: 负面提示词
            model_selection: 选择的AI模型
            style: 风格
            pose: 姿势
            resolution: 分辨率
            samples: 样本数量
            seed: 随机种子
            segm_model: 分割模型
            segm_quality: 分割质量
            parts: 要分割的部位
            include_physics: 是否包含物理
            export_format: 导出格式
            
        Returns:
            导出路径和预览图像
        """
        try:
            # 更新模型配置
            if model_selection:
                # 从选择的显示文本中找到对应的模型ID
                selected_model_id = None
                selected_model_provider = None
                
                for model_id, model_info in AVAILABLE_MODELS.items():
                    display_text = f"{model_info['name']} ({model_info['size']}) - {model_info['description']}"
                    if display_text == model_selection:
                        selected_model_id = model_id
                        selected_model_provider = model_info['provider']
                        break
                
                if selected_model_id and selected_model_provider:
                    self.config['character']['model'] = selected_model_id
                    self.config['character']['provider'] = selected_model_provider
                    self._update_status(f"使用模型: {selected_model_id}", 5)
            
            # 步骤1：角色生成或使用现有图像
            character_path = None
            if character_image is not None:
                # 使用上传的图像
                character_path = os.path.join(self.temp_dir, "uploaded_character.png")
                if isinstance(character_image, np.ndarray):
                    Image.fromarray(character_image).save(character_path)
                else:
                    character_image.save(character_path)
                self._update_status("使用上传的角色图像", 10)
            else:
                # 生成新角色
                images = self.generate_character(prompt, negative_prompt, style, pose, 
                                              resolution, samples, seed)
                if images and len(images) > 0:
                    # 使用第一张生成的图像
                    character_path = os.path.join(self.temp_dir, "generated_character.png")
                    Image.fromarray(images[0]).save(character_path)
            
            if not character_path:
                self._update_status("获取角色图像失败，无法继续", 0)
                return None, None
            
            # 步骤2：图层分割
            layers_preview = self.separate_layers(Image.open(character_path), segm_model, 
                                              segm_quality, parts)
            
            # 获取最新的图层目录（应该是最近创建的）
            layer_dirs = [d for d in os.listdir(self.output_dir) 
                        if os.path.isdir(os.path.join(self.output_dir, d)) and d.startswith("layers_")]
            if not layer_dirs:
                self._update_status("找不到图层目录", 50)
                return None, None
            
            layer_dirs.sort(reverse=True)  # 最新的在前面
            layers_dir = os.path.join(self.output_dir, layer_dirs[0])
            
            # 步骤3：Cubism自动化
            project_path = self.automate_cubism(layers_dir)
            if not project_path:
                self._update_status("Cubism自动化失败，无法继续", 60)
                return None, layers_preview
            
            # 步骤4：参数生成
            params_success = self.generate_parameters(project_path)
            if not params_success:
                self._update_status("参数生成失败，将继续导出但可能缺少动画效果", 85)
            
            # 步骤5：导出模型
            export_path = self.export_model(project_path, export_format)
            if not export_path:
                self._update_status("模型导出失败", 90)
                return None, layers_preview
            
            # 完成
            self._update_status("完整处理流程完成！", 100)
            return export_path, layers_preview
            
        except Exception as e:
            error_msg = f"处理过程中出错: {str(e)}"
            logger.error(error_msg)
            self._update_status(error_msg, 0)
            return None, None
    
    def launch_gui(self, share: bool = False, inbrowser: bool = True, server_port: int = 7860):
        """启动GUI
        
        Args:
            share: 是否公开分享
            inbrowser: 是否在浏览器中打开
            server_port: 服务器端口
        """
        # 创建Gradio界面
        with gr.Blocks(theme=CUSTOM_THEME, title="Live2D AI Generator") as interface:
            # 页眉
            with gr.Row():
                gr.HTML("""
                    <div style="text-align: center; margin-bottom: 10px">
                        <h1 style="font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem">
                            Live2D AI Generator
                        </h1>
                        <h3 style="font-size: 1.2rem; font-weight: 400; margin-bottom: 1rem">
                            使用AI技术自动生成Live2D模型
                        </h3>
                    </div>
                """)
            
            # 主界面标签页
            with gr.Tabs():
                # 第一个标签页：一键生成
                with gr.TabItem("一键生成", id="quick_tab"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            # 输入选项
                            with gr.Group():
                                gr.Markdown("### 输入选项")
                                character_image_input = gr.Image(
                                    type="pil", 
                                    label="上传角色图像（可选）", 
                                    elem_id="character_image"
                                )
                            
                            with gr.Group():
                                gr.Markdown("### 角色生成参数（如未上传图像）")
                                prompt_input = gr.Textbox(
                                    value="可爱的动漫女孩，蓝色长发，绿色眼睛，微笑，前视图，白色背景",
                                    label="提示词",
                                    lines=2
                                )
                                negative_prompt_input = gr.Textbox(
                                    value="低质量，模糊，扭曲，额外的肢体，畸形",
                                    label="负面提示词",
                                    lines=2
                                )
                                
                                # 创建模型选项列表
                                model_options = []
                                for model_id, model_info in AVAILABLE_MODELS.items():
                                    model_options.append(f"{model_info['name']} ({model_info['size']}) - {model_info['description']}")
                                
                                # 获取当前配置的模型
                                current_model = self.config['character']['model']
                                current_model_index = 0
                                for i, (model_id, model_info) in enumerate(AVAILABLE_MODELS.items()):
                                    if model_id == current_model:
                                        current_model_index = i
                                        break
                                
                                # 添加模型选择下拉框
                                model_selection = gr.Dropdown(
                                    choices=model_options,
                                    value=model_options[current_model_index],
                                    label="AI模型",
                                    info="选择用于生成角色的AI模型"
                                )
                                
                                # 添加下载按钮
                                download_model_btn_quick = gr.Button("下载选定模型", variant="secondary")
                                download_status_quick = gr.Textbox(
                                    label="下载状态",
                                    interactive=False,
                                    placeholder="点击下载按钮开始下载模型...",
                                    visible=True
                                )
                                
                                style_dropdown = gr.Dropdown(
                                    choices=self.char_styles,
                                    value="anime",
                                    label="风格"
                                )
                                pose_dropdown = gr.Dropdown(
                                    choices=self.poses,
                                    value="front_facing",
                                    label="姿势"
                                )
                                resolution_dropdown = gr.Dropdown(
                                    choices=self.resolutions,
                                    value="1024x1024",
                                    label="分辨率"
                                )
                                with gr.Row():
                                    samples_slider = gr.Slider(
                                        minimum=1,
                                        maximum=8,
                                        value=4,
                                        step=1,
                                        label="样本数量"
                                    )
                                    seed_number = gr.Number(
                                        value=-1,
                                        label="随机种子（-1为随机）"
                                    )
                            
                            with gr.Group():
                                gr.Markdown("### 图层分割参数")
                                segm_model_input = gr.Dropdown(
                                    choices=self.segmentation_models,
                                    value="segment_anything",
                                    label="分割模型"
                                )
                                segm_quality_input = gr.Dropdown(
                                    choices=self.segmentation_qualities,
                                    value="high",
                                    label="分割质量"
                                )
                                parts_input = gr.CheckboxGroup(
                                    choices=["face", "eyes", "eyebrows", "mouth", "nose", "hair", 
                                            "body", "arms", "legs", "accessories"],
                                    value=["face", "eyes", "eyebrows", "mouth", "nose", "hair", 
                                          "body", "arms", "legs"],
                                    label="需要分割的部位"
                                )
                            
                            with gr.Group():
                                gr.Markdown("### 导出参数")
                                physics_input = gr.Checkbox(
                                    value=True,
                                    label="包含物理效果"
                                )
                                export_format_input = gr.Dropdown(
                                    choices=self.export_formats,
                                    value="model3.json",
                                    label="导出格式"
                                )
                            
                            # 提交按钮
                            create_btn = gr.Button("开始生成", variant="primary")
                            
                            # 添加帮助按钮
                            help_btn = gr.Button("查看帮助", variant="secondary")
                        
                        with gr.Column(scale=1):
                            # 输出区域
                            with gr.Group():
                                gr.Markdown("### 处理状态")
                                status_output = gr.Textbox(
                                    label="状态消息",
                                    lines=10,
                                    max_lines=10,
                                    interactive=False
                                )
                                progress_output = gr.Slider(
                                    minimum=0,
                                    maximum=100,
                                    value=0,
                                    step=1,
                                    label="进度",
                                    interactive=False
                                )
                            
                            # 帮助内容
                            help_markdown = gr.Markdown(
                                visible=False,
                                value="""
                                ### 使用说明
                                
                                1. **上传角色图像** 或者 **填写角色描述** 让AI生成角色
                                2. 选择合适的 **AI模型** 以获得最佳效果
                                3. 如果需要，可以在使用前先 **下载选定模型**
                                4. 调整 **风格、姿势、分辨率** 等参数
                                5. 选择要分割的 **角色部位**
                                6. 点击 **开始生成** 按钮启动处理
                                7. 查看 **处理状态** 和 **图层预览**
                                8. 生成完成后，可以点击 **打开输出文件夹** 查看结果
                                
                                > **提示**: 生成过程可能需要一些时间，特别是在首次下载模型时。
                                
                                ### 常见问题
                                
                                - **为什么模型下载很慢？** 模型文件较大，下载速度取决于您的网络连接。
                                - **如何提高生成质量？** 使用更详细的提示词，选择高分辨率和高质量的分割选项。
                                - **生成失败怎么办？** 检查错误消息，确保已安装所有依赖，并尝试重新启动应用。
                                
                                [点击查看完整文档](https://github.com/your-repo/live2d-ai-generator/wiki)
                                """
                            )
                            
                            with gr.Group():
                                gr.Markdown("### 图层预览")
                                layers_preview_output = gr.Image(
                                    type="numpy",
                                    label="图层预览",
                                    elem_id="layers_preview"
                                )
                            
                            with gr.Group():
                                gr.Markdown("### 导出结果")
                                export_path_output = gr.Textbox(
                                    label="导出路径",
                                    interactive=False
                                )
                                open_folder_btn = gr.Button("打开输出文件夹")
                
                # 第二个标签页：分步执行
                with gr.TabItem("分步执行", id="step_tab"):
                    gr.Markdown("### 分步执行功能正在开发中...")
                    # 这里将来可以添加分步执行的界面
                
                # 第三个标签页：配置设置
                with gr.TabItem("配置设置", id="config_tab"):
                    with gr.Row():
                        with gr.Column():
                            # 添加模型选择和下载部分
                            gr.Markdown("### AI模型设置")
                            
                            # 创建模型选项列表
                            model_options = []
                            for model_id, model_info in AVAILABLE_MODELS.items():
                                model_options.append(f"{model_info['name']} ({model_info['size']}) - {model_info['description']}")
                            
                            # 获取当前配置的模型
                            current_model = self.config['character']['model']
                            current_provider = self.config['character']['provider']
                            
                            # 查找当前模型在列表中的索引
                            current_model_index = 0
                            for i, (model_id, model_info) in enumerate(AVAILABLE_MODELS.items()):
                                if model_id == current_model:
                                    current_model_index = i
                                    break
                            
                            # 创建模型选择下拉框
                            model_dropdown = gr.Dropdown(
                                choices=model_options,
                                value=model_options[current_model_index],
                                label="选择AI模型",
                                info="选择用于生成角色的AI模型，不同模型有不同的特点和文件大小"
                            )
                            
                            # 创建模型下载按钮和状态显示
                            with gr.Row():
                                download_model_btn = gr.Button("下载选定模型", variant="primary")
                                model_download_status = gr.Textbox(
                                    label="下载状态",
                                    interactive=False,
                                    placeholder="点击下载按钮开始下载模型..."
                                )
                            
                            gr.Markdown("---")
                            
                            gr.Markdown("### Cubism设置")
                            cubism_path_input = gr.Textbox(
                                value=self.config['cubism']['executable_path'],
                                label="Cubism可执行文件路径",
                                placeholder="例如：C:/Program Files/Live2D Cubism 4.0/app/Cubism.exe"
                            )
                            
                            gr.Markdown("### 输出设置")
                            output_dir_input = gr.Textbox(
                                value=self.config['io']['output_dir'],
                                label="输出目录"
                            )
                            
                            gr.Markdown("### GPU设置")
                            gpu_enabled_input = gr.Checkbox(
                                value=self.config['misc']['gpu']['enabled'],
                                label="启用GPU"
                            )
                            
                            update_config_btn = gr.Button("更新配置", variant="primary")
                            config_status_output = gr.Textbox(
                                label="配置状态",
                                interactive=False
                            )
                
                # 第四个标签页：关于
                with gr.TabItem("关于", id="about_tab"):
                    gr.HTML("""
                        <div style="padding: 20px">
                            <h3>关于 Live2D AI Generator</h3>
                            <p>Live2D AI Generator 是一个自动化的Live2D模型生成工具，利用AI技术将2D角色图像转换为可动的Live2D模型。</p>
                            
                            <h4>主要功能：</h4>
                            <ul>
                                <li><strong>角色生成</strong>：使用Stable Diffusion等AI模型生成高质量的动漫角色立绘</li>
                                <li><strong>自动图层分割</strong>：使用先进的图像分割算法，自动将角色立绘分离为Live2D所需的各个部位图层</li>
                                <li><strong>Cubism自动化</strong>：自动与Live2D Cubism软件交互，导入图层并设置初始参数</li>
                                <li><strong>参数生成</strong>：自动生成眨眼、嘴部动画、呼吸效果等Live2D模型参数</li>
                                <li><strong>模型导出</strong>：将完成的模型导出为可用的格式，支持moc3和model3.json</li>
                            </ul>
                            
                            <h4>使用提示：</h4>
                            <ul>
                                <li>使用前需要设置Cubism软件路径</li>
                                <li>上传图像时，请使用正面或3/4视角的角色立绘</li>
                                <li>对于复杂服装和发型，可能需要手动调整分割结果</li>
                                <li>生成后检查并优化参数以获得最自然的动作效果</li>
                            </ul>
                            
                            <h4>版本信息：</h4>
                            <p>版本：1.0.0</p>
                            <p>&copy; 2023 Live2D AI Generator Team</p>
                        </div>
                    """)
            
            # 页脚
            with gr.Row():
                gr.HTML("""
                    <div style="text-align: center; margin-top: 20px; padding: 10px; border-top: 1px solid #E5E7EB">
                        <p>Live2D AI Generator - 版本 1.0.0</p>
                    </div>
                """)
            
            # 功能绑定
            def update_config(cubism_path, output_dir, gpu_enabled, selected_model):
                try:
                    # 解析选中的模型
                    selected_model_id = None
                    selected_model_provider = None
                    
                    # 从选择的显示文本中找到对应的模型ID
                    for model_id, model_info in AVAILABLE_MODELS.items():
                        display_text = f"{model_info['name']} ({model_info['size']}) - {model_info['description']}"
                        if display_text == selected_model:
                            selected_model_id = model_id
                            selected_model_provider = model_info['provider']
                            break
                    
                    # 更新配置
                    self.config['cubism']['executable_path'] = cubism_path
                    self.config['io']['output_dir'] = output_dir
                    self.config['misc']['gpu']['enabled'] = gpu_enabled
                    
                    # 如果找到了选择的模型，更新模型设置
                    if selected_model_id and selected_model_provider:
                        self.config['character']['model'] = selected_model_id
                        self.config['character']['provider'] = selected_model_provider
                    
                    # 保存配置
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(self.config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    
                    # 重新加载配置
                    self.config = load_config(self.config_path)
                    
                    return "配置已更新"
                except Exception as e:
                    return f"更新配置时出错: {str(e)}"
                
            def download_selected_model(selected_model):
                try:
                    # 从选择的显示文本中找到对应的模型ID
                    selected_model_id = None
                    for model_id, model_info in AVAILABLE_MODELS.items():
                        display_text = f"{model_info['name']} ({model_info['size']}) - {model_info['description']}"
                        if display_text == selected_model:
                            selected_model_id = model_id
                            break
                    
                    if not selected_model_id:
                        return "错误：无法识别选择的模型"
                    
                    # 启动下载
                    full_model_info = AVAILABLE_MODELS[selected_model_id]
                    
                    # 创建状态消息
                    status_msg = f"开始下载模型: {full_model_info['name']} ({full_model_info['size']})...\n"
                    status_msg += "这可能需要一些时间，请耐心等待...\n"
                    yield status_msg
                    
                    # 在单独的线程中下载模型
                    result = {"success": False, "message": ""}
                    
                    def download_thread():
                        try:
                            success = CharacterGenerator.download_model(selected_model_id)
                            result["success"] = success
                            if success:
                                result["message"] = f"✅ 模型 {full_model_info['name']} 下载完成！"
                            else:
                                result["message"] = f"❌ 模型下载失败，请检查网络连接或手动下载。"
                        except Exception as e:
                            result["success"] = False
                            result["message"] = f"下载过程中出错: {str(e)}"
                    
                    # 启动下载线程
                    import threading
                    thread = threading.Thread(target=download_thread)
                    thread.daemon = True
                    thread.start()
                    
                    # 等待下载完成（每秒更新状态）
                    for i in range(600):  # 最多等待10分钟
                        if not thread.is_alive():
                            break
                        dots = "." * ((i % 3) + 1)
                        spaces = " " * (3 - ((i % 3) + 1))
                        current_status = f"{status_msg}\n下载中{dots}{spaces}"
                        yield current_status
                        time.sleep(1)
                    
                    # 检查线程是否还活着
                    if thread.is_alive():
                        return f"{status_msg}\n⚠️ 下载时间过长，但仍在继续。请检查模型下载缓存目录。"
                    
                    return f"{status_msg}\n{result['message']}"
                
                except Exception as e:
                    return f"下载模型时出错: {str(e)}"
            
            # 绑定模型选择和下载功能
            download_model_btn.click(
                fn=download_selected_model,
                inputs=[model_dropdown],
                outputs=[model_download_status]
            )
            
            # 绑定配置更新
            update_config_btn.click(
                fn=update_config,
                inputs=[cubism_path_input, output_dir_input, gpu_enabled_input, model_dropdown],
                outputs=[config_status_output]
            )
            
            # 绑定模型下载功能（在快速生成标签页）
            download_model_btn_quick.click(
                fn=download_selected_model,
                inputs=[model_selection],
                outputs=[download_status_quick]
            )
            
            # 绑定帮助按钮功能
            def toggle_help(visibility):
                return gr.update(visible=not visibility)
            
            help_btn.click(
                fn=toggle_help,
                inputs=[help_markdown],
                outputs=[help_markdown]
            )
            
            # 更新参数绑定
            create_btn.click(
                fn=self.run_full_process,
                inputs=[
                    character_image_input, prompt_input, negative_prompt_input, 
                    model_selection, style_dropdown, pose_dropdown, resolution_dropdown,
                    samples_slider, seed_number, segm_model_input, 
                    segm_quality_input, parts_input, physics_input, export_format_input
                ],
                outputs=[status_output, progress_output, export_path_output, layers_preview_output]
            )
            
            def open_output_folder():
                try:
                    # 获取输出目录的绝对路径
                    abs_path = os.path.abspath(self.output_dir)
                    
                    # 根据操作系统打开文件夹
                    if os.name == 'nt':  # Windows
                        os.startfile(abs_path)
                    elif os.name == 'posix':  # macOS 或 Linux
                        if sys.platform == 'darwin':  # macOS
                            os.system(f'open "{abs_path}"')
                        else:  # Linux
                            os.system(f'xdg-open "{abs_path}"')
                    
                    return
                except Exception as e:
                    logger.error(f"打开输出文件夹时出错: {str(e)}")
            
            open_folder_btn.click(
                fn=open_output_folder,
                inputs=None,
                outputs=None
            )
        
        # 启动服务器
        interface.launch(
            share=share, 
            inbrowser=inbrowser, 
            server_port=server_port,
            prevent_thread_lock=True
        )


def launch_gui(config_path: str = 'config.yml', share: bool = False, inbrowser: bool = True, server_port: int = 7860):
    """启动GUI的便捷函数
    
    Args:
        config_path: 配置文件路径
        share: 是否公开分享
        inbrowser: 是否在浏览器中打开
        server_port: 服务器端口
    """
    gui = Live2DGUI(config_path)
    gui.launch_gui(share, inbrowser, server_port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="启动Live2D AI Generator的图形用户界面")
    parser.add_argument("--config", type=str, default="config.yml", help="配置文件路径")
    parser.add_argument("--share", action="store_true", help="创建公开可访问的链接")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--port", type=int, default=7860, help="服务器端口")
    
    args = parser.parse_args()
    
    launch_gui(
        config_path=args.config,
        share=args.share,
        inbrowser=not args.no_browser,
        server_port=args.port
    ) 