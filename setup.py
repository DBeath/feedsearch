#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from codecs import open

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, "feedsearch", "__version__.py"), "r", "utf-8") as f:
    exec(f.read(), about)

with open(os.path.join(here, "README.rst"), encoding="utf-8") as f:
    readme = f.read()

if sys.argv[-1] == "publish":
    os.system("python3 setup.py sdist bdist_wheel")
    os.system("twine upload dist/*")
    sys.exit()

packages = ["feedsearch"]

required = ["requests", "beautifulsoup4", "feedparser", "click", "Werkzeug"]

setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=readme,
    author=about["__author__"],
    author_email=about["__author_email__"],
    url=about["__url__"],
    license=about["__license__"],
    packages=packages,
    install_requires=required,
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    python_requires=">=3",
)
