import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from benchmarking.config.manager import get_config_manager
from benchmarking.config.pydantic_config import BenchmarkConfig
from benchmarking.core.engine import BenchmarkEngine

async def test_config():
    config_path = "benchmark_gemini_flash.yaml"
    config_manager = get_config_manager()
    try:
        config_data = config_manager.load_config(config_path, "benchmark")
        print(f"Loaded config keys: {config_data.keys()}")
        print(f"Environment type: {type(config_data.get('environment'))}")
        
        config_obj = BenchmarkConfig.model_validate(config_data)
        print(f"Validated config environment: {config_obj.environment}")
        print(f"Validated config environment type: {type(config_obj.environment)}")
        
        dump = config_obj.model_dump()
        print(f"Dumped config environment: {dump.get('environment')}")
        print(f"Dumped config environment type: {type(dump.get('environment'))}")

        engine = BenchmarkEngine(config_obj)
        await engine.initialize()
        print("Engine initialized")
        
        result = await engine.run_benchmark(config=config_obj)
        print("Run benchmark completed")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_config())
