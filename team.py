"""
团队管理模块 - 实现Team、TeamLead和Teammate

核心功能：
1. Team - 团队配置和管理
2. TeamLead - 团队领导，负责创建团队、生成队友和协调工作
3. Teammate - 队友，处理分配的任务并与其他队友协作
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import json
import threading
import time
import uuid

from .agent import Agent, AgentState, AgentRole, ContextWindow
from .message import Message, MessageType, Mailbox, MessageBus
from .task import Task, TaskStatus, TaskList, TaskPriority


@dataclass
class TeamConfig:
    """团队配置"""
    name: str
    description: str = ""
    lead_agent_id: str = ""
    members: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "leadAgentId": self.lead_agent_id,
            "members": self.members,
            "createdAt": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamConfig":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            lead_agent_id=data.get("leadAgentId", ""),
            members=data.get("members", []),
            created_at=data.get("createdAt", datetime.now().isoformat())
        )


class Team:
    """
    团队类 - 管理团队配置和成员
    
    核心功能：
    1. 创建和管理团队配置
    2. 管理团队成员
    3. 协调消息传递
    4. 任务列表管理
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        storage_dir: Optional[Path] = None
    ):
        """
        初始化团队
        
        Args:
            name: 团队名称
            description: 团队描述
            storage_dir: 存储目录
        """
        self.config = TeamConfig(name=name, description=description)
        self.storage_dir = storage_dir or Path.home() / ".agent_teams" / name
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心组件
        self.message_bus = MessageBus(self.storage_dir / "inboxes")
        self.task_list = TaskList(name, self.storage_dir / "tasks.json")
        
        # 成员管理
        self._members: Dict[str, Agent] = {}
        self._lead: Optional["TeamLead"] = None
        
        # 加载已保存的配置
        self._load_config()
    
    def _load_config(self):
        """加载团队配置"""
        config_path = self.storage_dir / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = TeamConfig.from_dict(data)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
    
    def _save_config(self):
        """保存团队配置"""
        config_path = self.storage_dir / "config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
    
    def set_lead(self, lead: "TeamLead"):
        """设置团队领导"""
        self._lead = lead
        self.config.lead_agent_id = lead.agent_id
        self._save_config()
        
        # 注册邮箱
        mailbox = self.message_bus.register(lead.agent_id)
        lead.set_mailbox(mailbox)
    
    def add_member(self, teammate: "Teammate"):
        """添加团队成员"""
        self._members[teammate.agent_id] = teammate
        
        # 注册成员信息
        member_info = {
            "agentId": teammate.agent_id,
            "name": teammate.name,
            "agentType": teammate.agent_type,
            "prompt": teammate.prompt,
            "color": teammate.color,
            "joinedAt": datetime.now().isoformat()
        }
        self.config.members.append(member_info)
        self._save_config()
        
        # 注册邮箱
        mailbox = self.message_bus.register(teammate.agent_id)
        teammate.set_mailbox(mailbox)
    
    def remove_member(self, agent_id: str):
        """移除团队成员"""
        if agent_id in self._members:
            del self._members[agent_id]
            self.message_bus.unregister(agent_id)
            
            # 更新配置
            self.config.members = [
                m for m in self.config.members if m.get("agentId") != agent_id
            ]
            self._save_config()
    
    def get_member(self, agent_id: str) -> Optional["Teammate"]:
        """获取成员"""
        return self._members.get(agent_id)
    
    def get_all_members(self) -> List["Teammate"]:
        """获取所有成员"""
        return list(self._members.values())
    
    def broadcast(self, message: Message, exclude: Optional[List[str]] = None):
        """广播消息给所有成员"""
        exclude = exclude or []
        for agent_id in list(self._members.keys()) + [self._lead.agent_id if self._lead else None]:
            if agent_id and agent_id not in exclude:
                self.message_bus.send(message, agent_id)
    
    def get_status(self) -> Dict[str, Any]:
        """获取团队状态"""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "lead": self._lead.name if self._lead else None,
            "members": len(self._members),
            "tasks": self.task_list.get_progress()
        }
    
    def shutdown(self):
        """关闭团队"""
        if self._lead:
            self._lead.stop()
        for member in self._members.values():
            member.stop()


class TeamLead(Agent):
    """
    团队领导 - 创建团队、生成队友和协调工作
    
    核心职责：
    1. 创建和管理任务
    2. 生成和分配队友
    3. 监控进度
    4. 汇总结果
    """
    
    def __init__(
        self,
        name: str = "team-lead",
        prompt: str = "",
        team: Optional[Team] = None
    ):
        super().__init__(
            name=name,
            role=AgentRole.TEAM_LEAD,
            prompt=prompt or self._default_prompt()
        )
        self.team = team
        self._teammates: Dict[str, "Teammate"] = {}
        self._pending_results: Dict[str, Any] = {}
    
    def _default_prompt(self) -> str:
        """默认系统提示"""
        return """你是团队领导，负责协调多个队友完成复杂任务。

你的职责：
1. 分析任务需求，创建子任务
2. 根据任务特点分配给合适的队友
3. 监控任务进度，及时处理问题
4. 汇总结果，输出最终报告

你应该：
- 合理分解任务，避免过于细碎
- 选择合适的队友处理对应任务
- 主动跟进进度，不要被动等待
- 整合队友反馈，做出决策
"""
    
    def set_team(self, team: Team):
        """设置管理的团队"""
        self.team = team
        team.set_lead(self)
    
    def create_task(
        self,
        subject: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None
    ) -> Task:
        """
        创建任务
        
        Args:
            subject: 任务主题
            description: 任务描述
            priority: 优先级
            dependencies: 依赖任务ID
            
        Returns:
            创建的任务
        """
        if not self.team:
            raise ValueError("未设置团队")
        
        task = self.team.task_list.create_task(
            subject=subject,
            description=description,
            priority=priority,
            dependencies=dependencies
        )
        
        # 记录到上下文
        self.context.add_message("system", f"创建任务: {task}")
        
        return task
    
    def create_teammate(
        self,
        name: str,
        agent_type: str,
        prompt: str,
        color: str = "blue"
    ) -> "Teammate":
        """
        创建队友
        
        Args:
            name: 队友名称
            agent_type: 队友类型
            prompt: 系统提示
            color: 颜色标识
            
        Returns:
            创建的队友
        """
        if not self.team:
            raise ValueError("未设置团队")
        
        teammate = Teammate(
            name=name,
            agent_type=agent_type,
            prompt=prompt,
            color=color
        )
        
        self.team.add_member(teammate)
        self._teammates[teammate.agent_id] = teammate
        
        return teammate
    
    def assign_task(self, task_id: str, teammate_id: str) -> bool:
        """
        分配任务给队友
        
        Args:
            task_id: 任务ID
            teammate_id: 队友ID
            
        Returns:
            是否分配成功
        """
        if not self.team:
            return False
        
        # 更新任务状态
        task = self.team.task_list.update_task(task_id, owner=teammate_id)
        if not task:
            return False
        
        # 发送任务分配通知
        message = self.send_message(
            recipient_id=teammate_id,
            content=f"任务分配: #{task_id} - {task.subject}\n\n{task.description}",
            msg_type=MessageType.TASK_ASSIGNMENT,
            summary=f"任务分配: {task.subject}",
            metadata={"task_id": task_id}
        )
        
        self.team.message_bus.send(message, teammate_id)
        
        return True
    
    def send_to_teammate(
        self,
        teammate_id: str,
        content: str,
        summary: str = ""
    ) -> bool:
        """
        发送消息给队友
        
        Args:
            teammate_id: 队友ID
            content: 消息内容
            summary: 消息摘要
            
        Returns:
            是否发送成功
        """
        if not self.team:
            return False
        
        message = self.send_message(
            recipient_id=teammate_id,
            content=content,
            summary=summary
        )
        
        return self.team.message_bus.send(message, teammate_id)
    
    def check_progress(self) -> Dict[str, Any]:
        """检查任务进度"""
        if not self.team:
            return {}
        
        progress = self.team.task_list.get_progress()
        in_progress = self.team.task_list.get_in_progress_tasks()
        
        # 检查是否有队友空闲但任务未更新
        for task in in_progress:
            teammate = self._teammates.get(task.owner)
            if teammate and teammate.state == AgentState.IDLE:
                # 发送提醒
                self.send_to_teammate(
                    task.owner,
                    f"你已完成任务，但任务 #{task.task_id} 尚未标记完成。请更新任务状态。",
                    "任务状态更新提醒"
                )
        
        return progress
    
    def wait_for_completion(self, timeout: float = 300) -> bool:
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否全部完成
        """
        if not self.team:
            return True
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            progress = self.team.task_list.get_progress()
            pending = progress.get("pending", 0) + progress.get("in_progress", 0) + progress.get("blocked", 0)
            
            if pending == 0:
                return True
            
            time.sleep(1)
        
        return False
    
    def generate_report(self) -> str:
        """生成汇总报告"""
        if not self.team:
            return "无团队数据"
        
        tasks = self.team.task_list.get_all_tasks()
        
        report = [f"\n=== 团队报告: {self.team.config.name} ==="]
        report.append(f"生成时间: {datetime.now().isoformat()}\n")
        
        # 任务统计
        progress = self.team.task_list.get_progress()
        report.append("## 任务统计")
        for status, count in progress.items():
            if count > 0:
                report.append(f"  - {status}: {count}")
        
        # 已完成任务详情
        completed = self.team.task_list.get_completed_tasks()
        if completed:
            report.append("\n## 已完成任务")
            for task in completed:
                report.append(f"  ✅ #{task.task_id} {task.subject}")
                if task.result:
                    report.append(f"     结果: {task.result[:100]}...")
        
        # 进行中任务
        in_progress = self.team.task_list.get_in_progress_tasks()
        if in_progress:
            report.append("\n## 进行中任务")
            for task in in_progress:
                report.append(f"  🔄 #{task.task_id} {task.subject} ({task.owner})")
        
        return "\n".join(report)
    
    def process_message(self, message: Message) -> Optional[Message]:
        """处理消息"""
        if message.msg_type == MessageType.IDLE_NOTIFICATION:
            # 队友空闲通知，检查是否有待分配任务
            available = self.team.task_list.get_available_tasks()
            if available:
                # 分配一个任务
                task = available[0]
                sender_name = message.sender.split("@")[0]
                self.assign_task(task.task_id, message.sender)
        
        elif message.msg_type == MessageType.REPORT:
            # 接收汇报，存储结果
            self._pending_results[message.sender] = message.content
        
        return None
    
    def execute_task(self, task: Any) -> Any:
        """执行任务（TeamLead主要负责任务协调，不直接执行）"""
        return self.generate_report()
    
    def ask_user(
        self,
        question: str,
        options: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        询问用户
        
        Args:
            question: 问题
            options: 选项列表 [{"label": "选项1", "description": "描述1"}, ...]
            
        Returns:
            用户选择
        """
        return {
            "question": question,
            "options": options or [],
            "type": "ask_user"
        }


class Teammate(Agent):
    """
    队友 - 处理分配的任务并与其他队友协作
    
    核心职责：
    1. 接收和处理任务
    2. 与其他队友协作
    3. 汇报进度和结果
    4. 发送空闲通知
    """
    
    def __init__(
        self,
        name: str,
        agent_type: str = "general-purpose",
        prompt: str = "",
        color: str = "blue"
    ):
        super().__init__(
            name=name,
            role=AgentRole.TEAMMATE,
            prompt=prompt
        )
        self.agent_type = agent_type
        self.color = color
        self.current_task: Optional[Task] = None
        self._task_list: Optional[TaskList] = None
        self._team: Optional[Team] = None
    
    def set_team(self, team: Team):
        """设置所属团队"""
        self._team = team
        self._task_list = team.task_list
    
    def claim_available_task(self) -> Optional[Task]:
        """
        认领可用任务
        
        Returns:
            认领的任务，如果没有可用任务则返回None
        """
        if not self._task_list:
            return None
        
        available = self._task_list.get_available_tasks()
        if not available:
            return None
        
        # 认领第一个可用任务
        task = self._task_list.claim_task(available[0].task_id, self.agent_id)
        if task:
            self.current_task = task
            self.set_state(AgentState.WORKING)
        
        return task
    
    def complete_task(self, result: str):
        """
        完成当前任务
        
        Args:
            result: 任务结果
        """
        if not self.current_task or not self._task_list:
            return
        
        # 更新任务状态
        self._task_list.update_task(
            self.current_task.task_id,
            status=TaskStatus.COMPLETED,
            result=result
        )
        
        self.current_task = None
        self.set_state(AgentState.IDLE)
    
    def report_to_lead(self, content: str, summary: str = ""):
        """
        向团队领导汇报
        
        Args:
            content: 汇报内容
            summary: 汇报摘要
        """
        if not self._team or not self._team._lead:
            return
        
        message = self.send_message(
            recipient_id=self._team._lead.agent_id,
            content=content,
            msg_type=MessageType.REPORT,
            summary=summary or content[:50]
        )
        
        self._team.message_bus.send(message, self._team._lead.agent_id)
    
    def send_to_teammate(
        self,
        teammate_id: str,
        content: str,
        summary: str = ""
    ) -> bool:
        """
        发送消息给其他队友
        
        Args:
            teammate_id: 队友ID
            content: 消息内容
            summary: 消息摘要
            
        Returns:
            是否发送成功
        """
        if not self._team:
            return False
        
        message = self.send_message(
            recipient_id=teammate_id,
            content=content,
            summary=summary
        )
        
        return self._team.message_bus.send(message, teammate_id)
    
    def send_idle_notification(self, reason: str = "available"):
        """发送空闲通知给团队领导"""
        if not self._team or not self._team._lead:
            return
        
        notification = Message(
            msg_type=MessageType.IDLE_NOTIFICATION,
            sender=self.agent_id,
            recipient=self._team._lead.agent_id,
            content=f"空闲通知: {reason}",
            metadata={"idleReason": reason}
        )
        
        self._team.message_bus.send(notification, self._team._lead.agent_id)
    
    def check_for_new_tasks(self) -> List[Task]:
        """检查是否有新任务可以认领"""
        if not self._task_list:
            return []
        return self._task_list.get_available_tasks()
    
    def process_message(self, message: Message) -> Optional[Message]:
        """处理消息"""
        if message.msg_type == MessageType.TASK_ASSIGNMENT:
            # 接收任务分配
            task_id = message.metadata.get("task_id")
            if task_id and self._task_list:
                task = self._task_list.get_task(task_id)
                if task:
                    self.current_task = task
                    self.set_state(AgentState.WORKING)
        
        elif message.msg_type == MessageType.QUESTION:
            # 处理问题
            # 子类可以重写此逻辑
            pass
        
        return None
    
    def execute_task(self, task: Task) -> str:
        """
        执行任务 - 子类应该重写此方法实现具体任务逻辑
        
        Args:
            task: 要执行的任务
            
        Returns:
            任务结果
        """
        # 默认实现：返回任务描述
        result = f"任务 {task.subject} 已处理"
        self.complete_task(result)
        return result
    
    def _handle_idle_notification(self, message: Message):
        """处理空闲通知（来自其他队友）"""
        # 队友通常不需要处理其他队友的空闲通知
        pass
