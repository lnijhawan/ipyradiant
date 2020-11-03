# Copyright (c) 2020 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.
import traitlets as T

import ipywidgets as W
from rdflib import Graph, URIRef

from .custom_uri_ref import CustomURIRef
from .selection_widget import MultiPanelSelect


class ObjectLiteralApp(W.VBox):
    graph = T.Instance(Graph, allow_none=True)
    lit_button = T.Instance(W.Button)
    multiselect = T.Instance(MultiPanelSelect)
    namespaces = T.Dict(default_value={}, allow_none=True)

    def __init__(self, graph: Graph = None, *args, **kwargs):
        """
        This class is an example of how the MultiPanelSelect widget can be used in RDF
        graph manipulation. This application combines that MultiPanelSelect widget with a graph
        and a button that automatically moves certain predicates to the 'selected things' side via
        a set of queries and set analysis.

        This applciation inherits from the ipywidgets.VBox class as well.

        params:
        :graph: an rdflif.graph.Graph object, representing the graph to be queried on
        :namespaces: a python dict object that represents the list of namespaces one wishes to use
        with the current graph.
        """
        if graph is not None:
            kwargs["graph"] = graph
        if "layout" not in kwargs:
            kwargs["layout"] = {
                "min_height": "400px",
                "flex": "1",
            }
        super().__init__(*args, **kwargs)

        for key, value in self.namespaces.items():
            self.graph.namespace_manager.bind(key, value)

        self.lit_button.on_click(self.populate_predicates)
        self.children = [self.multiselect, self.lit_button]

    @T.default("graph")
    def make_default_graph(self):
        return Graph()

    @T.default("lit_button")
    def make_default_button(self):

        layout = W.Layout(width="300px", height="40px")  # set width and height

        button = W.Button(
            description="Add predicates where object is a literal",
            disabled=False,
            layout=layout,
        )

        return button

    @T.observe("graph")
    def _update_multiselect(self, change):
        self.multiselect = self.make_default_multiselect()

    @T.default("multiselect")
    def make_default_multiselect(self):
        self.all_preds = list(set(list(self.graph.predicates())))
        self.all_predicates = []
        for pred in self.all_preds:
            self.all_predicates.append(
                CustomURIRef(uri=pred, namespaces=self.graph.namespace_manager)
            )
        return MultiPanelSelect(
            data=self.all_predicates,
            left_panel_text="Available Predicates",
            right_panel_text="Predicates to Collapse",
        )

    def populate_predicates(self, b):
        """
        This is a class method that is activated when the 'add predicate where object is a literal' button
        is pressed. It runs two queries - one to find all predicates where object is not a literal and one to find
        all predicates where the object is a literal, and then takes the set difference between the two.

        This difference is then converted into what should go to each side of the multiselect, and subsequently
        passed to the CustomURIRef class in order to get a 'pretty' representation of the URIRef.
        """
        # query for all predicates where object is not literal
        predicates_to_uris = """
            SELECT DISTINCT  ?p
            WHERE {
                    ?s ?p ?o .
                FILTER (!isLiteral(?o))
                }
            """
        q1 = self.graph.query(predicates_to_uris)
        q1_results = set([result[0] for result in q1])

        # query for predicates where object IS literal
        predicates_to_literals = """
            SELECT DISTINCT  ?p
            WHERE {
                    ?s ?p ?o .
                FILTER isLiteral(?o)
                }
            """
        q2 = self.graph.query(predicates_to_literals)
        q2_results = set([result[0] for result in q2])
        # take difference of sets and turn to list

        selected_things = list(q2_results - q1_results)
        available_things = list(q1_results - q2_results)
        truncated_selected_uris = []
        truncated_available_uris = []
        for ref in selected_things:
            truncated_selected_uris.append(
                CustomURIRef(uri=ref, namespaces=self.graph.namespace_manager)
            )
        for ref in available_things:
            truncated_available_uris.append(
                CustomURIRef(uri=ref, namespaces=self.graph.namespace_manager)
            )
        # make sure things arent on both sides
        self.multiselect.available_things_list = truncated_available_uris
        self.multiselect.selected_things_list = truncated_selected_uris


def collapse_preds(netx_graph, preds_to_collapse, subjects):
    objects_found = set()
    for s, o in netx_graph.edges:

        for _, p, _ in netx_graph[s][o]["triples"]:

            if not isinstance(p, URIRef):
                raise ValueError(f"Predicate must be URIRef not a '{type(p)}'.")
            if p not in preds_to_collapse:
                continue

            # add data to subject node
            # TODO: custom representation?
            pred = p

            netx_graph.nodes[s][pred] = getattr(o, "value", o)

            # delete object node
            if o not in objects_found:
                objects_found.add(o)
            else:
                continue

    nodes_to_remove = objects_found - set(subjects)
    netx_graph.remove_nodes_from(nodes_to_remove)
    return netx_graph
