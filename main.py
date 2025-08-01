import time
import json
import os
import asyncio
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 存储结构
class AssistantStorage:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.banned_users = set()
        self.message_pool = {}
        self.current_id = 1
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        self.load_data()

    def save_data(self):
        """保存数据到文件"""
        data = {
            'banned_users': list(self.banned_users),
            'message_pool': self.message_pool,
            'current_id': self.current_id
        }
        with open(os.path.join(self.data_dir, 'assistant_data.json'), 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_data(self):
        """从文件加载数据"""
        try:
            path = os.path.join(self.data_dir, 'assistant_data.json')
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.banned_users = set(data.get('banned_users', []))
                    self.message_pool = data.get('message_pool', {})
                    self.current_id = data.get('current_id', 1)
        except Exception as e:
            logger.error(f"加载数据失败: {str(e)}")

    def add_message(self, user_id, user_name, content, unified_msg_origin):
        """添加消息到消息池"""
        msg_id = self.current_id
        self.current_id += 1
        
        message = {
            'user_id': user_id,
            'user_name': user_name,
            'content': content,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'unified_msg_origin': unified_msg_origin
        }
        
        self.message_pool[msg_id] = message
        self.save_data()
        return msg_id

    def get_message(self, msg_id):
        """获取指定ID的消息"""
        return self.message_pool.get(msg_id)

    def remove_message(self, msg_id):
        """移除指定ID的消息"""
        if msg_id in self.message_pool:
            del self.message_pool[msg_id]
            self.save_data()
            return True
        return False

    def clear_messages(self):
        """清空消息池"""
        self.message_pool = {}
        self.save_data()

    def ban_user(self, user_id):
        """封禁用户"""
        self.banned_users.add(user_id)
        self.save_data()

    def unban_user(self, user_id):
        """解封用户"""
        if user_id in self.banned_users:
            self.banned_users.remove(user_id)
            self.save_data()
            return True
        return False

    def is_banned(self, user_id):
        """检查用户是否被封禁"""
        return user_id in self.banned_users

    def get_all_message_ids(self):
        """获取所有消息ID"""
        return list(self.message_pool.keys())

@register("assistant", "开发者", "机器人转人工插件", "1.0.0")
class AssistantPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 创建数据存储目录
        data_dir = os.path.join(context.data_path, "plugins", "assistant")
        self.storage = AssistantStorage(data_dir)
        
        # 创建管理员通知任务
        asyncio.create_task(self.notify_admin_startup())

    async def notify_admin_startup(self):
        """插件启动时通知管理员"""
        await asyncio.sleep(5)  # 等待系统初始化完成
        logger.info("机器人转人工插件已启动")
    
    async def terminate(self):
        """插件终止时保存数据"""
        self.storage.save_data()
        logger.info("机器人转人工插件已终止")

    # 用户指令：转人工
    @filter.command("转人工")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def request_assistant(self, event: AstrMessageEvent, content: str = None):
        """用户请求转人工服务"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        # 检查是否被封禁
        if self.storage.is_banned(user_id):
            return event.plain_result("您已被封禁，无法使用转人工服务")
        
        # 检查内容是否为空
        if not content:
            return event.plain_result("请提供需要转达的内容，格式: /转人工 你好")
        
        # 添加消息到消息池
        msg_id = self.storage.add_message(
            user_id, 
            user_name, 
            content, 
            event.unified_msg_origin
        )
        
        # 通知管理员
        message = (
            f"用户【{user_name}】【{user_id}】【{msg_id}】传话啦！！！\n"
            f"内容: {content}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 获取所有管理员
        admins = self.context.get_config().get('admins', [])
        for admin_id in admins:
            await self.context.send_message(
                f"{event.platform_meta.name}:PRIVATE_MESSAGE:{admin_id}",
                [{"type": "plain", "text": message}]
            )
        
        return event.plain_result("您的消息已转达给管理员，请耐心等待回复")

    # 管理员指令：回复用户
    @filter.command("回复")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reply_to_user(self, event: AstrMessageEvent, msg_id: int, content: str):
        """管理员回复用户"""
        message = self.storage.get_message(msg_id)
        if not message:
            return event.plain_result(f"消息ID {msg_id} 不存在")
        
        # 发送回复给用户
        reply_msg = (
            f"管理员回消息啦！！\n"
            f"内容: {content}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await self.context.send_message(
            message['unified_msg_origin'],
            [{"type": "plain", "text": reply_msg}]
        )
        
        # 从消息池中移除
        self.storage.remove_message(msg_id)
        return event.plain_result("回复已发送")

    # 管理员指令：封禁用户
    @filter.command("封禁")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def ban_user(self, event: AstrMessageEvent, user_id: str):
        """封禁用户"""
        self.storage.ban_user(user_id)
        return event.plain_result(f"用户 {user_id} 已被封禁")

    # 管理员指令：解封用户
    @filter.command("解封")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def unban_user(self, event: AstrMessageEvent, user_id: str):
        """解封用户"""
        if self.storage.unban_user(user_id):
            return event.plain_result(f"用户 {user_id} 已解封")
        return event.plain_result(f"用户 {user_id} 不在封禁列表中")

    # 管理员指令：查看消息池
    @filter.command("查看消息池")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def list_messages(self, event: AstrMessageEvent):
        """列出所有待回复消息"""
        message_ids = self.storage.get_all_message_ids()
        if not message_ids:
            return event.plain_result("当前没有待回复消息")
        
        return event.plain_result(f"待回复消息ID: {', '.join(map(str, message_ids))}")

    # 管理员指令：查看消息详情
    @filter.command("查看消息")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def view_message(self, event: AstrMessageEvent, msg_id: int):
        """查看消息详情"""
        message = self.storage.get_message(msg_id)
        if not message:
            return event.plain_result(f"消息ID {msg_id} 不存在")
        
        msg_content = (
            f"用户【{message['user_name']}】【{message['user_id']}】【{msg_id}】传话啦！！！\n"
            f"内容: {message['content']}\n"
            f"时间: {message['time']}"
        )
        
        return event.plain_result(msg_content)

    # 管理员指令：清理内存
    @filter.command("清理内存")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def clear_memory(self, event: AstrMessageEvent):
        """清理消息池"""
        count = len(self.storage.message_pool)
        self.storage.clear_messages()
        return event.plain_result(f"已清理 {count} 条消息")
