#!/usr/bin/env python3
"""
RTL Debugger - 标准安装脚本

使用方式:
    pip install .              # 安装
    pip install -e .           # 开发模式
    pip install -e .[dev]      # 开发模式 + 开发依赖
"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# 读取 requirements
requirements = (this_directory / "requirements.txt").read_text(encoding='utf-8').splitlines()
requirements = [r.strip() for r in requirements if r.strip() and not r.startswith('#')]

setup(
    name='rtl_debugger',
    version='1.5.0',
    author='木叶村克劳',
    author_email='claude@example.com',
    description='RTL 波形分析调试工具 - 智能流式查询 + 深度分析 + 协议解析',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/lansongfu/rtl-debugger',
    project_urls={
        'Bug Tracker': 'https://github.com/lansongfu/rtl-debugger/issues',
        'Documentation': 'https://github.com/lansongfu/rtl-debugger#readme',
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Debuggers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    python_requires='>=3.10',
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.0',
            'pytest-cov>=4.0',
            'black>=23.0',
            'flake8>=6.0',
            'mypy>=1.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'rtl-debug=rtl_debugger.main:main',
            'rtl-debugger=rtl_debugger.main:main',
        ],
    },
    include_package_data=True,
    package_data={
        'rtl_debugger': ['*.md', '*.txt', '*.yaml'],
    },
)
