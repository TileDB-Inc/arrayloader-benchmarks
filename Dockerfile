FROM ubuntu
RUN apt-get update -y \
 && apt-get install -y cmake curl git python3 python3-pip wget

COPY install-conda.sh .
RUN ./install-conda.sh

ENV PATH=/root/miniconda3/condabin:$PATH
COPY environment.yml .
RUN conda env update -n env -f environment.yml --solver libmamba \
 && echo "conda activate env" >> ~/.bash_profile \
 && conda env list \
 && conda init bash \
 && echo "source ~/.bashrc" > ~/.bash_profile \
 && echo "conda activate env" >> ~/.bashrc

SHELL ["conda", "run", "-n", "env", "/bin/bash", "-c"]

COPY requirements.txt setup.py ./

COPY cellxgene-census/api/python/cellxgene_census/pyproject.toml cellxgene-census/api/python/cellxgene_census/pyproject.toml
COPY cellxgene-census/api/python/cellxgene_census/src/cellxgene_census/__init__.py cellxgene-census/api/python/cellxgene_census/src/cellxgene_census/__init__.py

COPY tiledb-soma/apis/python/setup.py tiledb-soma/apis/python/setup.py
COPY tiledb-soma/apis/python/pyproject.toml tiledb-soma/apis/python/pyproject.toml
COPY tiledb-soma/apis/python/version.py tiledb-soma/apis/python/version.py
COPY tiledb-soma/apis/python/README.md tiledb-soma/apis/python/README.md
COPY tiledb-soma/apis/python/requirements_dev.txt tiledb-soma/apis/python/requirements_dev.txt
COPY tiledb-soma/apis/python/dist_links tiledb-soma/apis/python/dist_links
COPY tiledb-soma/libtiledbsoma tiledb-soma/libtiledbsoma
COPY tiledb-soma/scripts tiledb-soma/scripts
COPY tiledb-soma/apis/python/src/tiledbsoma/__init__.py tiledb-soma/apis/python/src/tiledbsoma/__init__.py
COPY tiledb-soma/apis/python/src/tiledbsoma/*.h tiledb-soma/apis/python/src/tiledbsoma/*.cc tiledb-soma/apis/python/src/tiledbsoma/

RUN pip install \
    -e . \
    -e cellxgene-census/api/python/cellxgene_census \
    -e tiledb-soma/apis/python \
    awscli

COPY . .
