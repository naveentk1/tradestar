#!/usr/bin/env python3
"""
PyShell - A fully functional shell written in Python
Features: pipes, redirects, variables, globs, history, tab completion, aliases, jobs
"""

import os
import sys
import subprocess
import shlex
import glob
import readline
import signal
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ============ COLORS ============
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'

# ============ ENVIRONMENT ============
class Environment:
    def __init__(self):
        self.variables = dict(os.environ)
        self.aliases = {}
        self.history = []
        
    def set(self, key: str, value: str):
        self.variables[key] = value
        os.environ[key] = value
        
    def get(self, key: str, default: str = "") -> str:
        return self.variables.get(key, default)
    
    def expand(self, text: str) -> str:
        """Expand variables like $VAR or ${VAR}"""
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return self.get(var_name, match.group(0))
        
        # Match $VAR or ${VAR}
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        return re.sub(pattern, replace_var, text)
    
    def expand_tilde(self, path: str) -> str:
        """Expand ~ to home directory"""
        if path.startswith('~'):
            home = self.get('HOME', str(Path.home()))
            return home + path[1:]
        return path
    
    def add_alias(self, name: str, command: str):
        self.aliases[name] = command
    
    def get_alias(self, name: str) -> Optional[str]:
        return self.aliases.get(name)

# ============ COMMAND STRUCTURE ============
class Command:
    def __init__(self):
        self.args: List[str] = []
        self.input_file: Optional[str] = None
        self.output_file: Optional[str] = None
        self.append_output: bool = False
        self.background: bool = False

class Pipeline:
    def __init__(self):
        self.commands: List[Command] = []

# ============ PARSER ============
class Parser:
    @staticmethod
    def parse(input_line: str, env: Environment) -> List[Pipeline]:
        """Parse input into pipelines"""
        # Split by semicolon for multiple commands
        statements = Parser._split_by_semicolon(input_line)
        pipelines = []
        
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                pipelines.append(Parser._parse_pipeline(stmt, env))
        
        return pipelines
    
    @staticmethod
    def _split_by_semicolon(text: str) -> List[str]:
        """Split by ; while respecting quotes"""
        parts = []
        current = []
        in_quotes = False
        quote_char = None
        
        for char in text:
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
                current.append(char)
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current.append(char)
            elif char == ';' and not in_quotes:
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    @staticmethod
    def _parse_pipeline(text: str, env: Environment) -> Pipeline:
        """Parse a pipeline (commands separated by |)"""
        pipeline = Pipeline()
        
        # Split by pipe
        commands = Parser._split_by_pipe(text)
        
        for cmd_text in commands:
            pipeline.commands.append(Parser._parse_command(cmd_text, env))
        
        return pipeline
    
    @staticmethod
    def _split_by_pipe(text: str) -> List[str]:
        """Split by | while respecting quotes"""
        parts = []
        current = []
        in_quotes = False
        quote_char = None
        
        for char in text:
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
                current.append(char)
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current.append(char)
            elif char == '|' and not in_quotes:
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    @staticmethod
    def _parse_command(text: str, env: Environment) -> Command:
        """Parse a single command with redirects"""
        cmd = Command()
        tokens = shlex.split(text)
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token == '<':
                if i + 1 < len(tokens):
                    cmd.input_file = env.expand_tilde(env.expand(tokens[i + 1]))
                    i += 2
                else:
                    i += 1
            elif token == '>':
                if i + 1 < len(tokens):
                    cmd.output_file = env.expand_tilde(env.expand(tokens[i + 1]))
                    cmd.append_output = False
                    i += 2
                else:
                    i += 1
            elif token == '>>':
                if i + 1 < len(tokens):
                    cmd.output_file = env.expand_tilde(env.expand(tokens[i + 1]))
                    cmd.append_output = True
                    i += 2
                else:
                    i += 1
            elif token == '&' and i == len(tokens) - 1:
                cmd.background = True
                i += 1
            else:
                # Expand variables and globs
                expanded = env.expand(token)
                expanded = env.expand_tilde(expanded)
                
                # Glob expansion
                if '*' in expanded or '?' in expanded or '[' in expanded:
                    matches = glob.glob(expanded)
                    if matches:
                        cmd.args.extend(matches)
                    else:
                        cmd.args.append(expanded)
                else:
                    cmd.args.append(expanded)
                i += 1
        
        # Check for alias
        if cmd.args and cmd.args[0] in env.aliases:
            alias_cmd = env.aliases[cmd.args[0]]
            alias_tokens = shlex.split(alias_cmd)
            cmd.args = alias_tokens + cmd.args[1:]
        
        return cmd

# ============ BUILT-IN COMMANDS ============
class Builtins:
    @staticmethod
    def execute(cmd: Command, env: Environment) -> Optional[int]:
        """Execute built-in command, return None if not a builtin"""
        if not cmd.args:
            return None
        
        name = cmd.args[0]
        
        builtins = {
            'cd': Builtins.cmd_cd,
            'pwd': Builtins.cmd_pwd,
            'exit': Builtins.cmd_exit,
            'export': Builtins.cmd_export,
            'echo': Builtins.cmd_echo,
            'history': Builtins.cmd_history,
            'alias': Builtins.cmd_alias,
            'unalias': Builtins.cmd_unalias,
            'env': Builtins.cmd_env,
            'source': Builtins.cmd_source,
        }
        
        if name in builtins:
            return builtins[name](cmd, env)
        
        return None
    
    @staticmethod
    def cmd_cd(cmd: Command, env: Environment) -> int:
        path = cmd.args[1] if len(cmd.args) > 1 else env.get('HOME')
        path = env.expand_tilde(path)
        
        try:
            os.chdir(path)
            env.set('PWD', os.getcwd())
            return 0
        except FileNotFoundError:
            print(f"cd: {path}: No such file or directory", file=sys.stderr)
            return 1
        except PermissionError:
            print(f"cd: {path}: Permission denied", file=sys.stderr)
            return 1
    
    @staticmethod
    def cmd_pwd(cmd: Command, env: Environment) -> int:
        print(os.getcwd())
        return 0
    
    @staticmethod
    def cmd_exit(cmd: Command, env: Environment) -> int:
        code = int(cmd.args[1]) if len(cmd.args) > 1 else 0
        sys.exit(code)
    
    @staticmethod
    def cmd_export(cmd: Command, env: Environment) -> int:
        if len(cmd.args) < 2:
            # Print all variables
            for key, value in sorted(env.variables.items()):
                print(f"{key}={value}")
        else:
            for arg in cmd.args[1:]:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    env.set(key, value)
        return 0
    
    @staticmethod
    def cmd_echo(cmd: Command, env: Environment) -> int:
        output = ' '.join(cmd.args[1:])
        print(env.expand(output))
        return 0
    
    @staticmethod
    def cmd_history(cmd: Command, env: Environment) -> int:
        for i, line in enumerate(env.history, 1):
            print(f"  {i}  {line}")
        return 0
    
    @staticmethod
    def cmd_alias(cmd: Command, env: Environment) -> int:
        if len(cmd.args) < 2:
            # Print all aliases
            for name, command in sorted(env.aliases.items()):
                print(f"alias {name}='{command}'")
        else:
            for arg in cmd.args[1:]:
                if '=' in arg:
                    name, command = arg.split('=', 1)
                    command = command.strip('\'"')
                    env.add_alias(name, command)
        return 0
    
    @staticmethod
    def cmd_unalias(cmd: Command, env: Environment) -> int:
        for name in cmd.args[1:]:
            if name in env.aliases:
                del env.aliases[name]
        return 0
    
    @staticmethod
    def cmd_env(cmd: Command, env: Environment) -> int:
        for key, value in sorted(env.variables.items()):
            print(f"{key}={value}")
        return 0
    
    @staticmethod
    def cmd_source(cmd: Command, env: Environment) -> int:
        if len(cmd.args) < 2:
            print("source: missing file argument", file=sys.stderr)
            return 1
        
        try:
            with open(cmd.args[1], 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Execute each line
                        pipelines = Parser.parse(line, env)
                        for pipeline in pipelines:
                            Executor.execute_pipeline(pipeline, env)
            return 0
        except FileNotFoundError:
            print(f"source: {cmd.args[1]}: No such file", file=sys.stderr)
            return 1

# ============ EXECUTOR ============
class Executor:
    @staticmethod
    def execute_pipeline(pipeline: Pipeline, env: Environment) -> int:
        """Execute a pipeline of commands"""
        if not pipeline.commands:
            return 0
        
        # Single command - check for builtins
        if len(pipeline.commands) == 1:
            result = Builtins.execute(pipeline.commands[0], env)
            if result is not None:
                return result
        
        # Execute pipeline with pipes
        processes = []
        prev_pipe = None
        
        for i, cmd in enumerate(pipeline.commands):
            if not cmd.args:
                continue
            
            # Create pipe if not last command
            if i < len(pipeline.commands) - 1:
                curr_pipe = os.pipe()
            else:
                curr_pipe = None
            
            # Set up stdin
            stdin = None
            if i == 0 and cmd.input_file:
                stdin = open(cmd.input_file, 'r')
            elif prev_pipe:
                stdin = prev_pipe[0]
            
            # Set up stdout
            stdout = None
            if i == len(pipeline.commands) - 1 and cmd.output_file:
                mode = 'a' if cmd.append_output else 'w'
                stdout = open(cmd.output_file, mode)
            elif curr_pipe:
                stdout = curr_pipe[1]
            
            # Prepare stdin/stdout for subprocess
            stdin_fd = stdin.fileno() if stdin else None
            stdout_fd = stdout.fileno() if stdout else None
            
            try:
                proc = subprocess.Popen(
                    cmd.args,
                    stdin=stdin_fd,
                    stdout=stdout_fd,
                    stderr=subprocess.PIPE if not cmd.background else None
                )
                processes.append(proc)
                
                # Close pipes in parent
                if stdin and isinstance(stdin, int):
                    os.close(stdin)
                if stdout and isinstance(stdout, int):
                    os.close(stdout)
                
            except FileNotFoundError:
                print(f"{cmd.args[0]}: command not found", file=sys.stderr)
                return 127
            except Exception as e:
                print(f"Error executing {cmd.args[0]}: {e}", file=sys.stderr)
                return 1
            
            # Close previous pipe read end
            if prev_pipe:
                os.close(prev_pipe[0])
            
            # Set up for next iteration
            prev_pipe = curr_pipe
        
        # Wait for all processes
        last_status = 0
        if not cmd.background:
            for proc in processes:
                proc.wait()
                last_status = proc.returncode
        else:
            print(f"[{processes[-1].pid}] started in background")
        
        return last_status

# ============ SHELL ============
class Shell:
    def __init__(self):
        self.env = Environment()
        self.last_status = 0
        
        # Set up readline
        self._setup_readline()
        
        # Load shell rc file if exists
        rc_file = os.path.expanduser('~/.pyshellrc')
        if os.path.exists(rc_file):
            with open(rc_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            pipelines = Parser.parse(line, self.env)
                            for pipeline in pipelines:
                                Executor.execute_pipeline(pipeline, self.env)
                        except:
                            pass
    
    def _setup_readline(self):
        """Set up readline for history and tab completion"""
        # History file
        history_file = os.path.expanduser('~/.pyshell_history')
        try:
            readline.read_history_file(history_file)
        except FileNotFoundError:
            pass
        
        readline.set_history_length(1000)
        
        # Tab completion
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self._completer)
        
        # Save history on exit
        import atexit
        atexit.register(readline.write_history_file, history_file)
    
    def _completer(self, text, state):
        """Tab completion function"""
        options = []
        
        # Complete commands from PATH
        if '/' not in text:
            path_dirs = self.env.get('PATH', '').split(':')
            for directory in path_dirs:
                if os.path.isdir(directory):
                    try:
                        for item in os.listdir(directory):
                            if item.startswith(text):
                                options.append(item)
                    except PermissionError:
                        pass
        
        # Complete files/directories
        try:
            matches = glob.glob(text + '*')
            options.extend(matches)
        except:
            pass
        
        options = sorted(set(options))
        
        if state < len(options):
            return options[state]
        return None
    
    def get_prompt(self) -> str:
        """Generate colorful prompt"""
        user = self.env.get('USER', 'user')
        hostname = os.uname().nodename
        cwd = os.getcwd()
        
        # Shorten home directory to ~
        home = self.env.get('HOME')
        if cwd.startswith(home):
            cwd = '~' + cwd[len(home):]
        
        # Color the prompt
        prompt = (
            f"{Colors.BOLD}{Colors.GREEN}{user}@{hostname}{Colors.RESET}:"
            f"{Colors.BOLD}{Colors.BLUE}{cwd}{Colors.RESET}"
            f"{Colors.YELLOW}${Colors.RESET} "
        )
        
        return prompt
    
    def run(self):
        """Main shell loop"""
        print(f"{Colors.CYAN}PyShell v1.0 - A Python Shell{Colors.RESET}")
        print("Type 'exit' to quit\n")
        
        # Ignore SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        
        while True:
            try:
                # Get input
                line = input(self.get_prompt())
                
                if not line.strip():
                    continue
                
                # Add to history
                self.env.history.append(line)
                
                # Parse and execute
                pipelines = Parser.parse(line, self.env)
                
                for pipeline in pipelines:
                    self.last_status = Executor.execute_pipeline(pipeline, self.env)
                
                # Store last exit status
                self.env.set('?', str(self.last_status))
                
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
                self.last_status = 1

# ============ MAIN ============
if __name__ == '__main__':
    shell = Shell()
    shell.run()