"""
Async Operations Module for Okik CLI
Enhanced performance through async/await patterns
"""

import asyncio
import aiofiles
import aiohttp
import json
import yaml
from typing import List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from kubernetes_asyncio import client, config
from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()

class AsyncKubernetesManager:
    """Async Kubernetes API manager with connection pooling"""
    
    def __init__(self):
        self._clients = {}
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize Kubernetes configuration asynchronously"""
        if not self._initialized:
            await config.load_kube_config()
            self._initialized = True
    
    async def get_client(self, api_type: str):
        """Get a pooled Kubernetes API client"""
        async with self._lock:
            if api_type not in self._clients:
                await self.initialize()
                if api_type == "apps_v1":
                    self._clients[api_type] = client.AppsV1Api()
                elif api_type == "core_v1":
                    self._clients[api_type] = client.CoreV1Api()
                elif api_type == "autoscaling_v1":
                    self._clients[api_type] = client.AutoscalingV1Api()
            return self._clients[api_type]

class AsyncFileManager:
    """Async file operations for better I/O performance"""
    
    @staticmethod
    async def read_yaml(file_path: str) -> Dict[str, Any]:
        """Asynchronously read and parse YAML file"""
        async with aiofiles.open(file_path, 'r') as file:
            content = await file.read()
            return yaml.safe_load(content)
    
    @staticmethod
    async def read_json(file_path: str) -> Dict[str, Any]:
        """Asynchronously read and parse JSON file"""
        async with aiofiles.open(file_path, 'r') as file:
            content = await file.read()
            return json.loads(content)
    
    @staticmethod
    async def write_yaml(file_path: str, data: Dict[str, Any]):
        """Asynchronously write YAML file"""
        content = yaml.dump(data, default_flow_style=False)
        async with aiofiles.open(file_path, 'w') as file:
            await file.write(content)
    
    @staticmethod
    async def write_json(file_path: str, data: Dict[str, Any]):
        """Asynchronously write JSON file"""
        content = json.dumps(data, indent=2)
        async with aiofiles.open(file_path, 'w') as file:
            await file.write(content)

class AsyncDeploymentManager:
    """Async deployment operations for better performance"""
    
    def __init__(self):
        self.k8s_manager = AsyncKubernetesManager()
        self.file_manager = AsyncFileManager()
    
    async def deploy_multiple_services(self, yaml_files: List[str], progress: Progress):
        """Deploy multiple services concurrently"""
        tasks = []
        task_ids = []
        
        for yaml_file in yaml_files:
            task_id = progress.add_task(f"Deploying {yaml_file}...", total=100)
            task_ids.append(task_id)
            
            task = asyncio.create_task(
                self._deploy_single_service(yaml_file, progress, task_id)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _deploy_single_service(self, yaml_file: str, progress: Progress, task_id: TaskID):
        """Deploy a single service asynchronously"""
        try:
            # Read YAML configuration
            progress.update(task_id, advance=20, description=f"Reading {yaml_file}...")
            yaml_content = await self.file_manager.read_yaml(yaml_file)
            
            # Get appropriate Kubernetes client
            progress.update(task_id, advance=20, description=f"Connecting to Kubernetes...")
            
            kind = yaml_content.get('kind', '').lower()
            if kind == 'deployment':
                client_api = await self.k8s_manager.get_client('apps_v1')
                deploy_func = client_api.create_namespaced_deployment
            elif kind == 'service':
                client_api = await self.k8s_manager.get_client('core_v1')
                deploy_func = client_api.create_namespaced_service
            else:
                raise ValueError(f"Unsupported resource type: {kind}")
            
            # Deploy the resource
            progress.update(task_id, advance=40, description=f"Deploying {yaml_file}...")
            result = await deploy_func(
                namespace="default",
                body=yaml_content
            )
            
            progress.update(task_id, advance=20, description=f"Deployed {yaml_file} successfully!")
            return {"status": "success", "file": yaml_file, "result": result}
            
        except Exception as e:
            progress.update(task_id, advance=100, description=f"Failed to deploy {yaml_file}: {str(e)}")
            return {"status": "error", "file": yaml_file, "error": str(e)}

class AsyncBuildManager:
    """Async Docker build operations"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def build_multiple_images(self, build_configs: List[Dict[str, Any]], progress: Progress):
        """Build multiple Docker images concurrently"""
        semaphore = asyncio.Semaphore(4)  # Limit concurrent builds
        tasks = []
        
        for config in build_configs:
            task = asyncio.create_task(
                self._build_single_image(config, progress, semaphore)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _build_single_image(self, config: Dict[str, Any], progress: Progress, semaphore: asyncio.Semaphore):
        """Build a single Docker image asynchronously"""
        async with semaphore:
            task_id = progress.add_task(f"Building {config['name']}...", total=100)
            
            try:
                # Prepare build context
                progress.update(task_id, advance=20, description=f"Preparing {config['name']}...")
                await self._prepare_build_context(config)
                
                # Run Docker build in thread executor
                progress.update(task_id, advance=30, description=f"Building {config['name']}...")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._run_docker_build,
                    config
                )
                
                progress.update(task_id, advance=50, description=f"Built {config['name']} successfully!")
                return {"status": "success", "config": config, "result": result}
                
            except Exception as e:
                progress.update(task_id, advance=100, description=f"Failed to build {config['name']}: {str(e)}")
                return {"status": "error", "config": config, "error": str(e)}
    
    async def _prepare_build_context(self, config: Dict[str, Any]):
        """Prepare build context asynchronously"""
        # Create build directory
        build_dir = Path(config['build_dir'])
        build_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy files asynchronously
        await asyncio.gather(
            self._copy_file(config['source_file'], build_dir / 'main.py'),
            self._copy_file(config['dockerfile'], build_dir / 'Dockerfile'),
            self._copy_file(config['requirements'], build_dir / 'requirements.txt')
        )
    
    async def _copy_file(self, src: str, dst: Path):
        """Copy file asynchronously"""
        async with aiofiles.open(src, 'rb') as src_file:
            content = await src_file.read()
        
        async with aiofiles.open(dst, 'wb') as dst_file:
            await dst_file.write(content)
    
    def _run_docker_build(self, config: Dict[str, Any]) -> str:
        """Run Docker build in executor (blocking operation)"""
        import subprocess
        
        cmd = [
            'docker', 'build',
            '-t', config['image_name'],
            '-f', str(Path(config['build_dir']) / 'Dockerfile'),
            config['build_dir']
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Docker build failed: {result.stderr}")
        
        return result.stdout

# Example usage functions
async def async_deploy_example():
    """Example of async deployment"""
    deployment_manager = AsyncDeploymentManager()
    
    yaml_files = [
        '.okik/services/k8/embedder-config.yaml',
        '.okik/services/k8/mockllm-config.yaml'
    ]
    
    with Progress() as progress:
        results = await deployment_manager.deploy_multiple_services(yaml_files, progress)
        
        for result in results:
            if isinstance(result, dict):
                if result['status'] == 'success':
                    console.print(f"✅ Successfully deployed {result['file']}", style="bold green")
                else:
                    console.print(f"❌ Failed to deploy {result['file']}: {result['error']}", style="bold red")

async def async_build_example():
    """Example of async building"""
    build_manager = AsyncBuildManager()
    
    build_configs = [
        {
            'name': 'embedder',
            'image_name': 'okik/embedder:latest',
            'source_file': 'main.py',
            'dockerfile': '.okik/docker/Dockerfile',
            'requirements': 'requirements.txt',
            'build_dir': '.okik/temp/embedder'
        },
        {
            'name': 'mockllm',
            'image_name': 'okik/mockllm:latest',
            'source_file': 'main.py',
            'dockerfile': '.okik/docker/Dockerfile',
            'requirements': 'requirements.txt',
            'build_dir': '.okik/temp/mockllm'
        }
    ]
    
    with Progress() as progress:
        results = await build_manager.build_multiple_images(build_configs, progress)
        
        for result in results:
            if isinstance(result, dict):
                if result['status'] == 'success':
                    console.print(f"✅ Successfully built {result['config']['name']}", style="bold green")
                else:
                    console.print(f"❌ Failed to build {result['config']['name']}: {result['error']}", style="bold red")

# CLI integration example
def run_async_deploy():
    """Run async deployment from CLI"""
    asyncio.run(async_deploy_example())

def run_async_build():
    """Run async build from CLI"""
    asyncio.run(async_build_example())

if __name__ == "__main__":
    # Example usage
    print("Running async deployment example...")
    asyncio.run(async_deploy_example())
    
    print("Running async build example...")
    asyncio.run(async_build_example())