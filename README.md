# Auto-PPT Agent

An AI Agent that automatically creates PowerPoint presentations from a single prompt using **MCP (Model Context Protocol)** architecture.

## Overview

This project demonstrates a production-grade agentic AI system that:

- **Plans** a presentation structure using an LLM
- **Executes** the plan step-by-step via MCP tool calls
- **Observes** each result before proceeding
- **Saves** a valid `.pptx` file

## Architecture

```
User Prompt
    |
    v
+---------------------+       stdio        +---------------------+
|   Agent (agent.py)  |<------------------>|  PPT MCP Server     |
|                     |    MCP Protocol     |  (ppt_server.py)    |
|  - plan(prompt)     |                     |                     |
|  - execute(plan)    |                     |  - create_pres()    |
|  - observe(result)  |                     |  - add_slide()      |
|                     |                     |  - save_pres()      |
|  Uses: HF LLM API  |                     |  - get_count()      |
+---------------------+                     +---------------------+
          |                                           |
          | stdio                                      |
          v                                            |
+---------------------+                                |
|  Search MCP Server  |   MCP Protocol                 |
|  (search_server.py) |<-------------------------------+
|  - search_web()     |
+---------------------+
          |
          v
    output/*.pptx
```

## Agentic Flow

```
PLAN --> RESEARCH (web search) --> CREATE PRESENTATION --> ADD SLIDE --> OBSERVE --> NEXT SLIDE --> ... --> SAVE FILE
```

1. **Planning Phase**: The LLM generates a structured JSON plan with slide titles and bullet points
2. **Research Phase**: The agent connects to the Search MCP Server, gathers real-world facts, and enhances bullets
3. **Execution Loop**: For each slide in the plan, the agent calls PPT MCP tools and observes results
4. **Observation**: After each tool call, the agent verifies the result (e.g., slide count matches)
5. **Save**: The final presentation is saved to the `output/` folder

## Tech Stack

- **Python 3.10+**
- **MCP (Model Context Protocol)** - Agent-to-tool communication
- **python-pptx** - PowerPoint file generation
- **Qwen2.5-72B-Instruct** - LLM via HuggingFace Inference API
- **duckduckgo-search** - Optional web search for enriched content

## Folder Structure

```
my_first_ppt_agent/
|-- agent/
|   |-- __init__.py
|   |-- config.py          # Environment variable loading
|   |-- mcp_client.py      # MCP client (connects to servers)
|   |-- agent.py           # Main agent (plan + execute + observe)
|   |-- test_llm.py        # LLM connection test
|-- mcp_servers/
|   |-- __init__.py
|   |-- ppt_server.py      # PPT MCP Server (4 tools)
|   |-- search_server.py   # Web Search MCP Server (bonus)
|   |-- test_ppt_tools.py  # Tool unit tests
|-- output/                # Generated .pptx files
|-- main.py                # Entry point
|-- requirements.txt
|-- .env                   # HF_API_KEY
```

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/my_first_ppt_agent.git
   cd my_first_ppt_agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv my_venv
   my_venv\Scripts\activate    # Windows
   # source my_venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file:
   ```
   HF_API_KEY="your_huggingface_api_key_here"
   ```

## Usage

### Generate a presentation
```bash
python main.py "Create a 5-slide presentation on AI in healthcare"
```

### Vague prompts work too
```bash
python main.py "Tell me about space"
```

### Custom slide count
```bash
python main.py "Make 7 slides about climate change"
```

### Interactive mode
```bash
python main.py
# Then type your prompt when asked
```

### Run tool tests
```bash
python -m mcp_servers.test_ppt_tools
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `create_presentation(title)` | Creates a new PPTX with a title slide (PPT Server) |
| `add_slide(title, bullets)` | Adds a content slide with 3-5 bullet points (PPT Server) |
| `save_presentation(filename)` | Saves the .pptx to output/ folder (PPT Server) |
| `get_slide_count()` | Returns current slide count for observation (PPT Server) |
| `search_web(query)` | Searches the web for topic facts (Search Server) |

## Robustness Features

- **5-strategy JSON fallback parsing** for unreliable LLM output
- **Automatic bullet validation**: 3-5 bullets, max 12 words each
- **Fallback plan generation** when the LLM fails completely
- **Graceful error handling** - never crashes, always produces output
- **Slide count verification** after each tool call
- **Smart topic extraction** from vague or complex prompts
