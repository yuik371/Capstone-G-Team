"""Emergency CDSS machine-learning package.

The package is intentionally split by responsibility so that image datasets,
structured clinical data, and future multimodal models can evolve without
turning the training entry point into a monolithic script.
"""

__all__ = ["datasets", "models", "utils"]

