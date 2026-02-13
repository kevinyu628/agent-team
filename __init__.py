"""
Agent Teams - 多智能体协作框架

基于Claude Code Agent Teams的原理和架构实现
"""

from .agent import Agent, AgentState, AgentRole, ContextWindow
from .message import Message, MessageType, Mailbox, MessageBus
from .task import Task, TaskStatus, TaskList, TaskPriority
from .team import Team, TeamLead, Teammate
from .coordinator import Coordinator, DelegationMode, PlanApproval

__version__ = "1.0.0"
__all__ = [
    "Agent", "AgentState", "AgentRole", "ContextWindow",
    "Message", "MessageType", "Mailbox", "MessageBus",
    "Task", "TaskStatus", "TaskList", "TaskPriority",
    "Team", "TeamLead", "Teammate",
    "Coordinator", "DelegationMode", "PlanApproval"
]
