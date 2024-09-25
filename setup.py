from setuptools import setup, find_packages

import re
version = re.search(
    '^__version__\s*=\s*"(.*)"', open("rapyuta_io_sdk_v2/__init__.py").read(), re.M
).group(1)

with open("README.md", encoding="utf-8") as f:
    long_desc = f.read()

setup(
    name="rapyuta_io_sdk_v2",
    version=version,
    description="Rapyuta.io Python SDK V2",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="Rapyuta Robotics",
    author_email="opensource@rapyuta-robotics.com",
    packages=find_packages(include=["rapyuta_io_sdk_v2*"]),
    python_requires=">=3.8",
    license="Apache 2.0",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    install_requires=[
        "httpx>=0.27.2",
        "pydantic-settings>=2.5.2",
        "python-benedict>=0.33.2",
        "pyyaml>=6.0.2",
        "setuptools>=75.1.0",
    ],
    extras_require={},
)
