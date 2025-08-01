from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import time

class MessagePool:
    """消息池管理类"""
    def __init__(self):
        self.messages = {}  # 存储消息 {id: {user_id, user_name, message, timestamp}}
        self.banned_users = set()  # 被封禁的用户
        self.next_id = 1  # 消息编号从1开始
    
    def add_message(self, user_id, user_name, message):
        """添加消息到消息池"""
        # 检查用户是否被封禁
        if user_id in self.banned_users:
            return None  # 被封禁用户不能添加消息
        
        # 生成唯一编号
        message_id = self.next_id
        self.next_id += 1
        
        # 存储消息
        self.messages[message_id] = {
            'user_id': user_id,
            'user_name': user_name,
            'message': message,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return message_id
    
    def get_message(self, message_id):
        """根据编号获取消息"""
        return self.messages.get(message_id)
    
    def remove_message(self, message_id):
        """从消息池中移除消息"""
        if message_id in self.messages:
            del self.messages[message_id]
    
    def ban_user(self, user_id):
        """封禁用户"""
        self.banned_users.add(user_id)
    
    def unban_user(self, user_id):
        """解封用户"""
        if user_id in self.banned_users:
            self.banned_users.remove(user_id)
    
    def is_banned(self, user_id):
        """检查用户是否被封禁"""
        return user_id in self.banned_users
    
    def get_all_message_ids(self):
        """获取所有消息编号"""
        return list(self.messages.keys())
    
    def clear_all(self):
        """清空消息池"""
        self.messages.clear()
        self.banned_users.clear()
        self.next_id = 1

@register("astrbot_plugin_transfer_to_human", "YourName", "QQ机器人转人工插件，实现用户与管理员之间的消息传递", "1.0.0", "https://github.com/yourname/astrbot_plugin_transfer_to_human")
class TransferToHumanPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.message_pool = MessagePool()
        logger.info("转人工插件已加载")
    
    @filter.command("转人工")
    async def transfer_to_human(self, event: AstrMessageEvent):
        """处理用户转人工请求"""
        # 检查是否为私聊
        if not event.is_private_chat():
            yield event.plain_result("该功能只能在私聊中使用")
            return
        
        # 获取用户信息
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        # 检查用户是否被封禁
        if self.message_pool.is_banned(user_id):
            yield event.plain_result("您已被管理员封禁，无法使用此功能")
            return
        
        # 获取消息内容
        message_content = event.message_str.strip()
        if message_content == "/转人工" or message_content == "/转人工 ":
            yield event.plain_result("请输入完整指令，格式：/转人工 <消息内容>")
            return
        
        # 移除指令前缀
        if message_content.startswith("/转人工 "):
            message_content = message_content[6:].strip()
        
        # 添加消息到消息池
        message_id = self.message_pool.add_message(user_id, user_name, message_content)
        
        # 检查消息是否添加成功
        if message_id is None:
            yield event.plain_result("消息发送失败，您可能已被管理员封禁")
            return
        
        # 构造发送给管理员的消息
        admin_message = f"用户【{user_name}】【{user_id}】【{message_id}】传话啦！！！\n【内容】{message_content}\n【时间】{time.strftime('%Y-%m-%d %H:%M:%S')}"
        # 这里需要实现发送给管理员的逻辑，暂时用日志代替
        logger.info(f"发送给管理员的消息: {admin_message}")
        
        # 回复用户
        yield event.plain_result("消息已发送给管理员，请耐心等待回复")
    
    @filter.command("回复")
    async def reply_to_user(self, event: AstrMessageEvent):
        """处理管理员回复用户"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 检查是否为私聊
        if not event.is_private_chat():
            yield event.plain_result("该功能只能在私聊中使用")
            return
        
        # 获取指令内容
        command_content = event.message_str.strip()
        if command_content == "/回复" or command_content == "/回复 ":
            yield event.plain_result("请输入完整指令，格式：/回复 <编号> <回复内容>")
            return
        
        # 解析指令参数
        parts = command_content.split(" ", 2)
        if len(parts) < 3:
            yield event.plain_result("请输入完整指令，格式：/回复 <编号> <回复内容>")
            return
        
        try:
            message_id = int(parts[1])
            reply_content = parts[2]
        except ValueError:
            yield event.plain_result("编号必须是数字，请重新输入")
            return
        
        # 获取原始消息
        original_message = self.message_pool.get_message(message_id)
        if not original_message:
            yield event.plain_result(f"未找到编号为 {message_id} 的消息")
            return
        
        # 发送回复给用户
        # 这里需要实现发送给用户的逻辑，暂时用日志代替
        user_reply = f"管理员回消息啦！！\n【内容】{reply_content}\n【时间】{time.strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(f"发送给用户 {original_message['user_name']}({original_message['user_id']}) 的回复: {user_reply}")
        
        # 从消息池中移除已回复的消息
        self.message_pool.remove_message(message_id)
        
        # 回复管理员
        yield event.plain_result(f"已回复给用户【{original_message['user_name']}】，消息已从消息池中移除")
    
    @filter.command("封禁")
    async def ban_user(self, event: AstrMessageEvent):
        """管理员封禁用户"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 获取指令内容
        command_content = event.message_str.strip()
        if command_content == "/封禁" or command_content == "/封禁 ":
            yield event.plain_result("请输入完整指令，格式：/封禁 <QQ号>")
            return
        
        # 解析QQ号
        parts = command_content.split(" ", 1)
        if len(parts) < 2:
            yield event.plain_result("请输入完整指令，格式：/封禁 <QQ号>")
            return
        
        try:
            target_user_id = parts[1]
            # 封禁用户
            self.message_pool.ban_user(target_user_id)
            yield event.plain_result(f"用户 {target_user_id} 已被封禁")
        except Exception as e:
            logger.error(f"封禁用户失败: {str(e)}")
            yield event.plain_result("封禁用户失败，请查看日志")
    
    @filter.command("解封")
    async def unban_user(self, event: AstrMessageEvent):
        """管理员解封用户"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 获取指令内容
        command_content = event.message_str.strip()
        if command_content == "/解封" or command_content == "/解封 ":
            yield event.plain_result("请输入完整指令，格式：/解封 <QQ号>")
            return
        
        # 解析QQ号
        parts = command_content.split(" ", 1)
        if len(parts) < 2:
            yield event.plain_result("请输入完整指令，格式：/解封 <QQ号>")
            return
        
        try:
            target_user_id = parts[1]
            # 解封用户
            self.message_pool.unban_user(target_user_id)
            yield event.plain_result(f"用户 {target_user_id} 已被解封")
        except Exception as e:
            logger.error(f"解封用户失败: {str(e)}")
            yield event.plain_result("解封用户失败，请查看日志")
    
    @filter.command("查看消息池")
    async def view_message_pool(self, event: AstrMessageEvent):
        """管理员查看消息池"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 获取所有消息编号
        message_ids = self.message_pool.get_all_message_ids()
        
        if not message_ids:
            yield event.plain_result("消息池为空")
            return
        
        # 格式化输出
        result = "消息池中的消息编号：\n" + "\n".join([str(mid) for mid in message_ids])
        yield event.plain_result(result)
    
    @filter.command("查看消息")
    async def view_message(self, event: AstrMessageEvent):
        """管理员查看具体消息"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 获取指令内容
        command_content = event.message_str.strip()
        if command_content == "/查看消息" or command_content == "/查看消息 ":
            yield event.plain_result("请输入完整指令，格式：/查看消息 <编号>")
            return
        
        # 解析编号
        parts = command_content.split(" ", 1)
        if len(parts) < 2:
            yield event.plain_result("请输入完整指令，格式：/查看消息 <编号>")
            return
        
        try:
            message_id = int(parts[1])
        except ValueError:
            yield event.plain_result("编号必须是数字，请重新输入")
            return
        
        # 获取消息
        message = self.message_pool.get_message(message_id)
        if not message:
            yield event.plain_result(f"未找到编号为 {message_id} 的消息")
            return
        
        # 格式化输出
        result = f"用户【{message['user_name']}】【{message['user_id']}】【{message_id}】传话啦！！！\n【内容】{message['message']}\n【时间】{message['timestamp']}"
        yield event.plain_result(result)
    
    @filter.command("清理内存")
    async def clear_memory(self, event: AstrMessageEvent):
        """管理员清理内存"""
        # 检查是否为管理员
        if not event.is_admin():
            yield event.plain_result("这是机器人管理员专属指令")
            return
        
        # 清理消息池
        self.message_pool.clear_all()
        yield event.plain_result("消息池已清空")
    
    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("转人工插件已卸载")