import sqlite3
import random
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import At
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from astrbot.core.star import StarTools  # 确保导入 StarTools
from astrbot.api import logger

# 导入各个功能模块
from .pet_system import PetSystem, PET_TYPES
from .battle_system import BattleSystem
from .shop_system import ShopSystem
from .image_generator import ImageGenerator

@register(
    "群宠物养成插件",
    "YourName",
    "一个简单的群内宠物养成插件，支持随机领养、属性克制、进化系统、状态卡、PVE与PVP对战等功能。",
    "1.0.0",
    "https://github.com/yourname/astrbot_plugin_pet"
)
class PetPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # --- 修复：使用 StarTools 获取数据目录 ---
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_pet")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建一个用于存放临时状态图的缓存目录
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 假设 assets 文件夹与插件目录同级
        self.assets_dir = Path(__file__).parent / "assets"
        self.db_path = self.data_dir / "pets.db"
        
        # 初始化各个系统
        self.pet_system = PetSystem(self)
        self.battle_system = BattleSystem(self)
        self.shop_system = ShopSystem(self)
        self.image_generator = ImageGenerator(self)
        
        # 初始化数据库
        self.pet_system._init_database()
        
        logger.info("群宠物养成插件已加载。")
        
    # --- 命令注册 ---
    @filter.command("领养宠物")
    async def adopt_pet(self, event: AstrMessageEvent, pet_name: str | None = None):
        async for result in self.pet_system.adopt_pet(event, pet_name):
            yield result
            
    @filter.command("我的宠物")
    async def my_pet_status(self, event: AstrMessageEvent):
        async for result in self.pet_system.my_pet_status(event):
            yield result
            
    @filter.command("宠物进化")
    async def evolve_pet(self, event: AstrMessageEvent):
        async for result in self.pet_system.evolve_pet(event):
            yield result
            
    @filter.command("散步")
    async def walk_pet(self, event: AstrMessageEvent):
        async for result in self.battle_system.walk_pet(event):
            yield result
            
    @filter.command("对决")
    async def duel_pet(self, event: AiocqhttpMessageEvent):
        async for result in self.battle_system.duel_pet(event):
            yield result
            
    @filter.command("宠物商店")
    async def shop(self, event: AstrMessageEvent):
        async for result in self.shop_system.shop(event):
            yield result
            
    @filter.command("宠物背包")
    async def backpack(self, event: AstrMessageEvent):
        async for result in self.shop_system.backpack(event):
            yield result
            
    @filter.command("购买")
    async def buy_item(self, event: AstrMessageEvent, item_name: str, quantity: int = 1):
        async for result in self.shop_system.buy_item(event, item_name, quantity):
            yield result
            
    @filter.command("投喂")
    async def feed_pet_item(self, event: AstrMessageEvent, item_name: str):
        async for result in self.shop_system.feed_pet_item(event, item_name):
            yield result
            
    @filter.command("宠物菜单")
    async def pet_menu(self, event: AstrMessageEvent):
        """显示所有可用的宠物插件命令。"""
        menu_text = """--- 🐾 宠物插件帮助菜单 🐾 ---

    【核心功能】
    /领养宠物 [宠物名字]
    功能：随机领养一只初始宠物（烈焰、碧波兽、莲莲草、碎裂岩、金刚）并为它命名。
    用法示例：/领养宠物 豆豆

    /我的宠物
    功能：以图片形式查看你当前宠物的详细状态。

    /宠物进化
    功能：当宠物达到指定等级时，让它进化成更强的形态（烈焰→炽焰龙、碧波兽→瀚海蛟、莲莲草→百草王、碎裂岩→岩脊守护者、金刚→破甲金刚）。

    /宠物背包
    功能：查看你拥有的所有物品和对应的数量。

    【冒险与对战】
    /散步
    功能：带宠物外出散步，可能会触发奇遇、获得奖励或遭遇野生宠物。

    /对决 @某人
    功能：与群内其他玩家的宠物进行一场1v1对决，有30分钟冷却时间。

    【商店与喂养】
    /宠物商店
    功能：查看所有可以购买的商品及其价格和效果。

    /购买 [物品名] [数量]
    功能：从商店购买指定数量的物品，数量为可选参数，默认为1。

    /投喂 [物品名]
    功能：从背包中使用食物来喂养你的宠物，恢复其状态。
    """
        yield event.plain_result(menu_text)

    async def terminate(self):
        """插件卸载/停用时调用。"""
        logger.info("群宠物养成插件已卸载。")