import importlib.util
import sys
import os
from typing import Any, Optional

def load_module(module_name: str, file_path: str) -> Optional[Any]:
    """
    Dynamically load a Python module from file path
    
    Args:
        module_name: Name for the module
        file_path: Absolute path to the Python file
        
    Returns:
        Loaded module or None if failed
    """
    try:
        # Convert relative path to absolute path
        if not os.path.isabs(file_path):
            # Get the project root directory (2 levels up from api/utils/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            file_path = os.path.join(project_root, file_path)
            
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
            
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            print(f"❌ Failed to create spec for {file_path}")
            return None
            
        module = importlib.util.module_from_spec(spec)
        
        # Add the module to sys.modules before execution to handle circular imports
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as exec_error:
            # Remove from sys.modules if execution failed
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise exec_error
        
        return module
    except Exception as e:
        print(f"❌ Error loading module {module_name} from {file_path}: {e}")
        return None

def get_class_from_module(module: Any, class_name: str) -> Optional[Any]:
    """
    Get a class from a loaded module
    
    Args:
        module: Loaded module
        class_name: Name of the class to get
        
    Returns:
        Class object or None if not found
    """
    try:
        return getattr(module, class_name)
    except AttributeError:
        print(f"❌ Class {class_name} not found in module")
        return None

def get_function_from_module(module: Any, function_name: str) -> Optional[Any]:
    """
    Get a function from a loaded module
    
    Args:
        module: Loaded module  
        function_name: Name of the function to get
        
    Returns:
        Function object or None if not found
    """
    try:
        return getattr(module, function_name)
    except AttributeError:
        print(f"❌ Function {function_name} not found in module")
        return None