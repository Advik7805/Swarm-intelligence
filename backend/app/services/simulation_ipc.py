"""
Simulation IPC module
Inter-process communication between the Flask backend and simulation scripts.

A simple command/response pattern over the filesystem:
1. 1. Flask writes commands into the commands/ directory
2. 2. the sim script polls for commands, runs them, and writes responses to responses/
3. 3. Flask polls the responses directory for results
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('hivemind.simulation_ipc')


class CommandType(str, Enum):
    """Command types"""
    INTERVIEW = "interview"           # single-agent interview
    BATCH_INTERVIEW = "batch_interview"  # batch interview
    CLOSE_ENV = "close_env"           # close environment


class CommandStatus(str, Enum):
    """Command status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """An IPC command."""
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """An IPC response."""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
        Simulation IPC client (Flask side).
    
        Sends commands to the simulation process and waits for responses.
    """
    
    def __init__(self, simulation_dir: str):
        """
                Initialize the IPC client.
        
        Args:
                        simulation_dir: simulation data directory
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
                # make sure the directory exists
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
                Send a command and wait for its response.
        
        Args:
                        command_type: command type
                        args: command arguments
                        timeout: seconds
                        poll_interval: polling interval in seconds
            
        Returns:
            IPCResponse
            
        Raises:
                        TimeoutError: response wait timed out
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
                # write the command file
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"IPC command sent: {command_type.value}, command_id={command_id}")
        
                # wait for the response
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)
                    
                                        # clean up command and response files
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f"IPC response received: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse the response: {e}")
            
            time.sleep(poll_interval)
        
                # timed out
        logger.error(f"IPC response wait timed out: command_id={command_id}")
        
                # clean up the command file
        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"Command response wait timed out ({timeout}s)")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
                Send a single-agent interview command.
        
        Args:
            agent_id: Agent ID
                        prompt: interview question
                        platform: optional platform
                - "twitter": Twitter platform only
                - "reddit": Reddit platform only  
                                - None: both platforms on dual-platform runs, else that run's platform
                        timeout: seconds
            
        Returns:
                        IPCResponse whose result holds the interview outcome
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
                Send a batch-interview command.
        
        Args:
            interviews: list of {"agent_id": int, "prompt": str, "platform": str(optional)}
            platform: default (overridden per interview item)
                - "twitter": Twitter platform only by default
                - "reddit": Reddit platform only by default
                - None: dual-platform runs interview both platforms per agent
                        timeout: seconds
            
        Returns:
            IPCResponse whose result holds all interview outcomes
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
                Send the close-environment command.
        
        Args:
                        timeout: seconds
            
        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
                Check whether the simulation environment is alive.
        
                Decided by checking the env_status.json file.
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
        Simulation IPC server (simulation-script side).
    
        Polls the command directory, executes commands, returns responses.
    """
    
    def __init__(self, simulation_dir: str):
        """
                Initialize the IPC server.
        
        Args:
                        simulation_dir: simulation data directory
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
                # make sure the directory exists
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
                # environment status
        self._running = False
    
    def start(self):
        """Mark the server as running."""
        self._running = True
        self._update_env_status("alive")
    
    def stop(self):
        """Mark the server as stopped."""
        self._running = False
        self._update_env_status("stopped")
    
    def _update_env_status(self, status: str):
        """Update the environment status file."""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_commands(self) -> Optional[IPCCommand]:
        """
                Poll the command directory; return the first pending command.
        
        Returns:
                        IPCCommand or None
        """
        if not os.path.exists(self.commands_dir):
            return None
        
                # command files sorted by time
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Failed to read command file: {filepath}, {e}")
                continue
        
        return None
    
    def send_response(self, response: IPCResponse):
        """
                Send a response.
        
        Args:
                        response: the IPC response
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
                # delete the command file
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def send_success(self, command_id: str, result: Dict[str, Any]):
        """Send a success response."""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))
    
    def send_error(self, command_id: str, error: str):
        """Send an error response."""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))
