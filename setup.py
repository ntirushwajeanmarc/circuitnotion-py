from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="circuitnotion",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="IoT library for connecting Raspberry Pi to CircuitNotion platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/circuitnotion-py",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/circuitnotion-py/issues",
        "Documentation": "https://github.com/yourusername/circuitnotion-py#readme",
        "Source Code": "https://github.com/yourusername/circuitnotion-py",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Hardware",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.7",
    install_requires=[
        "websockets>=10.0",
    ],
    extras_require={
        "gpio": ["RPi.GPIO>=0.7.0"],
        "sensors": [
            "adafruit-circuitpython-dht",
            "adafruit-blinka",
        ],
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "flake8>=4.0",
        ],
    },
    keywords="iot raspberry-pi gpio sensors websocket home-automation",
    include_package_data=True,
    zip_safe=False,
)