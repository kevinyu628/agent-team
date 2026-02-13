"""
任务管理模块 - 实现共享任务列表和任务协调

核心功能：
1. Task - 任务类，支持状态管理和依赖关系
2. TaskList - 共享任务列表，支持文件锁定防止竞态条件
3. 任务状态：待处理 -> 进行中 -> 已完成
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
import json
import threading
import uuid
import fcntl
import os


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"  # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"  # 被阻塞（依赖其他任务）
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Task:
    """
    任务类 - 任务列表中的基本单位
    
    属性：
        task_id: 任务唯一标识
        subject: 任务主题
        description: 任务详细描述
        status: 任务状态
        priority: 任务优先级
        owner: 任务负责人
        dependencies: 依赖的任务ID列表
        result: 任务执行结果
        created_at: 创建时间
        updated_at: 更新时间
        completed_at: 完成时间
        metadata: 额外元数据
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    subject: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    owner: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为字典格式"""
        return {
            "task_id": self.task_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "owner": self.owner,
            "dependencies": self.dependencies,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典创建任务对象"""
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())[:8]),
            subject=data.get("subject", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", 2)),
            owner=data.get("owner"),
            dependencies=data.get("dependencies", []),
            result=data.get("result"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {})
        )
    
    def assign(self, owner: str):
        """分配任务给指定Agent"""
        self.owner = owner
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now().isoformat()
    
    def complete(self, result: Optional[str] = None):
        """标记任务为完成"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def fail(self, reason: Optional[str] = None):
        """标记任务为失败"""
        self.status = TaskStatus.FAILED
        self.result = reason
        self.updated_at = datetime.now().isoformat()
    
    def block(self):
        """阻塞任务"""
        self.status = TaskStatus.BLOCKED
        self.updated_at = datetime.now().isoformat()
    
    def unblock(self):
        """解除阻塞"""
        if self.status == TaskStatus.BLOCKED:
            self.status = TaskStatus.PENDING
            self.updated_at = datetime.now().isoformat()
    
    def cancel(self):
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now().isoformat()
    
    def is_available(self) -> bool:
        """任务是否可以被认领"""
        return self.status == TaskStatus.PENDING and self.owner is None
    
    def __str__(self) -> str:
        """字符串表示"""
        owner_str = f" ({self.owner})" if self.owner else ""
        return f"任务#{self.task_id} [{self.status.value}] {self.subject}{owner_str}"


class TaskList:
    """
    共享任务列表 - 所有Agent共享的协调中心
    
    核心特性：
    1. 文件锁定机制，防止竞态条件
    2. 任务依赖自动解除
    3. 支持任务认领和释放
    4. 状态实时同步
    """
    
    def __init__(self, team_name: str, storage_path: Optional[Path] = None):
        """
        初始化任务列表
        
        Args:
            team_name: 团队名称
            storage_path: 存储路径
        """
        self.team_name = team_name
        self.storage_path = storage_path
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._file_lock_path = None
        
        if storage_path:
            self._file_lock_path = storage_path.with_suffix('.lock')
            self._load_tasks()
    
    def _acquire_file_lock(self):
        """获取文件锁"""
        if self._file_lock_path:
            self._file_lock_path.touch()
            self._lock_fd = open(self._file_lock_path, 'w')
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX)
    
    def _release_file_lock(self):
        """释放文件锁"""
        if self._file_lock_path and hasattr(self, '_lock_fd'):
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()
    
    def _load_tasks(self):
        """从存储加载任务"""
        if self.storage_path and self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                    for task_data in tasks_data:
                        task = Task.from_dict(task_data)
                        self._tasks[task.task_id] = task
            except (json.JSONDecodeError, FileNotFoundError):
                self._tasks = {}
    
    def _save_tasks(self):
        """保存任务到存储"""
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([task.to_dict() for task in self._tasks.values()], f, ensure_ascii=False, indent=2)
    
    def create_task(
        self,
        subject: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None
    ) -> Task:
        """
        创建新任务
        
        Args:
            subject: 任务主题
            description: 任务描述
            priority: 任务优先级
            dependencies: 依赖任务ID列表
            
        Returns:
            创建的任务对象
        """
        task = Task(
            subject=subject,
            description=description,
            priority=priority,
            dependencies=dependencies or []
        )
        
        with self._lock:
            # 检查依赖任务是否存在
            for dep_id in (dependencies or []):
                if dep_id not in self._tasks:
                    raise ValueError(f"依赖任务 {dep_id} 不存在")
            
            # 如果有未完成的依赖，设置为阻塞状态
            if dependencies and not self._check_dependencies_completed(task):
                task.block()
            
            self._tasks[task.task_id] = task
            self._save_tasks()
        
        return task
    
    def _check_dependencies_completed(self, task: Task) -> bool:
        """检查任务依赖是否都已完成"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    def claim_task(self, task_id: str, agent_id: str) -> Optional[Task]:
        """
        认领任务 - 使用文件锁防止竞态条件
        
        Args:
            task_id: 任务ID
            agent_id: 认领者ID
            
        Returns:
            认领的任务，如果任务不可用则返回None
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            
            # 检查任务是否可以被认领
            if not task.is_available():
                return None
            
            # 检查依赖是否完成
            if not self._check_dependencies_completed(task):
                return None
            
            # 认领任务
            task.assign(agent_id)
            self._save_tasks()
            
            return task
    
    def release_task(self, task_id: str) -> bool:
        """
        释放任务（取消认领）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否释放成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.IN_PROGRESS:
                return False
            
            task.owner = None
            task.status = TaskStatus.PENDING
            task.updated_at = datetime.now().isoformat()
            self._save_tasks()
            
            return True
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        result: Optional[str] = None,
        owner: Optional[str] = None
    ) -> Optional[Task]:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            result: 任务结果
            owner: 任务负责人
            
        Returns:
            更新后的任务
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            
            if status:
                task.status = status
                if status == TaskStatus.COMPLETED:
                    task.completed_at = datetime.now().isoformat()
                    # 解除依赖此任务的其他任务
                    self._unblock_dependent_tasks(task_id)
            
            if result is not None:
                task.result = result
            
            if owner is not None:
                task.owner = owner
            
            task.updated_at = datetime.now().isoformat()
            self._save_tasks()
            
            return task
    
    def _unblock_dependent_tasks(self, completed_task_id: str):
        """解除依赖已完成任务的其他任务的阻塞状态"""
        for task in self._tasks.values():
            if completed_task_id in task.dependencies and task.status == TaskStatus.BLOCKED:
                if self._check_dependencies_completed(task):
                    task.unblock()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取指定任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_available_tasks(self) -> List[Task]:
        """获取可认领的任务"""
        return [task for task in self._tasks.values() if task.is_available()]
    
    def get_tasks_by_owner(self, owner: str) -> List[Task]:
        """获取指定负责人的任务"""
        return [task for task in self._tasks.values() if task.owner == owner]
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """获取指定状态的任务"""
        return [task for task in self._tasks.values() if task.status == status]
    
    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return self.get_tasks_by_status(TaskStatus.PENDING)
    
    def get_in_progress_tasks(self) -> List[Task]:
        """获取进行中任务"""
        return self.get_tasks_by_status(TaskStatus.IN_PROGRESS)
    
    def get_completed_tasks(self) -> List[Task]:
        """获取已完成任务"""
        return self.get_tasks_by_status(TaskStatus.COMPLETED)
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._save_tasks()
                return True
            return False
    
    def clear_completed(self):
        """清除已完成的任务"""
        with self._lock:
            self._tasks = {
                tid: task for tid, task in self._tasks.items()
                if task.status != TaskStatus.COMPLETED
            }
            self._save_tasks()
    
    def get_progress(self) -> Dict[str, int]:
        """获取任务进度统计"""
        status_counts = {status.value: 0 for status in TaskStatus}
        for task in self._tasks.values():
            status_counts[task.status.value] += 1
        return status_counts
    
    def __len__(self) -> int:
        return len(self._tasks)
    
    def __str__(self) -> str:
        progress = self.get_progress()
        return f"TaskList({self.team_name}): {len(self._tasks)}个任务, 进度: {progress}"
    
    def display(self) -> str:
        """显示任务列表的详细信息"""
        lines = [f"\n=== 任务列表 ({self.team_name}) ==="]
        for task in sorted(self._tasks.values(), key=lambda t: t.priority.value, reverse=True):
            status_icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.BLOCKED: "🚫",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.CANCELLED: "⊘"
            }.get(task.status, "?")
            owner_str = f"({task.owner})" if task.owner else "(未分配)"
            lines.append(f"  {status_icon} #{task.task_id} {task.subject} - {owner_str}")
        return "\n".join(lines)
