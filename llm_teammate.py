"""
LLM集成示例 - 展示如何将真实LLM集成到Agent Teams

这个示例展示了如何创建一个实际可用的LLM驱动的队友
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, Dict, Any, List
import time
import json

from core import (
    Teammate, Task, TaskStatus, MessageType, Message
)


class LLMTeammate(Teammate):
    """
    LLM驱动的队友 - 使用真实LLM API
    
    使用方法:
    1. 设置你的LLM API（如OpenAI、Claude等）
    2. 实现call_llm方法
    3. 创建队友实例并添加到团队
    """
    
    def __init__(
        self,
        name: str,
        agent_type: str,
        prompt: str,
        color: str = "blue",
        api_key: Optional[str] = None,
        model: str = "gpt-4"
    ):
        super().__init__(name, agent_type, prompt, color)
        self.api_key = api_key
        self.model = model
        self._conversation_history: List[Dict[str, str]] = []
        
        # 初始化对话历史
        self._conversation_history.append({
            "role": "system",
            "content": prompt
        })
    
    def call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        调用LLM API - 子类需要实现此方法
        
        以下是伪代码示例，实际使用时需要根据你选择的LLM API进行实现
        
        示例（使用OpenAI）:
        ```python
        import openai
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            api_key=self.api_key
        )
        return response.choices[0].message.content
        ```
        
        示例（使用Claude）:
        ```python
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.prompt,
            messages=messages
        )
        return response.content[0].text
        ```
        """
        # 这里是一个模拟实现
        # 实际使用时，请替换为真实的LLM API调用
        
        # 模拟响应
        last_user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_message = msg["content"]
                break
        
        # 返回模拟响应
        return f"[{self.name}] 收到消息: {last_user_message[:100]}...\n\n" \
               f"作为{self.agent_type}专家，我已经处理了这个请求。"
    
    def execute_task(self, task: Task) -> str:
        """
        使用LLM执行任务
        
        Args:
            task: 要执行的任务
            
        Returns:
            任务结果
        """
        self.set_state(self.State.WORKING if hasattr(self, 'State') else None)
        
        # 构建任务消息
        task_message = f"""
请完成以下任务:

任务主题: {task.subject}
任务描述: {task.description}

请提供详细的分析和建议。
"""
        
        # 添加到对话历史
        self._conversation_history.append({
            "role": "user",
            "content": task_message
        })
        
        # 调用LLM
        try:
            response = self.call_llm(self._conversation_history)
            
            # 添加响应到历史
            self._conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # 完成任务
            self.complete_task(response)
            
            return response
            
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            self.complete_task(error_msg)
            return error_msg
    
    def process_message(self, message: Message) -> Optional[Message]:
        """
        使用LLM处理消息
        
        Args:
            message: 接收到的消息
            
        Returns:
            可选的回复消息
        """
        # 先调用父类处理
        super().process_message(message)
        
        # 对于普通消息，使用LLM生成回复
        if message.msg_type == MessageType.MESSAGE:
            self._conversation_history.append({
                "role": "user",
                "content": f"来自{message.sender}的消息: {message.content}"
            })
            
            try:
                response = self.call_llm(self._conversation_history)
                self._conversation_history.append({
                    "role": "assistant",
                    "content": response
                })
                
                # 发送回复
                if self._team and self._team._lead:
                    return self.send_message(
                        recipient_id=message.sender,
                        content=response,
                        summary=f"回复: {response[:50]}"
                    )
            except Exception as e:
                print(f"处理消息时出错: {e}")
        
        return None


class OpenAITeammate(LLMTeammate):
    """
    使用OpenAI API的队友实现
    
    使用前需要安装: pip install openai
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None
    
    def _init_client(self):
        """初始化OpenAI客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("请先安装openai: pip install openai")
    
    def call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用OpenAI API"""
        self._init_client()
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        
        return response.choices[0].message.content


class ClaudeTeammate(LLMTeammate):
    """
    使用Anthropic Claude API的队友实现
    
    使用前需要安装: pip install anthropic
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None
    
    def _init_client(self):
        """初始化Claude客户端"""
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("请先安装anthropic: pip install anthropic")
    
    def call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用Claude API"""
        self._init_client()
        
        # Claude API格式转换
        claude_messages = []
        for msg in messages:
            if msg["role"] != "system":  # Claude单独处理system
                claude_messages.append(msg)
        
        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.prompt,
            messages=claude_messages
        )
        
        return response.content[0].text


# 使用示例
def example_usage():
    """展示如何使用LLM驱动的队友"""
    
    example_code = '''
from pathlib import Path
from core import Team, TeamLead, TaskPriority

# 1. 创建团队
team = Team(
    name="ai-research-team",
    description="AI研究分析团队",
    storage_dir=Path("./team_data")
)

# 2. 创建团队领导
lead = TeamLead(name="research-lead")
lead.set_team(team)

# 3. 创建LLM驱动的队友

# 使用OpenAI
from openai import OpenAI

openai_expert = OpenAITeammate(
    name="gpt-analyst",
    agent_type="analyst",
    prompt="你是一个专业的AI分析师，擅长分析技术趋势和提供见解。",
    color="blue",
    api_key="your-openai-api-key",
    model="gpt-4"
)
openai_expert.set_team(team)
team.add_member(openai_expert)

# 或使用Claude
claude_expert = ClaudeTeammate(
    name="claude-architect",
    agent_type="architect",
    prompt="你是一个系统架构师，专注于设计可扩展的AI系统架构。",
    color="green",
    api_key="your-anthropic-api-key",
    model="claude-3-opus-20240229"
)
claude_expert.set_team(team)
team.add_member(claude_expert)

# 4. 创建并分配任务
task = lead.create_task(
    subject="分析2024年AI发展趋势",
    description="分析2024年AI领域的主要发展趋势，包括技术突破和应用场景",
    priority=TaskPriority.HIGH
)

lead.assign_task(task.task_id, openai_expert.agent_id)

# 5. 执行任务
result = openai_expert.execute_task(task)
print(result)

# 6. 生成报告
print(lead.generate_report())
'''
    
    print("LLM集成示例代码:")
    print(example_code)


if __name__ == "__main__":
    example_usage()
