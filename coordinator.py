"""
协调器模块 - 实现任务协调和调度

核心功能：
1. Coordinator - 协调器，管理任务分配和队友调度
2. 任务依赖解析
3. 自动任务分配
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import threading
import time

from .agent import Agent, AgentState, AgentRole
from .message import Message, MessageType
from .task import Task, TaskStatus, TaskList, TaskPriority
from .team import Team, TeamLead, Teammate


class Coordinator:
    """
    协调器 - 管理团队的任务分配和队友调度
    
    核心功能：
    1. 自动任务分配
    2. 任务依赖管理
    3. 队友状态监控
    4. 负载均衡
    """
    
    def __init__(self, team: Team):
        """
        初始化协调器
        
        Args:
            team: 要协调的团队
        """
        self.team = team
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 调度策略
        self._strategy = "round_robin"  # round_robin, priority, capability
        self._teammate_index = 0
        
        # 回调
        self._on_task_assigned: Optional[Callable] = None
        self._on_task_completed: Optional[Callable] = None
    
    def set_strategy(self, strategy: str):
        """
        设置调度策略
        
        Args:
            strategy: 策略名称 (round_robin, priority, capability)
        """
        self._strategy = strategy
    
    def start(self):
        """启动协调器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止协调器"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
    
    def _run_loop(self):
        """协调器主循环"""
        while self._running:
            try:
                # 检查待分配任务
                self._assign_pending_tasks()
                
                # 检查任务依赖
                self._check_dependencies()
                
                # 检查超时任务
                self._check_timeout_tasks()
                
                # 短暂休眠
                time.sleep(1)
                
            except Exception as e:
                print(f"协调器错误: {e}")
    
    def _assign_pending_tasks(self):
        """分配待处理任务"""
        available_tasks = self.team.task_list.get_available_tasks()
        if not available_tasks:
            return
        
        # 获取空闲队友
        idle_teammates = [
            t for t in self.team.get_all_members()
            if t.state == AgentState.IDLE and t.current_task is None
        ]
        
        if not idle_teammates:
            return
        
        # 根据策略分配任务
        for task in sorted(available_tasks, key=lambda t: t.priority.value, reverse=True):
            if not idle_teammates:
                break
            
            # 选择队友
            teammate = self._select_teammate(task, idle_teammates)
            if teammate:
                self.assign_task(task, teammate)
                idle_teammates.remove(teammate)
    
    def _select_teammate(self, task: Task, candidates: List[Teammate]) -> Optional[Teammate]:
        """
        根据策略选择队友
        
        Args:
            task: 任务
            candidates: 候选队友列表
            
        Returns:
            选中的队友
        """
        if not candidates:
            return None
        
        if self._strategy == "round_robin":
            # 轮询选择
            teammate = candidates[self._teammate_index % len(candidates)]
            self._teammate_index += 1
            return teammate
        
        elif self._strategy == "priority":
            # 选择当前任务最少的队友
            return min(candidates, key=lambda t: len(self.team.task_list.get_tasks_by_owner(t.agent_id)))
        
        elif self._strategy == "capability":
            # 根据能力匹配（简化实现：根据提示词匹配）
            task_keywords = task.subject.lower().split()
            for teammate in candidates:
                prompt_lower = teammate.prompt.lower()
                if any(kw in prompt_lower for kw in task_keywords):
                    return teammate
            # 没有匹配则随机选一个
            return candidates[0]
        
        return candidates[0]
    
    def assign_task(self, task: Task, teammate: Teammate) -> bool:
        """
        分配任务给队友
        
        Args:
            task: 任务
            teammate: 队友
            
        Returns:
            是否分配成功
        """
        if not self.team._lead:
            return False
        
        # 更新任务状态
        claimed = self.team.task_list.claim_task(task.task_id, teammate.agent_id)
        if not claimed:
            return False
        
        teammate.current_task = task
        teammate.set_state(AgentState.WORKING)
        
        # 发送任务分配消息
        message = Message(
            msg_type=MessageType.TASK_ASSIGNMENT,
            sender=self.team._lead.agent_id,
            recipient=teammate.agent_id,
            content=f"任务分配: #{task.task_id} - {task.subject}\n\n{task.description}",
            summary=f"任务分配: {task.subject}",
            metadata={"task_id": task.task_id}
        )
        
        self.team.message_bus.send(message, teammate.agent_id)
        
        # 触发回调
        if self._on_task_assigned:
            self._on_task_assigned(task, teammate)
        
        return True
    
    def _check_dependencies(self):
        """检查任务依赖并解除阻塞"""
        blocked_tasks = self.team.task_list.get_tasks_by_status(TaskStatus.BLOCKED)
        
        for task in blocked_tasks:
            # 检查所有依赖是否完成
            all_completed = True
            for dep_id in task.dependencies:
                dep_task = self.team.task_list.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_completed = False
                    break
            
            if all_completed:
                self.team.task_list.update_task(task.task_id, status=TaskStatus.PENDING)
    
    def _check_timeout_tasks(self):
        """检查超时任务"""
        in_progress = self.team.task_list.get_in_progress_tasks()
        timeout_seconds = 3600  # 1小时超时
        
        for task in in_progress:
            # 检查任务是否超时
            updated_time = datetime.fromisoformat(task.updated_at)
            elapsed = (datetime.now() - updated_time).total_seconds()
            
            if elapsed > timeout_seconds:
                # 标记为失败
                self.team.task_list.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    result="任务超时"
                )
                
                # 重置队友状态
                teammate = self.team.get_member(task.owner)
                if teammate:
                    teammate.current_task = None
                    teammate.set_state(AgentState.IDLE)
    
    def get_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        return {
            "running": self._running,
            "strategy": self._strategy,
            "available_tasks": len(self.team.task_list.get_available_tasks()),
            "idle_teammates": len([
                t for t in self.team.get_all_members()
                if t.state == AgentState.IDLE
            ]),
            "task_progress": self.team.task_list.get_progress()
        }
    
    def on_task_assigned(self, callback: Callable):
        """设置任务分配回调"""
        self._on_task_assigned = callback
    
    def on_task_completed(self, callback: Callable):
        """设置任务完成回调"""
        self._on_task_completed = callback


class DelegationMode:
    """
    委派模式 - 限制TeamLead仅使用协调工具
    
    在委派模式下：
    1. TeamLead被限制为仅协调工具
    2. 不能直接接触代码
    3. 适合需要严格分工的复杂项目
    """
    
    def __init__(self, team_lead: TeamLead):
        self.team_lead = team_lead
        self._allowed_tools = {
            "create_teammate", "create_task", "assign_task",
            "send_to_teammate", "check_progress", "generate_report"
        }
    
    def is_allowed(self, action: str) -> bool:
        """检查操作是否被允许"""
        return action in self._allowed_tools
    
    def execute(self, action: str, *args, **kwargs) -> Any:
        """
        执行操作（仅在允许列表内）
        
        Args:
            action: 操作名称
            
        Returns:
            操作结果
        """
        if not self.is_allowed(action):
            raise PermissionError(f"委派模式下不允许执行: {action}")
        
        method = getattr(self.team_lead, action, None)
        if method:
            return method(*args, **kwargs)
        
        raise AttributeError(f"未知操作: {action}")


class PlanApproval:
    """
    计划审批 - 队友提交计划，TeamLead审批
    
    工作流程：
    1. 队友提交计划
    2. TeamLead审查
    3. 批准/拒绝（附反馈）
    4. 队友修正或开始实施
    """
    
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    
    def __init__(self, team: Team):
        self.team = team
        self._plans: Dict[str, Dict[str, Any]] = {}
    
    def submit_plan(self, task_id: str, plan: str, teammate_id: str) -> str:
        """
        提交计划
        
        Args:
            task_id: 任务ID
            plan: 计划内容
            teammate_id: 提交者ID
            
        Returns:
            计划ID
        """
        plan_id = f"plan-{task_id}"
        
        self._plans[plan_id] = {
            "task_id": task_id,
            "plan": plan,
            "submitter": teammate_id,
            "status": self.STATUS_PENDING,
            "feedback": None,
            "submitted_at": datetime.now().isoformat()
        }
        
        # 通知TeamLead
        if self.team._lead:
            message = Message(
                msg_type=MessageType.MESSAGE,
                sender=teammate_id,
                recipient=self.team._lead.agent_id,
                content=f"计划提交: 任务 #{task_id}\n\n{plan}",
                summary=f"计划提交: 任务 #{task_id}"
            )
            self.team.message_bus.send(message, self.team._lead.agent_id)
        
        return plan_id
    
    def approve_plan(self, plan_id: str, feedback: str = "") -> bool:
        """
        批准计划
        
        Args:
            plan_id: 计划ID
            feedback: 反馈意见
            
        Returns:
            是否批准成功
        """
        if plan_id not in self._plans:
            return False
        
        plan = self._plans[plan_id]
        plan["status"] = self.STATUS_APPROVED
        plan["feedback"] = feedback
        
        # 通知队友
        teammate = self.team.get_member(plan["submitter"])
        if teammate:
            message = Message(
                msg_type=MessageType.MESSAGE,
                sender=self.team._lead.agent_id if self.team._lead else "system",
                recipient=plan["submitter"],
                content=f"计划已批准: 任务 #{plan['task_id']}\n\n反馈: {feedback}",
                summary="计划已批准"
            )
            self.team.message_bus.send(message, plan["submitter"])
        
        return True
    
    def reject_plan(self, plan_id: str, feedback: str) -> bool:
        """
        拒绝计划
        
        Args:
            plan_id: 计划ID
            feedback: 拒绝原因
            
        Returns:
            是否拒绝成功
        """
        if plan_id not in self._plans:
            return False
        
        plan = self._plans[plan_id]
        plan["status"] = self.STATUS_REJECTED
        plan["feedback"] = feedback
        
        # 通知队友
        if self.team._lead:
            message = Message(
                msg_type=MessageType.MESSAGE,
                sender=self.team._lead.agent_id,
                recipient=plan["submitter"],
                content=f"计划被拒绝: 任务 #{plan['task_id']}\n\n原因: {feedback}",
                summary="计划被拒绝"
            )
            self.team.message_bus.send(message, plan["submitter"])
        
        return True
    
    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """获取计划"""
        return self._plans.get(plan_id)
    
    def get_pending_plans(self) -> List[Dict[str, Any]]:
        """获取待审批计划"""
        return [
            plan for plan in self._plans.values()
            if plan["status"] == self.STATUS_PENDING
        ]
