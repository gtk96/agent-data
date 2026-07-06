"""
Setup script for agent-data package.
"""

from setuptools import setup, find_packages

setup(
    name="agent-data",
    version="0.1.0",
    description="A unified data access layer for AI Agent applications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Agent Data Team",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=1.10.0",
        "numpy>=1.21.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0.0",
            "mypy>=0.900",
        ],
        "postgres": ["asyncpg>=0.27.0"],
        "chroma": ["chromadb>=0.3.0"],
        "qdrant": ["qdrant-client>=1.3.0"],
        "api": ["aiohttp>=3.8.0"],
        "tracing": [
            "opentelemetry-api>=1.0.0",
            "opentelemetry-sdk>=1.0.0",
        ],
        "langchain": ["langchain>=0.1.0"],
        "llamaindex": ["llama-index>=0.10.0"],
        "all": [
            "agent-data[postgres,chroma,qdrant,api,tracing]",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
    ],
)