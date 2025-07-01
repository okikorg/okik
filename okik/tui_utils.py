"""
TUI Utilities for Okik CLI
Enhanced terminal user interface components
"""

from typing import List, Dict, Any, Optional, Callable
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED, DOUBLE
import asyncio
from concurrent.futures import ThreadPoolExecutor

console = Console()

class InteractiveMenu:
    """Create an interactive menu with keyboard navigation"""
    
    def __init__(self, title: str, options: List[Dict[str, Any]]):
        self.title = title
        self.options = options
        self.selected_index = 0
        
    def display(self) -> Optional[Dict[str, Any]]:
        """Display the menu and return the selected option"""
        with Live(self._render(), refresh_per_second=10, console=console) as live:
            while True:
                key = console.input()
                
                if key.lower() == 'q':
                    return None
                elif key == '\n' or key == '\r':
                    return self.options[self.selected_index]
                elif key == '\x1b[A':  # Up arrow
                    self.selected_index = max(0, self.selected_index - 1)
                elif key == '\x1b[B':  # Down arrow
                    self.selected_index = min(len(self.options) - 1, self.selected_index + 1)
                
                live.update(self._render())
    
    def _render(self) -> Panel:
        """Render the menu"""
        menu_items = []
        for i, option in enumerate(self.options):
            if i == self.selected_index:
                menu_items.append(f"[bold cyan]▶ {option['label']}[/bold cyan]")
            else:
                menu_items.append(f"  {option['label']}")
        
        content = "\n".join(menu_items)
        content += "\n\n[dim]Use ↑↓ arrows to navigate, Enter to select, Q to quit[/dim]"
        
        return Panel(
            content,
            title=self.title,
            box=ROUNDED,
            border_style="cyan"
        )

class TaskRunner:
    """Run multiple tasks in parallel with progress tracking"""
    
    def __init__(self, title: str = "Running Tasks"):
        self.title = title
        self.tasks = []
        
    def add_task(self, name: str, func: Callable, *args, **kwargs):
        """Add a task to be executed"""
        self.tasks.append({
            'name': name,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'status': 'pending',
            'result': None,
            'error': None
        })
    
    def run(self) -> List[Dict[str, Any]]:
        """Execute all tasks in parallel"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            
            task_id = progress.add_task(f"[cyan]{self.title}", total=len(self.tasks))
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                
                for task in self.tasks:
                    future = executor.submit(
                        self._run_task,
                        task
                    )
                    futures.append((future, task))
                
                for future, task in futures:
                    try:
                        result = future.result()
                        task['result'] = result
                        task['status'] = 'completed'
                    except Exception as e:
                        task['error'] = str(e)
                        task['status'] = 'failed'
                    
                    progress.update(task_id, advance=1)
        
        return self.tasks
    
    def _run_task(self, task: Dict[str, Any]) -> Any:
        """Execute a single task"""
        return task['func'](*task['args'], **task['kwargs'])

class LiveMetrics:
    """Display live metrics in a dashboard-like interface"""
    
    def __init__(self, title: str = "Live Metrics"):
        self.title = title
        self.metrics = {}
        self.running = False
        
    def update_metric(self, key: str, value: Any, unit: str = ""):
        """Update a metric value"""
        self.metrics[key] = {
            'value': value,
            'unit': unit,
            'updated': time.time()
        }
    
    async def start(self):
        """Start the live display"""
        self.running = True
        
        with Live(self._render(), refresh_per_second=2, console=console) as live:
            while self.running:
                live.update(self._render())
                await asyncio.sleep(0.5)
    
    def stop(self):
        """Stop the live display"""
        self.running = False
    
    def _render(self) -> Layout:
        """Render the metrics dashboard"""
        layout = Layout()
        
        # Create header
        header = Panel(
            Align.center(Text(self.title, style="bold cyan")),
            box=DOUBLE,
            border_style="cyan"
        )
        
        # Create metrics grid
        metrics_table = Table(box=ROUNDED, show_header=False)
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="yellow", justify="right")
        
        for key, data in self.metrics.items():
            value_str = f"{data['value']}"
            if data['unit']:
                value_str += f" {data['unit']}"
            metrics_table.add_row(key, value_str)
        
        # Add timestamp
        metrics_table.add_row(
            "[dim]Last Updated[/dim]",
            f"[dim]{time.strftime('%H:%M:%S')}[/dim]"
        )
        
        layout.split_column(
            Layout(header, size=3),
            Layout(Panel(metrics_table, box=ROUNDED))
        )
        
        return layout

def create_spinner_context(message: str):
    """Create a context manager for spinner with message"""
    return console.status(f"[cyan]{message}[/cyan]", spinner="dots")

def format_size(bytes: float) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def format_duration(seconds: float) -> str:
    """Format duration to human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"

def create_comparison_table(
    title: str,
    data: List[Dict[str, Any]],
    columns: List[str]
) -> Table:
    """Create a comparison table with highlighting"""
    table = Table(title=title, box=ROUNDED, title_style="bold cyan")
    
    # Add columns
    for col in columns:
        table.add_column(col, style="cyan" if col == columns[0] else "white")
    
    # Add rows with conditional formatting
    for row_data in data:
        row = []
        for col in columns:
            value = row_data.get(col, "")
            
            # Apply conditional formatting
            if isinstance(value, bool):
                row.append("[green]✓[/green]" if value else "[red]✗[/red]")
            elif isinstance(value, (int, float)) and col != columns[0]:
                # Highlight best values (assuming lower is better)
                min_val = min(d.get(col, float('inf')) for d in data if isinstance(d.get(col), (int, float)))
                if value == min_val:
                    row.append(f"[bold green]{value}[/bold green]")
                else:
                    row.append(str(value))
            else:
                row.append(str(value))
        
        table.add_row(*row)
    
    return table

def create_ascii_chart(
    data: List[float],
    width: int = 40,
    height: int = 10,
    title: str = ""
) -> str:
    """Create a simple ASCII chart"""
    if not data:
        return ""
    
    max_val = max(data)
    min_val = min(data)
    range_val = max_val - min_val or 1
    
    # Normalize data
    normalized = [(v - min_val) / range_val * height for v in data]
    
    # Create chart
    chart_lines = []
    
    if title:
        chart_lines.append(f"[bold cyan]{title}[/bold cyan]")
        chart_lines.append("")
    
    # Y-axis labels and chart
    for y in range(height, -1, -1):
        line = f"{min_val + (y/height * range_val):>8.2f} │"
        
        for x, value in enumerate(normalized):
            if value >= y:
                line += "█"
            else:
                line += " "
        
        chart_lines.append(line)
    
    # X-axis
    chart_lines.append("         └" + "─" * len(data))
    
    return "\n".join(chart_lines)