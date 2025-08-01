from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os

class MessagePool:
    def __init__(self, plugin_dir: str):
        self.messages = []  # 存储消息的列表
        self.banned_users = set()  # 存储被封禁用户的集合
        self.plugin_dir = plugin_dir
        
    def add_message(self, user_id: str, message: str) -> int:
        """添加消息到消息池，返回消息ID或None（如果用户被封禁）"""
        if user_id in self.banned_users:
            return None  # 被封禁用户不能添加消息
        message_id = len(self.messages)
        self.messages.append({
            "id": message_id,
            "user_id": user_id,
            "message": message,
            "replied": False
        })
        return message_id
        
    def get_messages(self) -> list:
        """获取所有消息"""
        return self.messages
        
    def get_message_by_id(self, message_id: int) -> dict:
        """根据ID获取消息"""
        if 0 <= message_id < len(self.messages):
            return self.messages[message_id]
        return None
        
    def mark_as_replied(self, message_id: int):
        """标记消息为已回复"""
        if 0 <= message_id < len(self.messages):
            self.messages[message_id]["replied"] = True
            
    def ban_user(self, user_id: str):
        """封禁用户"""
        self.banned_users.add(user_id)
        
    def unban_user(self, user_id: str):
        """解封用户"""
        self.banned_users.discard(user_id)
        
    def is_banned(self, user_id: str) -> bool:
        """检查用户是否被封禁"""
        return user_id in self.banned_users
        
    def get_banned_users(self) -> set:
        """获取所有被封禁的用户"""
        return self.banned_users.copy()
        
    def clear(self):
        """清空消息池和封禁列表"""
        self.messages.clear()
        self.banned_users.clear()


@register("zrg", "Soulter", "一个转人工插件，用户可以发送消息给管理员，管理员可以回复用户消息", "1.0.0", "https://github.com/Soulter/AstrBot")
class TransferToHumanPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 使用os.path.dirname(__file__)获取插件目录，而不是context.data_path
        plugin_dir = os.path.dirname(__file__)
        self.message_pool = MessagePool(plugin_dir)
        self.admin_users = set()  # 管理员用户集合
        
        # 添加默认管理员（可以根据需要修改）
        # self.admin_users.add("admin_user_id")
        
    def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        return user_id in self.admin_users
        
    @filter.command("转人工")
    @filter.command("/transfer")
    async def transfer_to_human(self, event: AstrMessageEvent):
        """用户请求转人工服务"""
        user_id = event.get_sender_id()
        message_content = event.get_message_str()
        
        # 检查用户是否被封禁
        if self.message_pool.is_banned(user_id):
            yield event.plain_result("您已被管理员封禁，无法发送消息。")
            return
            
        # 提取消息内容（去除命令前缀）
        if message_content.startswith("转人工"):
            content = message_content[3:].strip()
        elif message_content.startswith("/transfer"):
            content = message_content[9:].strip()
        else:
            content = message_content
            
        # 添加消息到消息池
        message_id = self.message_pool.add_message(user_id, content)
        
        # 检查消息是否添加成功
        if message_id is None:
            yield event.plain_result("消息发送失败，您可能已被管理员封禁。")
            return
            
        # 通知用户消息已发送
        yield event.plain_result(f"您的消息已发送给管理员，消息编号：{message_id}")
        
    @filter.command("/回复")
    async def admin_reply(self, event: AstrMessageEvent):
        """管理员回复用户消息"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        message_content = event.get_message_str()
        
        # 解析命令参数
        parts = message_content.split(" ", 2)
        if len(parts) < 3:
            yield event.plain_result("命令格式错误。使用方法：/回复 <消息编号> <回复内容>")
            return
            
        try:
            message_id = int(parts[1])
            reply_content = parts[2]
        except ValueError:
            yield event.plain_result("消息编号必须是数字。")
            return
            
        # 获取消息
        message = self.message_pool.get_message_by_id(message_id)
        if not message:
            yield event.plain_result("未找到指定的消息编号。")
            return
            
        # 标记消息为已回复
        self.message_pool.mark_as_replied(message_id)
        
        # 发送回复给用户
        # 这里需要使用AstrBot的API发送私聊消息
        # 由于API限制，我们暂时只能通知管理员回复已记录
        yield event.plain_result(f"已记录对消息#{message_id}的回复：{reply_content}\n注意：实际发送给用户的功能需要额外实现。")
        
    @filter.command("/封禁")
    async def ban_user(self, event: AstrMessageEvent):
        """封禁用户"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        message_content = event.get_message_str()
        parts = message_content.split(" ", 1)
        
        if len(parts) < 2:
            yield event.plain_result("命令格式错误。使用方法：/封禁 <用户ID>")
            return
            
        target_user_id = parts[1]
        self.message_pool.ban_user(target_user_id)
        yield event.plain_result(f"用户 {target_user_id} 已被封禁。")
        
    @filter.command("/解封")
    async def unban_user(self, event: AstrMessageEvent):
        """解封用户"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        message_content = event.get_message_str()
        parts = message_content.split(" ", 1)
        
        if len(parts) < 2:
            yield event.plain_result("命令格式错误。使用方法：/解封 <用户ID>")
            return
            
        target_user_id = parts[1]
        self.message_pool.unban_user(target_user_id)
        yield event.plain_result(f"用户 {target_user_id} 已被解封。")
        
    @filter.command("/查看消息池")
    async def view_message_pool(self, event: AstrMessageEvent):
        """查看消息池中的所有消息"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        messages = self.message_pool.get_messages()
        if not messages:
            yield event.plain_result("消息池为空。")
            return
            
        result = "消息池中的消息：\n"
        for msg in messages:
            status = "已回复" if msg["replied"] else "未回复"
            result += f"#{msg['id']} 用户{msg['user_id']}: {msg['message']} [{status}]\n"
            
        yield event.plain_result(result)
        
    @filter.command("/查看消息")
    async def view_message(self, event: AstrMessageEvent):
        """查看特定消息"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        message_content = event.get_message_str()
        parts = message_content.split(" ", 1)
        
        if len(parts) < 2:
            yield event.plain_result("命令格式错误。使用方法：/查看消息 <消息编号>")
            return
            
        try:
            message_id = int(parts[1])
        except ValueError:
            yield event.plain_result("消息编号必须是数字。")
            return
            
        message = self.message_pool.get_message_by_id(message_id)
        if not message:
            yield event.plain_result("未找到指定的消息编号。")
            return
            
        status = "已回复" if message["replied"] else "未回复"
        result = f"消息#{message_id}\n用户: {message['user_id']}\n内容: {message['message']}\n状态: {status}"
        yield event.plain_result(result)
        
    @filter.command("/清理内存")
    async def clear_memory(self, event: AstrMessageEvent):
        """清理消息池和封禁列表"""
        user_id = event.get_sender_id()
        
        # 检查权限
        if not self.is_admin(user_id):
            yield event.plain_result("您没有权限执行此操作。")
            return
            
        self.message_pool.clear()
        yield event.plain_result("消息池和封禁列表已清空。")