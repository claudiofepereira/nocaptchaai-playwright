from setuptools import setup, find_packages

setup(
    name="nocaptchaai_playwright",
    version="0.0.1",
    description="Playwright implementation of the NoCaptchaAI API",
    url="https://github.com/claudiofepereira/nocaptchaai-playwright",
    author="Cláudio Pereira",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "playwright>=1.32.1",
        "requests>=2.28.2",
    ],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
)
