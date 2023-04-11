from setuptools import setup, find_packages

setup(
    name="nocaptchaai_playwright",
    version="0.0.3",
    description="Playwright implementation of the NoCaptchaAI API",
    long_description="\n".join(DOCLINES[2:]),
    url="https://github.com/claudiofepereira/nocaptchaai-playwright",
    author="Cláudio Pereira",
    license="MIT",
    packages=["nocaptchaai_playwright"],
    install_requires=[
        "playwright",
        "requests",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
