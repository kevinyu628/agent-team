"""
消息系统模块 - 实现Agent之间的通信机制

核心功能：
1. Message - 消息类，支持多种消息类型
2. Mailbox - 邮箱系统，每个Agent都有独立的收件箱
3. 消息自动传递机制，无需轮询
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import threading
import uuid


class MessageType(Enum):
    """消息类型枚举"""
    MESSAGE = "message"  # 普通消息，点对点发送
    BROADCAST = "broadcast"  # 广播消息，发给所有队友
    IDLE_NOTIFICATION = "idle_notification"  # 空闲通知，队友完成任务后自动发送
    TASK_ASSIGNMENT = "task_assignment"  # 任务分配通知
    TASK_UPDATE = "task_update"  # 任务状态更新通知
    QUESTION = "question"  # 提问消息
    ANSWER = "answer"  # 回答消息
    REPORT = "report"  # 汇报消息


@dataclass
class Message:
    """
    消息类 - Agent之间通信的基本单位
    
    属性：
        msg_id: 消息唯一标识
        msg_type: 消息类型
        sender: 发送者ID
        recipient: 接收者ID
        content: 消息内容
        summary: 消息摘要（用于快速预览）
        timestamp: 时间戳
        read: 是否已读
        metadata: 额外元数据
    """
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    msg_type: MessageType = MessageType.MESSAGE
    sender: str = ""
    recipient: str = ""
    content: str = ""
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """将消息转换为字典格式"""
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "read": self.read,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息对象"""
        return cls(
            msg_id=data.get("msg_id", str(uuid.uuid4())[:8]),
            msg_type=MessageType(data.get("msg_type", "message")),
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            read=data.get("read", False),
            metadata=data.get("metadata", {})
        )
    
    def mark_read(self):
        """标记消息为已读"""
        self.read = True
    
    def __str__(self) -> str:
        """字符串表示"""
        status = "已读" if self.read else "未读"
        return f"[{self.msg_type.value}] {self.sender} -> {self.recipient}: {self.summary or self.content[:50]}... ({status})"


class Mailbox:
    """
    邮箱系统 - 管理Agent的消息收发
    
    核心特性：
    1. 每个Agent都有独立的收件箱
    2. 消息自动传递，无需轮询
    3. 支持消息持久化存储
    4. 线程安全
    """
    
    def __init__(self, owner_id: str, storage_path: Optional[Path] = None):
        """
        初始化邮箱
        
        Args:
            owner_id: 邮箱所有者的ID
            storage_path: 消息存储路径（可选）
        """
        self.owner_id = owner_id
        self.storage_path = storage_path
        self._inbox: List[Message] = []
        self._lock = threading.Lock()
        self._message_handlers: Dict[MessageType, List[callable]] = {}
        
        # 加载已存储的消息
        if storage_path and storage_path.exists():
            self._load_messages()
    
    def _load_messages(self):
        """从存储加载消息"""
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                messages_data = json.load(f)
                for msg_data in messages_data:
                    self._inbox.append(Message.from_dict(msg_data))
        except (json.JSONDecodeError, FileNotFoundError):
            self._inbox = []
    
    def _save_messages(self):
        """保存消息到存储"""
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([msg.to_dict() for msg in self._inbox], f, ensure_ascii=False, indent=2)
    
    def receive(self, message: Message):
        """
        接收消息 - 消息自动传递时调用
        
        Args:
            message: 接收到的消息
        """
        with self._lock:
            message.recipient = self.owner_id
            self._inbox.append(message)
            self._save_messages()
            
            # 触发消息处理器
            handlers = self._message_handlers.get(message.msg_type, [])
            for handler in handlers:
                try:
                    handler(message)
                except Exception as e:
                    print(f"消息处理器执行错误: {e}")
    
    def send(self, message: Message, recipient_mailbox: "Mailbox"):
        """
        发送消息到指定邮箱
        
        Args:
            message: 要发送的消息
            recipient_mailbox: 接收者的邮箱
        """
        message.sender = self.owner_id
        recipient_mailbox.receive(message)
    
    def get_unread(self) -> List[Message]:
        """获取所有未读消息"""
        with self._lock:
            return [msg for msg in self._inbox if not msg.read]
    
    def get_all(self) -> List[Message]:
        """获取所有消息"""
        with self._lock:
            return list(self._inbox)
    
    def get_by_type(self, msg_type: MessageType) -> List[Message]:
        """获取指定类型的消息"""
        with self._lock:
            return [msg for msg in self._inbox if msg.msg_type == msg_type]
    
    def get_by_sender(self, sender_id: str) -> List[Message]:
        """获取来自指定发送者的消息"""
        with self._lock:
            return [msg for msg in self._inbox if msg.sender == sender_id]
    
    def mark_all_read(self):
        """标记所有消息为已读"""
        with self._lock:
            for msg in self._inbox:
                msg.mark_read()
            self._save_messages()
    
    def register_handler(self, msg_type: MessageType, handler: callable):
        """
        注册消息处理器
        
        Args:
            msg_type: 消息类型
            handler: 处理函数，接收Message参数
        """
        if msg_type not in self._message_handlers:
            self._message_handlers[msg_type] = []
        self._message_handlers[msg_type].append(handler)
    
    def clear(self):
        """清空邮箱"""
        with self._lock:
            self._inbox.clear()
            self._save_messages()
    
    def __len__(self) -> int:
        return len(self._inbox)
    
    def __str__(self) -> str:
        unread = len(self.get_unread())
        return f"Mailbox({self.owner_id}): {len(self._inbox)}条消息, {unread}条未读"


class MessageBus:
    """
    消息总线 - 管理团队中所有Agent的邮箱
    
    核心功能：
    1. 注册和管理Agent邮箱
    2. 实现消息路由
    3. 支持广播消息
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """
        初始化消息总线
        
        Args:
            storage_dir: 消息存储目录
        """
        self.storage_dir = storage_dir
        self._mailboxes: Dict[str, Mailbox] = {}
        self._lock = threading.Lock()
    
    def register(self, agent_id: str) -> Mailbox:
        """
        为Agent注册邮箱
        
        Args:
            agent_id: Agent ID
            
        Returns:
            注册的邮箱实例
        """
        with self._lock:
            if agent_id not in self._mailboxes:
                storage_path = None
                if self.storage_dir:
                    storage_path = self.storage_dir / f"{agent_id}.json"
                self._mailboxes[agent_id] = Mailbox(agent_id, storage_path)
            return self._mailboxes[agent_id]
    
    def unregister(self, agent_id: str):
        """注销Agent邮箱"""
        with self._lock:
            if agent_id in self._mailboxes:
                del self._mailboxes[agent_id]
    
    def get_mailbox(self, agent_id: str) -> Optional[Mailbox]:
        """获取Agent的邮箱"""
        return self._mailboxes.get(agent_id)
    
    def send(self, message: Message, recipient_id: str) -> bool:
        """
        发送消息到指定Agent
        
        Args:
            message: 消息
            recipient_id: 接收者ID
            
        Returns:
            是否发送成功
        """
        mailbox = self._mailboxes.get(recipient_id)
        if mailbox:
            mailbox.receive(message)
            return True
        return False
    
    def broadcast(self, message: Message, exclude_sender: bool = True):
        """
        广播消息给所有Agent
        
        Args:
            message: 消息
            exclude_sender: 是否排除发送者
        """
        broadcast_msg = Message(
            msg_type=MessageType.BROADCAST,
            sender=message.sender,
            content=message.content,
            summary=message.summary
        )
        
        for agent_id, mailbox in self._mailboxes.items():
            if exclude_sender and agent_id == message.sender:
                continue
            mailbox.receive(broadcast_msg)
    
    def get_all_agents(self) -> List[str]:
        """获取所有注册的Agent ID"""
        return list(self._mailboxes.keys())
