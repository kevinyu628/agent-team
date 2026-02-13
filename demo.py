"""
Agent Teams 完整演示示例

演示多Agent协作的核心功能：
1. 团队创建
2. 任务创建和分配
3. 消息传递
4. 任务执行和状态更新
5. 汇报和汇总
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
from pathlib import Path

from core import (
    Agent, AgentState, AgentRole,
    Message, MessageType, Mailbox, MessageBus,
    Task, TaskStatus, TaskList, TaskPriority,
    Team, TeamLead, Teammate,
    Coordinator
)


class MockLLMTeammate(Teammate):
    """
    模拟LLM队友 - 用于演示
    
    在实际应用中，这里会调用真实的LLM API
    """
    
    def __init__(self, name: str, agent_type: str, prompt: str, color: str = "blue"):
        super().__init__(name, agent_type, prompt, color)
        self._response_handlers = {
            "ux": self._handle_ux_task,
            "architect": self._handle_architect_task,
            "critic": self._handle_critic_task,
            "researcher": self._handle_research_task,
            "developer": self._handle_developer_task
        }
    
    def execute_task(self, task: Task) -> str:
        """执行任务"""
        print(f"\n[{self.name}] 开始执行任务: {task.subject}")
        
        # 模拟工作
        self.set_state(AgentState.WORKING)
        time.sleep(1)  # 模拟处理时间
        
        # 根据类型处理
        handler = self._response_handlers.get(self.agent_type, self._handle_generic_task)
        result = handler(task)
        
        # 完成任务
        self.complete_task(result)
        print(f"[{self.name}] 任务完成!")
        
        return result
    
    def _handle_ux_task(self, task: Task) -> str:
        """处理UX分析任务"""
        result = f"""
## UX分析报告: {task.subject}

### 用户旅程分析
1. 用户首先需要了解Agent Teams的概念
2. 然后需要创建团队和分配任务
3. 最后需要查看结果和汇总

### 关键体验点
- **团队创建**: 需要简洁明了的界面
- **任务分配**: 需要可视化任务状态
- **进度监控**: 需要实时更新的进度条

### 改进建议
1. 添加任务依赖可视化
2. 提供队友状态实时显示
3. 支持任务优先级拖拽排序
"""
        return result
    
    def _handle_architect_task(self, task: Task) -> str:
        """处理架构分析任务"""
        result = f"""
## 架构分析报告: {task.subject}

### 核心组件
1. **Team**: 团队配置和管理
2. **TeamLead**: 团队领导，协调工作
3. **Teammate**: 队友，执行具体任务
4. **TaskList**: 共享任务列表
5. **Mailbox**: 消息邮箱

### 数据流
```
TeamLead -> 创建任务 -> TaskList
TeamLead -> 分配任务 -> Teammate
Teammate -> 执行任务 -> 结果
Teammate -> 汇报 -> TeamLead
```

### 扩展点
- 支持更多消息类型
- 添加任务优先级调度
- 实现委派模式
"""
        return result
    
    def _handle_critic_task(self, task: Task) -> str:
        """处理批判性分析任务"""
        result = f"""
## 批判性分析: {task.subject}

### 潜在问题
1. **消息延迟**: 文件系统存储可能导致消息延迟
2. **竞态条件**: 多个队友同时认领任务
3. **状态同步**: TeamLead和Teammate状态可能不一致

### 局限性
- 没有真正的并行执行
- 缺乏错误恢复机制
- 没有任务超时处理

### 改进建议
1. 使用数据库替代文件存储
2. 实现分布式锁
3. 添加心跳检测
"""
        return result
    
    def _handle_research_task(self, task: Task) -> str:
        """处理研究任务"""
        result = f"""
## 研究报告: {task.subject}

### 调研结果
1. 发现了多个相关的多Agent框架
2. 分析了各框架的优缺点
3. 提出了改进方向

### 参考框架
- AutoGen: 微软的多Agent框架
- CrewAI: 角色扮演式Agent
- LangGraph: 图结构工作流

### 最佳实践
- 明确角色分工
- 使用消息传递而非共享状态
- 实现任务依赖管理
"""
        return result
    
    def _handle_developer_task(self, task: Task) -> str:
        """处理开发任务"""
        result = f"""
## 开发报告: {task.subject}

### 已实现功能
1. ✅ 核心Agent类
2. ✅ 消息系统
3. ✅ 任务管理
4. ✅ 团队协调

### 代码统计
- 总行数: ~1500行
- 核心模块: 6个
- 测试覆盖: 待添加

### 下一步
1. 添加单元测试
2. 实现持久化存储
3. 集成真实LLM
"""
        return result
    
    def _handle_generic_task(self, task: Task) -> str:
        """处理通用任务"""
        return f"任务 '{task.subject}' 已完成。结果：通用处理完成。"


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*20} {title} {'='*20}")
    else:
        print("=" * 60)


def demo_basic_usage():
    """演示基本用法"""
    print_separator("基本用法演示")
    
    # 1. 创建团队
    print("\n1. 创建团队")
    team = Team(
        name="demo-team",
        description="演示团队"
    )
    print(f"   团队创建成功: {team.config.name}")
    
    # 2. 创建TeamLead
    print("\n2. 创建团队领导")
    lead = TeamLead(name="lead", team=team)
    print(f"   TeamLead创建成功: {lead.agent_id}")
    
    # 3. 创建队友
    print("\n3. 创建队友")
    ux_expert = MockLLMTeammate(
        name="ux-expert",
        agent_type="ux",
        prompt="你是UX分析专家",
        color="blue"
    )
    team.add_member(ux_expert)
    print(f"   UX专家创建成功: {ux_expert.agent_id}")
    
    architect = MockLLMTeammate(
        name="architect",
        agent_type="architect",
        prompt="你是系统架构师",
        color="green"
    )
    team.add_member(architect)
    print(f"   架构师创建成功: {architect.agent_id}")
    
    # 4. 创建任务
    print("\n4. 创建任务")
    task1 = lead.create_task(
        subject="分析用户界面体验",
        description="从UX角度分析Agent Teams的用户界面设计"
    )
    print(f"   任务创建成功: {task1}")
    
    task2 = lead.create_task(
        subject="设计系统架构",
        description="设计Agent Teams的技术架构"
    )
    print(f"   任务创建成功: {task2}")
    
    # 5. 分配任务
    print("\n5. 分配任务")
    lead.assign_task(task1.task_id, ux_expert.agent_id)
    print(f"   任务#{task1.task_id} 分配给 {ux_expert.name}")
    
    lead.assign_task(task2.task_id, architect.agent_id)
    print(f"   任务#{task2.task_id} 分配给 {architect.name}")
    
    # 6. 执行任务
    print("\n6. 执行任务")
    ux_expert.execute_task(task1)
    architect.execute_task(task2)
    
    # 7. 检查进度
    print("\n7. 任务进度")
    progress = team.task_list.get_progress()
    print(f"   进度: {progress}")
    
    # 8. 生成报告
    print("\n8. 生成报告")
    report = lead.generate_report()
    print(report)


def demo_message_passing():
    """演示消息传递"""
    print_separator("消息传递演示")
    
    # 创建消息总线
    bus = MessageBus()
    
    # 注册邮箱
    mailbox1 = bus.register("agent-1")
    mailbox2 = bus.register("agent-2")
    
    print("\n1. 发送普通消息")
    msg = Message(
        msg_type=MessageType.MESSAGE,
        sender="agent-1",
        recipient="agent-2",
        content="你好，这是测试消息",
        summary="测试消息"
    )
    bus.send(msg, "agent-2")
    print(f"   发送: {msg}")
    
    # 读取消息
    unread = mailbox2.get_unread()
    print(f"   未读消息: {len(unread)}条")
    
    print("\n2. 发送广播消息")
    broadcast = Message(
        sender="agent-1",
        content="这是广播消息",
        summary="广播通知"
    )
    bus.broadcast(broadcast)
    print(f"   广播给: {bus.get_all_agents()}")
    
    print("\n3. 消息统计")
    print(f"   agent-1邮箱: {len(mailbox1)}条消息")
    print(f"   agent-2邮箱: {len(mailbox2)}条消息")


def demo_task_dependencies():
    """演示任务依赖"""
    print_separator("任务依赖演示")
    
    # 创建任务列表
    task_list = TaskList("dependency-demo")
    
    print("\n1. 创建有依赖关系的任务")
    # 创建基础任务
    task1 = task_list.create_task(
        subject="数据收集",
        description="收集所需数据"
    )
    print(f"   创建任务: {task1.subject} (#{task1.task_id})")
    
    # 创建依赖任务
    task2 = task_list.create_task(
        subject="数据分析",
        description="分析收集的数据",
        dependencies=[task1.task_id]
    )
    print(f"   创建任务: {task2.subject} (#{task2.task_id}) - 依赖 #{task1.task_id}")
    print(f"   任务状态: {task2.status.value} (应该为blocked)")
    
    print("\n2. 完成依赖任务")
    task_list.update_task(task1.task_id, status=TaskStatus.COMPLETED)
    print(f"   任务 #{task1.task_id} 已完成")
    
    # 检查依赖任务状态
    task2_updated = task_list.get_task(task2.task_id)
    print(f"   依赖任务状态: {task2_updated.status.value} (应该自动解除阻塞)")
    
    print("\n3. 任务列表状态")
    print(task_list.display())


def demo_coordinator():
    """演示协调器"""
    print_separator("协调器演示")
    
    # 创建团队
    team = Team(name="coordinator-demo", description="协调器演示团队")
    
    # 创建TeamLead
    lead = TeamLead(name="lead", team=team)
    
    # 创建多个队友
    teammates = []
    for i, (name, agent_type) in enumerate([
        ("researcher-1", "researcher"),
        ("researcher-2", "researcher"),
        ("developer", "developer")
    ]):
        teammate = MockLLMTeammate(
            name=name,
            agent_type=agent_type,
            prompt=f"你是{name}",
            color=["blue", "green", "yellow"][i]
        )
        teammate.set_team(team)
        team.add_member(teammate)
        teammates.append(teammate)
    
    # 创建协调器
    coordinator = Coordinator(team)
    
    print("\n1. 创建多个任务")
    tasks = []
    for i in range(5):
        task = lead.create_task(
            subject=f"研究任务 {i+1}",
            description=f"第{i+1}个研究任务",
            priority=[TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH][i % 3]
        )
        tasks.append(task)
        print(f"   创建: {task.subject} (优先级: {task.priority.name})")
    
    print("\n2. 协调器状态")
    status = coordinator.get_status()
    print(f"   策略: {status['strategy']}")
    print(f"   可用任务: {status['available_tasks']}")
    print(f"   空闲队友: {status['idle_teammates']}")
    
    print("\n3. 手动分配任务")
    for i, task in enumerate(tasks[:3]):
        teammate = teammates[i % len(teammates)]
        coordinator.assign_task(task, teammate)
        print(f"   任务 #{task.task_id} -> {teammate.name}")
    
    print("\n4. 任务进度")
    print(team.task_list.display())


def demo_full_workflow():
    """演示完整工作流"""
    print_separator("完整工作流演示")
    
    print("\n创建一个完整的Agent Team来分析Agent Teams本身...")
    
    # 1. 创建团队
    team = Team(
        name="agent-team-analyzer",
        description="分析Agent Teams功能的设计与实现",
        storage_dir=Path.home() / ".agent_teams_demo" / "agent-team-analyzer"
    )
    
    # 2. 创建TeamLead
    lead = TeamLead(
        name="team-lead",
        prompt="""你是团队领导，负责协调多Agent分析任务。
你的职责是创建任务、分配给合适的队友、监控进度并汇总结果。"""
    )
    lead.set_team(team)
    
    # 3. 创建队友（模拟不同的专业角色）
    ux_expert = MockLLMTeammate(
        name="ux-expert",
        agent_type="ux",
        prompt="你是UX分析专家，专注于用户体验设计分析",
        color="blue"
    )
    ux_expert.set_team(team)
    team.add_member(ux_expert)
    
    architect = MockLLMTeammate(
        name="architect",
        agent_type="architect",
        prompt="你是系统架构师，专注于技术架构设计",
        color="green"
    )
    architect.set_team(team)
    team.add_member(architect)
    
    critic = MockLLMTeammate(
        name="critic",
        agent_type="critic",
        prompt="你是批判性思考者，从反面角度分析问题",
        color="yellow"
    )
    critic.set_team(team)
    team.add_member(critic)
    
    print(f"\n团队创建完成:")
    print(f"  - 团队: {team.config.name}")
    print(f"  - 领导: {lead.name}")
    print(f"  - 成员: {[m.name for m in team.get_all_members()]}")
    
    # 4. 创建任务
    print("\n创建分析任务...")
    
    task1 = lead.create_task(
        subject="从UX角度分析Agent Team用户体验",
        description="""作为UX专家，分析Agent Team功能的用户体验设计：
1. 用户旅程分析
2. 关键体验点
3. 改进建议""",
        priority=TaskPriority.HIGH
    )
    
    task2 = lead.create_task(
        subject="从架构角度分析Agent Team技术实现",
        description="""作为架构师，分析Agent Team的技术架构：
1. 核心组件分析
2. 数据流设计
3. 扩展性考虑""",
        priority=TaskPriority.HIGH
    )
    
    task3 = lead.create_task(
        subject="作为魔鬼代言人质疑Agent Team的价值",
        description="""作为批判性思考者，质疑Agent Team功能：
1. 潜在问题
2. 局限性分析
3. 改进方向""",
        priority=TaskPriority.MEDIUM
    )
    
    print(f"任务创建完成: {len(team.task_list)}个任务")
    
    # 5. 分配任务
    print("\n分配任务给队友...")
    lead.assign_task(task1.task_id, ux_expert.agent_id)
    lead.assign_task(task2.task_id, architect.agent_id)
    lead.assign_task(task3.task_id, critic.agent_id)
    
    # 6. 执行任务（并行）
    print("\n队友开始工作...")
    
    def run_task(teammate, task):
        result = teammate.execute_task(task)
        teammate.report_to_lead(result, f"任务完成: {task.subject}")
    
    threads = []
    for teammate, task in [(ux_expert, task1), (architect, task2), (critic, task3)]:
        t = threading.Thread(target=run_task, args=(teammate, task))
        threads.append(t)
        t.start()
    
    # 等待所有任务完成
    for t in threads:
        t.join()
    
    # 7. 检查进度
    print("\n检查任务进度...")
    progress = lead.check_progress()
    print(f"进度: {progress}")
    
    # 8. 生成汇总报告
    print("\n" + "=" * 60)
    print(lead.generate_report())
    
    # 9. 团队状态
    print("\n团队状态:")
    status = team.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("    Agent Teams - 多智能体协作框架演示")
    print("    基于Claude Code Agent Teams原理实现")
    print("=" * 60)
    
    # 运行各个演示
    demo_basic_usage()
    demo_message_passing()
    demo_task_dependencies()
    demo_coordinator()
    demo_full_workflow()
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
