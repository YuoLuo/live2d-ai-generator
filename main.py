#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Live2D AI Generator - 自动化生成Live2D模型的工具
作者: AI助手
版本: 1.0.0
"""

import os
import yaml
import argparse
import logging
from pathlib import Path
from tqdm import tqdm
import time

# 导入各个模块
from modules.character_gen import CharacterGenerator
from modules.layer_separator import LayerSeparator
from modules.cubism_automation import CubismAutomation
from modules.parameters_gen import ParametersGenerator
from modules.exporter import ModelExporter

def setup_logging(config):
    """设置日志系统"""
    try:
        # 首先尝试从misc配置中获取logging配置
        log_config = config['misc']['logging']
    except (KeyError, TypeError):
        # 如果找不到，则直接从根配置获取
        log_config = config.get('logging')
        if not log_config:
            # 如果仍然找不到，使用默认配置
            log_config = {
                'level': 'INFO',
                'file': './logs/app.log'
            }
    
    log_dir = os.path.dirname(log_config['file'])
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=getattr(logging, log_config['level']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_config['file']),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('live2d_generator')

def ensure_directories(config):
    """确保所有必要的目录都存在"""
    dirs = [
        config['export']['output_dir'],
        config['misc']['temp_dir'],
        os.path.join(config['export']['output_dir'], 'character'),
        os.path.join(config['export']['output_dir'], 'layers'),
        os.path.join(config['export']['output_dir'], 'model')
    ]
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

def load_config(config_path='config.yml'):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def main():
    """主函数，协调整个流程"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Live2D AI Generator')
    parser.add_argument('--config', type=str, default='config.yml', help='配置文件路径')
    parser.add_argument('--skip-character', action='store_true', help='跳过角色生成阶段')
    parser.add_argument('--skip-layer', action='store_true', help='跳过图层分割阶段')
    parser.add_argument('--skip-cubism', action='store_true', help='跳过Cubism自动化阶段')
    parser.add_argument('--skip-parameters', action='store_true', help='跳过参数生成阶段')
    parser.add_argument('--skip-export', action='store_true', help='跳过导出阶段')
    parser.add_argument('--character-image', type=str, help='使用现有的角色图像')
    parser.add_argument('--layer-dir', type=str, help='使用现有的图层目录')
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 设置日志
    logger = setup_logging(config)
    logger.info("Live2D AI Generator启动")
    
    # 确保目录存在
    ensure_directories(config)
    
    # 初始化计时器
    start_time = time.time()
    
    # 1. 角色生成
    character_path = None
    if not args.skip_character:
        logger.info("开始角色生成阶段...")
        character_generator = CharacterGenerator(config)
        if args.character_image:
            character_path = args.character_image
            logger.info(f"使用现有的角色图像: {character_path}")
        else:
            character_path = character_generator.generate()
            logger.info(f"角色生成完成，保存至: {character_path}")
    else:
        logger.info("跳过角色生成阶段")
        if args.character_image:
            character_path = args.character_image
        
    # 2. 图层分割
    layers_dir = None
    if not args.skip_layer and character_path:
        logger.info("开始图层分割阶段...")
        layer_separator = LayerSeparator(config)
        if args.layer_dir:
            layers_dir = args.layer_dir
            logger.info(f"使用现有的图层目录: {layers_dir}")
        else:
            layers_dir = layer_separator.separate(character_path)
            logger.info(f"图层分割完成，保存至: {layers_dir}")
    else:
        logger.info("跳过图层分割阶段")
        if args.layer_dir:
            layers_dir = args.layer_dir
    
    # 3. Cubism自动化
    cubism_project = None
    if not args.skip_cubism and layers_dir:
        logger.info("开始Cubism自动化阶段...")
        cubism_automation = CubismAutomation(config)
        cubism_project = cubism_automation.automate(layers_dir)
        logger.info(f"Cubism自动化完成，项目保存至: {cubism_project}")
    else:
        logger.info("跳过Cubism自动化阶段")
    
    # 4. 参数生成
    if not args.skip_parameters and cubism_project:
        logger.info("开始参数生成阶段...")
        parameters_generator = ParametersGenerator(config)
        parameters_generator.generate(cubism_project)
        logger.info("参数生成完成")
    else:
        logger.info("跳过参数生成阶段")
    
    # 5. 导出
    if not args.skip_export and cubism_project:
        logger.info("开始导出阶段...")
        exporter = ModelExporter(config)
        export_path = exporter.export(cubism_project)
        logger.info(f"导出完成，模型保存至: {export_path}")
    else:
        logger.info("跳过导出阶段")
    
    # 计算总耗时
    total_time = time.time() - start_time
    logger.info(f"整个流程完成，总耗时: {total_time:.2f}秒")
    logger.info(f"请在{config['export']['output_dir']}目录查看生成的文件")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"发生错误: {str(e)}", exc_info=True)
        raise 