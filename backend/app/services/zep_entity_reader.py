"""
    Zep entity read-and-filter service.
Reads nodes from the Zep graph and keeps those matching predefined entity types.
"""

from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field
from zep_cloud import NotFoundError

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from ..utils.zep import call_zep_read_with_retry, get_zep_client

logger = get_logger('hivemind.zep_entity_reader')

# for generic return types
T = TypeVar('T')


@dataclass
class EntityNode:
    """Entity node data structure."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
        # related edge info
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
        # related other-node info
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """        Entity types (the default Entity label excluded)."""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """A filtered entity collection."""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
        Zep entity read-and-filter service.
    
        Main functions:
    1.     1. Read every node in the Zep graph
    2.     2. Keep nodes matching predefined entity types (labels beyond Entity)
    3.     3. Fetch each entity's related edges and neighbor nodes
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = get_zep_client(self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
                Zep API call with retries.
        
        Args:
                        func: zero-arg lambda/callable to run
                        operation_name: name used in logs
                        max_retries: retry cap (default 3 attempts total)
                        initial_delay: first backoff delay in seconds
            
        Returns:
                        The API call result.
        """
        return call_zep_read_with_retry(
            func,
            operation_name=operation_name,
            max_attempts=max_retries,
            initial_delay=initial_delay,
        )
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
                Get all nodes of a graph (paginated).

        Args:
                        graph_id: graph id

        Returns:
                        The node list.
        """
        logger.info(f"Fetching all nodes of graph {graph_id}...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"Fetched {len(nodes_data)} nodes")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
                Get all edges of a graph (paginated).

        Args:
                        graph_id: graph id

        Returns:
                        The edge list.
        """
        logger.info(f"Fetching all edges of graph {graph_id}...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"Fetched {len(edges_data)} edges")
        return edges_data
    
    def get_node_edges(
        self,
        node_uuid: str,
        *,
        graph_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
                Get a node's related edges.

                On Zep Cloud 3.25, ``graph.node.get_edges`` empirically returns only
                edges where the node is the source, despite docs saying "all edges".
                For full context pass graph_id: paginate the whole graph and filter
        
        Args:
                        node_uuid: node UUID
                        graph_id: graph id; when given, both directions are returned
            
        Returns:
                        The edge list.
        """
        try:
            if graph_id:
                return [
                    edge
                    for edge in self.get_all_edges(graph_id)
                    if edge["source_node_uuid"] == node_uuid
                    or edge["target_node_uuid"] == node_uuid
                ]

                        # call the Zep API with retries
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_edges(node_uuid=node_uuid),
                operation_name=f"get node edges(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            # An empty edge list is valid data. Authentication, permission and
            # transport failures must not be made indistinguishable from it.
            logger.error(f"Failed to get edges for node {node_uuid}: {str(e)}")
            raise
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
                Keep only nodes matching the predefined entity types.
        
                Filter logic:
        -         - a node whose only label is "Entity" fits no predefined type: skip it
        -         - labels beyond "Entity"/"Node" mean a predefined type: keep it
        
        Args:
                        graph_id: graph id
                        defined_entity_types: whitelist of types (optional; only these kept)
                        enrich_with_edges: also fetch each entity's related edges?
            
        Returns:
                        FilteredEntities: the filtered collection
        """
        logger.info(f"Filtering entities of graph {graph_id}...")
        
                # get all nodes
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
                # get all edges (for lookups later)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
                # map node UUID -> node data
        node_map = {n["uuid"]: n for n in all_nodes}
        
                # filter matching entities
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
                        # logic: labels must include something beyond "Entity"/"Node"
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                                # default label only: skip
                continue
            
                        # with a whitelist, check the type matches
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
                        # build the EntityNode
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            
                        # fetch related edges and nodes
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                                # neighbor node basic info
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        logger.info(f"Filtering done: {total_count} nodes total, {len(filtered_entities)} matched, "
                   f"entity types: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
                Get one entity with full context (edges + neighbors, with retries).
        
        Args:
                        graph_id: graph id
                        entity_uuid: entity UUID
            
        Returns:
                        EntityNode or None
        """
        try:
                        # fetch the node with retries
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"get node detail(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
                        # fetch the node's edges
            edges = self.get_node_edges(entity_uuid, graph_id=graph_id)
            
                        # fetch all nodes for neighbor lookups
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
                        # process related edges and nodes
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
                            # neighbor node info
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except NotFoundError:
            return None
        except Exception as e:
            # Only an actual Zep 404 means "entity not found". Propagate 401,
            # 403 and exhausted transport errors so callers cannot prepare a
            # simulation with silently incomplete graph context.
            logger.error(f"Failed to get entity {entity_uuid}: {str(e)}")
            raise
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
                Get all entities of a given type.
        
        Args:
                        graph_id: graph id
                        entity_type: type name (e.g. "Student", "PublicFigure")
            enrich_with_edges: also fetch related edges?
            
        Returns:
                        The entity list.
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
