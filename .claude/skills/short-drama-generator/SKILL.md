---
name: "short-drama-generator"
description: "整合文学IP分析、微短剧叙事、影视化转换、人物塑造、剧本格式化、市场分析、硅基流动API集成和UI组件等技能，实现完整的网络文学微短剧剧本生成系统，支持API密钥输入、剧本生成和下载功能。"
---

# 微短剧剧本生成器

## 功能描述

该技能整合了所有子技能，实现了完整的网络文学微短剧剧本生成系统，包括：

1. **技能组合逻辑**：将各个子技能有机组合，形成完整的剧本生成流程
2. **完整生成流程**：从文学IP分析到最终剧本生成和下载的全流程
3. **硅基流动API集成**：调用硅基流动API实现AI模型生成
4. **用户友好界面**：提供直观的UI界面，支持API密钥输入和参数设置
5. **多格式下载**：支持Word、PDF和纯文本格式的剧本下载
6. **响应式设计**：适配不同屏幕尺寸和设备

## 工作流程

```
1. 用户输入API密钥 → 2. 输入网络文学内容 → 3. 设置生成参数 → 4. 启动生成流程 → 5. 文学IP分析 → 6. 微短剧叙事设计 → 7. 影视化转换 → 8. 人物塑造 → 9. 剧本格式化 → 10. 市场分析优化 → 11. 生成最终剧本 → 12. 提供下载选项
```

## 技能组合逻辑

该系统采用模块化设计，各个子技能之间通过明确的输入输出接口进行交互，形成完整的工作流：

| 阶段 | 主要技能 | 输入 | 输出 |
|------|----------|------|------|
| 1. IP分析 | literary-ip-analysis | 网络文学内容 | 核心卖点、故事框架、人物关系 |
| 2. 叙事设计 | short-drama-narration | IP分析结果 | 分集大纲、叙事结构、悬念设计 |
| 3. 影视化转换 | visualization-conversion | 叙事设计结果 | 场景设计、镜头调度、动作设计 |
| 4. 人物塑造 | character-development | 影视化转换结果 | 核心人设、行为设计、人物弧光 |
| 5. 剧本生成 | silicon-flow-api | 人物塑造结果 | 初稿剧本 |
| 6. 剧本格式化 | script-formatting | 初稿剧本 | 标准格式剧本 |
| 7. 市场优化 | market-analysis | 标准格式剧本 | 优化后的最终剧本 |
| 8. UI交互 | ui-components | 最终剧本 | 可下载的剧本文件 |

## 技术实现

### 核心代码结构

```python
class ShortDramaGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.skills = {
            'ip_analysis': LiteraryIPAnalysis(),
            'narration': ShortDramaNarration(),
            'visualization': VisualizationConversion(),
            'character': CharacterDevelopment(),
            'script_formatting': ScriptFormatting(),
            'market_analysis': MarketAnalysis(),
            'silicon_flow': SiliconFlowAPI(api_key)
        }
    
    def generate_script(self, novel_content, params):
        # 1. 文学IP分析
        ip_analysis_result = self.skills['ip_analysis'].analyze(novel_content)
        
        # 2. 微短剧叙事设计
        narration_result = self.skills['narration'].design(ip_analysis_result, params)
        
        # 3. 影视化转换
        visualization_result = self.skills['visualization'].convert(narration_result)
        
        # 4. 人物塑造
        character_result = self.skills['character'].develop(visualization_result)
        
        # 5. 使用硅基流动API生成初稿
        prompt = self._build_prompt(character_result, params)
        draft_script = self.skills['silicon_flow'].call_model(
            model='gpt-4',
            prompt=prompt,
            temperature=params['temperature'],
            max_tokens=params['max_tokens']
        )
        
        # 6. 剧本格式化
        formatted_script = self.skills['script_formatting'].format(draft_script)
        
        # 7. 市场分析优化
        final_script = self.skills['market_analysis'].optimize(formatted_script, params)
        
        return final_script
    
    def _build_prompt(self, character_result, params):
        # 构建适合AI模型的提示词
        pass
    
    def download_script(self, script_content, format):
        # 生成可下载的剧本文件
        return self.skills['script_formatting'].generate_download_link(script_content, format)
```

### API集成

```python
class SiliconFlowAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://api.siliconflow.cn/v1'
    
    def call_model(self, model, prompt, temperature=0.7, max_tokens=2000):
        import requests
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': '你是一名专业的微短剧编剧，擅长将网络文学改编为微短剧剧本。'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        response = requests.post(f'{self.base_url}/chat/completions', headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
```

## UI界面实现

该系统提供了完整的UI界面，包括：

1. **API密钥输入窗口**：首次使用时自动弹出，支持密钥保存和测试
2. **剧本生成界面**：包含输入区域、参数设置和操作按钮
3. **参数设置面板**：支持调整题材类型、集数、时长、创意度等参数
4. **进度显示**：实时显示剧本生成进度
5. **结果展示**：清晰展示生成的剧本内容
6. **下载功能**：支持多种格式的剧本下载

## 使用说明

### 1. 初始化设置

- 首次使用时，系统会自动弹出API密钥输入窗口
- 输入您的硅基流动API密钥并保存
- 可以随时点击设置按钮修改API密钥

### 2. 生成剧本

1. 在输入框中粘贴或输入网络文学内容
2. 调整生成参数：
   - 题材类型：甜宠、悬疑、都市、古装等
   - 集数：1-24集
   - 每集时长：5-20分钟
   - 创意度：0-1之间，数值越高创意越强
3. 点击"生成剧本"按钮
4. 等待生成完成，查看进度条

### 3. 下载剧本

- 生成完成后，在结果区域会显示生成的剧本
- 选择您需要的格式（Word、PDF或纯文本）
- 点击对应下载按钮
- 下载生成的剧本文件

## 配置选项

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| api_key | 硅基流动API密钥 | 无（首次使用需输入） |
| model | 使用的AI模型 | gpt-4 |
| temperature | 创意度 | 0.7 |
| max_tokens | 最大生成 tokens | 2000 |
| genre | 题材类型 | 甜宠 |
| episodes | 集数 | 12 |
| duration | 每集时长（分钟） | 10 |

## 技术栈

- **后端**：Python FastAPI
- **前端**：HTML、CSS、JavaScript
- **AI模型**：硅基流动API（支持gpt-4等多种模型）
- **文件处理**：python-docx、PyPDF2
- **部署**：支持本地部署和云服务器部署

## 注意事项

1. **API密钥安全**：请妥善保管您的API密钥，避免泄露
2. **成本控制**：合理设置生成参数，控制API调用成本
3. **内容审核**：生成的剧本可能需要人工审核，确保符合相关规定
4. **版权问题**：请确保您有权使用输入的网络文学内容
5. **浏览器兼容性**：建议使用Chrome、Firefox、Safari等现代浏览器

## 扩展功能

该系统支持以下扩展功能：

1. **多语言支持**：可扩展支持多种语言
2. **自定义模板**：支持自定义剧本格式模板
3. **批量生成**：支持批量生成多集剧本
4. **协作功能**：支持多人协作编辑和审核
5. **数据分析**：提供生成数据和市场分析报告

## 示例输出

```
【集数】第1集
【标题】命运的邂逅
【时长】12分钟

【场号】1
【场景】都市街头/咖啡店外
【时间】上午10点
【人物】林晓（28岁，职场女性）、陈阳（30岁，创业公司CEO）

【动作】林晓抱着文件急匆匆地走在街头，不小心撞到了正在打电话的陈阳。文件散落一地，陈阳的手机也掉在了地上。
【林晓】（道歉）对不起！我赶时间，没看路。
【陈阳】（弯腰捡手机，抬头认出对方）林晓？是你吗？

【场号】2
【场景】XX咖啡馆
【时间】白天
【人物】林晓、陈阳

【动作】两人坐在咖啡馆里，林晓搅动着咖啡，神情焦虑。
【陈阳】怎么了？看你这么着急。
【林晓】（叹气）我遇到麻烦了...
```

该技能整合了所有子技能，实现了从网络文学到微短剧剧本的完整生成流程，为用户提供了一个高效、便捷的微短剧剧本生成工具。