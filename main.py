from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os
import datetime
import random

from .database import SignDatabase
from .image_generator import ImageGenerator
from .sign_manager import SignManager

@register("astrbot_plugin_advanced_sign", "XiaoJie", "一个高级签到插件，包含等级系统、排行榜、商店系统", "1.0.0", "https://github.com/XiaoJie/astrbot_plugin_advanced_sign")
class AdvancedSignPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db = SignDatabase(os.path.dirname(__file__))
        self.img_gen = ImageGenerator(os.path.dirname(__file__))
        
    @filter.command("签到")
    async def sign(self, event: AstrMessageEvent):
        '''每日签到'''
        try:
            user_id = event.get_sender_id()
            group_id = event.get_group_id() if event.message_obj.group_id else None
            today = datetime.date.today().strftime('%Y-%m-%d')
            
            user_data = self.db.get_user_data(user_id)
            
            if user_data and user_data.get('last_sign') == today:
                image_path = await self.img_gen.create_sign_image("今天已经签到过啦~")
                if image_path:
                    yield event.image_result(image_path)
                    if os.path.exists(image_path):
                        os.remove(image_path)
                return

            # 执行签到逻辑
            result = SignManager.daily_sign(user_data, group_id)
            
            # 更新用户数据
            self.db.update_user_data(
                user_id,
                group_id=group_id,
                total_days=result['total_days'],
                last_sign=today,
                continuous_days=result['continuous_days'],
                exp=result['exp'],
                coins=result['coins'],
                level=result['level'],
                next_level_exp=result['next_level_exp']
            )

            # 存储用户昵称
            user_name = event.get_sender_name()
            self.db.update_user_name(user_id, user_name, group_id)
            
            # 记录签到历史
            self.db.log_sign(user_id, result['exp'], result['coins'])
            
            # 生成结果消息
            result_text = SignManager.format_sign_result(result)

            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"签到失败: {str(e)}")
            yield event.plain_result("签到失败了~请联系管理员检查日志")
            
    @filter.command("个人信息")
    async def user_info(self, event: AstrMessageEvent):
        '''查看个人信息'''
        try:
            user_id = event.get_sender_id()
            group_id = event.get_group_id() if event.message_obj.group_id else None
            
            user_data = self.db.get_user_data(user_id)
            if not user_data:
                yield event.plain_result("您还没有签到过哦~")
                return
                
            result_text = SignManager.format_user_info(user_data)
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"获取个人信息失败: {str(e)}")
            yield event.plain_result("获取个人信息失败~请联系管理员检查日志")
            

    @filter.command("连续签到排行榜")
    async def continuous_ranking(self, event: AstrMessageEvent):
        '''连续签到排行榜'''
        try:
            group_id = event.get_group_id() if event.message_obj.group_id else None
            
            ranking_data = self.db.get_continuous_sign_ranking(10)
            result_text = SignManager.format_continuous_ranking(ranking_data)
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"获取连续签到排行榜失败: {str(e)}")
            yield event.plain_result("获取连续签到排行榜失败~请联系管理员检查日志")
            
    @filter.command("等级排行榜")
    async def level_ranking(self, event: AstrMessageEvent):
        '''等级排行榜'''
        try:
            group_id = event.get_group_id() if event.message_obj.group_id else None
            
            ranking_data = self.db.get_level_ranking(10)
            result_text = SignManager.format_level_ranking(ranking_data)
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"获取等级排行榜失败: {str(e)}")
            yield event.plain_result("获取等级排行榜失败~请联系管理员检查日志")
            
    @filter.command("世界排行榜")
    async def world_ranking(self, event: AstrMessageEvent):
        '''世界总签到排行榜'''
        try:
            ranking_data = self.db.get_world_sign_ranking(10)
            result_text = SignManager.format_world_ranking(ranking_data)
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"获取世界排行榜失败: {str(e)}")
            yield event.plain_result("获取世界排行榜失败~请联系管理员检查日志")
            
    @filter.command("购买")
    async def buy_item(self, event: AstrMessageEvent):
        '''购买物品'''
        try:
            user_id = event.get_sender_id()
            args = event.message_str.split()[1:]
            
            if len(args) < 2:
                yield event.plain_result("命令格式错误，请使用: /购买 补签卡 数量")
                return
                
            item_name = args[0]
            try:
                quantity = int(args[1])
            except ValueError:
                yield event.plain_result("数量必须是数字")
                return
                
            if item_name != "补签卡":
                yield event.plain_result("目前只能购买补签卡")
                return
                
            # 执行购买逻辑
            result = SignManager.buy_item(user_id, item_name, quantity, self.db)
            
            if result['success']:
                yield event.plain_result(f"购买成功！花费了{result['cost']}金币，获得了{quantity}张补签卡")
            else:
                yield event.plain_result(f"购买失败：{result['message']}")

        except Exception as e:
            logger.error(f"购买物品失败: {str(e)}")
            yield event.plain_result("购买物品失败~请联系管理员检查日志")
            
    @filter.command("补签")
    async def resign(self, event: AstrMessageEvent):
        '''补签'''
        try:
            user_id = event.get_sender_id()
            group_id = event.get_group_id() if event.message_obj.group_id else None
            args = event.message_str.split()[1:]
            
            try:
                days = int(args[0]) if args else 1
            except ValueError:
                yield event.plain_result("补签天数必须是数字")
                return
                
            # 执行补签逻辑
            result = SignManager.resign(user_id, days, group_id, self.db)
            
            if result['success']:
                yield event.plain_result(f"补签成功！消耗了{result['cost']}张补签卡和{result['coins']}金币")
            else:
                yield event.plain_result(f"补签失败：{result['message']}")

        except Exception as e:
            logger.error(f"补签失败: {str(e)}")
            yield event.plain_result("补签失败~请联系管理员检查日志")
            
    @filter.command("查看背包")
    async def view_inventory(self, event: AstrMessageEvent):
        '''查看背包'''
        try:
            user_id = event.get_sender_id()
            
            inventory = self.db.get_user_inventory(user_id)
            result_text = SignManager.format_inventory(inventory)
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"查看背包失败: {str(e)}")
            yield event.plain_result("查看背包失败~请联系管理员检查日志")
            
    @filter.command("签到商店")
    async def sign_shop(self, event: AstrMessageEvent):
        '''签到商店'''
        try:
            # 显示商店商品信息
            shop_items = [
                ("补签卡", 100, "用于补签，每次补签消耗1张补签卡和10金币"),
            ]
            
            result_text = "签到商店\n"
            result_text += "=" * 20 + "\n"
            for item_name, price, description in shop_items:
                result_text += f"{item_name} - {price}金币\n{description}\n\n"
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"查看签到商店失败: {str(e)}")
            yield event.plain_result("查看签到商店失败~请联系管理员检查日志")
            
    @filter.command("我的排名")
    async def my_ranking(self, event: AstrMessageEvent):
        '''显示自己在世界排行榜、连续签到排行榜和等级排行榜的排名'''
        try:
            user_id = event.get_sender_id()
            group_id = event.get_group_id() if event.message_obj.group_id else None
            
            # 获取用户数据
            user_data = self.db.get_user_data(user_id)
            if not user_data:
                yield event.plain_result("您还没有签到过哦~")
                return
                
            # 获取各项排名（使用修复后的方法）
            world_total_rank = self.db.get_world_sign_rank(user_id)
            continuous_rank = self.db.get_continuous_sign_rank(user_id)
            
            # 获取等级排名
            self.db.cursor.execute('''
                SELECT COUNT(*) + 1 FROM sign_data
                WHERE level > ? OR (level = ? AND exp > ?)
            ''', (user_data['level'], user_data['level'], user_data['exp']))
            level_rank_row = self.db.cursor.fetchone()
            level_rank = level_rank_row[0] if level_rank_row else 1
            
            # 格式化结果
            result_text = SignManager.format_my_ranking(
                world_total_rank=world_total_rank,
                continuous_rank=continuous_rank,
                level_rank=level_rank
            )
            
            image_path = await self.img_gen.create_sign_image(result_text)
            if image_path:
                yield event.image_result(image_path)
                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            logger.error(f"获取我的排名失败: {str(e)}")
            yield event.plain_result("获取我的排名失败~请联系管理员检查日志")