import click


@click.group(context_settings=dict(max_content_width=120))
def cli():
    """Data-loading benchmarks for cellxgene-census and tiledbsoma."""
    pass
