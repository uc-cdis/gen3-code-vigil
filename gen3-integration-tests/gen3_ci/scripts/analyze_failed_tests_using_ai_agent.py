import asyncio
import os
import subprocess
import time

import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from utils import logger

load_dotenv()

SYSTEM_PROMPT = """You have access to MCP filesystem tools.

Rules:
- The allowed root directory is the Allure report root.
- Always use paths relative to the allowed root.
- Never use absolute paths.
- To analyze test results:
  1. Use list_directory on allure-report/data/test-cases
  2. Read each JSON file using read_file
  3. Extract tests where status == "failed"
  4. Return a structured summary including:
     - Test name (name field)
     - File name

Do not assume file contents. Always read files before answering.
"""


def setup_ollama_helm_chart():
    cmd = [
        "helm",
        "install",
        "ollama",
        "gen3_ci/ollama" "-n",
        os.getenv("NAMESPACE"),
    ]

    helm_install_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not helm_install_result.returncode == 0:
        raise Exception(
            f"Unable to install ollama. Error: {helm_install_result.stderr.strip()}"
        )

    cmd = [
        "kubectl",
        "wait",
        "--for=condition=ready",
        "pod",
        "-l",
        "app=ollama",
        "--timeout=5m",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    ollama_pod_ready_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not ollama_pod_ready_result.returncode == 0:
        raise Exception(
            f"Unable to install ollama. Error: {ollama_pod_ready_result.stderr.strip()}"
        )


def setup_port_forwarding():
    cmd = [
        "kubectl",
        "port-forward",
        "svc/ollama",
        "11434:11434",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process


def validate_ollama_model():
    response = requests.get("http://localhost:11434/api/tags")
    logger.info(response.json())
    return response.json()


async def run_test_failure_analysis():
    client = MultiServerMCPClient(
        {
            "filesystem": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "./allure-report",
                ],
            }
        }
    )

    tools = await client.get_tools()
    llm = ChatOllama(model="gemma:4b", temperature=0, base_url="http://localhost:11434")

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )

    response = await agent.ainvoke(
        {
            "messages": "Read all JSON files under ./allure-report/data/test-cases/ and summarize the failed tests with their names and error messages."
        }
    )
    logger.info(response)


if __name__ == "__main__":
    process = None
    try:
        # setup_ollama_helm_chart()
        process = setup_port_forwarding()
        time.sleep(10)
        assert "gemma:4b" in str(validate_ollama_model())
        asyncio.run(run_test_failure_analysis())
    except Exception as e:
        logger.info(f"Failed to run inference: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()
