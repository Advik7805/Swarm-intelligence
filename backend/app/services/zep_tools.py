"""
Zep retrieval tool service.
Wraps graph search, node reading, and edge queries for the Report Agent.

Core retrieval tools (optimized):
1. InsightForge (deep insight) - strongest hybrid retrieval; auto-generates sub-queries and searches multiple dimensions
2. PanoramaSearch (breadth) - full view, incl. expired content
3. QuickSearch (simple) - fast retrieval
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from zep_cloud import NotFoundError

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_locale, t
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from ..utils.zep import (
    call_zep_read_with_retry,
    get_zep_client,
    normalize_zep_search_limit,
    normalize_zep_search_query,
)

logger = get_logger('hivemind.zep_tools')


@dataclass
class SearchResult:
    """Search result."""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """Convert to a text format for LLM consumption."""
        text_parts = [f"Search query: {self.query}", f"Found {self.total_count} related facts"]
        
        if self.facts:
            text_parts.append("\n### Related facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node info."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """Convert to text format."""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "unknown type")
        return f"Entity: {self.name} (type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge info."""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # temporal info
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """Convert to text format."""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relation: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "unknown"
            invalid_at = self.invalid_at or "present"
            base_text += f"\nValidity: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (expired: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """Whether expired."""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """Whether invalidated."""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    InsightForge result.
    Contains per-sub-question retrieval results plus a synthesis.
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # per-dimension results
    semantic_facts: List[str] = field(default_factory=list)  # semantic search results
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # entity insights
    relationship_chains: List[str] = field(default_factory=list)  # relation chains
    
    # stats
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """Convert to a detailed text format for LLM consumption."""
        text_parts = [
            f"## Deep Future-Prediction Analysis",
            f"Analysis question: {self.query}",
            f"Prediction scenario: {self.simulation_requirement}",
            f"\n### Prediction data stats",
            f"- Relevant prediction facts: {self.total_facts}",
            f"- Involved entities: {self.total_entities}",
            f"- Relation chains: {self.total_relationships}"
        ]
        
        # sub-questions
        if self.sub_queries:
            text_parts.append(f"\n### Sub-questions analyzed")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # semantic search results
        if self.semantic_facts:
            text_parts.append(f"\n### [Key Facts] (quote these verbatim in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # entity insights
        if self.entity_insights:
            text_parts.append(f"\n### [Core Entities]")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'unknown')}** ({entity.get('type', 'entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  Summary: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  Related facts: {len(entity.get('related_facts', []))}")
        
        # relation chains
        if self.relationship_chains:
            text_parts.append(f"\n### [Relation Chains]")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Panorama search result.
    Contains all related info, incl. expired content.
    """
    query: str
    
    # all nodes
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # all edges (incl. expired)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # currently valid facts
    active_facts: List[str] = field(default_factory=list)
    # expired/invalidated facts (historical record)
    historical_facts: List[str] = field(default_factory=list)
    
    # stats
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """Convert to text format (full version, no truncation)."""
        text_parts = [
            f"## Panorama Search Results (full future view)",
            f"Query: {self.query}",
            f"\n### Stats",
            f"- Total nodes: {self.total_nodes}",
            f"- Total edges: {self.total_edges}",
            f"- Currently valid facts: {self.active_count}",
            f"- Historical/expired facts: {self.historical_count}"
        ]
        
        # currently valid facts (full output, no truncation)
        if self.active_facts:
            text_parts.append(f"\n### [Currently Valid Facts] (verbatim simulation output)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # historical/expired facts (full output, no truncation)
        if self.historical_facts:
            text_parts.append(f"\n### [Historical/Expired Facts] (evolution record)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # key entities (full output, no truncation)
        if self.all_nodes:
            text_parts.append(f"\n### [Involved Entities]")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Interview result for a single agent."""
    agent_name: str
    agent_role: str  # role type (student, teacher, media, etc.)
    agent_bio: str  # bio
    question: str  # interview question
    response: str  # interview answer
    key_quotes: List[str] = field(default_factory=list)  # key quotes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # show the full agent_bio, no truncation
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key quotes:**\n"
            for quote in self.key_quotes:
                # strip various quote styles
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # strip leading punctuation
                while clean_quote and clean_quote[0] in ',,;::.!?\n\r\t ':
                    clean_quote = clean_quote[1:]
                # filter junk containing question numbers (Question 1-9)
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # trim overlong content (at sentence ends, not hard cuts)
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview result.
    Contains interview answers from multiple simulated agents.
    """
    interview_topic: str  # interview topic
    interview_questions: List[str]  # question list
    
    # agents chosen for interview
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # per-agent interview answers
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # why these agents were chosen
    selection_reasoning: str = ""
    # consolidated interview summary
    summary: str = ""
    
    # stats
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """Convert to a detailed text format for LLM consumption and report quoting."""
        text_parts = [
            "## In-Depth Interview Report",
            f"**Interview topic:** {self.interview_topic}",
            f"**Interviewees:** {self.interviewed_count} / {self.total_agents} simulated agents",
            "\n### Selection Reasoning",
            self.selection_reasoning or "(auto-selected)",
            "\n---",
            "\n### Interview Transcripts",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(no interview records)\n\n---")

        text_parts.append("\n### Interview Summary & Key Takeaways")
        text_parts.append(self.summary or "(no summary)")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep retrieval tool service.
    
    [Core retrieval tools - optimized]
    1. insight_forge - deep insight retrieval (strongest; auto sub-queries, multi-dimension)
    2. panorama_search - breadth search (full view, incl. expired content)
    3. quick_search - simple search (fast retrieval)
    4. interview_agents - in-depth interviews (multi-perspective views from simulated agents)
    
    [Base tools]
    - search_graph - graph semantic search
    - get_all_nodes - fetch every node in the graph
    - get_all_edges - fetch every edge (with temporal info)
    - get_node_detail - node details
    - get_node_edges - edges connected to a node
    - get_entities_by_type - entities by type
    - get_entity_summary - relation summary for an entity
    """
    
    # retry config
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        
        self.client = get_zep_client(self.api_key)
        # LLM client used by InsightForge for sub-query generation
        self._llm_client = llm_client
        logger.info(t("console.zepToolsInitialized"))
    
    @property
    def llm(self) -> LLMClient:
        """Lazy-init the LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """Retry one safe read using typed Zep/HTTPX error classification."""

        return call_zep_read_with_retry(
            func,
            operation_name=operation_name,
            max_attempts=max_retries or self.MAX_RETRIES,
            initial_delay=self.RETRY_DELAY,
        )
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search.
        
        Uses hybrid search (semantic + BM25) over the graph.
        Falls back to local keyword matching if the Zep Cloud search API is unavailable.
        
        Args:
            graph_id: graph ID (Standalone Graph)
            query: search query
            limit: max results
            scope: "edges" or "nodes"
            
        Returns:
            SearchResult: the search results
        """
        logger.info(t("console.graphSearch", graphId=graph_id, query=query[:50]))
        
        zep_query = normalize_zep_search_query(query)
        zep_limit = normalize_zep_search_limit(limit)

        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=zep_query,
                    limit=zep_limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=t("console.graphSearchOp", graphId=graph_id)
            )
            
            facts = []
            edges = []
            nodes = []
            
            # parse edge search results
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # parse node search results
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # node summaries count as facts too
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.searchComplete", count=len(facts)))
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            # Authentication, invalid input, missing graphs, and exhausted
            # transient failures must remain visible to the report workflow.
            logger.error(t("console.zepSearchApiFallback", error=str(e)))
            raise
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword-match search (fallback when the Zep Search API is unavailable).
        
        Fetches all edges/nodes, then matches keywords locally.
        
        Args:
            graph_id: graph ID
            query: search query
            limit: max results
            scope: search scope
            
        Returns:
            SearchResult: the search results
        """
        logger.info(t("console.usingLocalSearch", query=query[:30]))
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # extract query keywords (simple tokenization)
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(",", " ").replace(chr(0xFF0C), " ").split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """Score how well text matches the query."""
            if not text:
                return 0
            text_lower = text.lower()
            # exact query match
            if query_lower in text_lower:
                return 100
            # keyword matches
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # fetch all edges and match
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # sort by score
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # fetch all nodes and match
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(t("console.localSearchComplete", count=len(facts)))
            
        except Exception as e:
            logger.error(t("console.localSearchFailed", error=str(e)))
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Fetch all nodes in the graph (paginated).

        Args:
            graph_id: graph ID

        Returns:
            List of nodes
        """
        logger.info(t("console.fetchingAllNodes", graphId=graph_id))

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(t("console.fetchedNodes", count=len(result)))
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        Fetch all edges in the graph (paginated, with temporal info).

        Args:
            graph_id: graph ID
            include_temporal: include temporal info (default True)

        Returns:
            List of edges (with created_at, valid_at, invalid_at, expired_at)
        """
        logger.info(t("console.fetchingAllEdges", graphId=graph_id))

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # attach temporal info
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(t("console.fetchedEdges", count=len(result)))
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Get details for a single node.
        
        Args:
            node_uuid: node UUID
            
        Returns:
            Node info or None
        """
        logger.info(t("console.fetchingNodeDetail", uuid=node_uuid[:8]))
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=t("console.fetchNodeDetailOp", uuid=node_uuid[:8])
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(t("console.fetchNodeDetailFailed", error=str(e)))
            raise
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Fetch all edges connected to a node.
        
        Fetches all graph edges, then filters those touching the given node.
        
        Args:
            graph_id: graph ID
            node_uuid: node UUID
            
        Returns:
            List of edges
        """
        logger.info(t("console.fetchingNodeEdges", uuid=node_uuid[:8]))
        
        try:
            # fetch all edges, then filter
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # keep edges where the node is source or target
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(t("console.foundNodeEdges", count=len(result)))
            return result
            
        except Exception as e:
            logger.error(t("console.fetchNodeEdgesFailed", error=str(e)))
            raise
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        Fetch entities by type.
        
        Args:
            graph_id: graph ID
            entity_type: entity type (e.g. Student, PublicFigure)
            
        Returns:
            Entities matching the type
        """
        logger.info(t("console.fetchingEntitiesByType", type=entity_type))
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # check whether labels contain the requested type
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(t("console.foundEntitiesByType", count=len(filtered), type=entity_type))
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Build a relation summary for the given entity.
        
        Searches all info related to the entity and produces a summary.
        
        Args:
            graph_id: graph ID
            entity_name: entity name
            
        Returns:
            Entity summary info
        """
        logger.info(t("console.fetchingEntitySummary", name=entity_name))
        
        # first search for info related to this entity
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # try to locate the entity among all nodes
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # pass the graph_id parameter
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Get graph statistics.
        
        Args:
            graph_id: graph ID
            
        Returns:
            Stats info
        """
        logger.info(t("console.fetchingGraphStats", graphId=graph_id))
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # entity type distribution
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # relation type distribution
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Gather simulation-related context info.
        
        Searches everything related to the simulation requirement.
        
        Args:
            graph_id: graph ID
            simulation_requirement: simulation requirement text
            limit: per-category result cap
            
        Returns:
            Simulation context info
        """
        logger.info(t("console.fetchingSimContext", requirement=simulation_requirement[:50]))
        
        # search info related to the simulation requirement
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # graph stats
        stats = self.get_graph_statistics(graph_id)
        
        # fetch all entity nodes
        all_nodes = self.get_all_nodes(graph_id)
        
        # keep entities with a real type (not bare Entity nodes)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # cap the count
            "total_entities": len(entities)
        }
    
    # ========== Core retrieval tools (optimized) ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        [InsightForge - deep insight retrieval]
        
        The strongest hybrid retrieval; decomposes the question and searches multiple dimensions:
        1. Uses an LLM to split the question into sub-questions
        2. Semantic search per sub-question
        3. Extracts related entities and fetches their details
        4. Traces relation chains
        5. Consolidates everything into deep insight
        
        Args:
            graph_id: graph ID
            query: user question
            simulation_requirement: simulation requirement text
            report_context: report context (optional; improves sub-query generation)
            max_sub_queries: max sub-questions
            
        Returns:
            InsightForgeResult: deep insight retrieval results
        """
        logger.info(t("console.insightForgeStart", query=query[:50]))
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: generate sub-questions with the LLM
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(t("console.generatedSubQueries", count=len(sub_queries)))
        
        # Step 2: semantic search per sub-question
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # also search the original question
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: extract related entity UUIDs from edges; fetch only those entities
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # fetch details for all related entities (unlimited, full output)
        entity_insights = []
        node_map = {}  # used later for relation-chain building
        
        for uuid in list(entity_uuids):  # process all entities, no truncation
            if not uuid:
                continue
            try:
                # fetch each related node individually
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "entity")
                    
                    # fetch all facts for this entity (no truncation)
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # full output, no truncation
                    })
            except Exception as e:
                logger.debug(f"Failed to fetch node {uuid}: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: build all relation chains (unlimited)
        relationship_chains = []
        for edge_data in all_edges:  # process all edges, no truncation
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(t("console.insightForgeComplete", facts=result.total_facts, entities=result.total_entities, relationships=result.total_relationships))
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        Generate sub-questions with an LLM.
        
        Breaks a complex question into independently searchable sub-questions.
        """
        system_prompt = """You are an expert question analyst. Your task is to decompose a complex question into several sub-questions that can each be observed independently in the simulated world.

Requirements:
1. Each sub-question must be specific enough to find related agent behavior or events in the simulated world
2. Sub-questions should cover different dimensions of the original question (who, what, why, how, when, where)
3. Sub-questions must stay relevant to the simulation scenario
4. Return JSON: {"sub_queries": ["sub-question 1", "sub-question 2", ...]}"""

        user_prompt = f"""Simulation requirement background:
{simulation_requirement}

{f"Report context: {report_context[:500]}" if report_context else ""}

Please decompose the following question into {max_queries} sub-questions:
{query}

Return the sub-question list as JSON."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # ensure a list of strings
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(t("console.generateSubQueriesFailed", error=str(e)))
            # fallback: return variants of the original question
            return [
                query,
                f"main participants of {query}",
                f"causes and effects of {query}",
                f"how {query} developed over time"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        [PanoramaSearch - breadth search]
        
        Builds a full-view snapshot, incl. all related content and historical/expired info:
        1. Fetches all related nodes
        2. Fetches all edges (incl. expired/invalidated)
        3. Classifies facts into currently-valid vs historical
        
        Best for understanding the full picture and tracing how events evolved.
        
        Args:
            graph_id: graph ID
            query: search query (used for relevance ranking)
            include_expired: include expired content (default True)
            limit: max results
            
        Returns:
            PanoramaResult: panorama search results
        """
        logger.info(t("console.panoramaSearchStart", query=query[:50]))
        
        result = PanoramaResult(query=query)
        
        # fetch all nodes
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # fetch all edges (with temporal info)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # classify facts
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # attach entity names to facts
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # expired/invalidated check
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # historical/expired fact - tag with timestamps
                valid_at = edge.valid_at or "unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # currently valid fact
                active_facts.append(edge.fact)
        
        # relevance ranking against the query
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace(chr(0xFF0C), " ").split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # sort and cap the count
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(t("console.panoramaSearchComplete", active=result.active_count, historical=result.historical_count))
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        [QuickSearch - simple search]
        
        Fast, lightweight retrieval:
        1. Calls Zep semantic search directly
        2. Returns the most relevant results
        3. Best for simple, direct lookups
        
        Args:
            graph_id: graph ID
            query: search query
            limit: max results
            
        Returns:
            SearchResult: search results
        """
        logger.info(t("console.quickSearchStart", query=query[:50]))
        
        # delegate to the existing search_graph method
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(t("console.quickSearchComplete", count=result.total_count))
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        [InterviewAgents - in-depth interviews]
        
        Calls the real OASIS interview API to interview running simulation agents:
        1. Reads persona files to learn all simulated agents
        2. Uses an LLM to analyze the interview need and pick the most relevant agents
        3. Generates interview questions with an LLM
        4. Calls /api/simulation/interview/batch for real interviews (dual-platform)
        5. Consolidates all interview results into a report
        
        [Important] Requires a running simulation (OASIS environment still up)
        
        [Use cases]
        - Understanding the event from different role perspectives
        - Collecting opinions from multiple parties
        - Getting real simulated-agent answers (not LLM-faked)
        
        Args:
            simulation_id: simulation ID (locates persona files and the interview API)
            interview_requirement: interview need (unstructured, e.g. "learn student views on the event")
            simulation_requirement: simulation background (optional)
            max_agents: max agents to interview
            custom_questions: custom questions (optional; auto-generated if omitted)
            
        Returns:
            InterviewResult: interview results
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(t("console.interviewAgentsStart", requirement=interview_requirement[:50]))
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: read persona files
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(t("console.profilesNotFound", simId=simulation_id))
            result.summary = "No interviewable agent persona files found"
            return result
        
        result.total_agents = len(profiles)
        logger.info(t("console.loadedProfiles", count=len(profiles)))
        
        # Step 2: pick interviewees with the LLM (returns agent_id list)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(t("console.selectedAgentsForInterview", count=len(selected_agents), indices=selected_indices))
        
        # Step 3: generate interview questions (if not provided)
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(t("console.generatedInterviewQuestions", count=len(result.interview_questions)))
        
        # merge questions into one interview prompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # add an optimizing prefix constraining the agent reply format
        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Drawing on your persona, all past memories and actions,\n"
            "answer the following questions directly in plain text.\n"
            "Reply rules:\n"
            "1. Answer in natural language; do not call any tools\n"
            "2. Do not return JSON or tool-call formats\n"
            "3. Do not use Markdown headings (e.g. #, ##, ###)\n"
            "4. Answer each question in order, starting every answer with 'Question X:' (X = question number)\n"
            "5. Separate answers with blank lines\n"
            "6. Give substantive answers - at least 2-3 sentences per question\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: call the real interview API (no platform => dual-platform by default)
        try:
            # build the batch interview list (no platform => dual-platform)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # use the optimized prompt
                    # no platform given: the API interviews on both twitter and reddit
                })
            
            logger.info(t("console.callingBatchInterviewApi", count=len(interviews_request)))
            
            # call SimulationRunner's batch interview method (no platform => dual-platform)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # no platform => dual-platform
                timeout=180.0   # dual-platform needs a longer timeout
            )
            
            logger.info(t("console.interviewApiReturned", count=api_result.get('interviews_count', 0), success=api_result.get('success')))
            
            # check API success
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "unknown error")
                logger.warning(t("console.interviewApiReturnedFailure", error=error_msg))
                result.summary = f"Interview API call failed: {error_msg}. Check the OASIS simulation environment status."
                return result
            
            # Step 5: parse API results into AgentInterview objects
            # dual-platform response shape: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "unknown")
                agent_bio = agent.get("bio", "")
                
                # this agent's answers on both platforms
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # strip possible JSON tool-call wrappers
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # always emit dual-platform markers
                twitter_text = twitter_response if twitter_response else "(no reply on this platform)"
                reddit_text = reddit_response if reddit_response else "(no reply on this platform)"
                response_text = f"[Twitter answer]\n{twitter_text}\n\n[Reddit answer]\n{reddit_text}"

                # extract key quotes (from both platform answers)
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # clean the response: strip markers, numbering, Markdown noise
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'Question\s*\d+\s*[.:：]\s*', '', clean_text)
                clean_text = re.sub(r'\[[^\]]+\]', '', clean_text)

                # strategy 1 (primary): pull complete, substantive sentences
                sentences = re.split(r'[.!?。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W,,;::.!?、]+', s.strip())
                    and not s.strip().startswith(('{', 'Question'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "." for s in meaningful[:3]]

                # strategy 2 (supplementary): long spans inside paired quotes
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[,，;；:.、]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # raised bio length cap
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # simulation not running
            logger.warning(t("console.interviewApiCallFailed", error=e))
            result.summary = f"Interview failed: {str(e)}. The simulation may have shut down; make sure the OASIS environment is running."
            return result
        except Exception as e:
            logger.error(t("console.interviewApiCallException", error=e))
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"Error during interviewing: {str(e)}"
            return result
        
        # Step 6: generate the interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(t("console.interviewAgentsComplete", count=result.interviewed_count))
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Strip JSON tool-call wrappers from an agent reply, keeping the actual content."""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load the simulation's agent persona files."""
        import os
        import csv
        
        # build persona file paths
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # try the Reddit JSON format first
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(t("console.loadedRedditProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readRedditProfilesFailed", error=e))
        
        # try the Twitter CSV format
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # convert CSV rows to the unified format
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "unknown"
                        })
                logger.info(t("console.loadedTwitterProfiles", count=len(profiles)))
                return profiles
            except Exception as e:
                logger.warning(t("console.readTwitterProfilesFailed", error=e))
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        Select interviewees with an LLM.
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: full info of the chosen agents
                - selected_indices: chosen indices (used for the API call)
                - reasoning: why these agents
        """
        
        # build the agent summary list
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """You are an expert interview planner. Given an interview requirement, pick the best interviewees from the simulated agent list.

Selection criteria:
1. The agent's identity/profession relates to the interview topic
2. The agent may hold unique or valuable views
3. Pick diverse perspectives (supporters, opponents, neutrals, professionals, etc.)
4. Prefer roles directly involved in the event

Return JSON:
{
    "selected_indices": [indices of the chosen agents],
    "reasoning": "explanation of the selection"
}"""

        user_prompt = f"""Interview requirement:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "not provided"}

Available agents ({len(agent_summaries)} total):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Pick up to {max_agents} best interviewees and explain your choice."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "auto-selected by relevance")
            
            # fetch full info for the chosen agents
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(t("console.llmSelectAgentFailed", error=e))
            # fallback: take the first N
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "using the default selection strategy"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate interview questions with an LLM."""
        
        agent_roles = [a.get("profession", "unknown") for a in selected_agents]
        
        system_prompt = """You are a professional journalist/interviewer. Generate 3-5 in-depth interview questions from the requirement.

Question rules:
1. Open-ended, inviting detailed answers
2. Different roles should plausibly give different answers
3. Cover facts, opinions, and feelings
4. Natural language, like a real interview
5. Keep each question under ~50 characters, concise
6. Ask directly - no background preamble or prefix

Return JSON: {"questions": ["question 1", "question 2", ...]}"""

        user_prompt = f"""Interview requirement: {interview_requirement}

Simulation background: {simulation_requirement if simulation_requirement else "not provided"}

Interviewee roles: {', '.join(agent_roles)}

Generate 3-5 interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"On {interview_requirement}, what is your view?"])
            
        except Exception as e:
            logger.warning(t("console.generateInterviewQuestionsFailed", error=e))
            return [
                f"Regarding {interview_requirement}, what is your opinion?",
                "How does this affect you or the group you represent?",
                "What should be done to resolve or improve this situation?"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate the interview summary."""
        
        if not interviews:
            return "No interviews were completed"
        
        # collect all interview content
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")
        
        quote_instruction = 'When quoting interviewees verbatim, use Chinese quotation marks 「」' if get_locale() == 'zh' else 'Use quotation marks "" when quoting interviewees'
        system_prompt = f"""You are a professional news editor. Write an interview summary from the interviewees' answers.

Summary rules:
1. Distill each party's main points
2. Note consensus and disagreements
3. Highlight valuable quotes
4. Objective and neutral - favor no side
5. Keep it under 1000 characters

Format constraints (must follow):
- Plain-text paragraphs separated by blank lines
- No Markdown headings (e.g. #, ##, ###)
- No horizontal rules (e.g. ---, ***)
- {quote_instruction}
- May use **bold** for keywords, but no other Markdown syntax"""

        user_prompt = f"""Interview topic: {interview_requirement}

Interview content:
{"".join(interview_texts)}

Generate the interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(t("console.generateInterviewSummaryFailed", error=e))
            # fallback: simple concatenation
            return f"Interviewed {len(interviews)} people, including: " + ", ".join([i.agent_name for i in interviews])
