# Agent Team - 多智能体协作框架

基于 Claude Code Agent Teams 的原理和架构实现的 Python 多智能体协作框架。

## 🌟 核心特性

- **多Agent协作**: 每个Agent拥有独立的上下文窗口，可以直接相互通信
- **共享任务列表**: 所有Agent共享任务列表，支持任务依赖和自动解除阻塞
- **消息系统**: 自动消息传递，无需轮询，支持多种消息类型
- **角色分工**: TeamLead 负责协调，Teammate 负责执行
- **灵活调度**: 支持多种任务分配策略

## 📦 项目结构

```
agent_team/
├── core/
│   ├── __init__.py      # 模块入口
│   ├── agent.py         # Agent基类
│   ├── message.py       # 消息系统
│   ├── task.py          # 任务管理
│   ├── team.py          # 团队管理
│   └── coordinator.py   # 协调器
├── utils/
│   └── helpers.py       # 工具函数
├── examples/
│   ├── demo.py          # 完整演示
│   └── llm_teammate.py  # LLM集成示例
├── tests/
│   └── test_agent_teams.py  # 单元测试
└── README.md
```

## 🚀 快速开始

### 基本用法

```python
from pathlib import Path
from core import Team, TeamLead, Teammate, TaskPriority

# 1. 创建团队
team = Team(
    name="my-team",
    description="我的多Agent团队",
    storage_dir=Path("./team_data")
)

# 2. 创建团队领导
lead = TeamLead(name="lead", prompt="你是团队领导...")
lead.set_team(team)

# 3. 创建队友
expert = Teammate(
    name="expert",
    agent_type="analyst",
    prompt="你是分析专家...",
    color="blue"
)
expert.set_team(team)
team.add_member(expert)

# 4. 创建并分配任务
task = lead.create_task(
    subject="分析任务",
    description="详细的任务描述",
    priority=TaskPriority.HIGH
)

lead.assign_task(task.task_id, expert.agent_id)

# 5. 执行任务
result = expert.execute_task(task)
print(result)

# 6. 生成报告
print(lead.generate_report())
```

### 消息传递

```python
from core import Message, MessageType, Mailbox, MessageBus

# 创建消息总线
bus = MessageBus()

# 注册邮箱
mailbox1 = bus.register("agent-1")
mailbox2 = bus.register("agent-2")

# 发送消息
msg = Message(
    msg_type=MessageType.MESSAGE,
    sender="agent-1",
    recipient="agent-2",
    content="你好，这是测试消息"
)
bus.send(msg, "agent-2")

# 读取消息
unread = mailbox2.get_unread()
print(f"未读消息: {len(unread)}条")
```

### 任务依赖

```python
from core import TaskList, TaskStatus

task_list = TaskList("my-team")

# 创建基础任务
task1 = task_list.create_task(subject="数据收集")

# 创建依赖任务（自动阻塞）
task2 = task_list.create_task(
    subject="数据分析",
    dependencies=[task1.task_id]
)
print(f"任务状态: {task2.status}")  # blocked

# 完成依赖任务
task_list.update_task(task1.task_id, status=TaskStatus.COMPLETED)

# 依赖任务自动解除阻塞
task2_updated = task_list.get_task(task2.task_id)
print(f"任务状态: {task2_updated.status}")  # pending
```

## 🏗️ 架构设计

### 核心组件

| 组件 | 角色 |
|------|------|
| **TeamLead** | 创建团队、生成队友和协调工作的主会话 |
| **Teammate** | 各自处理分配任务的单独实例 |
| **TaskList** | 队友认领和完成的共享工作项列表 |
| **Mailbox** | Agent之间通信的消息系统 |
| **Coordinator** | 任务分配和队友调度协调器 |

### 工作流程

```
TeamLead -> 创建任务 -> TaskList
TeamLead -> 分配任务 -> Teammate
Teammate -> 执行任务 -> 结果
Teammate -> 汇报 -> TeamLead
TeamLead -> 汇总报告 -> 用户
```

### 消息类型

| 类型 | 说明 |
|------|------|
| MESSAGE | 普通消息，点对点发送 |
| BROADCAST | 广播消息，发给所有队友 |
| IDLE_NOTIFICATION | 空闲通知，队友完成任务后自动发送 |
| TASK_ASSIGNMENT | 任务分配通知 |
| REPORT | 汇报消息 |

### 任务状态

```
待处理(PENDING) -> 进行中(IN_PROGRESS) -> 已完成(COMPLETED)
       ↓
    阻塞(BLOCKED) --依赖完成--> 待处理(PENDING)
       ↓
    失败(FAILED) / 取消(CANCELLED)
```

## 🔧 高级功能

### 委派模式

```python
from core import DelegationMode

# 启用委派模式后，TeamLead只能使用协调工具
delegation = DelegationMode(lead)

# 允许的操作
delegation.execute("create_task", subject="新任务")
delegation.execute("assign_task", task_id, teammate_id)

# 不允许的操作（会抛出异常）
delegation.execute("execute_task", task)  # PermissionError
```

### 计划审批

```python
from core import PlanApproval

approval = PlanApproval(team)

# 队友提交计划
plan_id = approval.submit_plan(
    task_id=task.task_id,
    plan="执行计划内容...",
    teammate_id=expert.agent_id
)

# TeamLead审批
approval.approve_plan(plan_id, feedback="计划通过")
# 或拒绝
approval.reject_plan(plan_id, feedback="需要修改...")
```

### LLM集成

```python
# 实现自定义LLM队友
class MyLLMTeammate(Teammate):
    def __init__(self, name, agent_type, prompt, api_key):
        super().__init__(name, agent_type, prompt)
        self.api_key = api_key
    
    def execute_task(self, task):
        # 调用你的LLM API
        response = self.call_llm(task.description)
        self.complete_task(response)
        return response
    
    def call_llm(self, prompt):
        # 实现你的LLM调用逻辑
        # 例如: OpenAI, Claude, 本地模型等
        pass
```

## 🧪 运行测试

```bash
cd agent_teams
python -m pytest tests/ -v
```

## 📝 使用场景

### 适合场景

- **研究和审查**: 多个队友同时调查问题的不同方面
- **新模块开发**: 队友各自负责一个独立部分
- **竞争假设调试**: 队友并行测试不同的理论
- **跨层协调**: 前端、后端、测试各由不同队友负责

### 不适合场景

- 顺序任务（一步依赖上一步）
- 同一文件编辑（会冲突）
- 简单任务（一个Agent就能搞定）
- 时效敏感（协调开销太大）

## 📄 许可证

MIT License

## 🙏 致谢

本框架基于 Claude Code Agent Teams 的设计理念实现，感谢 Anthropic 的创新工作。
