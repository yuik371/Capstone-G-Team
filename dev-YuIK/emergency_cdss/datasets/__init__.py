"""Dataset loaders used by Emergency CDSS experiments.

Import concrete loaders from their module rather than importing every optional
dataset here. This keeps package discovery lightweight as new modalities are
added.
"""

__all__ = ["wound_dataset", "burn_dataset", "landmark_dataset"]

