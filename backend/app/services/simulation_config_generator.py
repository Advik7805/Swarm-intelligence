"""
Intelligent simulation config generator.

Uses an LLM to derive detailed simulation parameters from the requirement,
documents, and graph info. Fully automated - no manual parameter setup.

Staged generation avoids failures from overlong single-shot output:
1. Generate the time config
2. Generate the event config
3. Generate agent configs in batches
4. Generate the platform config
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from ..utils.openai_chat_compat import create_chat_completion, extract_chat_completion_text
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('hivemind.simulation_config')

# China-timezone daily-rhythm defaults (Beijing time)

CHINA_TIMEZONE_CONFIG = {
    # small hours (almost no activity)

    "dead_hours": [0, 1, 2, 3, 4, 5],
    # morning (waking up)

    "morning_hours": [6, 7, 8],
    # work hours

    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # evening peak (most active)

    "peak_hours": [19, 20, 21, 22],
    # night (declining)

    "night_hours": [23],
    # activity factors

    "activity_multipliers": {
        "dead": 0.05,      # dead of night

        "morning": 0.4,    # morning ramp-up

        "work": 0.7,       # moderate during work

        "peak": 1.5,       # evening peak

        "night": 0.5       # late-night decline

    }
}


@dataclass
class AgentActivityConfig:
    """Per-agent activity config."""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # activity (0.0-1.0)

    activity_level: float = 0.5  # overall activity

    
    # posting frequency (expected posts per hour)

    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # active hours (24h clock, 0-23)

    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # response speed (delay to hot events, in simulated minutes)

    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # sentiment bias (-1.0..1.0, negative to positive)

    sentiment_bias: float = 0.0
    
    # stance (attitude on specific topics)

    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # influence weight (probability others see this agent's posts)

    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """Time simulation config (based on China-timezone daily rhythms)."""
    # total simulated duration (simulated hours)

    total_simulation_hours: int = 72  # default 72h (3 days)

    
    # minutes of simulated time per round - default 60 (1 hour) for a faster clock

    minutes_per_round: int = 60
    
    # agents activated per hour (range)

    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # peak hours (19-22, the most active window)

    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # trough hours (0-5, nearly nobody)

    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # very low small-hours activity

    
    # morning

    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # work hours

    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """   # event config
"""
    # initial event (trigger at simulation start)

    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # scheduled events (fired at set times)

    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # trending topic keywords

    hot_topics: List[str] = field(default_factory=list)
    
    # narrative direction

    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Platform-specific config."""
    platform: str  # twitter or reddit
    
    # recommender weights

    recency_weight: float = 0.4  # recency

    popularity_weight: float = 0.3  # popularity

    relevance_weight: float = 0.3  # relevance

    
    # virality threshold (interactions before spread kicks in)

    viral_threshold: int = 10
    
    # echo-chamber strength (how much similar views cluster)

    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Full simulation parameter set."""
    # basics

    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # time config

    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # agent configs

    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # event config

    event_config: EventConfig = field(default_factory=EventConfig)
    
    # platform config

    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLM config

    llm_model: str = ""
    llm_base_url: str = ""
    
    # generation metadata

    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # the LLM's reasoning

    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict."""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
        Intelligent simulation config generator.

    
        Analyzes the requirement, documents, and graph entities with an LLM to

        auto-generate the best simulation parameter configuration.

    
        Staged generation:

    1.     1. Time + event configs (lightweight)

    2.     2. Agent configs in batches (10-20 each)

    3. 4. Generate the platform config

    """
    
    # max context chars

    MAX_CONTEXT_LENGTH = 50000
    # agents per batch

    AGENTS_PER_BATCH = 15
    
    # per-step context truncation lengths (chars)

    TIME_CONFIG_CONTEXT_LENGTH = 10000   # time config

    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # event config

    ENTITY_SUMMARY_LENGTH = 300          # entity summary

    AGENT_SUMMARY_LENGTH = 300           # entity summary inside agent configs

    ENTITIES_PER_TYPE_DISPLAY = 20       # entities shown per type

    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
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
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
                Generate the full simulation config intelligently (staged).

        
        Args:
                        simulation_id: simulation ID

                        project_id: project ID

                        graph_id: graph ID

                        simulation_requirement: requirement text

                        document_text: raw document content

                        entities: filtered entity list

                        enable_twitter: enable Twitter

                        enable_reddit: enable Reddit

                        progress_callback: progress callback (current_step, total_steps, message)
(current_step, total_steps, message)
            
        Returns:
                        SimulationParameters: the full parameter set

        """
        logger.info(f"Starting intelligent config generation: simulation_id={simulation_id}, entities={len(entities)}")
        
        # total step count

        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # time + event + N agent batches + platform

        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1.         # build the base context

        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== step 1: time config ==========
        report_progress(1, t('progress.generatingTimeConfig'))
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"{t('progress.timeConfigLabel')}: {time_config_result.get('reasoning', t('common.success'))}")
        
        # ========== step 2: event config ==========
        report_progress(2, t('progress.generatingEventConfig'))
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"{t('progress.eventConfigLabel')}: {event_config_result.get('reasoning', t('common.success'))}")
        
        # ========== steps 3..N: agent configs in batches ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                t('progress.generatingAgentConfig', start=start_idx + 1, end=end_idx, total=len(entities))
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(t('progress.agentConfigResult', count=len(all_agent_configs)))
        
        # ========== assign publisher agents to initial posts ==========
        logger.info(f"Assigning publisher agents to initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(t('progress.postAssignResult', count=assigned_count))
        
        # ========== final step: platform config ==========
        report_progress(total_steps, t('progress.generatingPlatformConfig'))
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # assemble the final parameters

        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"Config generation done: {len(params.agent_configs)} agent configs")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """Build the LLM context, truncated to the max length."""
        
        # entity summary

        entity_summary = self._summarize_entities(entities)
        
        # build the context

        context_parts = [
            f"# Simulation requirement\n{simulation_requirement}",
            f"\n# Entity info ({len(entities)})\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # 500-char headroom

        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(document truncated)"
                context_parts.append(f"\n# Raw document\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Summarize the entities."""
        lines = []
        
        # group by type

        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n## {entity_type} ({len(type_entities)})")
            # respect the configured display count and summary length

            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ...   ... and {len(type_entities) - display_count} more")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """LLM call with retries and JSON repair."""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = create_chat_completion(
                    self.client,
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),  # cooler on each retry
                    # no max_tokens cap; let the LLM decide
                )
                
                content = extract_chat_completion_text(response)
                finish_reason = response.choices[0].finish_reason
                
                # truncated?
                if finish_reason == 'length':
                    logger.warning(f"LLM output truncated (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # parse the JSON

                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed (attempt {attempt+1}): {str(e)[:80]}")
                    
                    # attempt JSON repair

                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        Exception("LLM call failed")
    
    def _fix_truncated_json(self, content: str) -> str:
        """Repair truncated JSON."""
        content = content.strip()
        
        # count unclosed brackets

        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # check for an unterminated string

        if content and content[-1] not in '",}]':
            content += '"'
        
        # close brackets

        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to repair the config JSON."""
        import re
        
        # handle the truncated case first

        content = self._fix_truncated_json(content)
        
        # extract the JSON portion

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # strip newlines inside strings

            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # strip all control characters

                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generate the time config."""
        # respect the configured context truncation length

        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # max allowed (80% of the agent count)

        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""Based on the simulation requirement below, generate the time-simulation config.

{context_truncated}

# Task
Generate the time config JSON.

## Ground rules (reference only; adapt to the specific event and audience):
- Infer the target users' timezone and daily routine from the simulation scenario; the examples below use UTC+8
- 0:00-5:00 nearly nobody active (activity factor 0.05)
- 6:00-8:00 gradually waking up (0.4)
- 9:00-18:00 work hours, moderate activity (0.7)
- 19:00-22:00 evening peak (1.5)
- after 23:00 activity declines (0.5)
- General pattern: quiet small hours, rising morning, moderate workday, evening peak
- **Important**: the sample values are reference only - tune the periods to the event and the participants
  - e.g. students may peak 21:00-23:00; media are active all day; officials only during work hours
  - e.g. breaking news can drive late-night discussion; off_peak_hours may be shortened

## Return JSON (no markdown)
{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 3,
    "agents_per_hour_max": 8,
    "peak_hours": [19, 20, 21],
    "off_peak_hours": [0, 1, 2, 3, 4],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
    "reasoning": "why this timing fits the event"
}

Field notes:
- total_simulation_hours (int): total simulated time, 24-168h; short for breaking news, long for sustained topics
- minutes_per_round (int): minutes per round, 30-120, 60 recommended
- agents_per_hour_min (int): fewest agents activated per hour (range 1-{max_agents_allowed})
- agents_per_hour_max (int): most agents activated per hour (range 1-{max_agents_allowed})
- peak_hours (int array): peak hours, tuned to the participating group
- off_peak_hours (int array): trough hours, usually the small hours
- morning_hours (int array): morning hours
- work_hours (int array): work hours
- reasoning (string): briefly explain the configuration"""

        system_prompt = "You are a social-media simulation expert. Return pure JSON; the timing must fit the daily routine of the target users in the scenario."
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Time config LLM generation failed: {e}; using defaults")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Default time config (China-timezone rhythms)."""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 1h per round, faster clock

            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Using the default China-timezone rhythm config (1h per round)"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """Parse the time config, validating agents_per_hour against the agent count."""
        # raw values

        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # validate and clamp to the agent count

        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) exceeds the agent count ({num_entities}); clamped")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) exceeds the agent count ({num_entities}); clamped")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # ensure min < max

        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max; set both to {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # 1h per round default

            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # dead of night

            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """Generate the event config."""
        
        # available entity types for the LLM to reference

        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # representative entity names per type

        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # respect the configured context truncation length

        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""Based on the simulation requirement below, generate the event config.

Simulation requirement: {simulation_requirement}

{context_truncated}

# Available entity types and samples
{entity_types_info}

# Task
Generate the event config JSON:
- Extract trending topic keywords
- Describe the narrative direction of the discussion
- Design initial post content; **every post must set poster_type (publisher type)**

**Important**: poster_type must be chosen from the "available entity types" above so each initial post can be assigned to a fitting agent.
e.g. official statements come from Official/University types, news from MediaOutlet, student views from Student.

Return JSON (no markdown):
{
    "hot_topics": ["keyword1", "keyword2", ...],
    "narrative_direction": "<how the discussion should evolve>",
    "initial_posts": [
        {{"content": "post content", "poster_type": "entity type (must be chosen from the available types)"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}
}}"""

        system_prompt = "You are a sentiment-analysis expert. Return pure JSON. poster_type must exactly match an available entity type."
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'poster_type' field value MUST be in English PascalCase exactly matching the available entity types. Only 'content', 'narrative_direction', 'hot_topics' and 'reasoning' fields should use the specified language."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Event config LLM generation failed: {e}; using defaults")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
            "reasoning": "using the default config"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """Parse the event config result."""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
                Assign publisher agents to the initial posts.

        
                Matches each post's poster_type to the best-fit agent_id.

        """
        if not event_config.initial_posts:
            return event_config
        
        # index agents by entity type

        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # alias map (the LLM may emit varying type names)

        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # per-type used-index tracking so the same agent is not reused

        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # find a matching agent

            matched_agent_id = None
            
            # 1.             # 1. exact match

            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2.                 # 2. alias match

                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3.             # 3. still nothing: use the highest-influence agent

            if matched_agent_id is None:
                logger.warning(f"No agent matched type '{poster_type}'; using the highest-influence agent")
                if agent_configs:
                    # sort by influence, take the top

                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"Initial post assigned: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """Generate agent configs in batches."""
        
        # build entity info (configured summary length)

        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""Based on the information below, generate a social-media activity config for each entity.

Simulation requirement: {simulation_requirement}

{context_truncated}

# Entity list
{entities_info}

# Task
Generate an activity config per entity. Notes:
- **Timing fits the target audience routine**: the reference below is UTC+8 - adapt to the scenario
- **Official institutions** (University/GovernmentAgency): low activity (0.1-0.3), work hours (9-17), slow response (60-240 min), high influence (2.5-3.0)
- **Media** (MediaOutlet): medium activity (0.4-0.6), all day (8-23), fast response (5-30 min), high influence (2.0-2.5)
- **Individuals** (Student/Person/Alumni): high activity (0.6-0.9), mainly evenings (18-23), fast response (1-15 min), low influence (0.8-1.2)
- **Public figures/experts**: medium activity (0.4-0.6), medium-high influence (1.5-2.0)

Return JSON (no markdown):
[
    {{
        "agent_id": <must match the input>,
        "activity_level": <0.0-1.0>,
        "posts_per_hour": <posting frequency>,
        "comments_per_hour": <commenting frequency>,
        "active_hours": [<active hours, respecting the target routine>],
        "response_delay_min": <min response delay, minutes>,
        "response_delay_max": <max response delay, minutes>,
        "sentiment_bias": <-1.0 to 1.0>,
        "stance": {{"topic": "stance"}},
        "influence_weight": <influence weight>
        }},
        ...
    ]
}}"""

        system_prompt = "You are a social-media behavior analyst. Return pure JSON; configs must fit the daily routine of the target users in the scenario."
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}\nIMPORTANT: The 'stance' field value MUST be one of the English strings: 'supportive', 'opposing', 'neutral', 'observer'. All JSON field names and numeric values must remain unchanged. Only natural language text fields should use the specified language."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agent config batch LLM call failed: {e}; falling back to rules")
            llm_configs = {}
        
        # build AgentActivityConfig objects
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # rule-based fallback when the LLM skipped it

            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """Rule-based per-agent config (China-timezone rhythms)."""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # officials: work hours, low frequency, high influence

            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # media: all day, medium frequency, high influence

            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # experts/professors: work + evening, medium frequency

            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # students: mostly evenings, high frequency

            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # morning + evening

                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # alumni: mostly evenings

            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # lunch + evening

                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # general public: evening peak

            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # daytime + evening

                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
    

