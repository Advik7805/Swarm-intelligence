"""
OASIS agent profile generator.
Converts Zep graph entities into the agent-profile format the OASIS simulation platform expects.

Improvements:
1. Enriches node info with a second Zep retrieval pass
2. Optimized prompts generate very detailed personas
    3. Distinguishes individual vs abstract group entities
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, get_locale, set_locale, t
from ..utils.openai_chat_compat import create_chat_completion, extract_chat_completion_text
from ..utils.zep import (
    call_zep_read_with_retry,
    get_zep_client,
    is_retryable_zep_error,
    normalize_zep_search_query,
)
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('hivemind.oasis_profile')


def _coerce_to_str(value: Any) -> str:
    """Coerce a value to a plain string.

    Handles dict, list, and other non-string types that may be returned
    by LLM JSON parsing.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ('text', 'value', 'description', 'content', 'summary', 'name'):
            if key in value:
                candidate = _coerce_to_str(value[key])
                if candidate:
                    return candidate
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        str_items = [_coerce_to_str(item) for item in value]
        str_items = [item for item in str_items if item]
        return ', '.join(str_items)
    return str(value)


def _coerce_to_str_list(value: Any) -> List[str]:
    """Coerce a value to a list of strings.

    Handles nested structures that may be returned by LLM JSON parsing.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        result: List[str] = []
        for item in value:
            if isinstance(item, (list, tuple)):
                result.extend(_coerce_to_str_list(item))
            else:
                text = _coerce_to_str(item)
                if text:
                    result.append(text)
        return result
    text = _coerce_to_str(value)
    return [text] if text else []


@dataclass
class OasisAgentProfile:
    """OASIS agent profile data structure."""
    # common fields
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    # optional fields - Reddit style
    karma: int = 1000
    
    # optional fields - Twitter style
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # extra persona info
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # source entity info
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def __post_init__(self):
        """Normalize structured LLM fields once at the profile boundary."""
        self.bio = _coerce_to_str(self.bio) or self.name
        self.persona = _coerce_to_str(self.persona) or (
            f"{self.name} is a participant in social discussions."
        )
        self.country = _coerce_to_str(self.country) or None
        self.profession = _coerce_to_str(self.profession) or None
        self.gender = _coerce_to_str(self.gender) or None
        self.mbti = _coerce_to_str(self.mbti) or None
        self.interested_topics = _coerce_to_str_list(self.interested_topics)

    def to_reddit_format(self) -> Dict[str, Any]:
        """Convert to the Reddit platform format."""
        profile = {
            "user_id": self.user_id,
  # the OASIS library requires the field name 'username' (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
    # extra persona info
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """Convert to the Twitter platform format."""
        profile = {
            "user_id": self.user_id,
  # the OASIS library requires the field name 'username' (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
    # extra persona info
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a full dict."""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS profile generator.
    
    Converts Zep graph entities into agent profiles for OASIS.
    
    Optimized features:
    1. Uses Zep graph retrieval for richer context
    2. Very detailed personas (basics, career, personality, social-media behavior, ...)
    3. Distinguishes individual vs abstract group entities
    """
    
    # MBTI type list
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # common country list
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # individual-type entities (get a concrete persona)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # group/institution-type entities (get a representative account persona)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep client for context-enriching retrieval
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = get_zep_client(self.zep_api_key)
            except Exception as e:
                logger.warning(f"Failed to init the Zep client: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Generate an OASIS agent profile from a Zep entity.
        
        Args:
            entity: Zep entity node
            user_id: user ID (for OASIS)
            use_llm: whether to LLM-generate the detailed persona
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # basic info
        name = entity.name
        user_name = self._generate_username(name)
        
        # build the context info
        context = self._build_entity_context(entity)
        
        if use_llm:
            # LLM-generate the detailed persona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # rule-based basic persona
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """Generate a username."""
        # strip special characters, lowercase
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # random suffix to avoid collisions
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Gather rich entity-related info via Zep hybrid search.
        
        Zep has no built-in hybrid endpoint, so edges and nodes are searched separately and merged.
        Both searches run in parallel for speed.
        
        Args:
            entity: entity node object
            
        Returns:
        Dict with facts, node_summaries, context
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # a graph_id is required to search
        if not self.graph_id:
            logger.debug("Skipping Zep retrieval: no graph_id set")
            return results
        
        comprehensive_query = normalize_zep_search_query(
            t('progress.zepSearchQuery', name=entity_name)
        )
        
        def search_edges():
            """Search edges (facts/relations) - with retries."""
            return call_zep_read_with_retry(
                lambda: self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                ),
                operation_name=f"profile edge search ({entity.uuid})",
            )
        
        def search_nodes():
            """Search nodes (entity summaries) - with retries."""
            return call_zep_read_with_retry(
                lambda: self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                ),
                operation_name=f"profile node search ({entity.uuid})",
            )
        
        try:
            # run the edges and nodes searches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # collect results
                # Each request already has the configured HTTP timeout and
                # typed retry budget. A second hard-coded 30s future timeout
                # discarded late successes while the executor still waited.
                edge_result = edge_future.result()
                node_result = node_future.result()
            
            # process edge search results
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # process node search results
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"related entity: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # build the combined context
            context_parts = []
            if results["facts"]:
                context_parts.append("Fact info:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("Related entities:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep hybrid retrieval done: {entity_name}, {len(results['facts'])} facts, {len(results['node_summaries'])} related nodes")
            
        except Exception as e:
            logger.warning(f"Zep retrieval failed ({entity_name}): {e}")
            if not is_retryable_zep_error(e):
                raise
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        Build the entity's full context info.
        
        Includes:
        1. The entity's own edges (facts)
        2. Details of related nodes
        3. Rich info from Zep hybrid retrieval
        """
        context_parts = []
        
        # 1. entity attribute info
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### Entity attributes\n" + "\n".join(attrs))
        
        # 2. related edge info (facts/relations)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # unlimited
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (related entity)")
                    else:
                        relationships.append(f"- (related entity) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### Related facts and relations\n" + "\n".join(relationships))
        
        # 3. details of related nodes
            related_info = []
  # unlimited
            for node in entity.related_nodes:  # unlimited
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # filter out default labels
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### Related entity info\n" + "\n".join(related_info))
        
        # 4. richer info via Zep hybrid retrieval
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # dedup: exclude facts already present
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Facts retrieved from Zep\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Related nodes retrieved from Zep\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """Whether this is an individual-type entity."""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """Whether this is a group/institution-type entity."""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Generate a very detailed persona with the LLM.
        
        Differentiates by entity type:
        - individual: a concrete character persona
        - group/institution: a representative account persona
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # retry generation until success or max attempts
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = create_chat_completion(
                    self.client,
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
  # lower temperature each retry
                    # no max_tokens cap; let the LLM run free
                )
                
                content = extract_chat_completion_text(response)
                
                # truncated? (finish_reason != 'stop')
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLM output truncated (attempt {attempt+1}); attempting repair...")
                    content = self._fix_truncated_json(content)
                
                # try to parse the JSON
                try:
                    result = json.loads(content)
                    
                    # validate required fields
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parse failed (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # attempt a JSON repair
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
  # exponential backoff
        
        logger.warning(f"LLM persona generation failed after {max_attempts} attempts: {last_error}; falling back to rules")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """Repair truncated JSON (output cut off by the max_tokens limit)."""
        import re
        
        # if the JSON is truncated, try to close it
        content = content.strip()
        
        # count unclosed brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # check for an unterminated string
        # heuristic: a trailing quote with no comma/closing bracket suggests a cut string
        if content and content[-1] not in '",}]':
            # close the string
            content += '"'
        
        # close brackets
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """Try to repair broken JSON."""
        import re
        
        # 1. try the truncated case first
        content = self._fix_truncated_json(content)
        
        # 2. try to extract the JSON portion
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. handle newline problems inside strings
            # find string values and replace their newlines
            def fix_string_newlines(match):
                s = match.group(0)
                # replace real newlines inside strings with spaces
                s = s.replace('\n', ' ').replace('\r', ' ')
                # collapse extra whitespace
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # match JSON string values
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. try parsing
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. still failing: try more aggressive repair
                try:
                    # strip all control characters
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # collapse all whitespace runs
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. try to salvage partial info from the content
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # possibly truncated
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} is a {entity_type}.")
        # meaningful content extracted: mark as repaired
        if bio_match or persona_match:
            logger.info("Salvaged partial info from broken JSON")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. total failure: return the base structure
        logger.warning("JSON repair failed; returning the base structure")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is a {entity_type}."
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get the system prompt."""
        base_prompt = "You are an expert social-media persona generator. Produce detailed, realistic personas for sentiment simulation, mirroring the known real-world situation as closely as possible. You must return valid JSON; string values must not contain unescaped newlines."
        return f"{base_prompt}\n\n{get_language_instruction()}"
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build the detailed persona prompt for an individual entity."""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        context_str = context[:3000] if context else "no extra context"
        
        return f"""Generate a detailed social-media user persona for the entity, mirroring the known real-world situation as closely as possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Return JSON with these fields:

1. bio: social-media bio, ~200 characters
2. persona: detailed persona description (~2000 characters of plain text) covering:
   - basic info (age, occupation, education, location)
   - background (key life events, connection to the event, social relations)
   - personality (MBTI type, core traits, emotional expression style)
   - social-media behavior (posting frequency, content preferences, interaction style, language quirks)
   - stance (attitude toward the topic, what might anger or move them)
   - distinctive traits (catchphrases, unique experiences, hobbies)
   - personal memory (a key part of the persona: how this individual relates to the event and what they have already done or said in it)
3. age: numeric age (integer required)
4. gender: must be English: "male" or "female"
5. mbti: MBTI type (e.g. INTJ, ENFP)
6. country: country name in English (e.g. "United States")
7. profession: occupation
8. interested_topics: array of topics of interest

Important:
- Every field value must be a string or number; never use newline characters
- persona must be one coherent passage of prose
- {get_language_instruction()} (the gender field must be the English male/female)
- Content must stay consistent with the entity information
- age must be a valid integer; gender must be "male" or "female"
"""


    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build the detailed persona prompt for a group/institution entity."""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "none"
        context_str = context[:3000] if context else "no extra context"
        
        return f"""Generate a detailed social-media account persona for the institution/group entity, mirroring the known real-world situation as closely as possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Return JSON with these fields:

1. bio: official account bio, ~200 characters, professional and measured
2. persona: detailed account persona (~2000 characters of plain text) covering:
   - institution basics (official name, nature, founding background, core functions)
   - account positioning (account type, target audience, core purpose)
   - voice (language traits, stock phrases, topics to avoid)
   - publishing pattern (content types, cadence, active hours)
   - stance (official position on core topics; how controversy is handled)
   - special notes (the constituency represented, operating habits)
   - institutional memory (a key part of the persona: how the institution relates to the event and what it has already done or said in it)
3. age: fixed at 30 (placeholder age for institutional accounts)
4. gender: fixed at "other" (institutions use "other" - not an individual)
5. mbti: MBTI type describing the account's style, e.g. ISTJ for rigorous and conservative
6. country: country name in English (e.g. "United States")
7. profession: the institution's function
8. interested_topics: array of focus areas

Important:
- Every field value must be a string or number; null values are not allowed
- persona must be one coherent passage of prose; no newline characters
- {get_language_instruction()} (the gender field must be the English "other")
- age must be the integer 30; gender must be the string "other"
- The account's statements must fit its institutional role"""

    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
            # rule-based basic persona
        
        # different persona per entity type
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
  # placeholder institutional age
  # institutions use 'other'
  # institutional style: rigorous, conservative
                "country": "United States",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
  # placeholder institutional age
  # institutions use 'other'
  # institutional style: rigorous, conservative
                "country": "United States",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # default persona
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """Set the graph ID used for Zep retrieval."""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        Batch-generate agent profiles from entities (parallel-capable).
        
        Args:
            entities: entity list
            use_llm: whether to LLM-generate the detailed persona
            progress_callback: progress callback (current, total, message)
            graph_id: graph ID used for richer Zep retrieval context
            parallel_count: parallelism, default 5
            realtime_output_path: if given, the file is rewritten after each profile
            output_platform: output format ("reddit" or "twitter")
            
        Returns:
            List of agent profiles
        """
        import concurrent.futures
        from threading import Lock
        
        # set graph_id for Zep retrieval
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # preallocate to keep order
        completed_count = [0]  # list so the closure can mutate it
        lock = Lock()
        
        # helper: write profiles to file in real time
        def save_profiles_realtime():
            """Persist finished profiles to the file as they complete."""
            if not realtime_output_path:
                return
            
            with lock:
                # keep finished profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Realtime profile save failed: {e}")
        
        # Capture locale before spawning thread pool workers
        current_locale = get_locale()

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """Worker: generate a single profile."""
            set_locale(current_locale)
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # stream the generated persona to console and logs
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"Failed to generate a persona for entity {entity.name}: {str(e)}")
                # build a basic profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"Starting parallel persona generation: {total} agents (parallelism {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"Generating agent personas - {total} entities, parallelism {parallel_count}")
        print(f"{'='*60}\n")
        
        # run in a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # submit all tasks
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # collect results
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # realtime file write
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"Completed {current}/{total}: {entity.name} ({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} fell back to a backup persona: {error}")
                    else:
                        logger.info(f"[{current}/{total}] persona generated: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"Exception while processing {entity.name}: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # realtime file write
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"Persona generation done! {len([p for p in profiles if p])} agents generated")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """Print the generated persona to the console (full content, no truncation)."""
        separator = "-" * 70
        
        # build the full output content (no truncation)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'none'
        
        output_lines = [
            f"\n{separator}",
            t('progress.profileGenerated', name=entity_name, type=entity_type),
            f"{separator}",
            f"Username: {profile.user_name}",
            f"",
            f"[Bio]",
            f"{profile.bio}",
            f"",
            f"[Detailed Persona]",
            f"{profile.persona}",
            f"",
            f"[Basic Attributes]",
            f"Age: {profile.age} | Gender: {profile.gender} | MBTI: {profile.mbti}",
            f"Profession: {profile.profession} | Country: {profile.country}",
            f"Interested topics: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # console only (no logger duplicate of the full content)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Save profiles to a file (correct format per platform).
        
        OASIS platform format requirements:
        - Twitter: CSV
        - Reddit: JSON
        
        Args:
            profiles: profile list
            file_path: file path
            platform: platform type ("reddit" or "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Save Twitter profiles as CSV (matching the official OASIS requirement).
        
        OASIS Twitter CSV fields:
        - user_id: user ID (0-based, in CSV order)
        - name: the user's real name
        - username: username in the system
        - user_char: detailed persona (injected into the LLM system prompt to steer agent behavior)
        - description: short public bio (shown on the profile page)
        
        user_char vs description:
        - user_char: internal; the LLM system prompt deciding how the agent thinks and acts
        - description: external; the bio other users see
        """
        import csv
        
        # ensure the .csv extension
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # write the OASIS header row
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # write data rows
            for idx, profile in enumerate(profiles):
                # user_char: full persona (bio + persona) for the LLM system prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # handle newlines (replaced with spaces inside CSV)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: short bio for external display
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: sequential ID from 0
                    profile.name,           # name: real name
                    profile.user_name,      # username: username
                    user_char,              # user_char: full persona (internal LLM use)
                    description             # description: short bio (external display)
                ]
                writer.writerow(row)
        
        logger.info(f"Saved {len(profiles)} Twitter profiles to {file_path} (OASIS CSV format)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        Normalize the gender field to OASIS's English format.
        
        OASIS expects: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # Chinese-input mapping (LLM may answer in Chinese)
        gender_map = {
            "男": "male",
            "女": "female",
            "机构": "other",
            "其他": "other",
            # already English
            # already English
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Save Reddit profiles as JSON.
        
        Uses the same shape as to_reddit_format() so OASIS reads it correctly.
        Must include user_id - the key OASIS agent_graph.get_agent() matches on!
        
        Required fields:
        - user_id: user ID (integer; matches poster_agent_id in initial_posts)
        - username: username
        - name: display name
        - bio: bio
        - persona: detailed persona
        - age: age (integer)
        - gender: "male", "female", or "other"
        - mbti: MBTI type
        - country: country
        """
        data = []
        for idx, profile in enumerate(profiles):
            # same shape as to_reddit_format()
            item = {
  # key: user_id must be present
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150],
                "persona": profile.persona,
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS-required fields - ensure defaults
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "Unknown",
            }
            
            # optional fields
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(profiles)} Reddit profiles to {file_path} (JSON format, includes user_id)")
    
    # legacy method-name aliases kept for backward compatibility
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Deprecated] Use save_profiles() instead"""
        logger.warning("save_profiles_to_json is deprecated; use save_profiles")
        self.save_profiles(profiles, file_path, platform)
