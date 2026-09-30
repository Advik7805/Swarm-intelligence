"""
Report Agent service.
Simulation report generation with a ReACT pattern, built on LangChain + Zep.

Features:
1. Generates reports from the simulation requirement and Zep graph info
2. Plans the outline first, then generates section by section
3. Each section runs a multi-round ReACT think-and-reflect loop
4. Supports chatting with the user, autonomously calling retrieval tools
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction, t
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('hivemind.report_agent')


class ReportLogger:
    """
    Detailed Report Agent logger.
    
    Writes agent_log.jsonl into the report folder, recording every detailed step.
    Each line is one complete JSON object with timestamp, action type, details, etc.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the logger.
        
        Args:
            report_id: report ID; determines the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure the log file directory exists."""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """Elapsed seconds since start."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        Log one entry.
        
        Args:
            action: action type, e.g. 'start', 'tool_call', 'llm_response', 'section_complete'
            stage: current stage, e.g. 'planning', 'generating', 'completed'
            details: details dict, not truncated
            section_title: current section title (optional)
            section_index: current section index (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # append to the JSONL file
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Log report generation start."""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": t('report.taskStarted')
            }
        )
    
    def log_planning_start(self):
        """Log outline planning start."""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": t('report.planningStart')}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Log the context gathered during planning."""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": t('report.fetchSimContext'),
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Log outline planning completion."""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": t('report.planningComplete'),
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Log section generation start."""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": t('report.sectionStart', title=section_title)}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Log a ReACT thought."""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": t('report.reactThought', iteration=iteration)
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Log a tool call."""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": t('report.toolCall', toolName=tool_name)
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Log a tool call."""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # full result, no truncation
                "result_length": len(result),
                "message": t('report.toolResult', toolName=tool_name)
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Log an LLM response (full content, no truncation)."""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # full response, no truncation
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": t('report.llmResponse', hasToolCalls=has_tool_calls, hasFinalAnswer=has_final_answer)
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Log section content generation done (content only; not the whole section)."""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # full content, no truncation
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": t('report.sectionContentDone', title=section_title)
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Log section completion.

        The frontend watches this entry to know a section truly finished and to fetch its full content.
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": t('report.sectionComplete', title=section_title)
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Log report generation completion."""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": t('report.reportComplete')
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Log an error."""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": t('report.errorOccurred', error=error_message)
            }
        )


class ReportConsoleLogger:
    """
    Report Agent console logger.
    
    Mirrors console-style logs (INFO, WARNING, ...) into console_log.txt inside the report folder.
    Unlike agent_log.jsonl, this is plain-text console output.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the console logger.
        
        Args:
            report_id: report ID; determines the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Ensure the log file directory exists."""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """Attach a file handler so logs are written to the file too."""
        import logging
        
        # create the file handler
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # same compact format as the console
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # attach to the report_agent loggers
        loggers_to_attach = [
            'hivemind.report_agent',
            'hivemind.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # avoid duplicate handlers
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Close the file handler and detach it from the loggers."""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'hivemind.report_agent',
                'hivemind.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Make sure the file handler is closed on destruction."""
        self.close()


class ReportStatus(str, Enum):
    """Report status."""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section."""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown."""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline."""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown."""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Complete report."""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt template constants
# ═══════════════════════════════════════════════════════════════

# ── Tool descriptions ──
TOOL_DESC_INSIGHT_FORGE = """\
[Deep Insight Retrieval - powerful search tool]
This is our powerful retrieval function, designed for deep analysis. It will:
1. Automatically break your question into multiple sub-questions
2. Retrieve information from the simulation graph along multiple dimensions
3. Integrate semantic search, entity analysis, and relation-chain tracing
4. Return the most comprehensive, in-depth retrieval content

[Use when]
- You need to analyze a topic in depth
- You need to understand multiple facets of an event
- You need rich material to support a report section

[Returns]
- Related facts verbatim (ready to quote)
- Core entity insights
- Relation-chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
[Breadth Search - full-picture view]
This tool captures the complete picture of the simulation results, ideal for understanding how the event evolved. It will:
1. Fetch all related nodes and relations
2. Distinguish currently valid facts from historical/expired ones
3. Help you understand how sentiment evolved over time

[Use when]
- You need the full arc of the event
- You need to compare sentiment across stages
- You need comprehensive entity and relation info

[Returns]
- Currently valid facts (latest simulation results)
- Historical/expired facts (evolution record)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
[Simple Search - quick lookup]
A lightweight, fast retrieval tool for simple, direct information queries.

[Use when]
- You need to quickly find a specific fact
- You need to verify a claim
- Simple information retrieval

[Returns]
- The facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[In-Depth Interview - real agent interviews (dual-platform)]
Calls the OASIS simulation environment's interview API to interview running simulation agents for real!
This is not LLM role-play - it calls the real interview endpoint to get simulated agents' raw answers.
Interviews on both Twitter and Reddit simultaneously by default for broader perspectives.

Workflow:
1. Automatically reads the persona files to learn all simulated agents
2. Intelligently selects the agents most relevant to the interview topic (students, media, officials, etc.)
3. Generates interview questions automatically
4. Calls the /api/simulation/interview/batch endpoint for real dual-platform interviews
5. Consolidates all interviews into a multi-perspective analysis

[Use when]
- You need views from different role perspectives (What do students think? The media? Officials?)
- You need to collect opinions and stances from many parties
- You need simulated agents' real answers (from the OASIS environment)
- You want the report to be more vivid, with a full interview transcript

[Returns]
- Interviewed agents' identity info
- Each agent's answers on both Twitter and Reddit
- Key quotes (ready to cite)
- Interview summary and viewpoint comparison

[Important] Requires the OASIS simulation environment to be running!"""

# ── Outline planning prompt ──
PLAN_SYSTEM_PROMPT = """\
You are an expert writer of "future prediction reports" with a god's-eye view of the simulated world - you can observe every agent's behavior, statements, and interactions in the simulation.

[Core idea]
We built a simulated world and injected a specific "simulation requirement" as a variable. The simulated world's evolution is a prediction of what may happen in the future. What you are observing is not "experimental data" but a "rehearsal of the future".

[Your task]
Write a "future prediction report" answering:
1. Under the conditions we set, what happened in the future?
2. How did the various agents (groups of people) react and act?
3. What noteworthy future trends and risks does the simulation reveal?

[Report positioning]
- This IS a simulation-based future prediction report, revealing "if this, then what next"
- Focus on prediction outcomes: event trajectory, group reactions, emergent phenomena, potential risks
- Agents' words and actions in the simulated world are predictions of future human behavior
- It is NOT an analysis of the current real world
- It is NOT a generic sentiment round-up

[Section count limit]
- Between 2 and 5 sections
- No sub-sections; write each section's full content directly
- Keep content concise, focused on the core predictive findings
- Design the section structure yourself based on the prediction results

Output the report outline in JSON format:
{
    "title": "report title",
    "summary": "report summary (one sentence capturing the core prediction)",
    "sections": [
        {
            "title": "section title",
            "description": "section description"
        }
    ]
}
Note: the sections array must contain at least 2 and at most 5 elements!"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Prediction scenario]
The variable injected into the simulated world (simulation requirement): {simulation_requirement}

[Simulation world scale]
- Number of participating entities: {total_nodes}
- Number of relations produced between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active agents: {total_entities}

[Sample of future facts predicted by the simulation]
{related_facts_json}

Examine this rehearsal of the future with a god's-eye view:
1. Under the conditions we set, what state did the future take?
2. How did the various groups (agents) react and act?
3. What noteworthy future trends does the simulation reveal?

Based on the prediction results, design the most fitting report section structure.

[Reminder] Section count: at least 2, at most 5. Keep content concise and focused on the core prediction findings."""

# ── Section generation prompt ──
SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert writer of "future prediction reports", currently writing one section of the report.

Report title: {report_title}
Report summary: {report_summary}
Prediction scenario (simulation requirement): {simulation_requirement}

Section to write: {section_title}

═══════════════════════════════════════════════════════════════
[Core idea]
═══════════════════════════════════════════════════════════════

The simulated world is a rehearsal of the future. We injected specific conditions (the simulation requirement) into it,
and the agents' behavior and interactions in the simulation are predictions of how real groups will act in the future.

Your task:
- Reveal what happened in the future under the given conditions
- Predict how the various groups (agents) reacted and acted
- Surface noteworthy future trends, risks, and opportunities

DO NOT write an analysis of the current real world.
DO focus on "what the future will look like" - the simulation results ARE the predicted future.

═══════════════════════════════════════════════════════════════
[Most important rules - must follow]
═══════════════════════════════════════════════════════════════

1. [You MUST call tools to observe the simulated world]
   - You are observing a rehearsal of the future with a god's-eye view
   - All content must come from events and agent behavior in the simulated world
   - Using your own knowledge to write report content is forbidden
   - Call tools at least 3 times (at most 5) per section to observe the simulated world, which represents the future

2. [You MUST quote agents' original words]
   - Agents' statements and actions are predictions of future human behavior
   - Present these predictions as quotes in the report, e.g.:
     > "One group will say: original text..."
   - These quotes are the core evidence of the simulation's predictions

3. [Language consistency - quotes must be translated into the report language]
   - Tool output may contain text in a different language than the report
   - The entire report must be written in the language the user specified
   - When quoting other-language content from tool results, translate it into the report language first
   - Preserve the original meaning; keep the phrasing natural and fluent
   - This rule applies to both body text and quote blocks (> format)

4. [Faithfully present the prediction results]
   - Report content must reflect the simulation results that represent the future
   - Do not add information that does not exist in the simulation
   - If information is insufficient in some area, say so honestly

5. [Fabricating data is forbidden]
   - Fabricating usernames, quotes, statistics, or engagement data is forbidden
   - Never include <tool_result> blocks in your reply - only the system provides tool results
   - Only cite entities, quotes, and data that actually appear in tool results
   - If tool results contain nothing relevant, say so honestly instead of inventing content

═══════════════════════════════════════════════════════════════
[Formatting rules - extremely important!]
═══════════════════════════════════════════════════════════════

[One section = the minimal content unit]
- Each section is the report's minimal chunk
- NEVER use any Markdown headings inside a section (#, ##, ###, ####, etc.)
- Never start the content with the section's own title
- The system adds section titles automatically; write pure body text only
- You may use **bold**, paragraph breaks, quotes, and lists to organize content - but no headings

[Correct example]

This section analyzes the event's sentiment propagation. From deep analysis of the simulation data, we found...

**Ignition stage**

Weibo, as the event's first venue, carried the core function of breaking the news:

> "Weibo contributed 68% of the first-wave volume..."

**Amplification stage**

Douyin further amplified the event's impact:
- Strong visual impact
- High emotional resonance

[Wrong example]

## Executive Summary          <- WRONG! Never add any heading
### I. Ignition stage         <- WRONG! Never split with ###
#### 1.1 Detailed analysis    <- WRONG! Never split with ####

This section analyzes...

═══════════════════════════════════════════════════════════════
[Available retrieval tools] (call 3-5 times per section)
═══════════════════════════════════════════════════════════════

{tools_description}

[Tool usage advice - mix different tools, don't rely on just one]
- insight_forge: deep insight analysis; auto-decomposes the question and retrieves facts and relations on multiple dimensions
- panorama_search: wide panoramic search for the full picture, timeline, and evolution
- quick_search: quickly verify a specific fact
- interview_agents: interview simulated agents for first-person views and real reactions from different roles

═══════════════════════════════════════════════════════════════
[Workflow]
═══════════════════════════════════════════════════════════════

Each reply may do exactly ONE of the following two things (never both):

Option A - call a tool:
Output your thought, then call exactly one tool in this format:

<tool_call>
{{"name": "tool name", "parameters": {{"param name": "param value"}}}}
</tool_call>

The system will execute the tool and return the result to you. You must not and cannot write the tool result yourself.

Option B - output the final content:
When you have gathered enough information via tools, output the section content starting with "Final Answer:".

Strictly forbidden:
- Including both a tool call and a Final Answer in one reply
- Writing tool results (Observation) yourself - all tool results are injected by the system
- Calling more than one tool per reply

═══════════════════════════════════════════════════════════════
[Section content requirements]
═══════════════════════════════════════════════════════════════

1. Content must be based on simulation data retrieved via tools
2. Quote original text liberally to showcase the simulation
3. Use Markdown formatting (but NO headings):
   - Use **bold text** for emphasis (instead of sub-headings)
   - Use lists (- or 1.2.3.) to organize points
   - Use blank lines to separate paragraphs
   - NEVER use #, ##, ###, #### or any heading syntax
4. [Quote format - must be a standalone paragraph]
   Quotes must stand alone as their own paragraph with a blank line before and after - never mixed into a paragraph:

   Correct format:

   The school's response was seen as lacking substance.

   > "The school's handling looked rigid and slow in a fast-moving social media environment."

   This assessment reflects the public's broad dissatisfaction.

   Wrong format:

   The school's response was seen as lacking substance.> "The school's handling..." This assessment reflects...
5. Keep logical coherence with the other sections
6. [Avoid repetition] Read the completed sections below carefully; do not repeat the same information
7. [Emphasized again] Do not add any headings! Use **bold** instead of sub-headings"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed sections so far (read carefully to avoid repetition):

{previous_content}

═══════════════════════════════════════════════════════════════
[Current task] Write section: {section_title}
═══════════════════════════════════════════════════════════════

[Important reminders]
1. Read the completed sections above carefully; avoid repeating the same content!
2. Call a tool to gather simulation data before you start writing
3. Mix different tools; don't rely on just one
4. Report content must come from retrieval results, not your own knowledge

[Format warning - must follow]
- Do not write any heading (#, ##, ###, #### - none work)
- Do not open with "{section_title}"
- The system adds section titles automatically
- Write body text directly; use **bold** instead of sub-headings

Please begin:
1. First think (Thought) about what information this section needs
2. Then call a tool (Action) to gather simulation data
3. Once you have enough information, output the Final Answer (pure body text, no headings)"""

# ── In-loop ReACT message templates ──
REACT_OBSERVATION_TEMPLATE = """\
Observation (retrieval result):

═══ Tool {tool_name} returned ═══
{result}
═══════════════════════════════════════════════════════════════
You have called tools {tool_calls_count}/{max_tool_calls} times (used: {used_tools_str}){unused_hint}
- If the information is sufficient: output the section content starting with "Final Answer:" (must quote the original text above)
- If you need more information: call one tool to continue retrieving
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Notice] You have called tools only {tool_calls_count} time(s); at least {min_tool_calls} are required. "
    "Call more tools to gather simulation data before outputting the Final Answer.{unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "You have called tools only {tool_calls_count} time(s); at least {min_tool_calls} are required. "
    "Call a tool to gather simulation data.{unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Tool call limit reached ({tool_calls_count}/{max_tool_calls}); no further tool calls are allowed. "
    'Immediately output the section content starting with "Final Answer:" based on the information gathered.'
)

REACT_UNUSED_TOOLS_HINT = "\n💡 You have not used yet: {unused_list}. Try different tools for multi-angle information"

REACT_FORCE_FINAL_MSG = "Tool call limit reached. Output 'Final Answer:' directly and generate the section content."

# ── Chat prompt ──
CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise, efficient simulation-prediction assistant.

[Background]
Prediction condition: {simulation_requirement}

[Generated analysis report]
{report_content}

[Rules]
1. Answer questions based on the report content above first
2. Answer directly; avoid long-winded deliberation
3. Only call tools to retrieve more data when the report is insufficient
4. Keep answers concise, clear, and well-structured

[Available tools] (use only when needed; at most 1-2 calls)
{tools_description}

[Tool call format]
<tool_call>
{{"name": "tool name", "parameters": {{"param name": "param value"}}}}
</tool_call>

[Answer style]
- Concise and direct; no essays
- Use > quotes for key content
- Give the conclusion first, then the reasoning"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
# ReportAgent main class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - simulation report generation agent.

    Uses the ReACT (Reasoning + Acting) pattern:
    1. Planning: analyze the simulation requirement, plan the report outline
    2. Generation: write content section by section, with multiple tool calls per section
    3. Reflection: check content completeness and accuracy
    """
    
    # max tool calls (per section)
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    # max reflection rounds
    MAX_REFLECTION_ROUNDS = 3
    
    # max tool calls within a chat
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        Initialize the Report Agent.
        
        Args:
            graph_id: graph ID
            simulation_id: simulation ID
            simulation_requirement: simulation requirement text
            llm_client: LLM client (optional)
            zep_tools: Zep tools service (optional)
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # tool definitions
        self.tools = self._define_tools()
        
        # logger (initialized in generate_report)
        self.report_logger: Optional[ReportLogger] = None
        # logger (initialized in generate_report)
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(t('report.agentInitDone', graphId=graph_id, simulationId=simulation_id))
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define the available tools."""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "the question or topic you want to analyze in depth",
                    "report_context": "context of the current report section (optional; helps generate sharper sub-questions)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "search query, used for relevance ranking",
                    "include_expired": "whether to include expired/historical content (default True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "search query string",
                    "limit": "max results (optional, default 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "interview topic or requirement (e.g. 'learn what students think about the event')",
                    "max_agents": "max agents to interview (optional, default 5, max 10)"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute a tool call.
        
        Args:
            tool_name: tool name
            parameters: tool parameters
            report_context: report context (used by InsightForge)
            
        Returns:
            Tool execution result (text format)
        """
        logger.info(t('report.executingTool', toolName=tool_name, params=parameters))
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # breadth search - full picture
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # simple search - fast retrieval
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # in-depth interview - call the real OASIS interview API for simulated agent answers (dual-platform)
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== Legacy tools kept for backward compatibility (redirect internally) ==========
            
            elif tool_name == "search_graph":
                # redirect to quick_search
                logger.info(t('report.redirectToQuickSearch'))
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # redirect to insight_forge, which is stronger
                logger.info(t('report.redirectToInsightForge'))
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"Unknown tool: {tool_name}. Use one of: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(t('report.toolExecFailed', toolName=tool_name, error=str(e)))
            return f"Tool execution failed: {str(e)}"
    
    # valid tool-name set, used to validate bare-JSON fallback parsing
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse a tool call from an LLM response.

        Supported formats (in priority order):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (the whole response, or one line, is a tool-call JSON)
        """
        tool_calls = []

        # format 1: XML style (standard)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # format 2: fallback - LLM emitted bare JSON (no <tool_call> wrapper)
        # only tried when format 1 fails, to avoid matching JSON in body text
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # response may mix prose + bare JSON; try to extract the last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate that the parsed JSON is a legal tool call."""
        # supports {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} key styles
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # normalize keys to name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Build the tool description text."""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Params: {params_desc}")
        return "\n".join(desc_parts)

    @staticmethod
    def _strip_fake_tool_results(response: str) -> str:
        """Strip any <tool_result> blocks the LLM fabricated in its response.

        When the LLM generates a <tool_call> block and then continues to generate
        a <tool_result> block in the same response, we must strip the fake result
        before appending to message history. The real tool result will be injected
        separately by the system.
        """
        tag_pattern = re.compile(r'</?tool_result\b[^>]*>', flags=re.IGNORECASE)
        parts = []
        cursor = 0
        depth = 0

        for match in tag_pattern.finditer(response):
            if depth == 0:
                parts.append(response[cursor:match.start()])

            if match.group(0).lstrip().startswith('</'):
                depth = max(0, depth - 1)
            else:
                depth += 1
            cursor = match.end()

        if depth == 0:
            parts.append(response[cursor:])

        cleaned = ''.join(parts)
        # Treat a malformed opening tag without a closing `>` as unsafe too.
        cleaned = re.sub(r'<tool_result\b.*$', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan the report outline.
        
        Uses an LLM to analyze the simulation requirement and plan the outline.
        
        Args:
            progress_callback: progress callback
            
        Returns:
            ReportOutline: the report outline
        """
        logger.info(t('report.startPlanningOutline'))
        
        if progress_callback:
            progress_callback("planning", 0, t('progress.analyzingRequirements'))
        
        # fetch the simulation context first
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, t('progress.generatingOutline'))
        
        system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\n{get_language_instruction()}"
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, t('progress.parsingOutline'))
            
            # parse the outline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, t('progress.outlinePlanComplete'))
            
            logger.info(t('report.outlinePlanDone', count=len(sections)))
            return outline
            
        except Exception as e:
            logger.error(t('report.outlinePlanFailed', error=str(e)))
            # return the default outline (3 sections) as fallback
            return ReportOutline(
                title="Future Prediction Report",
                summary="Trend and risk analysis based on simulation predictions",
                sections=[
                    ReportSection(title="Prediction Scenario & Core Findings"),
                    ReportSection(title="Group Behavior Prediction Analysis"),
                    ReportSection(title="Trend Outlook & Risk Alerts")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate a single section with the ReACT pattern.
        
        ReACT loop:
        1. Thought - figure out what information is needed
        2. Action - call a tool to gather information
        3. Observation - analyze the tool result
        4. Repeat until the information suffices or the cap is hit
        5. Final Answer - write the section content
        
        Args:
            section: the section to generate
            outline: the full outline
            previous_sections: content of earlier sections (for coherence)
            progress_callback: progress callback
            section_index: section index (for logging)
            
        Returns:
            Section content (Markdown format)
        """
        logger.info(t('report.reactGenerateSection', title=section.title))
        
        # log section start
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # build the user prompt - pass up to 4000 chars per completed section
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # cap each section at 4000 chars
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(this is the first section)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT loop
        tool_calls_count = 0
        max_iterations = 5  # max iterations
        min_tool_calls = 3  # min tool calls
        conflict_retries = 0  # consecutive tool-call + Final Answer conflicts
        used_tools = set()  # tool names already called
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # report context, used by InsightForge for sub-question generation
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    t('progress.deepSearchAndWrite', current=tool_calls_count, max=self.MAX_TOOL_CALLS_PER_SECTION)
                )
            
            # call the LLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # check whether the LLM returned None (API failure or empty content)
            if response is None:
                logger.warning(t('report.sectionIterNone', title=section.title, iteration=iteration + 1))
                # iterations remain: append messages and retry
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(empty response)"})
                    messages.append({"role": "user", "content": "Please continue generating the content."})
                    continue
                # None on the final iteration too: break into the forced finish
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # parse once, reuse the result
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # -- conflict: LLM emitted a tool call AND a Final Answer --
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    t('report.sectionConflict', title=section.title, iteration=iteration+1, conflictCount=conflict_retries)
                )

                if conflict_retries <= 2:
                    # first two times: discard the response, ask the LLM to retry
                    cleaned_response = ReportAgent._strip_fake_tool_results(response)
                    messages.append({"role": "assistant", "content": cleaned_response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format error] Your reply contained both a tool call and a Final Answer, which is not allowed.\n"
                            "Each reply may do exactly one of the following:\n"
                            "- Call one tool (output a <tool_call> block; do not write a Final Answer)\n"
                            "- Output the final content (starting with 'Final Answer:'; do not include <tool_call>)\n"
                            "Please reply again doing only one of these."
                        ),
                    })
                    continue
                else:
                    # third time: degrade - truncate at the first tool call and force it
                    logger.warning(
                        t('report.sectionConflictDowngrade', title=section.title, conflictCount=conflict_retries)
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # log the LLM response
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # -- case 1: LLM emitted a Final Answer --
            if has_final_answer:
                cleaned_response = ReportAgent._strip_fake_tool_results(response)
                # too few tool calls: reject and require more tool use
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": cleaned_response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(these tools are unused so far, consider them: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # normal finish
                final_answer = cleaned_response.split("Final Answer:")[-1].strip()
                logger.info(t('report.sectionGenDone', title=section.title, count=tool_calls_count))

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # -- case 2: LLM tried to call a tool --
            if has_tool_calls:
                # tool budget exhausted -> tell it explicitly to output the Final Answer
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    cleaned_response = ReportAgent._strip_fake_tool_results(response)
                    messages.append({"role": "assistant", "content": cleaned_response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # execute only the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(t('report.multiToolOnlyFirst', total=len(tool_calls), toolName=call['name']))

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # build the unused-tools hint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                cleaned_response = ReportAgent._strip_fake_tool_results(response)
                messages.append({"role": "assistant", "content": cleaned_response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # -- case 3: neither a tool call nor a Final Answer --
            cleaned_response = ReportAgent._strip_fake_tool_results(response)
            messages.append({"role": "assistant", "content": cleaned_response})

            if tool_calls_count < min_tool_calls:
                # too few tool calls: recommend the unused ones
                unused_tools = all_tools - used_tools
                unused_hint = f"(these tools are unused so far, consider them: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # enough tool calls and the LLM produced content without the "Final Answer:" prefix
            # accept it as the final answer instead of spinning further
            logger.info(t('report.sectionNoPrefix', title=section.title, count=tool_calls_count))
            final_answer = cleaned_response

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # max iterations reached: force content generation
        logger.warning(t('report.sectionMaxIter', title=section.title))
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # check whether the LLM returned None during the forced finish
        if response is None:
            logger.error(t('report.sectionForceFailed', title=section.title))
            final_answer = t('report.sectionGenFailedContent')
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # log section content completion
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate the full report (streamed per section).
        
        Each section is saved to the folder as soon as it finishes - no waiting for the whole report.
        File layout:
        reports/{report_id}/
            meta.json       - report metadata
            outline.json    - report outline
            progress.json   - generation progress
            section_01.md   - section 1
            section_02.md   - section 2
            ...
            full_report.md  - complete report
        
        Args:
            progress_callback: progress callback (stage, progress, message)
            report_id: report ID (optional; auto-generated if omitted)
            
        Returns:
            Report: the complete report
        """
        import uuid
        
        # auto-generate report_id when not provided
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # completed section titles (for progress tracking)
        completed_section_titles = []
        
        try:
            # init: create the report folder and persist the initial state
            ReportManager._ensure_report_folder(report_id)
            
            # init the structured logger (agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # init the console logger (console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, t('progress.initReport'),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # phase 1: plan the outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, t('progress.startPlanningOutline'),
                completed_sections=[]
            )
            
            # log planning start
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, t('progress.startPlanningOutline'))
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # log planning completion
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # save the outline to disk
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, t('progress.outlineDone', count=len(outline.sections)),
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(t('report.outlineSavedToFile', reportId=report_id))
            
            # phase 2: generate sections one by one (saving each)
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # keep content for context
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # update progress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    t('progress.generatingSection', title=section.title, current=section_num, total=total_sections),
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        t('progress.generatingSection', title=section.title, current=section_num, total=total_sections)
                    )
                
                # generate the main section content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # save the section
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # log section completion
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(t('report.sectionSaved', reportId=report_id, sectionNum=f"{section_num:02d}"))
                
                # update progress
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    t('progress.sectionDone', title=section.title),
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # phase 3: assemble the full report
            if progress_callback:
                progress_callback("generating", 95, t('progress.assemblingReport'))
            
            ReportManager.update_progress(
                report_id, "generating", 95, t('progress.assemblingReport'),
                completed_sections=completed_section_titles
            )
            
            # assemble via ReportManager
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # total elapsed time
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # log report completion
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # save the final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, t('progress.reportComplete'),
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, t('progress.reportComplete'))
            
            logger.info(t('report.reportGenDone', reportId=report_id))
            
            # close the console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(t('report.reportGenFailed', error=str(e)))
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # log the error
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # persist the failure state
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, t('progress.reportFailed', error=str(e)),
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # ignore save failures
            
            # close the console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with the Report Agent.
        
        The agent may autonomously call retrieval tools while answering.
        
        Args:
            message: user message
            chat_history: conversation history
            
        Returns:
            {
                "response": "agent reply",
                "tool_calls": [list of tools called],
                "sources": [information sources]
            }
        """
        logger.info(t('report.agentChat', message=message[:50]))
        
        chat_history = chat_history or []
        
        # fetch the generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # cap the report length to bound the context size
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [report content truncated] ..."
        except Exception as e:
            logger.warning(t('report.fetchReportFailed', error=e))
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(no report yet)",
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # add conversation history
        for h in chat_history[-10:]:  # cap history length
            messages.append(h)
        
        # add the user message
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACT loop (simplified)
        tool_calls_made = []
        max_iterations = 2  # fewer iterations for chat
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # parse the tool call
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # no tool call: return the response directly
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                clean_response = ReportAgent._strip_fake_tool_results(clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # execute the tool call (limited)
            tool_results = []
            for call in tool_calls[:1]:  # at most 1 tool call per round
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # cap result length
                })
                tool_calls_made.append(call)
            
            # append results to the messages
            cleaned_response = ReportAgent._strip_fake_tool_results(response)
            messages.append({"role": "assistant", "content": cleaned_response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # max iterations reached: get the final response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # clean the response
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        clean_response = ReportAgent._strip_fake_tool_results(clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Report manager.
    
    Handles report persistence and retrieval.
    
    File layout (per-section output):
    reports/
      {report_id}/
        meta.json          - report metadata and status
        outline.json       - report outline
        progress.json      - generation progress
        section_01.md      - section 1
        section_02.md      - section 2
        ...
        full_report.md     - complete report
    """
    
    # report storage directory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure the report root directory exists."""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get the report folder path."""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure the report folder exists and return its path."""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get the meta file path."""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get the full-report Markdown path."""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get the outline file path."""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get the progress file path."""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get a section Markdown path."""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get the agent log file path."""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get the console log file path."""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Read the console log content.
        
        This is the console output (INFO, WARNING, ...) produced while generating the report,
        separate from the structured agent_log.jsonl entries.
        
        Args:
            report_id: report ID
            from_line: first line to read (incremental reads; 0 = from the start)
            
        Returns:
            {
                "logs": [log lines],
                "total_lines": total line count,
                "from_line": starting line number,
                "has_more": whether more logs exist
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # keep the raw log line, minus the trailing newline
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # read to the end
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Read the whole console log (single shot).
        
        Args:
            report_id: report ID
            
        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Read the agent log content.
        
        Args:
            report_id: report ID
            from_line: first line to read (incremental reads; 0 = from the start)
            
        Returns:
            {
                "logs": [log entries],
                "total_lines": total entry count,
                "from_line": starting line number,
                "has_more": whether more logs exist
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # skip unparseable lines
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # read to the end
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Read the whole agent log (single shot).
        
        Args:
            report_id: report ID
            
        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save the report outline.
        
        Call immediately after the planning phase completes.
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(t('report.outlineSaved', reportId=report_id))
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single section.

        Call immediately after each section finishes, enabling per-section output.

        Args:
            report_id: report ID
            section_index: section index (1-based)
            section: section object

        Returns:
            The saved file path
        """
        cls._ensure_report_folder(report_id)

        # build the section Markdown - clean possible duplicate headings
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # save the file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(t('report.sectionFileSaved', reportId=report_id, fileSuffix=file_suffix))
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content.
        
        1. Remove leading Markdown headings duplicating the section title
        2. Convert all ### and lower-level headings into bold text
        
        Args:
            content: raw content
            section_title: section title
            
        Returns:
            Cleaned content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Markdown heading line?
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # duplicate of the section title? (skip within the first 5 lines)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # convert every heading level (#, ##, ###, ####...) to bold
                # the system adds section titles; content must not contain headings
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # keep a blank line
                continue
            
            # if the previous line was a skipped heading, also skip an adjacent blank line
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # strip leading blank lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # strip leading horizontal rules
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # also strip blank lines right after a rule
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress.
        
        The frontend reads progress.json for live progress.
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress."""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        List generated sections.
        
        Returns info for all saved section files.
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # parse the section index from the filename
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble the complete report.
        
        Builds the full report from saved section files, with heading cleanup.
        """
        folder = cls._get_report_folder(report_id)
        
        # build the report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # read all section files in order
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # post-process: fix heading issues across the whole report
        md_content = cls._post_process_report(md_content, outline)
        
        # save the full report
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(t('report.fullReportAssembled', reportId=report_id))
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-process report content.
        
        1. Remove duplicate headings
        2. Keep the report title (#) and section titles (##); demote other levels (###, ####...)
        3. Collapse extra blank lines and rules
        
        Args:
            content: raw report content
            outline: report outline
            
        Returns:
            Processed content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # collect all section titles from the outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # heading line?
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # duplicate heading? (same content within 5 consecutive lines)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # skip the duplicate heading and its trailing blank line
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # heading level handling:
                # - # (level 1): only the report title may use it
                # - ## (level 2): section titles
                # - ### and below (level >= 3): convert to bold text
                
                if level == 1:
                    if title == outline.title:
                        # keep the report title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # section title mistakenly used #: fix to ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # other level-1 headings become bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # keep the section title
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # non-section level-2 headings become bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and below become bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # skip a rule immediately following a heading
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # keep a single blank line after headings
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # collapse runs of blank lines (keep at most 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and the full report."""
        cls._ensure_report_folder(report.report_id)
        
        # save metadata JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # save the outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # save the full Markdown report
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(t('report.reportSaved', reportId=report.report_id))
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get a report."""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # legacy format: files stored directly under the reports directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # rebuild the Report object
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # if markdown_content is empty, try reading full_report.md
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get a report by simulation ID."""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # legacy format: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """List reports."""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # new format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # legacy format: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # newest first by creation time
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete a report (the whole folder)."""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # new format: delete the whole folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(t('report.reportFolderDeleted', reportId=report_id))
            return True
        
        # legacy format: delete the standalone file
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
