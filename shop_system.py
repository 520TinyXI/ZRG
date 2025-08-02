import sqlite3
import random
from datetime import datetime, timedelta

# --- 静态游戏数据定义 (商店) ---
SHOP_ITEMS = {
    "普通口粮": {"price": 10, "type": "food", "satiety": 20, "mood": 5, "description": "能快速填饱肚子的基础食物。"},
    "美味罐头": {"price": 30, "type": "food", "satiety": 50, "mood": 15, "description": "营养均衡，宠物非常爱吃。"},
    "心情饼干": {"price": 25, "type": "food", "satiety": 10, "mood": 30, "description": "能让宠物心情愉悦的神奇零食。"},
}

STAT_MAP = {
    "exp": "经验值",
    "mood": "心情值",
    "satiety": "饱食度"
}

class ShopSystem:
    def __init__(self, plugin):
        self.plugin = plugin
        self.db_path = plugin.db_path
        
    async def shop(self, event: AstrMessageEvent):
        """显示宠物商店中可购买的物品列表。"""
        reply = "欢迎光临宠物商店！\n--------------------\n"
        for name, item in SHOP_ITEMS.items():
            reply += f"【{name}】 ${item['price']}\n效果: {item['description']}\n"
        reply += "--------------------\n使用 `/购买 [物品名] [数量]` 来购买。"
        yield event.plain_result(reply)
        
    async def backpack(self, event: AstrMessageEvent):
        """显示你的宠物背包中的物品。"""
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        if not self.plugin.pet_system._get_pet(user_id, group_id):
            yield event.plain_result("你还没有宠物，自然也没有背包啦。")
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND group_id = ?",
                           (int(user_id), int(group_id)))
            items = cursor.fetchall()

        if not items:
            yield event.plain_result("你的背包空空如也，去商店看看吧！")
            return

        reply = f"{event.get_sender_name()}的背包:\n--------------------\n"
        for item_name, quantity in items:
            reply += f"【{item_name}】 x {quantity}\n"
        yield event.plain_result(reply)
        
    async def buy_item(self, event: AstrMessageEvent, item_name: str, quantity: int = 1):
        """从商店购买物品"""
        user_id, group_id = event.get_sender_id(), event.get_group_id()

        if item_name not in SHOP_ITEMS:
            yield event.plain_result(f"商店里没有「{item_name}」这种东西。")
            return

        if not self.plugin.pet_system._get_pet(user_id, group_id):
            yield event.plain_result("你还没有宠物，无法购买物品。")
            return

        item_info = SHOP_ITEMS[item_name]
        total_cost = item_info['price'] * quantity

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE pets SET money = money - ? WHERE user_id = ? AND group_id = ? AND money >= ?",
                (total_cost, int(user_id), int(group_id), total_cost)
            )

            if cursor.rowcount == 0:
                yield event.plain_result(f"你的钱不够哦！购买 {quantity} 个「{item_name}」需要 ${total_cost}。")
                return

            cursor.execute("""
                    INSERT INTO inventory (user_id, group_id, item_name, quantity) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, group_id, item_name) 
                    DO UPDATE SET quantity = quantity + excluded.quantity
                """, (int(user_id), int(group_id), item_name, quantity))

            conn.commit()

        yield event.plain_result(f"购买成功！你花费 ${total_cost} 购买了 {quantity} 个「{item_name}」。")
        
    async def feed_pet_item(self, event: AstrMessageEvent, item_name: str):
        """从背包中使用食物投喂宠物"""
        user_id, group_id = event.get_sender_id(), event.get_group_id()
        pet = self.plugin.pet_system._get_pet(user_id, group_id)
        if not pet:
            yield event.plain_result("你还没有宠物，不能进行投喂哦。")
            return

        if item_name not in SHOP_ITEMS or SHOP_ITEMS[item_name].get('type') != 'food':
            yield event.plain_result(f"「{item_name}」不是可以投喂的食物。")
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND group_id = ? AND item_name = ? AND quantity > 0",
                (int(user_id), int(group_id), item_name)
            )

            if cursor.rowcount == 0:
                yield event.plain_result(f"你的背包里没有「{item_name}」。")
                return

            item_info = SHOP_ITEMS[item_name]
            satiety_gain = item_info.get('satiety', 0)
            mood_gain = item_info.get('mood', 0)

            cursor.execute(
                "UPDATE pets SET satiety = MIN(100, satiety + ?), mood = MIN(100, mood + ?) WHERE user_id = ? AND group_id = ?",
                (satiety_gain, mood_gain, int(user_id), int(group_id))
            )

            cursor.execute(
                "DELETE FROM inventory WHERE user_id = ? AND group_id = ? AND item_name = ? AND quantity <= 0",
                (int(user_id), int(group_id), item_name))

            conn.commit()

        satiety_chinese = STAT_MAP.get('satiety', '饱食度')
        mood_chinese = STAT_MAP.get('mood', '心情值')
        yield event.plain_result(
            f"你给「{pet['pet_name']}」投喂了「{item_name}」，它的{satiety_chinese}增加了 {satiety_gain}，{mood_chinese}增加了 {mood_gain}！")