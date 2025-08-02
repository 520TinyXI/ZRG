import sqlite3
import random
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from astrbot.api import logger

# 引入宠物类型数据
from .pet_system import PET_TYPES

class ImageGenerator:
    def __init__(self, plugin):
        self.plugin = plugin
        self.data_dir = plugin.data_dir
        self.assets_dir = plugin.assets_dir
        self.cache_dir = plugin.cache_dir
        
    def _get_pet_image_filename(self, pet_type: str, evolution_stage: int) -> str:
        """根据宠物类型和进化阶段返回对应的图片文件名"""
        # 定义宠物类型到图片文件名的映射
        pet_image_mapping = {
            "碧波兽": "WaterSprite_1.png",
            "瀚海蛟": "WaterSprite_2.png",
            "烈焰": "FirePup_1.png",
            "炽焰龙": "FirePup_2.png",
            "莲莲草": "LeafyCat_1.png",
            "百草王": "LeafyCat_2.png",
            "碎裂岩": "cataclastic_rock_1.png",
            "岩脊守护者": "cataclastic_rock_2.png",
            "金刚": "King_Kong_1.png",
            "破甲金刚": "King_Kong_2.png"
        }
        
        # 获取进化信息
        pet_type_info = PET_TYPES.get(pet_type, {})
        evolutions = pet_type_info.get('evolutions', {})
        evo_info = evolutions.get(evolution_stage, {})
        evo_name = evo_info.get('name', pet_type)  # 如果没有找到进化名称，则使用宠物类型名称
        
        # 返回对应的图片文件名，如果找不到则返回默认图片
        return pet_image_mapping.get(evo_name, "background.png")
        
    def _generate_pet_status_image(self, pet_data: dict, sender_name: str) -> Path | str:
        """
        根据宠物数据生成一张状态图并保存为文件。
        成功则返回文件路径(Path)，失败则返回错误信息字符串(str)。
        """
        try:
            # 创建默认素材目录
            assets_dir = self.assets_dir
            if not assets_dir.exists():
                assets_dir.mkdir(parents=True, exist_ok=True)
                
            # 创建默认背景和字体文件（如果不存在）
            bg_path = assets_dir / "background.png"
            font_path = assets_dir / "font.ttf"
            
            # 如果素材文件不存在，创建简单的默认文件
            if not bg_path.exists():
                # 创建默认背景
                bg_img = Image.new('RGB', (800, 600), color=(70, 130, 180))
                bg_img.save(bg_path, format='PNG')
                
            if not font_path.exists():
                # 使用默认字体
                font_path = None
            
            W, H = 800, 600
            img = Image.open(bg_path).resize((W, H))
            draw = ImageDraw.Draw(img)
            
            # 尝试使用指定字体，如果失败则使用默认字体
            try:
                if font_path and font_path.exists():
                    font_title = ImageFont.truetype(str(font_path), 40)
                    font_text = ImageFont.truetype(str(font_path), 28)
                else:
                    font_title = ImageFont.load_default()
                    font_text = ImageFont.load_default()
            except:
                font_title = ImageFont.load_default()
                font_text = ImageFont.load_default()

            pet_type_info = PET_TYPES[pet_data['pet_type']]
            evo_info = pet_type_info['evolutions'][pet_data['evolution_stage']]
            
            # 加载宠物图片
            pet_image_filename = self._get_pet_image_filename(pet_data['pet_type'], pet_data['evolution_stage'])
            pet_image_path = self.assets_dir / pet_image_filename
            if pet_image_path.exists():
                pet_img = Image.open(pet_image_path).resize((200, 200))
                img.paste(pet_img, (100, 150))
            
            # 绘制宠物信息
            draw.text((W / 2, 50), f"{pet_data['pet_name']}的状态", font=font_title, fill="white", anchor="mt")
            draw.text((400, 150), f"主人: {sender_name}", font=font_text, fill="white")
            draw.text((400, 200), f"种族: {evo_info['name']} ({pet_data['pet_type']})", font=font_text, fill="white")
            draw.text((400, 250), f"等级: Lv.{pet_data['level']}", font=font_text, fill="white")

            # 经验条
            exp_for_level = self.plugin.pet_system._exp_for_next_level(pet_data['level'])
            exp_ratio = min(1.0, pet_data['exp'] / exp_for_level) if exp_for_level > 0 else 0
            draw.text((400, 300), f"经验: {pet_data['exp']} / {exp_for_level}", font=font_text, fill="white")
            draw.rectangle([400, 340, 750, 360], outline="white", fill="gray")
            draw.rectangle([400, 340, 400 + 350 * exp_ratio, 360], fill="#66ccff")

            # 属性值
            draw.text((400, 390), f"攻击: {pet_data['attack']}", font=font_text, fill="white")
            draw.text((600, 390), f"防御: {pet_data['defense']}", font=font_text, fill="white")
            draw.text((400, 440), f"心情: {pet_data['mood']}/100", font=font_text, fill="white")
            draw.text((600, 440), f"饱食度: {pet_data['satiety']}/100", font=font_text, fill="white")

            # 金钱
            draw.text((400, 490), f"金钱: ${pet_data.get('money', 0)}", font=font_text, fill="#FFD700")

            # 将图片保存到缓存文件夹
            output_path = self.cache_dir / f"status_{pet_data['group_id']}_{pet_data['user_id']}.png"
            img.save(output_path, format='PNG')
            return output_path

        except Exception as e:
            logger.error(f"生成状态图时发生未知错误: {e}")
            return f"生成状态图时发生未知错误: {e}"