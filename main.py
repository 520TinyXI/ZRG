import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain

# 消息存储结构
class UserMessage:
    def __init__(self, user_id: str, nickname: str, content: str, timestamp: str):
        self.user_id = user_id
        self.nickname = nickname
        self.content = content
        self.timestamp = timestamp

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            user_id=data["user_id"],
            nickname=data["nickname"],
            content=data["content"],
            timestamp=data["timestamp"]
        )

# 插件主类
@register("human_transfer", "AstrBot开发者", "机器人转人工插件", "1.0.0")
class HumanTransferPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.message_pool: Dict[int, UserMessage] = {}  # 消息池，编号->消息
        self.banned_users = set()  # 被封禁的用户QQ号
        self.next_id = 1  # 下一个可用的消息编号
        
        # 创建数据存储目录
        self.data_dir = os.path.join(self.context.get_data_path(), "human_transfer")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 加载保存的数据
        self._load_data()

    def _get_data_path(self, filename: str) -> str:
        """获取数据文件完整路径"""
        return os.path.join(self.data_dir, filename)
    
    def _load_data(self):
        """从文件加载数据"""
        try:
            # 加载消息池
            msg_pool_path = self._get_data_path("message_pool.json")
            if os.path.exists(msg_pool_path):
                with open(msg_pool_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.message_pool = {
                        int(k): UserMessage.from_dict(v) 
                        for k, v in data["message_pool"].items()
                    }
                    self.next_id = data["next_id"]
            
            # 加载封禁列表
            banned_path = self._get_data_path("banned_users.json")
            if os.path.exists(banned_path):
                with open(banned_path, "r", encoding="utf-8") as f:
                    self.banned_users = set(json.load(f))
        except Exception as e:
            logger.error(f"加载数据失败: {str(e)}")
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            # 保存消息池
            msg_pool_path = self._get_data_path("message_pool.json")
            with open(msg_pool_path, "w", encoding="utf-8") as f:
                json.dump({
                    "message_pool": {
                        k: v.to_dict() 
                        for k, v in self.message_pool.items()
                    },
                    "next_id": self.next_id
                }, f, ensure_ascii=False, indent=2)
            
            # 保存封禁列表
            banned_path = self._get_data_path("banned_users.json")
            with open(banned_path, "w", encoding="utf-8") as f:
                json.dump(list(self.banned_users), f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存数据失败: {str(e)}")

    # 用户转人工指令
    @filter.command("转人工")
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def transfer_to_human(self, event: AstrMessageEvent, *args):
        # 检查用户是否被封禁
        user_id = event.get_sender_id()
        if user_id in self.banned_users:
            yield event.plain_result("您已被管理员封禁，无法使用转人工服务")
            return
        
        # 检查参数是否完整
        if not args:
            yield event.plain_result("请提供需要转达的内容，格式：/转人工 你好")
            return
        
        # 获取用户信息
        nickname = event.get_sender_name()
        content = " ".join(args)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 创建消息对象并存储
        msg_id = self.next_id
        self.message_pool[msg_id] = UserMessage(user_id, nickname, content, timestamp)
        self.next_id += 1
        self._save_data()
        
        # 通知管理员
        admin_msg = (
            f"用户【{nickname}】【{user_id}】【{msg_id}】传话啦！！！\n"
            f"内容：{content}\n"
            f"时间：{timestamp}"
        )
        await self._notify_admin(admin_msg)
        
        yield event.plain_result(f"您的消息已转达给管理员，编号：{msg_id}")

    # 管理员回复指令
    @filter.command("回复")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def admin_reply(self, event: AstrMessageEvent, msg_id: str, *args):
        # 检查参数
        if not msg_id.isdigit() or not args:
            yield event.plain_result("格式错误，正确格式：/回复 编号 内容")
            return
        
        msg_id = int(msg_id)
        content = " ".join(args)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 查找消息
        if msg_id not in self.message_pool:
            yield event.plain_result(f"找不到编号为 {msg_id} 的消息")
            return
        
        # 获取原始消息
        user_msg = self.message_pool[msg_id]
        
        # 通知用户
        user_msg_content = (
            f"管理员回消息啦！！\n"
            f"内容：{content}\n"
            f"时间：{timestamp}"
        )
        await self.context.send_message(
            self._get_unified_msg_origin(user_msg.user_id),
            [Plain(user_msg_content)]
        )
        
        # 删除消息并保存
        del self.message_pool[msg_id]
        self._save_data()
        yield event.plain_result(f"已回复用户【{user_msg.nickname}】")

    # 管理员封禁指令
    @filter.command("封禁")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def ban_user(self, event: AstrMessageEvent, user_id: str):
        if not user_id.isdigit():
            yield event.plain_result("QQ号格式错误")
            return
            
        self.banned_users.add(user_id)
        self._save_data()
        yield event.plain_result(f"已封禁用户 {user_id}")

    # 管理员解封指令
    @filter.command("解封")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def unban_user(self, event: AstrMessageEvent, user_id: str):
        if not user_id.isdigit():
            yield event.plain_result("QQ号格式错误")
            return
            
        if user_id in self.banned_users:
            self.banned_users.remove(user_id)
            self._save_data()
            yield event.plain_result(f"已解封用户 {user_id}")
        else:
            yield event.plain_result(f"用户 {user_id} 未被封禁")

    # 查看消息池指令
    @filter.command("查看消息池")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def list_messages(self, event: AstrMessageEvent):
        if not self.message_pool:
            yield event.plain_result("当前没有待回复的消息")
            return
            
        msg_list = "\n".join([str(msg_id) for msg_id in self.message_pool.keys()])
        yield event.plain_result(f"待回复消息编号：\n{msg_list}")

    # 查看消息详情指令
    @filter.command("查看消息")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def view_message(self, event: AstrMessageEvent, msg_id: str):
        if not msg_id.isdigit():
            yield event.plain_result("消息编号格式错误")
            return
            
        msg_id = int(msg_id)
        if msg_id not in self.message_pool:
            yield event.plain_result(f"找不到编号为 {msg_id} 的消息")
            return
            
        user_msg = self.message_pool[msg_id]
        message_detail = (
            f"用户【{user_msg.nickname}】【{user_msg.user_id}】【{msg_id}】传话啦！！！\n"
            f"内容：{user_msg.content}\n"
            f"时间：{user_msg.timestamp}"
        )
        yield event.plain_result(message_detail)

    # 清理内存指令
    @filter.command("清理内存")
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def clear_memory(self, event: AstrMessageEvent):
        count = len(self.message_pool)
        self.message_pool.clear()
        self._save_data()
        yield event.plain_result(f"已清理所有缓存消息，共 {count} 条")

    # 管理员指令权限检查
    @filter.command("封禁", "解封", "查看消息池", "查看消息", "清理内存", prefix=False)
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def admin_command_permission(self, event: AstrMessageEvent):
        yield event.plain_result("这是管理员专属指令，您没有权限使用")

    # 通知管理员方法
    async def _notify_admin(self, message: str):
        # 获取所有管理员
        admins = self.context.get_config().get("admins", [])
        
        # 给每个管理员发送消息
        for admin_id in admins:
            await self.context.send_message(
                self._get_unified_msg_origin(admin_id), 
                [Plain(message)]
            )
    
    def _get_unified_msg_origin(self, user_id: str) -> str:
        """获取统一消息来源标识符"""
        return f"qq:{filter.EventMessageType.PRIVATE_MESSAGE}:{user_id}"

    # 插件终止时清理资源
    async def terminate(self):
        logger.info("转人工插件已终止，保存数据")
        self._save_data()
