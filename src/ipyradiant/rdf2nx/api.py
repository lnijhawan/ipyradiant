from typing import Dict, Union

from pandas import DataFrame
from networkx import MultiDiGraph
from rdflib import Graph as RDFGraph, Literal, URIRef
from rdflib.namespace import Namespace, NamespaceManager

from .converters import URItoID, URItoShortID
from .nodes import NodeIRIs, NodeProperties, NodeTypes
from .edges import ReifiedRelations, RelationProperties, RelationTypes
from .literal_map import LiteralMap, LiteralTyping


# TODO subclass from RDF2LPG and add adapters for NX/neo4j/etc.
class RDF2NX:
    """A class for converting RDF graphs to Networkx property graphs."""
    # Track converted predicates over classmethod calls
    converted_predicates = {}
    initNs = None

    # Queries TODO improve?
    node_iris = NodeIRIs
    node_properties = NodeProperties
    node_types = NodeTypes
    reified_relations = ReifiedRelations
    relation_properties = RelationProperties
    relation_types = RelationTypes

    @classmethod
    def process_properties(cls, iri: URIRef, properties: DataFrame) -> Dict:
        """Use a DataFrame of properties to create a dictionary of data for the
          networkx object.

        :param iri: the rdflib.term.URIRef of the node/edge
        :param properties: a DataFrame of properties
        :return: a dictionary of the processed properties
        """
        nx_properties = {"iri": iri}
        for group_predicate, group_df in properties.groupby(["predicate"]):
            group_values = group_df["value"].values

            if group_predicate not in cls.converted_predicates:
                cls.converted_predicates[group_predicate] = URItoShortID(
                    group_predicate,
                    ns=cls.initNs
                )

            # handle multiple predicate-objects
            if len(group_df) > 1:
                assert len(set(map(type,
                                   group_values))) == 1, \
                    "Values must all be of the same type."
                # Convert multiple values into a single cast_value
                # TODO map callable should be mapper for proper type in the future
                cast_value = tuple(map(str, group_values))
            else:
                # TODO use mapper to get proper type
                cast_value = str(group_values[0])

            nx_properties[cls.converted_predicates[group_predicate]] = cast_value

        return nx_properties

    @classmethod
    def transform_nodes(cls, rdf_graph: RDFGraph) -> Dict[URIRef, Dict]:
        """Returns node data for all nodes.

        TODO #59 & #60

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :return: dictionary (indexed by node IRI) containing the node data for networkx
        """
        node_data = {}

        # TODO paginate (LIMIT+OFFSET) and used to batch process the nodes in parallel?
        node_iris = NodeIRIs.run_query(rdf_graph)

        for node_iri in node_iris["iri"]:
            # print("Processing node w/ IRI:", node_iri)
            # Get the types for the node (must bind iri)
            types = NodeTypes.run_query(rdf_graph, iri=node_iri)
            # TODO use URItoShortID?
            # TODO this isn't actually used.
            #  Should this impact nx_graph differently than just the normal rdf:type?
            type_list = tuple(map(URItoID, types["type_"].values))

            # Get the properties for the node (must bind iri)
            properties = NodeProperties.run_query(rdf_graph, iri=node_iri)
            nx_node_properties = cls.process_properties(node_iri, properties)

            node_data[node_iri] = nx_node_properties

        return node_data

    @classmethod
    def transform_edges(cls, rdf_graph: RDFGraph) -> Dict[URIRef, Dict]:
        """Returns edge data for all edges.

        TODO #59 & #60

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :return: dictionary (indexed by node IRI) containing the edge data for networkx
        """
        edge_data = {}

        # Get properties for basic relationships
        # Overwrite namespace for fictitious IRI (uses base)
        RelationTypes.initNs = cls.initNs
        basic_relations = RelationTypes.run_query(rdf_graph)
        for iri, predicate, source, target in basic_relations.values:
            if predicate not in cls.converted_predicates:
                cls.converted_predicates[predicate] = URItoShortID(predicate, ns=cls.initNs)

            edge_data[iri] = {
                "source": source,
                "target": target,
                "attrs": {"_label": cls.converted_predicates[predicate]},
            }

        # Get properties for reified relations
        reified_relations = ReifiedRelations.run_query(rdf_graph)
        for iri, predicate, source, target in reified_relations.values:
            properties = RelationProperties.run_query(rdf_graph, iri=iri)
            nx_edge_properties = cls.process_properties(iri, properties)
            edge_data[iri] = {
                "source": source,
                "target": target,
                "attrs": nx_edge_properties,  # TODO add _label?
            }

        return edge_data

    @classmethod
    def convert(
            cls,
            rdf_graph: RDFGraph,
            namespaces: Union[NamespaceManager, Dict[str, Union[str, Namespace, URIRef]]] = None,
    ) -> MultiDiGraph:
        """The main method for converting an RDF graph to a networkx representation.

        :param rdf_graph: the rdflib.graph.Graph containing the raw data
        :param namespaces: the collection of namespaces used to simplify URIs
        :return: the networkx MultiDiGraph containing all collected node/edge data
        """
        if cls.initNs is None:
            if namespaces is None:
                namespaces = rdf_graph.namespaces
            cls.initNs = dict(namespaces)
            assert "base" in cls.initNs, "For conversion, namespaces must include a base namespace."

        nx_graph = MultiDiGraph()

        nodes = cls.transform_nodes(rdf_graph)
        edges = cls.transform_edges(rdf_graph)

        for node_iri, node_attrs in nodes.items():
            nx_graph.add_node(node_iri, **node_attrs)

        for edge_iri, edge_data in edges.items():
            try:
                edge_source = edge_data.get("source")
                edge_target = edge_data.get("target")
                edge_attrs = edge_data.get("attrs")
            except AttributeError:
                raise AttributeError("Test")

            if edge_source in nx_graph.nodes and edge_target in nx_graph.nodes:
                edge_attrs["iri"] = edge_iri
                nx_graph.add_edge(edge_source, edge_target, **edge_attrs)

        return nx_graph