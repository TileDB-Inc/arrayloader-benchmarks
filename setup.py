from os import environ, getcwd

from setuptools import setup, find_packages


cwd = getcwd()
reqs = open('requirements.txt').readlines()
# During development, better to install this library and these deps like:
# ```bash
# pip install -e . -e cellxgene-census/api/python/cellxgene_census -e tiledb-soma/apis/python
# ```
if environ.get('BENCHMARKS_INSTALL_LOCAL_DEPS'):
    reqs += [
        f"cellxgene_census @ file://localhost/{cwd}/cellxgene-census/api/python/cellxgene_census",
        f"tiledbsoma @ file://localhost/{cwd}/tiledb-soma/apis/python",
    ]

setup(
    name="arrayloader-benchmarks",
    version="0.0.1",
    install_requires=reqs,
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'alb = benchmarks.cli.main:cli',
        ],
    },
)
