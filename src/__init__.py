__all__ = ["DenseRetriever", "GraphRetriever"]


def __getattr__(name):
    """Import optional retrieval dependencies only when that retriever is used."""
    if name == "DenseRetriever":
        from .dense_retrieval import DenseRetriever

        return DenseRetriever
    if name == "GraphRetriever":
        from .graph_retrieval import GraphRetriever

        return GraphRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
