"""
Agent Teams 单元测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
from pathlib import Path
import time

from core import (
    Agent, AgentState, AgentRole, ContextWindow,
    Message, MessageType, Mailbox, MessageBus,
    Task, TaskStatus, TaskList, TaskPriority,
    Team, TeamLead, Teammate,
    Coordinator
)


class TestMessage(unittest.TestCase):
    """测试消息类"""
    
    def test_message_creation(self):
        """测试消息创建"""
        msg = Message(
            msg_type=MessageType.MESSAGE,
            sender="agent-1",
            recipient="agent-2",
            content="测试消息",
            summary="测试"
        )
        
        self.assertIsNotNone(msg.msg_id)
        self.assertEqual(msg.msg_type, MessageType.MESSAGE)
        self.assertEqual(msg.sender, "agent-1")
        self.assertFalse(msg.read)
    
    def test_message_serialization(self):
        """测试消息序列化"""
        msg = Message(
            msg_type=MessageType.BROADCAST,
            sender="agent-1",
            content="广播消息"
        )
        
        msg_dict = msg.to_dict()
        restored = Message.from_dict(msg_dict)
        
        self.assertEqual(msg.msg_id, restored.msg_id)
        self.assertEqual(msg.msg_type, restored.msg_type)
        self.assertEqual(msg.content, restored.content)
    
    def test_message_mark_read(self):
        """测试标记已读"""
        msg = Message(content="测试")
        self.assertFalse(msg.read)
        msg.mark_read()
        self.assertTrue(msg.read)


class TestMailbox(unittest.TestCase):
    """测试邮箱类"""
    
    def test_mailbox_receive(self):
        """测试邮箱接收消息"""
        mailbox = Mailbox("test-agent")
        
        msg = Message(
            sender="other",
            content="测试消息"
        )
        mailbox.receive(msg)
        
        self.assertEqual(len(mailbox), 1)
        self.assertEqual(len(mailbox.get_unread()), 1)
    
    def test_mailbox_mark_read(self):
        """测试标记已读"""
        mailbox = Mailbox("test-agent")
        
        mailbox.receive(Message(sender="a", content="消息1"))
        mailbox.receive(Message(sender="b", content="消息2"))
        
        self.assertEqual(len(mailbox.get_unread()), 2)
        mailbox.mark_all_read()
        self.assertEqual(len(mailbox.get_unread()), 0)
    
    def test_mailbox_handler(self):
        """测试消息处理器"""
        mailbox = Mailbox("test-agent")
        received = []
        
        def handler(msg):
            received.append(msg)
        
        mailbox.register_handler(MessageType.MESSAGE, handler)
        mailbox.receive(Message(msg_type=MessageType.MESSAGE, content="测试"))
        
        self.assertEqual(len(received), 1)


class TestTask(unittest.TestCase):
    """测试任务类"""
    
    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            subject="测试任务",
            description="这是一个测试任务"
        )
        
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertIsNone(task.owner)
    
    def test_task_assign(self):
        """测试任务分配"""
        task = Task(subject="测试")
        task.assign("agent-1")
        
        self.assertEqual(task.owner, "agent-1")
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
    
    def test_task_complete(self):
        """测试任务完成"""
        task = Task(subject="测试")
        task.assign("agent-1")
        task.complete("完成结果")
        
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result, "完成结果")
        self.assertIsNotNone(task.completed_at)
    
    def test_task_serialization(self):
        """测试任务序列化"""
        task = Task(
            subject="测试",
            description="描述",
            priority=TaskPriority.HIGH
        )
        task.assign("agent-1")
        
        task_dict = task.to_dict()
        restored = Task.from_dict(task_dict)
        
        self.assertEqual(task.task_id, restored.task_id)
        self.assertEqual(task.subject, restored.subject)
        self.assertEqual(task.owner, restored.owner)


class TestTaskList(unittest.TestCase):
    """测试任务列表"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir) / "tasks.json"
    
    def test_create_task(self):
        """测试创建任务"""
        task_list = TaskList("test-team", self.storage_path)
        
        task = task_list.create_task(
            subject="测试任务",
            description="描述"
        )
        
        self.assertIsNotNone(task.task_id)
        self.assertEqual(len(task_list), 1)
    
    def test_claim_task(self):
        """测试认领任务"""
        task_list = TaskList("test-team", self.storage_path)
        
        task = task_list.create_task(subject="测试")
        claimed = task_list.claim_task(task.task_id, "agent-1")
        
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.owner, "agent-1")
        self.assertEqual(claimed.status, TaskStatus.IN_PROGRESS)
    
    def test_claim_unavailable_task(self):
        """测试认领不可用任务"""
        task_list = TaskList("test-team", self.storage_path)
        
        task = task_list.create_task(subject="测试")
        task_list.claim_task(task.task_id, "agent-1")
        
        # 尝试再次认领
        claimed = task_list.claim_task(task.task_id, "agent-2")
        self.assertIsNone(claimed)
    
    def test_task_dependencies(self):
        """测试任务依赖"""
        task_list = TaskList("test-team", self.storage_path)
        
        task1 = task_list.create_task(subject="任务1")
        task2 = task_list.create_task(
            subject="任务2",
            dependencies=[task1.task_id]
        )
        
        # 任务2应该被阻塞
        self.assertEqual(task2.status, TaskStatus.BLOCKED)
        
        # 完成任务1
        task_list.update_task(task1.task_id, status=TaskStatus.COMPLETED)
        
        # 任务2应该自动解除阻塞
        task2_updated = task_list.get_task(task2.task_id)
        self.assertEqual(task2_updated.status, TaskStatus.PENDING)
    
    def test_get_available_tasks(self):
        """测试获取可用任务"""
        task_list = TaskList("test-team", self.storage_path)
        
        task_list.create_task(subject="任务1")
        task_list.create_task(subject="任务2")
        
        available = task_list.get_available_tasks()
        self.assertEqual(len(available), 2)


class TestTeam(unittest.TestCase):
    """测试团队"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.team_dir = Path(self.temp_dir) / "test-team"
    
    def test_team_creation(self):
        """测试团队创建"""
        team = Team(
            name="test-team",
            description="测试团队",
            storage_dir=self.team_dir
        )
        
        self.assertEqual(team.config.name, "test-team")
        self.assertTrue(self.team_dir.exists())
    
    def test_add_member(self):
        """测试添加成员"""
        team = Team(name="test", storage_dir=self.team_dir)
        
        teammate = Teammate(
            name="expert",
            agent_type="analyst",
            prompt="测试"
        )
        team.add_member(teammate)
        
        self.assertEqual(len(team.get_all_members()), 1)


class TestCoordinator(unittest.TestCase):
    """测试协调器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.team_dir = Path(self.temp_dir) / "coord-team"
    
    def test_coordinator_status(self):
        """测试协调器状态"""
        team = Team(name="test", storage_dir=self.team_dir)
        lead = TeamLead(name="lead", team=team)
        
        coordinator = Coordinator(team)
        status = coordinator.get_status()
        
        self.assertIn("running", status)
        self.assertIn("strategy", status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
