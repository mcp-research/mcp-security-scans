#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="mcp_security_scans",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "GitHubKit[auth-app]",
        "python-dotenv",
        "GitPython",
    ],
    extras_require={
        "dev": ["flake8>=7.2.0"],
    },
)