"""basic tooling widgets
"""

# Copyright (c) 2020 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.


__all__ = ["MultiPanelSelect", "CustomURIRef", "ObjectLiteralApp", "collapse_preds"]
from .custom_uri_ref import CustomURIRef
from .object_literal_collapsing import ObjectLiteralApp, collapse_preds
from .selection_widget import MultiPanelSelect
