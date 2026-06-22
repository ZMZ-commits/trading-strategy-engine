from setuptools import setup, find_packages

setup(
    name="trading-strategy-engine",
    version="0.1.0",
    packages=find_packages(exclude=["tests*"]),
    install_requires=["pydantic>=2.0", "pandas>=2.0", "numpy>=1.24"],
    python_requires=">=3.10",
)
