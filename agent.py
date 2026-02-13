"""
Agent基类模块 - 定义Agent的基本属性和行为

核心功能：
1. Agent - Agent基类
2. AgentState - Agent状态管理
3. 上下文窗口管理
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from abc import ABC, abstractmethod
import threading
import uuid

from .message import Message, MessageType, Mailbox


class AgentState(Enum):
    """Agent状态枚举"""
    IDLE = "idle"  # 空闲
    WORKING = "working"  # 工作中
    WAITING = "waiting"  # 等待中
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 错误状态


class AgentRole(Enum):
    """Agent角色枚举"""
    TEAM_LEAD = "team_lead"  # 团队领导
    TEAMMATE = "teammate"  # 队友
    COORDINATOR = "coordinator"  # 协调者


@dataclass
class ContextWindow:
    """
    上下文窗口 - Agent的记忆和工作空间
    
    每个Agent都有独立的上下文窗口，用于存储：
    1. 对话历史
    2. 工作记忆
    3. 项目上下文
    """
    max_tokens: int = 4096
    messages: List[Dict[str, Any]] = field(default_factory=list)
    working_memory: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str):
        """添加消息到上下文"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_recent_messages(self, n: int = 10) -> List[Dict[str, Any]]:
        """获取最近n条消息"""
        return self.messages[-n:]
    
    def set_memory(self, key: str, value: Any):
        """设置工作记忆"""
        self.working_memory[key] = value
    
    def get_memory(self, key: str) -> Optional[Any]:
        """获取工作记忆"""
        return self.working_memory.get(key)
    
    def clear(self):
        """清空上下文"""
        self.messages.clear()
        self.working_memory.clear()


class Agent(ABC):
    """
    Agent基类 - 所有Agent的抽象基类
    
    核心属性：
        agent_id: Agent唯一标识
        name: Agent名称
        role: Agent角色
        state: 当前状态
        mailbox: 邮箱
        context: 上下文窗口
        prompt: 系统提示词
    
    核心方法：
        start(): 启动Agent
        stop(): 停止Agent
        process_message(): 处理消息（抽象方法）
        execute_task(): 执行任务（抽象方法）
    """
    
    def __init__(
        self,
        name: str,
        role: AgentRole = AgentRole.TEAMMATE,
        prompt: str = "",
        agent_id: Optional[str] = None
    ):
        """
        初始化Agent
        
        Args:
            name: Agent名称
            role: Agent角色
            prompt: 系统提示词
            agent_id: Agent ID（可选，自动生成）
        """
        self.agent_id = agent_id or f"{name}@{str(uuid.uuid4())[:8]}"
        self.name = name
        self.role = role
        self.prompt = prompt
        self.state = AgentState.IDLE
        
        # 核心组件
        self.context = ContextWindow()
        self.mailbox: Optional[Mailbox] = None
        
        # 线程控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 回调函数
        self._on_message_received: Optional[Callable] = None
        self._on_state_changed: Optional[Callable] = None
        self._on_task_completed: Optional[Callable] = None
    
    def set_mailbox(self, mailbox: Mailbox):
        """设置邮箱"""
        self.mailbox = mailbox
        # 注册空闲通知处理器
        self.mailbox.register_handler(
            MessageType.IDLE_NOTIFICATION,
            self._handle_idle_notification
        )
    
    def set_state(self, new_state: AgentState):
        """设置Agent状态"""
        old_state = self.state
        self.state = new_state
        if self._on_state_changed and old_state != new_state:
            self._on_state_changed(self, old_state, new_state)
    
    def send_message(
        self,
        recipient_id: str,
        content: str,
        msg_type: MessageType = MessageType.MESSAGE,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        发送消息
        
        Args:
            recipient_id: 接收者ID
            content: 消息内容
            msg_type: 消息类型
            summary: 消息摘要
            metadata: 元数据
            
        Returns:
            创建的消息对象
        """
        message = Message(
            msg_type=msg_type,
            sender=self.agent_id,
            recipient=recipient_id,
            content=content,
            summary=summary or content[:50],
            metadata=metadata or {}
        )
        
        # 添加到上下文
        self.context.add_message("sent", content)
        
        return message
    
    def send_idle_notification(self, reason: str = "available"):
        """发送空闲通知"""
        notification = Message(
            msg_type=MessageType.IDLE_NOTIFICATION,
            sender=self.agent_id,
            content=f"空闲通知: {reason}",
            metadata={"idleReason": reason}
        )
        return notification
    
    def _handle_idle_notification(self, message: Message):
        """处理空闲通知"""
        # 子类可以重写此方法
        pass
    
    def receive_message(self, message: Message):
        """
        接收消息
        
        Args:
            message: 接收到的消息
        """
        if self.mailbox:
            self.mailbox.receive(message)
        
        # 添加到上下文
        self.context.add_message("received", message.content)
        
        # 触发回调
        if self._on_message_received:
            self._on_message_received(self, message)
    
    def read_messages(self) -> List[Message]:
        """读取所有未读消息"""
        if self.mailbox:
            messages = self.mailbox.get_unread()
            for msg in messages:
                msg.mark_read()
            return messages
        return []
    
    @abstractmethod
    def process_message(self, message: Message) -> Optional[Message]:
        """
        处理消息 - 子类必须实现
        
        Args:
            message: 要处理的消息
            
        Returns:
            可选的回复消息
        """
        pass
    
    @abstractmethod
    def execute_task(self, task: Any) -> Any:
        """
        执行任务 - 子类必须实现
        
        Args:
            task: 要执行的任务
            
        Returns:
            任务执行结果
        """
        pass
    
    def start(self):
        """启动Agent"""
        if self._running:
            return
        
        self._running = True
        self.set_state(AgentState.IDLE)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止Agent"""
        self._running = False
        self.set_state(AgentState.STOPPED)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
    
    def _run_loop(self):
        """Agent主循环"""
        while self._running:
            try:
                # 检查是否有新消息
                messages = self.read_messages()
                for message in messages:
                    self.process_message(message)
                
                # 短暂休眠
                threading.Event().wait(0.1)
                
            except Exception as e:
                self.set_state(AgentState.ERROR)
                print(f"Agent {self.name} 发生错误: {e}")
    
    def on_message_received(self, callback: Callable):
        """设置消息接收回调"""
        self._on_message_received = callback
    
    def on_state_changed(self, callback: Callable):
        """设置状态变化回调"""
        self._on_state_changed = callback
    
    def on_task_completed(self, callback: Callable):
        """设置任务完成回调"""
        self._on_task_completed = callback
    
    def __str__(self) -> str:
        return f"Agent({self.name}, {self.role.value}, {self.state.value})"
    
    def __repr__(self) -> str:
        return self.__str__()
