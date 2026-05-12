import openai
import json
import requests

# 配置OpenAI API密钥（请替换为你的实际密钥）
openai.api_key = "YOUR_OPENAI_API_KEY"


def get_weather(city):
    """
    使用示例天气API获取指定城市的天气信息
    这里以WeatherAPI为例（请替换为有效的API）
    """
    # 替换为实际可用的天气API
    api_key = "YOUR_WEATHER_API_KEY"
    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={city}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        # 解析天气信息（示例：温度和天气状况）
        temp_c = data['current']['temp_c']
        condition = data['current']['condition']['text']
        return f"{city}当前温度{temp_c}℃，天气状况：{condition}"
    else:
        return "抱歉，未能获取天气信息。"


# 1. 定义函数描述（Function Description）
functions = [
    {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "需要查询天气的城市名称"
                }
            },
            "required": ["city"]
        }
    }
]

# 2. 发送用户请求（User Query）
response = openai.ChatCompletion.create(
    model="gpt-4-1106-preview",  # 支持函数调用的模型
    messages=[
        {"role": "user", "content": "北京今天的天气如何？"}
    ],
    tools=functions,
    tool_choice="auto"  # 让模型自行决定是否调用函数
)

# 3. 检查模型是否返回了函数调用
response_message = response["choices"][0]["message"]
if response_message.get("tool_calls"):
    # 解析函数调用信息
    tool_call = response_message["tool_calls"][0]
    function_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    # 4. 调用实际的函数
    if function_name == "get_weather":
        function_response = get_weather(arguments["city"])

    # 5. 将函数返回结果发送回模型
        second_response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "user", "content": "北京今天的天气如何？"},
                {"role": "tool", "content": function_response, "tool_call_id": tool_call["id"]}
            ]
        )

        final_answer = second_response["choices"][0]["message"]["content"]
        print("模型最终回复:", final_answer)
else:
    print("模型回复:", response_message["content"])
