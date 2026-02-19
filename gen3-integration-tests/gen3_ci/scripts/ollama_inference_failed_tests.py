import os
import subprocess

import requests
from dotenv import load_dotenv
from utils import logger

load_dotenv()


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
    response = requests.get("http://ollama:11434/api/tags")
    logger.info(response.json())
    return response.json()


if __name__ == "__main__":
    process = None
    try:
        process = setup_port_forwarding()
        assert "gemma:4b" in str(validate_ollama_model())
    except Exception as e:
        logger.error(f"Failed to run inference: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()
